# ViewTexForge

**ViewTexForge** is a Blender add-on for capturing multi-view images from 3D models, generating AI-assisted texture images through ComfyUI, and reprojecting and merging the generated results back onto the 3D model as a unified UV texture.

> Release: **v1.0**  
> Target: **Blender 5.1.x**

[日本語 README](README.md)

---

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Setup](#setup)
- [Quick Start](#quick-start)
- [Camera Layout Recommendation](#camera-layout-recommendation)
- [Output](#output)
- [Settings Reference](#settings-reference)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Changelog](#changelog)
- [License](#license)

---

## Overview

ViewTexForge provides a workflow for generating textures for 3D characters and models while referencing the colors, surface appearance, and design of a reference image.

The workflow is organized into three main stages:

```text
Blender / ViewTexForge
        │
        ├─ 1. Capture
        │    ├─ Clay
        │    ├─ Normal
        │    ├─ Depth
        │    ├─ Mask
        │    └─ Camera / Raw Depth / Geometry Mask for Texture Merge
        │
        ▼
ComfyUI
        │
        ├─ 2. AI Texture Generation
        │    └─ Generate each camera view using a Reference Image
        │
        ▼
ViewTexForge
        │
        └─ 3. Texture Merge
             └─ Merge generated multi-view images into a UV Texture
```

You can run **Capture → ComfyUI → Texture Merge** as one continuous process, or execute each stage independently.

### Main Features

- Auto Camera Capture with 2 x 2 (4 Cameras) / 3 x 3 (9 Cameras)
- Multi-view Clay / Normal / Depth / Mask output
- Automatic Raw CAMERA_Z / Geometry Mask / Camera Metadata generation for Texture Merge
- Lit Clay Render with automatic lighting
- Auto Light Power based on model scale
- HTTP API integration with ComfyUI
- Reference-based generation using Qwen Image Edit
- Albedo Mode
- Texture Merge from multiple generated camera views
- Independent or chained execution of Capture / ComfyUI / Texture Merge
- Per-stage Progress / Status display

---

## Requirements

### ViewTexForge

- Blender **5.1.x**
- Developed and primarily tested on Windows

### ComfyUI Workflow

The bundled workflow mainly requires:

- ComfyUI
- NVIDIA RTX GPU
- Qwen Image Edit 2511 GGUF
- DiffSynth ControlNet (Depth / Canny / Inpaint)
- NVIDIA RTX Video Super Resolution
- Marigold IID when using Albedo Mode

The bundled ComfyUI workflow has been **tested successfully on an NVIDIA RTX GPU with 8 GB VRAM**. GPUs with more VRAM may provide smoother operation by reducing model offload and reload frequency.

For details, see the [ComfyUI Workflow README](docs/comfyui/README_EN.md).

---

## Installation

1. Download the ViewTexForge v1.0 ZIP from **GitHub Releases**.
2. Do not extract the ZIP.
3. Launch Blender.
4. Open `Edit > Preferences > Add-ons`.
5. Choose **Install from Disk...**.
6. Select the downloaded ViewTexForge ZIP.
7. Enable **ViewTexForge** after installation.
8. In the 3D Viewport, press `N` and open the **ViewTexForge** tab in the Sidebar.

For the complete initial setup, see the [Setup Guide](docs/en/setup.md).

---

## Setup

To use the full ViewTexForge workflow, ComfyUI must also be installed and configured.

### 1. ComfyUI

Install ComfyUI and confirm that it can launch normally. The main installation options are:

| Method | Download / Repository | Official Setup Documentation |
|---|---|---|
| GitHub / Manual Install | [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) | [Manual Installation](https://docs.comfy.org/installation/manual_install) |
| Windows Portable | [Download Page](https://docs.comfy.org/installation/comfyui_portable_windows#download-comfyui-portable) | [ComfyUI Portable for Windows](https://docs.comfy.org/installation/comfyui_portable_windows) |
| Desktop | [ComfyUI Download](https://comfy.org/download) | [Comfy Desktop for Windows](https://docs.comfy.org/installation/desktop/windows) |

This README does not cover ComfyUI installation and initial configuration in detail. **Follow the official ComfyUI setup documentation for the installation method you choose, and make sure ComfyUI can run correctly on its own before continuing with ViewTexForge setup.**

> The bundled ViewTexForge workflow uses NVIDIA RTX Video Super Resolution, so the standard configuration assumes an NVIDIA RTX GPU.

Default ViewTexForge Server URL:

```text
http://127.0.0.1:8188
```

### 2. Required Models

The current bundled workflow uses:

```text
qwen-image-edit-2511-Q8_0.gguf
qwen_2.5_vl_7b_fp8_scaled.safetensors
qwen_image_vae.safetensors
Qwen-Image-Lightning-4steps-V2.0-bf16.safetensors
qwen_image_depth_diffsynth_controlnet.safetensors
qwen_image_canny_diffsynth_controlnet.safetensors
qwen_image_inpaint_diffsynth_controlnet.safetensors
```

When using Albedo Mode, the following are also used:

```text
prs-eth/marigold-iid-appearance-v1-1
prs-eth/marigold-iid-lighting-v1-1
```

### Model Storage Location

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

Marigold models are downloaded through `ComfyUI-Marigold` from Hugging Face.

Custom Nodes, model download sources, VRAM requirements, and detailed workflow structure are documented separately:

**→ [Qwen 3D Character Texture Generator - ComfyUI Workflow README](docs/comfyui/README_EN.md)**

For the complete setup procedure, see the [Setup Guide](docs/en/setup.md).

---

## Quick Start

To run **Capture → ComfyUI → Texture Merge** with the minimum required settings:

### Before You Start

- Start ComfyUI.
- Make sure the target model has a usable UV map.
- Open the target model in Blender.

### ViewTexForge

1. Set **Output Directory**.
2. Open **Capture Settings**.
3. Set **Render Target** if needed.
   - `All Renderable`: use all renderable objects in the scene
   - `Selected Only`: use only selected objects
4. Choose **Camera Layout**.
   - `2 x 2 (4 Cameras)` - default / recommended
   - `3 x 3 (9 Cameras)` - for wider directional coverage
5. Open **ComfyUI Settings** and set a **Reference Image**.
6. Change **Server URL** only if ComfyUI is not using the default local address.
7. Set **Execution > Mode** to `Capture -> ComfyUI -> Texture Merge`.
8. Click **Run Selected Mode**.

For your first test, it is recommended to keep the other settings at their defaults.

See [Usage](docs/en/usage.md) for details.

---

## Camera Layout Recommendation

| Layout | Cameras | Recommendation | Notes |
|---|---:|---|---|
| 2 x 2 | 4 | **Recommended** | Good balance between processing cost and generation resolution per view |
| 3 x 3 | 9 | **Recommended** | Provides broader directional coverage |

The public ViewTexForge v1.0 GUI supports **4 Cameras / 9 Cameras** for Auto Cameras.

The ComfyUI workflow can internally handle other grid configurations, but ViewTexForge v1.0 exposes only 2 x 2 and 3 x 3 because they provide more reliable aspect-ratio behavior in Qwen and better per-view generation resolution.

---

## Output

Running Capture creates purpose-specific files under the Output Directory.

```text
<Output Directory>/
├─ clay/
├─ normal/
├─ depth/
├─ mask/
├─ raw_depth/
├─ geometry_mask/
├─ camera/
├─ generated/
├─ merged/
└─ capture.json
```

- `clay` / `depth` / `mask`: primarily used for ComfyUI generation
- `raw_depth` / `geometry_mask` / `camera`: used for Texture Merge
- `generated`: images generated by ComfyUI
- `merged`: Texture Merge output
- `capture.json`: manifest for the Capture stage

---

## Settings Reference

For descriptions of each setting, its default value, and when to change it, see:

**→ [Settings Reference](docs/en/settings.md)**

---

## Troubleshooting

If you encounter a problem, see the symptom-based checks and solutions here:

**→ [Troubleshooting](docs/en/troubleshooting.md)**

---

## Documentation

- [Setup Guide](docs/en/setup.md)
- [Usage](docs/en/usage.md)
- [Settings Reference](docs/en/settings.md)
- [Troubleshooting](docs/en/troubleshooting.md)
- [Changelog](docs/en/changelog.md)
- [ComfyUI Workflow README](docs/comfyui/README_EN.md)

---

## Changelog

### v1.0

Initial public release of ViewTexForge.

Main features:

- Multi-view Capture with Auto Cameras
- Clay / Normal / Depth / Mask output
- Auto Lighting / Auto Light Power
- ComfyUI integration
- Qwen Image Edit-based multi-view generation
- Albedo Mode
- Texture Merge
- Unified Capture / ComfyUI / Texture Merge execution
- 2 x 2 (4 Cameras) / 3 x 3 (9 Cameras) layouts

For the complete development history, see the [Changelog](docs/en/changelog.md).

---

## License

ViewTexForge is released under the **MIT License**.

See [LICENSE](LICENSE) for details.

---

*Generated by ChatGPT Sol 5.6*
