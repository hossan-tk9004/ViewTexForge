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
