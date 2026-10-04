# Qwen 3D Character Texture Generator (GGUF v2)

This ComfyUI workflow is designed to **process multi-view images captured from a 3D character and generate texture-oriented multi-view images while referencing the color palette and surface appearance of a reference image**.

It primarily takes `clay` / `depth` / `mask` images exported from ViewTexForge and uses Qwen Image Edit 2511 together with three DiffSynth ControlNet branches — Depth, Canny, and Inpaint — to generate the character appearance while preserving the original shape as much as possible.

After generation, the result is upscaled with NVIDIA RTX Video Super Resolution and split back into individual camera views. When **Albedo Mode** is enabled, Marigold IID appearance / lighting estimation is used to suppress lighting information and extract an Albedo-like result from the generated images.

---

## Required Models

This workflow uses the following models.

### Qwen Image Edit

- `qwen-image-edit-2511-Q8_0.gguf`
- `qwen_2.5_vl_7b_fp8_scaled.safetensors`
- `qwen_image_vae.safetensors`
- `Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors`

### DiffSynth ControlNet

- `qwen_image_depth_diffsynth_controlnet.safetensors`
- `qwen_image_canny_diffsynth_controlnet.safetensors`
- `qwen_image_inpaint_diffsynth_controlnet.safetensors`

### Albedo Mode

When using Albedo Mode, the following Marigold IID models are also required.

- `prs-eth/marigold-iid-appearance-v1-1`
- `prs-eth/marigold-iid-lighting-v1-1`

The Marigold models are downloaded through `ComfyUI-Marigold` from Hugging Face.

## Model Storage Location

```text
📂 ComfyUI/
├── 📂 models/
│   ├── 📂 vae/
│   │   └── qwen_image_vae.safetensors
│   ├── 📂 loras/
│   │   └── Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
│   ├── 📂 diffusion_models/
│   │   └── qwen-image-edit-2511-Q8_0.gguf
│   ├── 📂 text_encoders/
│   │   └── qwen_2.5_vl_7b_fp8_scaled.safetensors
│   └── 📂 model_patches/
│       ├── qwen_image_depth_diffsynth_controlnet.safetensors
│       ├── qwen_image_canny_diffsynth_controlnet.safetensors
│       └── qwen_image_inpaint_diffsynth_controlnet.safetensors
```

---

## Workflow Overview

```text
ViewTexForge output
  ├─ clay/*.png
  ├─ depth/*.png
  └─ mask/*.png
        ↓
Load image lists
        ↓
Auto-detect view count / build multi-view grid
        ↓
Build multi-view grids
        ↓
Resize to Qwen working resolution
        ↓
Qwen Image Edit 2511 (GGUF)
  ├─ Reference image
  ├─ Depth ControlNet
  ├─ Canny ControlNet
  └─ Inpaint ControlNet + mask
        ↓
4-step generation
        ↓
RTX Video Super Resolution (ULTRA)
        ↓
Downscale / split back to individual views
        ↓
Albedo Mode
  ├─ OFF → generated images directly
  └─ ON  → Marigold IID → PBR Extractor → Albedo
        ↓
Save images
```

---

# 1. What This Workflow Does

The purpose of this workflow is to **convert multi-view images of a 3D model into color and texture representations closer to a reference image while preserving the original 3D shape as much as possible**.

The following inputs are used:

- Clay / Render image
- Depth image
- Mask image
- Reference image

Images captured from multiple cameras are first combined into a single grid image and passed to Qwen Image Edit as one image.

Qwen receives the following information at the same time:

- Original multi-view image
- Reference image
- Depth ControlNet
- Canny ControlNet
- Inpaint ControlNet
- Geometry Mask

Compared with a simple Image-to-Image workflow, this is intended to **preserve the original 3D shape, silhouette, and depth relationships more reliably during texture generation**.

The current Positive Prompt follows this policy:

```text
Replace the color palette of image1 based on image2.
Albedo texture map, flat colors, completely unlit, no shadows,
no directional lighting, flat gray background.
```

The Negative Prompt is currently almost empty.

---

# 2. Supported View Counts

The Clay image count is used to combine the multi-view images into a single grid before passing them to Qwen.

This workflow is primarily designed around **square grids such as 2 x 2, 3 x 3, and 4 x 4**.

The recommended configurations are:

| View Count | Grid | Recommendation |
|---:|---:|---|
| 4 | 2 x 2 | **Recommended** |
| 9 | 3 x 3 | **Recommended** |
| 16 | 4 x 4 | Not recommended |

