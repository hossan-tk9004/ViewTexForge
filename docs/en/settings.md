# ViewTexForge Settings Reference

[← Back to README](../../README_EN.md)

This page describes the main settings shown in the public ViewTexForge v1.0 GUI.

> For a first run, it is recommended to try the [Quick Start](usage.md) with the default settings.

---

## Save

### Output Directory

Root folder for Capture, Generated, and Texture Merge outputs.

Default:

```text
//ai_texture_capture
```

Processing stops if the path is invalid, an unresolved Blender-relative path, or not writable.

### Show Explorer

Opens the current Output Directory in Explorer.

---

# Capture Settings

## Render Target

### All Renderable

Uses renderable objects in the scene.

### Selected Only

Captures only the currently selected targets.

Useful for first tests or when processing a specific character only.

**Default:** `All Renderable`

---

## Output Size

### Qwen Preset

Capture image resolution.

| Setting | Use |
|---|---|
| 1024 x 1024 (Recommended) | Standard / recommended |
| 1280 x 1280 (Balanced) | Slightly higher resolution |
| 1536 x 1536 (Detail) | Higher detail / increased processing cost |

**Default:** `1024 x 1024`

---

## Clay Rendering

### Mode

#### Solid Viewport

Outputs Clay images using Solid Viewport + MatCap.

#### Lit Clay Render

Outputs rendered images using a gray Clay Material and lighting.

**Default:** `Lit Clay Render`

### Lighting

Shown when using Lit Clay Render.

#### Use Existing Lighting

Uses the current Scene Lighting.

#### Use Auto Lighting

ViewTexForge automatically creates five Area Lights: Front / Back / Left / Right / Top.

**Default:** `Use Auto Lighting`

---

## Camera

The public v1.0 GUI uses Auto Cameras.

### Camera Layout

#### 2 x 2 (4 Cameras)

```text
Front / Right / Back / Left
```

**Default / Recommended**

#### 3 x 3 (9 Cameras)

Uses an axis-heavy nine-view capture set:

```text
Front
Right
Back
Left
Top
Bottom
Front-Right (slightly elevated)
Front-Left (slightly elevated)
Lower-Front
```

Use this when you need generation and projection data from more directions.

### Camera Margin

Framing margin for Auto Cameras.

- Smaller value: fit the model closer to the frame edges
- Larger value: add more surrounding margin

**Default:** `1.05`

The camera is automatically fitted from the bounds of the target geometry projected onto each camera's local 2D plane.

---

## Output Settings

### Output Images

#### Clay

Outputs the main Clay image used by ComfyUI.

**Default:** ON

#### Normal

Outputs Normal images.

**Default:** ON

#### Depth

Outputs normalized Depth images for ComfyUI.

**Default:** ON

#### Mask

Outputs foreground Mask images for ComfyUI.

**Default:** ON

> At least one of Clay / Normal / Depth / Mask must be enabled to run Capture.

Texture Merge data such as `raw_depth` / `geometry_mask` / `camera` is generated separately as part of the Capture Contract.

---

## Lighting Options

Available when using `Lit Clay Render + Use Auto Lighting`.

### Power Mode

#### Auto

Automatically calculates Area Light Power from the target model's bounding size.

This reduces the need to manually adjust light power for very large or very small models.

**Default:** `Auto`

#### Manual

Lets you specify Light Power manually.

**Light Power** is shown only in Manual mode.

### Light Power

Area Light Power used in Manual Power Mode.

**Default:** `1000.0`

### Normalize

Sets Normalize on automatically generated Area Lights.

**Default:** ON

### Cast Shadow

Enables shadows for automatically generated lights.

**Default:** OFF

### Exposure

Defaults:

```text
Front : 6.0
Back  : 6.0
Left  : 6.0
Right : 6.0
Top   : 8.0
```

### Light Color

Color of automatically generated lights.

**Default:** White

### Keep Auto Lights (Debug)

Keeps automatically generated lights in the Scene after Capture.

OFF is recommended for normal use.

**Default:** OFF

---

# ComfyUI Settings

## Reference Image

Image used by Qwen Image Edit as the appearance and color reference.

The same Reference Image is used for all camera views.

Required when using the full workflow.

---

## Server URL

Base URL of the ComfyUI server.

