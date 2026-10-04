# Troubleshooting

[← Back to README](../../README_EN.md)

If you encounter a problem while using ViewTexForge, check this page first.

ViewTexForge spans **Blender / Capture / ComfyUI / Texture Merge**, so identifying the stage where the error occurs usually makes the cause easier to isolate.

## Table of Contents

- [Blender / Add-on](#blender--add-on)
- [Output Directory](#output-directory)
- [Capture](#capture)
- [ComfyUI Connection](#comfyui-connection)
- [ComfyUI Workflow / Models](#comfyui-workflow--models)
- [Generation](#generation)
- [Texture Merge](#texture-merge)
- [Performance / VRAM](#performance--vram)
- [If the Problem Is Not Resolved](#if-the-problem-is-not-resolved)

---

## Blender / Add-on

### ViewTexForge does not appear in Blender

**Check:**

1. Confirm you are using Blender **5.1.x**.
2. Confirm **ViewTexForge** is enabled under `Edit > Preferences > Add-ons`.
3. Press `N` in the 3D Viewport and look for the **ViewTexForge** Sidebar tab.
4. If it does not appear immediately after installation, restart Blender.

### A Python error appears when enabling the add-on

Check the Traceback in Blender's **System Console**.

If ViewTexForge files are missing or incomplete, remove the add-on and reinstall it from the distribution ZIP.

---

## Output Directory

### An Output Directory error appears

Before Capture / ComfyUI / Texture Merge starts, ViewTexForge verifies that the output location exists and is writable.

**Check:**

- **Output Directory** is not empty.
- The selected folder is writable.
- You selected a folder, not a file.
- If you use a Blender-relative path beginning with `//`, save the `.blend` file first.

If unsure, create a new empty folder on a local drive and select it.

---

## Capture

### Capture does not start

**Check:**

- If `Render Target` is `Selected Only`, confirm the intended objects are selected.
- Confirm the target objects are not excluded from rendering.
- Confirm Clay / Normal / Depth / Mask are not all disabled.
- Confirm Output Directory is valid.

Capture cannot start if no supported capture target can be found.

### Selected Only does not capture the intended model

`Selected Only` captures only supported objects that are selected at execution time.

Immediately before running Capture, confirm that all required objects are selected.

### The model is clipped by the camera / appears too small

Auto Cameras project evaluated target geometry into each camera and fit the Orthographic Camera to the projected bounds.

Adjust **Camera Margin** first:

- If the model is clipped: increase the Margin.
- If the model appears too small: decrease the Margin.

Also check whether an unrelated object far away from the model is included in the Capture target.

### Clay is too bright / too dark

When `Power Mode` is **Auto**, ViewTexForge calculates light intensity from the target size.

If the result is not appropriate, check the target object scale and Capture target. If necessary, switch Power Mode to Manual and adjust Light Power.

### Camera Metadata creation fails

Texture Merge Capture validates the consistency of Camera JSON / Raw CAMERA_Z / Geometry Mask and related data.

If validation fails, check Blender's **System Console**. Camera JSON contract errors may include more detailed information there.

---

## ComfyUI Connection

### Cannot connect to ComfyUI

Default Server URL:

```text
http://127.0.0.1:8188
```

**Check:**

1. ComfyUI is running.
2. ComfyUI can be opened in a browser.
3. ViewTexForge **Server URL** matches the ComfyUI address.
4. If ComfyUI uses another port, specify that port.

ViewTexForge checks connection status through ComfyUI's `/system_stats` endpoint.

### Connection Failed appears even though ComfyUI is running

If ComfyUI is not running at `127.0.0.1:8188`, enter the actual URL in ViewTexForge.

Also check whether local HTTP traffic is being blocked by a firewall, security software, or network configuration.

---

## ComfyUI Workflow / Models

### Workflow Error appears

ViewTexForge detects required nodes in the bundled ComfyUI API Workflow by **`_meta.title`, not node ID**.

Workflow Validation Error occurs if a required contract node is missing, duplicated, or has an unexpected node type.

For normal v1.0 use, use the bundled workflow without modifying its contract nodes.

Detailed errors are shown in Blender's **System Console**.

### Missing Nodes appears

The bundled workflow requires multiple Custom Nodes and relatively recent ComfyUI Core nodes.

1. Update ComfyUI to a relatively recent version.
2. Run **Install Missing Custom Nodes** from ComfyUI Manager.
3. Install the required Custom Nodes.
4. Restart ComfyUI.

See the [ComfyUI Workflow README](../comfyui/README_EN.md) for the required Custom Nodes.

### Model not found / a model cannot be loaded

Confirm both the model file name and storage location.

Main storage locations:

```text
ComfyUI/
└─ models/
   ├─ vae/
   ├─ loras/
   ├─ diffusion_models/
   ├─ text_encoders/
   └─ model_patches/
```

See the [ComfyUI Workflow README](../comfyui/README_EN.md) for the exact models and locations.

After adding models, restart ComfyUI or refresh the model list as needed.

### Reference Image error appears

ComfyUI Generation requires a valid **Reference Image**.

Check that:

- The file still exists.
- The correct image is selected in ViewTexForge.
- An old path is not left behind after moving or deleting the image.

---

## Generation

### ComfyUI Generation does not start

Check in this order:

1. Capture completed successfully.
2. `clay` / `depth` / `mask` exist in Output Directory.
3. ComfyUI is running.
4. Server URL is correct.
5. Reference Image is set.
6. The workflow has no Missing Nodes.
7. All required models are installed.

### Generated view order does not match

`clay` / `depth` / `mask` must correspond in the same camera order.

It is recommended to use the folders generated by ViewTexForge directly and avoid manually renaming or reordering files.

### Generated geometry is heavily distorted

The bundled workflow uses Depth / Canny / Inpaint ControlNet to help preserve shape, but AI generation cannot guarantee exact geometric correspondence.

Check:

- The captured Clay / Depth / Mask are correct.
- The Reference Image does not strongly contradict the target character.
- You are using the recommended 2 x 2 or 3 x 3 Camera Layout.

### I want to use a camera count other than 4 / 9

The public ViewTexForge v1.0 GUI supports **2 x 2 (4 Cameras)** and **3 x 3 (9 Cameras)**.

The bundled ComfyUI workflow may contain internal handling for other view counts, but they are not exposed as public ViewTexForge v1.0 settings.

---

## Texture Merge

### Texture Merge does not start

Texture Merge requires data created by both Capture and ComfyUI Generation.

Check:

- Camera JSON exists under `camera/`.
- Generated images exist under `generated/`.
- Each view in the Generated Manifest has matching Camera JSON and Generated Image information.
- The target object has not been deleted or replaced after Capture.
- The target object has a usable UV map.

### Camera JSON not found appears

The Camera JSON required by Texture Merge cannot be found.

Run Capture again, then run ComfyUI Generation before Texture Merge.

Do not manually move or delete files under `camera/` in Output Directory.

### Generated color not found appears

A generated ComfyUI image cannot be found, or its location no longer matches the path stored in the Manifest.

Run ComfyUI Generation again and check the contents of `generated/`.

### Specified UV Layer not found / UV-related error appears

Texture Merge requires UVs on the target Mesh.

Check that:

- The target Mesh has a UV Map.
- The UV Layer was not deleted or renamed after Capture.
- Geometry / UVs have not changed significantly between Capture and Texture Merge.

### Target Object not found appears

The target object recorded during Capture cannot be identified in the current Scene.

If you deleted, replaced, or significantly changed the object structure after Capture, it is recommended to **restart from Capture**.

### Unpainted regions remain after Texture Merge

UV regions that are not visible from any camera may remain unresolved depending on the settings.

First try increasing Camera Layout to 3 x 3 (9 Cameras).

If you change Advanced Fill / Surface Sample settings, adjust them gradually and compare the result rather than making large changes at once.

### Seams or view differences are visible after Texture Merge

If generated camera views already contain differences in color, lighting, or detail, those differences may remain after merging.

Consider:

- Trying Albedo Mode.
- Reviewing the Reference Image and Prompt.
- Checking Capture / Generation output for each view.
- Switching Camera Layout to 3 x 3.

---

## Performance / VRAM

### CUDA Out of Memory / insufficient VRAM

The bundled ComfyUI workflow has been **tested successfully on an NVIDIA RTX GPU with 8 GB VRAM**, but available VRAM varies depending on other GPU applications and system conditions.

If necessary, try:

- Close other GPU-heavy applications.
- Use ComfyUI Low VRAM / model offloading.
- Disable Albedo Mode.
- Reduce RTX Video Super Resolution workload.
- Use lighter Marigold settings.
- Use a lower-bit Qwen GGUF model.

See the VRAM Requirements section in the [ComfyUI Workflow README](../comfyui/README_EN.md).

### Generation is very slow

On an 8 GB VRAM environment, CPU RAM offloading and repeated model loading may make processing slower than on higher-VRAM GPUs.

Albedo Mode also adds Marigold Appearance / Lighting processing, so it takes longer than when Albedo Mode is disabled.

---

## If the Problem Is Not Resolved

When reporting an issue, include the following information when possible:

- ViewTexForge version
- Blender version
- ComfyUI installation method (Desktop / Portable / Manual)
- GPU and VRAM capacity
- Execution Mode used
- Error message
- Blender System Console Traceback / ViewTexForge log
- ComfyUI Console error
- Stage where the issue occurred (Capture / ComfyUI / Texture Merge)

For isolation, instead of starting with the full pipeline, run each stage separately:

```text
Capture only
    ↓
ComfyUI only
    ↓
Texture Merge only
```

This makes it easier to determine which stage is causing the problem.