### Recommended: 2 x 2 / 3 x 3

**2 x 2 (4 views) and 3 x 3 (9 views) are the recommended configurations.**

Square grids tend to preserve the original aspect ratio more reliably when processed by Qwen, and the shape of each camera image is also more stable in the generated result.

### 3 x 2 / 4 x 3 Grid

**3 x 2 (6 views) and 4 x 3 (12 views) can also be generated.**

However, in actual testing, Qwen tended to alter the overall grid aspect ratio. Compared with the source image, the final output size and the proportions of each cell may not be preserved accurately.

For this reason, 6-view and 12-view configurations are usable, but they are not currently recommended.

### 4 x 4 and Larger

**4 x 4 (16 views) or larger grids are not recommended for practical use.**

Packing many views into a single generated image reduces the effective generation resolution available to each view, causing a noticeable loss of texture detail.

Although the workflow is intended to support 16 views or more, testing has shown that textures become too coarse to achieve practical image quality.

> **Recommended:** 2 x 2 / 3 x 3  
> **Usable but not recommended:** 3 x 2 / 4 x 3  
> **Not recommended:** 4 x 4 or larger

The grid cell size is determined from the resolution of the first Clay image.

---

# 3. Required Custom Nodes

## ComfyUI-GGUF

Required to load the Qwen Image Edit 2511 GGUF model.

Node used:

```text
LoaderGGUF
```

Repository:

https://github.com/city96/ComfyUI-GGUF

---

## Comfy_KepListStuff

Used to load multiple images from a folder as a list.

Nodes used:

```text
ImageListLoader
List Length
```

Repository:

https://github.com/M1kep/Comfy_KepListStuff

---

## ComfyUI-Easy-Use

Used for conditional branching based on image count and for numerical calculations.

Example nodes:

```text
easy simpleMathDual
easy ifElse
easy int
```

Repository:

https://github.com/yolain/ComfyUI-Easy-Use

---

## ComfyUI Impact Pack

Used to temporarily package variable values into a list.

Node used:

```text
ImpactMakeAnyList
```

Repository:

https://github.com/ltdrdata/ComfyUI-Impact-Pack

---

## ComfyUI Essentials

Used to extract white regions and related masks from the Geometry Mask.

Node used:

```text
MaskFromRGBCMYBW+
```

Repository:

https://github.com/cubiq/ComfyUI_essentials

---

## KJNodes for ComfyUI

Used for converting Seed values into strings for file names and for image range remapping before Marigold processing.

Nodes used:

```text
SomethingToString
RemapImageRange
```

Repository:

https://github.com/kijai/ComfyUI-KJNodes

---

## ComfyUI-Marigold

Required for Marigold IID estimation in Albedo Mode.

Nodes used:

```text
MarigoldModelLoader
MarigoldDepthEstimation_v2
```

Repository:

https://github.com/kijai/ComfyUI-Marigold

---

## ComfyUI-TextureAlchemy

Extracts Albedo and other PBR maps from Marigold appearance / lighting output.

Nodes used:

```text
PBRExtractor
PBRSplitter
```

Repository:

https://github.com/amtarr/ComfyUI-TextureAlchemy

---

## NVIDIA RTX Nodes for ComfyUI

Used to upscale generated images.

Node used:

```text
RTXVideoSuperResolution
```

Repository:

https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI

This workflow uses:

```text
Quality: ULTRA
Resize type: target dimensions
```

An NVIDIA RTX GPU is required.

---

# 4. ComfyUI Built-in / Recent Core Nodes

This workflow also uses relatively recent ComfyUI Core nodes.

Examples:

```text
TextEncodeQwenImageEditPlus
FluxKontextMultiReferenceLatentMethod
ModelPatchLoader
QwenImageDiffsynthControlnet
ResizeImageMaskNode
SplitImageToTileList
ImageGrid
GetImageSize
GetItemFromList
StringConcatenate
ComfyMathExpression
CFGNorm
ComfySwitchNode
```

For this reason, **older versions of ComfyUI may show Missing Node errors when loading the workflow.**

Updating ComfyUI to a relatively recent version is recommended.

## KayTool

Used to convert numeric values to integers.

Node used:

```text
To_Int
```

Repository:

https://github.com/kk8bit/KayTool

In ComfyUI Manager, search for `kaytool` to install it.