**Default:**

```text
http://127.0.0.1:8188
```

### Status

Shows the connection state to ComfyUI.

```text
Connected
Checking...
Connection Failed
Unknown
```

### Workflow Status

Checks whether the bundled workflow can be controlled by ViewTexForge.

```text
Valid
Checking...
Error
Unknown
```

The public GUI does not expose workflow selection; the bundled workflow is used.

---

## Generate Options

### Albedo Mode

When ON, ViewTexForge uses Marigold IID after ComfyUI generation to produce an Albedo-like result with reduced lighting information.

**Default:** OFF

### Albedo Source

Shown only when Albedo Mode is ON.

- `appearance`
- `lighting`

**Default:** `lighting`

### Seed Mode

#### Fixed

Uses Base Seed directly.

#### Increment

Increments Base Seed for each workflow batch.

#### Random

ViewTexForge chooses a random seed at execution time.

**Default:** `Fixed`

### Base Seed

Base Seed used by Fixed / Increment modes.

**Default:** `18`

---

# Texture Merge Settings

## Texture Resolution

Resolution of the output Base Color texture.

```text
1024 x 1024
2048 x 2048
4096 x 4096
```

**Default:** `2048 x 2048`

### Material Apply

#### Do Not Apply

Saves the texture file only and does not modify the Blender Material.

#### Apply to Current Material

Replaces the Base Color connection of the current Material.

#### Apply to New Material

Duplicates the current Material, connects the merged Base Color to the new Material, and assigns it to the Object.

**Default:** `Apply to New Material`

---

## Texture Merge Options

### Merge Output Folder

Texture Merge output folder created under Output Directory.

**Default:**

```text
merged
```

---

## Advanced

The default values are recommended for normal use.

### Depth Tolerance

#### Auto

Automatically calculates per-view Depth tolerance from the Capture pixel footprint.

**Default:** `Auto`

Auto values:

```text
Depth Sigma Scale  : 0.65 px
Depth Cutoff Scale : 1.70 px
```

#### Manual

Uses explicit values in meters.

Default manual values:

```text
Depth Sigma  : 0.0012 m
Depth Cutoff : 0.003 m
```

### RGB Surface Check

#### Off

Uses conventional nearest-pixel sampling.

#### Local Surface

Requires the RGB pixel center to correspond to the same local mesh surface, helping reduce incorrect color sampling near boundaries and occlusions.

**Default:** `Local Surface`

### RGB Boundary Guard (capture px)

Guard width around silhouette / occlusion boundaries.

When set to `-1`, the value is derived automatically from generation scale.

**Default:** `-1`

### Small Hole Fill

#### Off

Leaves unobserved UV texels unresolved.

#### Constrained

Fills only small, local holes when the surrounding color range is sufficiently consistent.

**Default:** `Constrained`

Advanced defaults:

```text
Fill Vertex Group     : empty
Max Hole Area         : 8 texels
Max Surface Distance  : 0.002
Min Source Weight     : 0.05
Max Source Color Range: 0.18
```

### Merge Tuning

#### Facing Exponent

Exponent applied to camera-facing weight.

**Default:** `4.0`

#### Face Gate Gain

Strength of the face-normal gate.

**Default:** `12.0`

#### Padding Radius

Padding distance used to extend color outside UV islands.

**Default:** `16`

#### PNG Bit Depth

- 8 bit
- 16 bit

**Default:** `8 bit`

#### Debug Output

Writes diagnostic images and reports for Texture Merge.

**Default:** OFF

---

# Execution

## Mode

| Mode | Processing |
|---|---|
| Capture only | Capture |
| Capture -> ComfyUI | Capture → ComfyUI |
| Capture -> ComfyUI -> Texture Merge | Capture → ComfyUI → Texture Merge |
| ComfyUI only | ComfyUI |
| ComfyUI -> Texture Merge | ComfyUI → Texture Merge |
| Texture Merge only | Texture Merge |

**Default:** `Capture -> ComfyUI -> Texture Merge`

### Run Selected Mode

Runs the selected Execution Mode.

---

# Status

The Status section is always visible.

### Current Stage

Current processing stage.

### Overall Progress

Progress of the complete Execution.

### Stage Progress

Progress of the current stage.

### Status Message

Shows the current operation and result messages.
