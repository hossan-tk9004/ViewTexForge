# ViewTexForge Changelog

[← Back to README](../../README_EN.md)

## v1.0 - Initial Public Release

Initial release for GitHub.

Main features:

- Blender 5.1.x support
- Auto Camera 2 x 2 (4 Cameras) / 3 x 3 (9 Cameras)
- Clay / Normal / Depth / Mask Capture
- Raw CAMERA_Z / Geometry Mask / Camera Metadata
- Auto Lighting
- Auto / Manual Light Power
- ComfyUI HTTP API Integration
- Bundled Qwen Image Edit Workflow
- Albedo Mode
- Integrated Texture Merge
- Six Execution Modes
- Modal Capture / Texture Merge Progress
- Output Directory Validation
- Status / Progress UI

---

# Development History

The following versions document development leading up to the v1.0 public release.

## v0.5.18

- Added Auto / Manual Power Mode.
- Made Auto the default and automatically calculate Area Light Power from target bounds and auto-light rig scale.
- Used a squared size relationship and safety clamp based on model size.
- Show Light Power only in Manual mode.

## v0.5.17

- Unified effective widths of Render Target radio choices and standard option rows.
- Enlarged Reference Image preview.

## v0.5.16

- Changed Render Target to a horizontal radio-style UI.
- Changed Reference Image to a compact two-row label + path / thumbnail layout.
- Hid Workflow selection from the ComfyUI panel and fixed the bundled workflow as the release workflow.

## v0.5.15

- Refined release GUI and defaults.
- Kept Capture / ComfyUI / Texture Merge Settings visible while collapsing secondary options.
- Changed Clay Rendering defaults to Lit Clay Render + Auto Lighting.
- Fixed Camera mode to Auto Cameras for the release workflow.
- Limited Camera Layout to 2 x 2 (4 Cameras) / 3 x 3 (9 Cameras).
- Show Albedo Source only when Albedo Mode is ON.
- Fixed Texture Merge visibility to Strict Ray.
- Organized Depth Tolerance / RGB Surface Check / Small Hole Fill / tuning settings under Advanced.

## v0.5.14

- Added Output Directory validation to Capture / ComfyUI / Texture Merge / Show Explorer.
- Converted Capture to a modal incremental operation with view/pass progress.
- Converted Texture Merge to a modal incremental operation with per-step progress.
- Execution now waits for modal Capture / Texture Merge stages and reflects them in Overall Progress.
- Improved runtime lock release on failure / cancellation.

## v0.5.12

- Adjusted 9-camera Front-Right / Front-Left to pitch +15 degrees.
- Kept Lower-Front at pitch -30 degrees.

## v0.5.11

- Changed 9-camera layout to an axis-heavy validation set.
- Front / Right / Back / Left / Top / Bottom / Front-Right / Front-Left / Lower-Front.

## v0.5.10

- Adjusted 9-camera layout to a left-right symmetric configuration.
- Tested Front + four upper diagonals + four lower diagonals.

## v0.5.9

- Replaced temporary 8-camera validation mode with legacy 9-camera mode.
- Tested Auto Camera layouts with 4 / 6 / 9 / 12 / 16 views.

## v0.5.8

- Added 4 / 6 / 8 / 12 / 16 camera layouts for validation.
- Restored legacy 8-view horizontal ring / 16-view angle set.

## v0.5.7

- Changed Auto Camera orthographic fitting to use evaluated target geometry bounds in each camera local 2D plane.
- Removed the cube/AABB-based ortho-scale floor that caused oblique views to appear too small.
- Applied Camera Margin to projected fitting.

## v0.5.6

- Implemented and tested 2 x 2 / 3 x 2 / 4 x 3 tiling for 4 / 6 / 12 cameras.
- Added `grid_columns` / `grid_rows` to `capture.json`.

## v0.5.5

- Changed ComfyUI `mask` output to RGB 8-bit pure black/white.
- Changed ComfyUI `depth` output to RGB 8-bit.
- Kept Texture Merge `depth_raw` / `geometry_mask` unchanged.

## v0.5.0

- Expanded Auto Cameras multi-view layouts.
- Organized Capture output into purpose-specific `clay / normal / depth / mask / raw_depth / geometry_mask / camera` folders.
- Standardized `view_XXXX` naming.
- Added `capture.json` manifest.
- Added stale view file cleanup.

## v0.4.0

- Integrated Standalone Texture Merge Core v1.
- Made Capture / ComfyUI / Texture Merge settings collapsible.
- Added six unified Execution modes.
- Added shared Status / overall / stage progress.
- Expanded the ComfyUI generated manifest for Texture Merge.

## v0.3.4

- Hid ComfyUI workflow selection from the main panel.
- Hid Texture Merge Contract / ComfyUI Input Mapping from the main panel.
- Added Show Explorer.
- Improved ComfyUI progress display.

## v0.3.3

- Standardized Capture folder / view_id to canonical numeric IDs such as `view_0001`, `view_0002`, ...
- Fixed `view_0001` as Front.
- Added contiguous view ID validation during ComfyUI capture discovery.

## v0.3.2

- Fixed upload filename collisions for `clay.png / depth.png / mask.png` across multiple camera folders.
- Changed upload filenames to include View ordinal / view_id.

## v0.3.1

- Placed the bundled ComfyUI API workflow under `workflows/`.
- Added a ViewTexForge workflow contract based on `_meta.title`.
- Added validation at workflow startup / change / before generation submission.

## v0.3.0

- Added ViewTexForge -> ComfyUI generation integration.
- Added Server URL / connection monitor / Reference Image / Seed Mode.
- Added HTTP polling-based progress.
- Added generated image download / generated manifest.

## v0.2.1

- Standardized Raw CAMERA_Z to METERS.
- Changed Geometry Mask / Raw Depth to geometry rasterization independent of material alpha / AA.
- Expanded Camera JSON v2 coordinate-system metadata.
- Standardized Geometry Digest serialization to `VTFGEOM1_LE_F64_U64`.

## v0.2.0

- Camera JSON format_version 2.
- Added `capture_id`.
- Added ORTHO `projection_matrix`.
- Added Raw CAMERA_Z EXR.
- Added `geometry_mask.png`.
- Added EVALUATED_RENDER Geometry Digest.

## v0.1.14

- Added `depth_space = CAMERA_Z` metadata to camera.json.

## v0.1.13

- Fixed Auto4 framing and output resolution / aspect fitting.
- Limited Camera Margin to Auto Cameras.

## v0.1.12

- Added Camera Margin control.

## v0.1.11

- Added Cast Shadow option for Auto lights.
- Improved Auto Camera framing based on target cube bounds.

## v0.1.10

- Applied auto-light exposure to Blender `Light.exposure`.
- Added Light Power / Normalize / directional Exposure to the UI.
- Changed Auto Light placement to a cube based on the target bounds' longest axis.

## v0.1.9

- Added Keep Auto Lights (Debug).

## v0.1.8

- Changed Auto Light placement to target bounding-box faces.
- Adopted Square Area Light / Normalize.

## v0.1.3

- Added Blender 5.1 compositor / File Output API support.
- Added Qwen output size presets.
- Added Viewport Camera preview overlay.
- Added Solid Viewport / Lit Clay Render.
- Added Existing Lighting / Auto 5-area-light rig.

## v0.1.2

- Added Blender-version-compatible Eevee engine selection.
- Added version display to the ViewTexForge panel.