If any Missing Nodes remain, use **Install Missing Custom Nodes** in ComfyUI Manager.

---

# 5. Input Folder Structure

This workflow is designed to receive the following folders from ViewTexForge:

```text
<output root>/
├─ clay/
│  ├─ view_000.png
│  ├─ view_001.png
│  └─ ...
├─ depth/
│  ├─ view_000.png
│  ├─ view_001.png
│  └─ ...
├─ mask/
│  ├─ view_000.png
│  ├─ view_001.png
│  └─ ...
└─ generated/
```

The exact file names are not fixed, but the images in each folder must be arranged in **the same camera order**.

`ImageListLoader` currently uses:

```text
file_filter = *.png
sort_method = numerical
```

Therefore, it is recommended that file names include numeric values that make the camera order clear.

---

# 6. Reference Image

The Reference Image is supplied from the following node:

```text
ViewTexForge_input_ReferenceImage
```

It is passed to Qwen Image Edit as:

```text
image1 = multi-view source image
image2 = reference image
```

Its main purpose is to **transfer color and design information from the reference while preserving the shape of the 3D model**.

---

# 7. Multi-view Grid Generation

Clay / Depth / Mask images are each converted into independent grids.

```text
Clay  → ImageGrid
Depth → ImageGrid
Mask  → ImageGrid
```

All grids use the same cell width, cell height, and column count, so the same camera remains in the same grid position across all inputs.

This correspondence is important for maintaining consistency across the Depth / Canny / Inpaint ControlNet inputs.

---

# 8. Qwen Processing Resolution

The processing resolution is switched based on the number of cameras.

```text
4 views  → 1024 x 1024
6 views  → 1248 x 832
12 views → 1152 x 864
```

All images are resized using Bicubic interpolation.

This workflow does not use `FluxKontextImageScale`. Instead, it uses a standard Resize Image/Mask node so that **the aspect ratio can be controlled explicitly**.

---

# 10. ControlNet Structure

The ControlNets are applied as Model Patches in the following order:

```text
Qwen Image Edit model
  ↓
Depth DiffSynth ControlNet
  ↓
Canny DiffSynth ControlNet
  ↓
Inpaint DiffSynth ControlNet
  ↓
CFG Norm
  ↓
KSampler
```

## Depth

Input:

```text
Depth grid
```

Purpose:

- Preserve the 3D shape of the character
- Preserve front/back relationships between parts
- Reduce silhouette collapse

## Canny

Canny is generated from the Clay grid.

```text
low_threshold  = 0.05
high_threshold = 0.20
```

Purpose:

- Preserve contours
- Preserve boundaries around the face, clothing, and accessories
- Reduce inconsistencies between camera views

## Inpaint

White regions are extracted from the Mask grid and passed to the Inpaint ControlNet.

```text
threshold R = 0.15
threshold G = 0.15
threshold B = 0.15
```

Purpose:

- Control the generation area using the Geometry Mask
- Reduce unwanted generation in the background and outside the target area

---

# 11. Qwen Sampling Settings

Current main settings:

```text
Model      : qwen-image-edit-2511-Q8_0.gguf
LoRA       : Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
Steps      : 4
CFG        : 1.0
Sampler    : Euler
Scheduler  : Simple
Denoise    : 1.0
Aura shift : 3.0
CFG Norm   : 1.0
```

Because the workflow is built around the Lightning 4-step LoRA, generation uses significantly fewer steps than standard Qwen Image Edit.

`ModelSamplingAuraFlow` is configured with `shift = 3.0` and `sampling = flow`.

`CFGNorm` is applied with strength 1.0 / pre_cfg false.

---

# 12. Reference Latent Method

The following is applied to both Positive and Negative conditioning:

```text
FluxKontextMultiReferenceLatentMethod
reference_latents_method = index_timestep_zero
```

This node is used to specify how multiple reference-image latents from Qwen Image Edit Plus are handled.

The official ComfyUI Qwen Image Edit 2511 template indicates that this setting may be required for repackaged models.

---

# 13. RTX Video Super Resolution

The Qwen output is passed to RTX Video Super Resolution.

Setting:

```text
Quality = ULTRA
```

The upscale target resolution is calculated from the original tile size and the grid size.

The result is then resized to 0.5x with Bicubic interpolation and split back into individual camera images using `SplitImageToTileList`.

In other words:

```text
Qwen output
    ↓
RTX VSR high-resolution upscale
    ↓
0.5x resize
    ↓
individual camera tiles
```

