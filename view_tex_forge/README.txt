ViewTexForge Add-on
=========================

Install:
1. Zip the folder "view_tex_forge" or use the provided zip.
2. In Blender, open Edit > Preferences > Add-ons > Install...
3. Select the zip file.
4. Enable "ViewTexForge".

UI Location:
- 3D Viewport > N Panel > ViewTexForge

Features:
- Render target mode:
  - All Renderable
  - Selected Only
- Output image types:
  - Clay (Viewport Solid + MatCap)
  - Normal
  - Depth
  - Mask
- Camera modes:
  - Viewport Camera
  - Auto 4 Cameras
  - Specified Camera
- Output directory selection
- camera.json export per view

Notes:
- Clay output requires a visible 3D Viewport (not background mode).
- Temporary cameras created in Viewport/Auto4 mode are deleted after capture.

Version 0.1.2:
- Added Blender-version compatible Eevee engine selection (BLENDER_EEVEE_NEXT / BLENDER_EEVEE).


v0.1.2
- Render engine compatibility now inspects the available RNA enum values before assignment.
- No unsupported BLENDER_EEVEE_NEXT probe is performed.
- Added version display to the ViewTexForge panel.

Version 0.1.3
- Blender 5.1 compositor API: Scene.compositing_node_group / CompositorNodeTree
- Blender 5.1 File Output API: directory / file_name / file_output_items
- Removed Scene.node_tree / Scene.use_nodes dependency

- Output size presets for Qwen workflows: 1024 / 1280 / 1536
- Viewport Camera preview overlay for final output frame

- Clay rendering modes: Solid Viewport / Lit Clay Render
- Lighting modes for lit clay: Existing Lighting / Auto 5-area-light rig
- Auto lights: front/back/left/right exposure default 6, top exposure default 8
- Lighting options UI: collapsible section with exposure and color controls

Version 0.1.8
- Updated auto light placement to use the target bounding box faces (front/back/left/right/top).
- Auto light shape is now Square.
- Auto light power is now fixed at 1000.0.
- Auto light normalize is now enabled.

Version 0.1.9
- Added Keep Auto Lights (Debug) option under Lighting Options.
- When enabled, generated auto lights remain in __VIEWTEXFORGE_LIGHTS__ after capture.
- Existing scene-light visibility and world settings are still restored after capture.
- A later auto-light capture replaces the previous retained debug rig to avoid duplication.

Version 0.1.10
- Auto-light exposure now writes to Blender Light.exposure as intended.
- Lighting Options now expose Light Power, Normalize, and per-direction Exposure (Front/Back/Left/Right/Top).
- Auto-light placement now uses a cube fitted from the longest target bounding-box axis.
- Auto-light square size now matches that cube size.

Version 0.1.11
- Added Cast Shadow option for auto-generated lights (default OFF).
- Lighting Options now expose Cast Shadow alongside Light Power / Exposure / Normalize.
- Auto-camera framing now uses a cube fitted from the longest target bounding-box axis and fills the image with a small margin.
- Ortho camera scale now matches the cube bounds for more consistent framing across views.

Version 0.1.12
- Added Camera Margin control to the UI for tighter or looser framing.
- Auto/ViewPort/Specified orthographic cameras now use the user-defined camera fit margin when auto-fitting.

Version 0.1.13
- Fixed loose Auto4 framing caused by fitting cameras before applying the selected square output resolution.
- Corrected orthographic aspect fitting logic.
- Camera Margin is now Auto 4 Cameras only.
- Viewport Camera and Specified Camera preserve their authored framing.

Version 0.1.14
- Added depth_space metadata to camera.json.
- depth_space is written as CAMERA_Z, matching the camera-space -Z depth convention used for depth near/far normalization.

Version 0.2.0
- Camera JSON upgraded to format_version 2 for Standalone Texture Merge v1.
- Added one capture_id shared by all views from a single Capture Images operation.
- Added ORTHO projection_matrix using the final render resolution/aspect.
- Added Raw CAMERA_Z depth export as depth_raw.exr (OpenEXR, 32-bit float).
- Added geometry_mask.png from the same validity test used to gate Raw CAMERA_Z.
- Added EVALUATED_RENDER Geometry Digest captured from a RENDER dependency graph.
- Geometry Digest hashes evaluated vertex positions, triangles, corner UVs, matrix_world, and meters_per_world_unit.
- Existing clay.png / normal.png / normalized depth.png / mask.png outputs remain available for ComfyUI workflows.
- Registration and Texture Merge itself are intentionally not implemented in ViewTexForge.

