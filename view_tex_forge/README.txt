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