---

# 14. Albedo Mode

The mode is switched using the following Boolean node:

```text
ViewTexForge_input_AlbedoMode
```

## OFF

Images split after RTX VSR are saved directly as Generated Images.

## ON

The split images are passed to Marigold.

```text
Generated image
  ↓
Remap Image Range
  ├─ Marigold IID Appearance
  └─ Marigold IID Lighting
        ↓
PBR Extractor
        ↓
PBR Splitter
        ↓
Albedo
```

PBR Extractor settings:

```text
albedo_source      = lighting
gamma_albedo       = 0.45
gamma_metal_rough  = 2.0
gamma_lighting_ao  = 0.45
```

Only the Albedo output from PBR Splitter is saved in the final output.

---

# 15. Marigold Settings

Both Appearance and Lighting use the following settings:

```text
seed                  = 123
denoise_steps         = 12
ensemble_size         = 4
scheduler             = DDIMScheduler
use_taesd_vae         = false
keep_model_loaded     = false
```

Because `keep_model_loaded = false`, the Marigold models are not kept resident after estimation.

This reduces VRAM usage, but repeated runs may take longer because the models need to be reloaded.

---

# 16. Output

Save node:

```text
ViewTexForge_output_GeneratedImage
```

Output folder:

```text
ViewTexForge_output/
```

File name prefix:

```text
generated_<seed>
```

Example when Seed is 18:

```text
ViewTexForge_output/generated_18_00001_.png
ViewTexForge_output/generated_18_00002_.png
...
```

The exact numbering depends on ComfyUI's SaveImage naming convention.

---

# 17. VRAM Requirements

This workflow is **designed around an 8 GB VRAM environment and has been confirmed to run successfully on an NVIDIA RTX GPU with 8 GB VRAM**.

It is a relatively heavy configuration because it uses Qwen Image Edit 2511 Q8 GGUF, the Qwen VL Text Encoder, three ControlNets, RTX VSR, and — when Albedo Mode is enabled — Marigold. However, the workflow can still run on 8 GB VRAM by making use of model loading / unloading and offloading.

## VRAM Guideline

| VRAM | Evaluation |
|---:|---|
| 8 GB | **Tested / baseline environment for this workflow** |
| 12 GB | More headroom and generally more comfortable model switching / generation |
| 16 GB | Plenty of headroom; fewer offloads and potentially more stable processing |
| 24 GB+ | Very comfortable for higher-resolution processing and additional models |

In other words, **12 GB or more is not a requirement. This workflow is intended to run on 8 GB VRAM.**

Higher-VRAM environments can generally reduce CPU offloading and model reload frequency, improving processing speed and overall usability.

The parts most likely to consume VRAM are:

1. Qwen Image Edit 2511
2. Qwen 2.5 VL 7B Text Encoder
3. Three DiffSynth ControlNets
4. RTX Video Super Resolution ULTRA
5. Marigold appearance / lighting

### Notes for 8 GB VRAM

- This workflow has been tested successfully with 8 GB VRAM.
- ComfyUI / PyTorch may offload models to system RAM when necessary.
- Compared with higher-VRAM systems, model switching and reloading may take longer.
- Running many other GPU applications at the same time can reduce available VRAM.
- Enabling Albedo Mode requires additional Marigold model loading, so processing takes longer than when it is disabled.

### If You Need to Reduce VRAM Usage Further

Consider:

- Using ComfyUI Low VRAM / model offloading
- Disabling Albedo Mode
- Temporarily disabling RTX VSR
- Lowering RTX VSR Quality from ULTRA to HIGH / MEDIUM
- Reducing Marigold `ensemble_size`
- Keeping Marigold `keep_model_loaded = false`
- Using a lower-bit Qwen GGUF model

---

# 18. Hardware Requirements

## GPU

Recommended:

```text
NVIDIA RTX GPU
```

This workflow assumes an NVIDIA RTX environment because it uses the RTX Video Super Resolution node.

If RTX VSR is removed, other GPU environments may be possible within the compatibility limits of Qwen / Marigold, but those configurations are not verified in this README.

## System RAM

System RAM is also important because GGUF model CPU offloading may be used.

Recommended guideline:

```text
32 GB minimum recommended
64 GB preferred for low-VRAM operation
```

This is particularly useful on systems with 8–12 GB VRAM, where models may be offloaded to main memory.

---

# 19. Recommended Installation Procedure

