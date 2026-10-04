# ViewTexForge Usage

[← Back to README](../../README_EN.md)

This page explains the basic usage of ViewTexForge v1.0.

---

## Quick Start - Run with Only the Required Settings

For your first run, it is recommended to keep advanced settings at their defaults.

### 1. Start ComfyUI

Start ComfyUI first.

Default URL:

```text
http://127.0.0.1:8188
```

### 2. Open the Target Model in Blender

If you plan to run Texture Merge, make sure the target Mesh has a UV map.

### 3. Output Directory

Set the output location in **Save > Output Directory**.

Default:

```text
//ai_texture_capture
```

`//` is a Blender-relative path based on the current `.blend` file.

### 4. Capture Settings

Open **Capture Settings**.

Minimum items to check:

#### Render Target

- `All Renderable` - use all renderable targets in the scene
- `Selected Only` - use only the currently selected objects

#### Camera Layout

- `2 x 2 (4 Cameras)` - **recommended / default**
- `3 x 3 (9 Cameras)` - for broader directional coverage

For a first test, `2 x 2 (4 Cameras)` is recommended.

### 5. Reference Image

Open **ComfyUI Settings** and choose the image whose texture, color palette, and surface appearance should be used as the reference.

The same Reference Image is used for all camera views.

### 6. ComfyUI Connection

If ComfyUI is running on the same PC with the default settings, keep the default Server URL:

```text
http://127.0.0.1:8188
```

Confirm:

```text
Status: Connected
Workflow Status: Valid
```

### 7. Execution Mode

To run the complete pipeline, choose:

```text
Capture -> ComfyUI -> Texture Merge
```

### 8. Run

Click **Run Selected Mode**.

ViewTexForge processes the stages in order:

```text
Capture
  ↓
ComfyUI
  ↓
Texture Merge
```

Use the **Status** section to monitor Current Stage / Overall Progress / Stage Progress.

---

## Individual Stage Execution

Each stage can also be run independently.

| Execution Mode | Description |
|---|---|
| Capture only | Capture only |
| Capture -> ComfyUI | Run ComfyUI after Capture |
| Capture -> ComfyUI -> Texture Merge | Run the complete pipeline |
| ComfyUI only | Run ComfyUI using the latest valid Capture |
| ComfyUI -> Texture Merge | Run Texture Merge after ComfyUI generation |
| Texture Merge only | Run Texture Merge using the latest generated result |

You can also use the individual Run buttons inside the Capture / ComfyUI / Texture Merge sections.

---

## Capture Output

Capture creates the selected image outputs plus data required for Texture Merge.

```text
<Output Directory>/
├─ clay/
│  ├─ view_0001.png
│  └─ ...
├─ normal/
├─ depth/
├─ mask/
├─ raw_depth/
│  ├─ view_0001.exr
│  └─ ...
├─ geometry_mask/
├─ camera/
│  ├─ view_0001.json
│  └─ ...
└─ capture.json
```

`view_0001` is the Front view used as the reference view for Auto Camera layouts.

---

## ComfyUI Generation

ViewTexForge sends Capture outputs to the bundled workflow and generates images using the Reference Image.

Main inputs:

```text
Clay
Depth
Mask
Reference Image
```

The bundled workflow combines Qwen Image Edit 2511 with Depth / Canny / Inpaint DiffSynth ControlNet to generate the appearance while preserving the source 3D shape as much as possible.

Generated images are saved under `generated/` in the Output Directory.

See the [ComfyUI Workflow README](../comfyui/README_EN.md) for details.

---

## Albedo Mode

When **Generate Options > Albedo Mode** is enabled, an additional process attempts to extract an Albedo-like result with reduced lighting information from the generated image.

Albedo Source:

- `appearance`
- `lighting` - default

Albedo extraction using Marigold IID does not guarantee a physically accurate Base Color. It is used as a practical preprocessing step to produce results that are easier to use in Texture Merge / Baking.

---

## Texture Merge

Texture Merge projects generated camera images back onto the model using Camera / Raw Depth / Geometry information and combines them into a UV texture.

Default settings:

```text
Texture Resolution : 2048 x 2048
Material Apply     : Apply to New Material
Depth Tolerance    : Auto
RGB Surface Check  : Local Surface
Small Hole Fill    : Constrained
```

For the first run, the defaults are recommended.

See the [Settings Reference](settings.md) for detailed Texture Merge settings.

---

## Recommended First Test

Recommended first-test configuration:

```text
Render Target     : Selected Only
Qwen Preset       : 1024 x 1024
Clay Rendering    : Lit Clay Render
Lighting          : Use Auto Lighting
Power Mode        : Auto
Camera Layout     : 2 x 2 (4 Cameras)
Reference Image   : any single reference image
Albedo Mode       : OFF
Texture Resolution: 2048 x 2048
Material Apply    : Apply to New Material
Execution Mode    : Capture -> ComfyUI -> Texture Merge
```

Using `Selected Only` with only the target model selected makes the initial test scope easier to control.

---

## Troubleshooting Checklist

### Cannot connect to ComfyUI

- Confirm ComfyUI is running.
- Confirm Server URL / Port match.
- Confirm `http://127.0.0.1:8188` is reachable when using defaults.

### Workflow Status is Error

- Update ComfyUI.
- Update ComfyUI Manager.
- Install Missing Custom Nodes.
- Confirm required model locations.

Details: [ComfyUI Workflow README](../comfyui/README_EN.md)

### Capture does not start

- Confirm Output Directory is valid.
- Confirm Render Target includes at least one valid object.
- Confirm at least one of Clay / Normal / Depth / Mask is enabled.

### Texture Merge fails

- Confirm a UV Layer exists.
- Confirm the target geometry was not changed after Capture.
- Confirm corresponding generated images exist under `generated/`.
- Confirm Capture and Generated `view_id` values correspond.