Version 0.2.1
- Raw CAMERA_Z is generated in METERS from the same EVALUATED_RENDER triangle set used for Geometry Mask.
- Geometry Mask and Raw Depth no longer use Render Layers Position/Alpha and do not depend on material alpha or AA.
- RENDER-evaluated camera matrix_world and projection_matrix are the canonical camera values.
- Geometry Digest serialization now follows VTFGEOM1_LE_F64_U64 exactly.
- Camera JSON v2 now records coordinate_system, matrix_convention, image_origin, and pixel_center_offset.
- texture_merge_v1_compatible remains false unless the v1 contract checks all pass.

Version 0.3.0
- Added initial ViewTexForge -> ComfyUI generation integration.
- Added configurable ComfyUI Server URL (default http://127.0.0.1:8188).
- Connection status is checked automatically at add-on startup, after URL changes, periodically, and again at generation start.
- Added API workflow JSON selector and a single shared Reference Image selector.
- Added Fixed / Increment / Random seed modes. Seed resolution is performed by ViewTexForge before submitting the workflow.
- Added HTTP-polling based generation status/progress display without blocking Blender's UI.
- The current workflow adapter targets Qwen_3DCharacterTexture_generator_ggfu and processes the latest 4-view capture as one 2x2-grid ComfyUI job.
- Clay / normalized Depth / Mask are uploaded for each of the 4 views, together with the shared reference image.
- Generated tiles are downloaded to <Output Directory>/generated and renamed by view_id.
- generated/generated_manifest.json records capture_id, workflow hash, reference hash, resolved seed, source-view mapping, and generated output mapping.

ViewTexForge v0.3.1 - ComfyUI Workflow Contract
-------------------------------------------------
The bundled ComfyUI API workflow is stored under workflows/ and is used by default.
A custom workflow can be selected from the UI when needed.

ViewTexForge discovers integration nodes by _meta.title, not by ComfyUI node ID.
Required contract titles:
  ViewTexForge_input_SourceImage01..NN
  ViewTexForge_input_DepthImage01..NN
  ViewTexForge_input_MaskImage01..NN
  ViewTexForge_input_ReferenceImage
  ViewTexForge_input_PositivePrompt
  ViewTexForge_input_NegativePrompt
  ViewTexForge_input_Seed
  ViewTexForge_input_OutputDirName
  ViewTexForge_input_OutputFilePrefix
  ViewTexForge_output_GeneratedImage

The Source/Depth/Mask counts must match and numbering must be contiguous from 01.
The workflow is validated automatically on startup, when its selection changes, and
when the workflow file changes on disk. UI shows Workflow Status; detailed validation
errors are printed to the Blender system console. Generate also validates immediately
before submitting the workflow to ComfyUI.


v0.3.2
- Fixed ComfyUI upload filename collisions when multiple camera folders contain clay.png/depth.png/mask.png.
- Uploaded input names now include the view ordinal and view_id so each workflow slot references a distinct file.
- Added ComfyUI input mapping logs to Blender System Console.


Version 0.3.3 - Canonical View IDs
----------------------------------
- Capture folders now use canonical numeric IDs: view_0001, view_0002, ...
- The first Auto4 camera is always the canonical front view and therefore view_0001.
- Natural-language direction names are no longer persisted as view_id or folder names.
- No view_index field is added to camera.json; ordering is derived from the four-digit suffix of view_id.
- ComfyUI capture discovery validates canonical, contiguous view IDs and sorts by their numeric suffix.
- The ComfyUI panel shows the resolved input mapping; only view_0001 is annotated as (Front) for usability.


ViewTexForge v0.3.4 - UI / Progress polish
- ComfyUI workflow selection is no longer exposed; the bundled workflow is always used.
- Texture Merge Contract and ComfyUI Input Mapping are hidden from the main panel.
- Save section includes Show Explorer to open the configured output directory.
- HTTP-polling generation progress now advances as an estimated activity percentage while a job is running.
- Status text updates every poll with elapsed time and poll count so a long generation does not look hung.
- Exact ComfyUI console stdout is not captured because ViewTexForge does not own the external ComfyUI process; completion remains authoritative via /history.

ViewTexForge v0.4.0
- Integrated Standalone Texture Merge Core v1.
- Added collapsible Capture / ComfyUI / Texture Merge settings (closed by default, scene-persistent).
- Added single Execution selector with six single/multi-stage modes.
- Added always-visible shared Status section with overall and stage progress.
- Added Texture Merge settings and Run Texture Merge button.
- ComfyUI generation now emits Texture Merge compatible views[] metadata in generated_manifest.json.
- Texture Merge derives texture_merge_manifest.json and merge_settings.json automatically.


Version 0.5.0
- Auto Cameras supports selectable 2x2 (4), 3x3 (9), and 4x4 (16) deterministic view sets.
- view_0001 remains the canonical Front view.
- 3x3 uses eight horizontal views plus Top; 4x4 adds upper and lower rings.
- Capture outputs are grouped by type: clay, normal, depth, mask, raw_depth, geometry_mask, and camera.
- Capture filenames are normalized to view_XXXX across all output types.
- Added capture.json manifest with capture_id, grid size, ordered views, directions, folders, and per-view file paths.
- Managed capture folders are cleared of stale view_XXXX files before each capture so folder loading remains deterministic across changing Auto Camera layouts.
- Existing ComfyUI integration code is unchanged in this release.
- Bundled ComfyUI workflow JSON replaced with the supplied workflow.

Version 0.5.5
- Kept Texture Merge source data unchanged while updating only the ComfyUI-facing helper exports.
- mask/view_XXXX.png is now rewritten as RGB 8-bit with pure black/white values duplicated to R=G=B.
- depth/view_XXXX.png is now rewritten as RGB 8-bit with the original normalized depth appearance preserved as closely as possible.
- depth_raw/view_XXXX.exr and geometry_mask/view_XXXX.png remain the authoritative Texture Merge inputs and are not changed by this update.
- capture.json metadata now reports the ComfyUI depth helper as 8-bit RGB duplicated depth and the mask helper as 8-bit RGB duplicated binary mask.


Version 0.5.6
- Reworked Auto Cameras from 4 / 9 / 16 views to 4 / 6 / 12 cameras for 2x2 / 3x2 / 4x3 ComfyUI tiling.
- 4-camera mode is unchanged: Front / Right / Back / Left.
- 6-camera mode uses the six orthogonal directions: Front / Right / Back / Left / Top / Bottom.
- 12-camera mode uses 4 horizontal views, 4 upper diagonal views at pitch +45 degrees, and 4 lower cardinal views at pitch -35 degrees.
- view_0001 remains Front in every Auto Camera layout.
- capture.json now records grid_columns and grid_rows in addition to grid_size.
- Bundled ComfyUI grid column calculation now uses ceil(sqrt(view_count)) so 4 / 6 / 12 images form 2x2 / 3x2 / 4x3 grids.


Version 0.5.7
- Auto Camera orthographic fitting now uses the actual evaluated target geometry projected into each camera's local 2D plane.
- Removed the cube/AABB-based ortho-scale floor that caused oblique Upper/Lower views to appear much smaller than horizontal views.
- Auto Cameras are laterally recentered from each view's projected 2D bounds before ortho_scale is calculated.
- Camera Margin is applied to the final projected fit, so the dominant projected axis targets approximately 1 / margin of the frame.
- Camera JSON continues to be captured after the final fitted camera transform/ortho scale, preserving Texture Merge projection consistency.
- Bundled ComfyUI workflow JSON replaced with the newly supplied workflow.


Version 0.5.8
- Added selectable Auto Camera layouts for 4 / 6 / 8 / 12 / 16 cameras.
- Restored the legacy 8-view horizontal ring (the former 9-view family without the standalone Top camera) for validation.
- Restored the legacy 16-view angle set while keeping the newer projected 2D BBox orthographic fitting.
- 8-camera mode uses a 4x2 tile layout; 16-camera mode uses a 4x4 tile layout.
- Bundled ComfyUI workflow JSON replaced with the newly supplied workflow.

Version 0.5.9
- Replaced the temporary 8-camera validation mode with the restored legacy 9-camera mode.
- Auto Camera layouts are now 4 / 6 / 9 / 12 / 16.
- 9-camera mode uses the legacy 3x3 layout: eight horizontal views plus Top.
- The projected 2D BBox orthographic fit remains active for all auto-camera layouts, including 9 and 16.


Version 0.5.10
- Updated the 9-camera Auto Camera layout to a left/right symmetric arrangement.
- 9-camera mode now uses Front plus four upper diagonal views at pitch +40 degrees and four lower diagonal views at pitch -30 degrees.
- Projected 2D BBox fitting remains active for all nine cameras.


Version 0.5.11
- Reworked the 9-camera Auto Camera layout to an axis-heavy validation set.
- 9-camera mode is now Front / Right / Back / Left / Top / Bottom / Front-Right / Front-Left / Lower-Front.
- The projected 2D BBox orthographic fitting remains active for the updated 9-camera layout.


Version 0.5.12
- Adjusted the 9-camera Front-Right and Front-Left views from pitch 0 degrees to pitch +15 degrees.
- Other 9-camera angles remain unchanged, including Lower-Front at pitch -30 degrees.
- Projected 2D BBox orthographic fitting remains active.
