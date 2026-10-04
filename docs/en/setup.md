# ViewTexForge Setup Guide

[← Back to README](../../README_EN.md)

This page explains how to install ViewTexForge v1.0 in Blender and prepare the bundled ComfyUI workflow for use.

---

## 1. Install ViewTexForge

### Requirements

- Blender 5.1.x
- ViewTexForge v1.0 Release ZIP

### Install

1. Download the ViewTexForge v1.0 ZIP from **GitHub Releases**.
2. Do not extract the ZIP.
3. Launch Blender.
4. Open `Edit > Preferences > Add-ons`.
5. Choose **Install from Disk...**.
6. Select the ViewTexForge ZIP.
7. Enable the installed **ViewTexForge** add-on.
8. In the 3D Viewport, press `N` and confirm that the **ViewTexForge** tab appears in the Sidebar.

---

## 2. Install ComfyUI

ComfyUI is required when using the `ComfyUI` stage of the full workflow.

Choose one of the following installation methods based on your environment.

| Method | Download / Repository | Official Setup Documentation |
|---|---|---|
| GitHub / Manual Install | [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) | [Manual Installation](https://docs.comfy.org/installation/manual_install) |
| Windows Portable | [Download Page](https://docs.comfy.org/installation/comfyui_portable_windows#download-comfyui-portable) | [ComfyUI Portable for Windows](https://docs.comfy.org/installation/comfyui_portable_windows) |
| Desktop | [ComfyUI Download](https://comfy.org/download) | [Comfy Desktop for Windows](https://docs.comfy.org/installation/desktop/windows) |

For ComfyUI installation and initial configuration, **follow the official documentation for the installation method you choose**. Before configuring ViewTexForge, confirm that ComfyUI can launch and operate correctly on its own.

> The bundled workflow uses NVIDIA RTX Video Super Resolution, so the standard configuration assumes an NVIDIA RTX GPU. On Windows with an NVIDIA RTX GPU, the Portable or Desktop editions are convenient options.

Default ViewTexForge Server URL:

```text
http://127.0.0.1:8188
```

If ComfyUI uses a different port or runs on another machine, change **ComfyUI Settings > Server URL** in ViewTexForge.

---

## 3. Update ComfyUI

The bundled workflow uses relatively recent ComfyUI Core nodes.

Older ComfyUI versions may show Missing Node errors. The following is recommended:

1. Update ComfyUI to a relatively recent version.
2. Update ComfyUI Manager.
3. Open the bundled workflow in ComfyUI.
4. Run **Install Missing Custom Nodes**.
5. Install the required Custom Nodes.
6. Restart ComfyUI.

---

## 4. Required Models

### Qwen Image Edit

```text
qwen-image-edit-2511-Q8_0.gguf
qwen_2.5_vl_7b_fp8_scaled.safetensors
qwen_image_vae.safetensors
Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
```

### DiffSynth ControlNet

```text
qwen_image_depth_diffsynth_controlnet.safetensors
qwen_image_canny_diffsynth_controlnet.safetensors
qwen_image_inpaint_diffsynth_controlnet.safetensors
```

### Albedo Mode

When using Albedo Mode:

```text
prs-eth/marigold-iid-appearance-v1-1
prs-eth/marigold-iid-lighting-v1-1
```

Marigold models are downloaded through `ComfyUI-Marigold` from Hugging Face.

---

## 5. Model Storage Location

```text
ComfyUI/
└─ models/
   ├─ vae/
   │  └─ qwen_image_vae.safetensors
   ├─ loras/
   │  └─ Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
   ├─ diffusion_models/
   │  └─ qwen-image-edit-2511-Q8_0.gguf
   ├─ text_encoders/
   │  └─ qwen_2.5_vl_7b_fp8_scaled.safetensors
   └─ model_patches/
      ├─ qwen_image_depth_diffsynth_controlnet.safetensors
      ├─ qwen_image_canny_diffsynth_controlnet.safetensors
      └─ qwen_image_inpaint_diffsynth_controlnet.safetensors
```

For model download sources and additional details, see:

**→ [ComfyUI Workflow README](../comfyui/README_EN.md)**

---

## 6. Required Custom Nodes

The bundled workflow mainly uses:

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

For the purpose of each node and repository links, see the [ComfyUI Workflow README](../comfyui/README_EN.md).

---

## 7. Hardware Guideline

The bundled ComfyUI workflow has been **tested successfully on an NVIDIA RTX GPU with 8 GB VRAM**.

| VRAM | Guideline |
|---:|---|
| 8 GB | Tested / baseline environment |
| 12 GB | More headroom |
| 16 GB | High headroom |
| 24 GB+ | Comfortable for higher-resolution processing and additional models |

System RAM guideline:

```text
32 GB minimum recommended
64 GB preferred for low-VRAM operation
```

Because the bundled workflow uses NVIDIA RTX Video Super Resolution, the standard configuration assumes an NVIDIA RTX GPU.

---

## 8. Check the ViewTexForge / ComfyUI Connection

1. Start ComfyUI.
2. Open ViewTexForge in Blender.
3. Expand **ComfyUI Settings**.
4. Check **Server URL**.
5. Confirm `Status: Connected`.
6. Confirm `Workflow Status: Valid`.

If the connection fails, confirm that ComfyUI is running and that the URL and port match.

---

## 9. Before Using Texture Merge

Texture Merge uses Camera / Raw Depth / Geometry information captured during the Capture stage to project generated images and combine them into a UV texture.

Main requirements:

- The target Mesh has a UV Layer.
- The current v1 Core assumes a single UV tile within the 0-1 range.
- Do not significantly modify the target geometry after Capture.
- Keep the corresponding target Object available between Capture and Merge.

When using ViewTexForge's unified Execution modes, the required manifests and intermediate files are created automatically.

---

## 10. Setup Complete

The basic setup is now complete.

Continue with the **Quick Start** in [Usage](usage.md).