1. Update ComfyUI to a relatively recent version
2. Update ComfyUI Manager
3. Load this workflow JSON
4. Run `Install Missing Custom Nodes`
5. Install the Custom Nodes listed above
6. Place the required Qwen / LoRA / ControlNet / VAE / Text Encoder models
7. Restart ComfyUI
8. Confirm that there are no Missing Nodes
9. Export `clay` / `depth` / `mask` images from ViewTexForge
10. Set the Folder Paths
11. Set the Reference Image
12. Set Seed / Albedo Mode
13. Run Queue Prompt

---

# 20. Important Notes

## Camera Order

The order of Clay / Depth / Mask images must match exactly.

For example:

```text
clay/view_000.png
depth/view_000.png
mask/view_000.png
```

must all correspond to the same camera.

---

## Number of Images

The recommended configurations are:

```text
4 views  → 2 x 2
9 views  → 3 x 3
```

The following are supported but not recommended:

```text
6 views  → 3 x 2
12 views → 4 x 3
```

And:

```text
16 views or more → not recommended
```

If additional view-count configurations are added, the following may also need to be updated:

- Grid columns
- Grid rows
- Qwen processing resolution
- Output split size

---

## Albedo Extraction

Albedo generated by Marigold IID does not guarantee a physically accurate Base Color.

It is used as a practical preprocessing step to separate lighting and shading information from the generated image as much as possible, making the output easier to use in later Texture Merge / Baking stages.

---

# 21. Main ViewTexForge API Nodes

The following node titles are intended to be controlled from ViewTexForge:

```text
ViewTexForge_input_ReferenceImage
ViewTexForge_input_NegativePrompt
ViewTexForge_input_PositivePrompt
ViewTexForge_input_Seed
ViewTexForge_input_OutputDirName
ViewTexForge_input_OutputFilePrefix
ViewTexForge_input_SourceImageFolderPath
ViewTexForge_input_DepthImageFolderPath
ViewTexForge_input_MaskImageFolderPath
ViewTexForge_input_AlbedoMode
ViewTexForge_input_AlbedoSource

ViewTexForge_output_GeneratedImage
```

Using these names allows the Blender side to search the ComfyUI API workflow JSON and replace only the required parameters.

---

# 22. Dependencies Summary

## Models

```text
qwen-image-edit-2511-Q8_0.gguf
qwen_2.5_vl_7b_fp8_scaled.safetensors
qwen_image_vae.safetensors
Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
qwen_image_depth_diffsynth_controlnet.safetensors
qwen_image_canny_diffsynth_controlnet.safetensors
qwen_image_inpaint_diffsynth_controlnet.safetensors
prs-eth/marigold-iid-appearance-v1-1
prs-eth/marigold-iid-lighting-v1-1
```

## Custom Nodes

```text
ComfyUI-GGUF
Comfy_KepListStuff
ComfyUI-Easy-Use
ComfyUI-Impact-Pack
ComfyUI_essentials
ComfyUI-KJNodes
KayTool
ComfyUI-Marigold
ComfyUI-TextureAlchemy
Nvidia_RTX_Nodes_ComfyUI
```

A recent version of ComfyUI Core is also required.

---

# 23. Source / Reference Links

ComfyUI:

https://github.com/Comfy-Org/ComfyUI

Qwen Image models for ComfyUI:

https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI

Qwen Image Edit 2511 GGUF:

https://huggingface.co/unsloth/Qwen-Image-Edit-2511-GGUF

Qwen Image DiffSynth ControlNets:

https://huggingface.co/Comfy-Org/Qwen-Image-DiffSynth-ControlNets

Qwen Image Lightning:

https://huggingface.co/lightx2v/Qwen-Image-Lightning

ComfyUI GGUF:

https://github.com/city96/ComfyUI-GGUF

ComfyUI Marigold:

https://github.com/kijai/ComfyUI-Marigold

TextureAlchemy:

https://github.com/amtarr/ComfyUI-TextureAlchemy

KayTool:

https://github.com/kk8bit/KayTool

NVIDIA RTX Nodes:

https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI

---

# 24. Workflow Version Notes

README generated from:

```text
Qwen_3DCharacterTexture_generator_ggfu_v2.json
```

The analyzed workflow combines Qwen 2511 / GGUF / DiffSynth ControlNet / RTX VSR / Marigold Albedo extraction.

If the workflow's node structure, model names, or input-node names are changed in the future, update the Dependencies / Workflow Structure sections in this README accordingly.
