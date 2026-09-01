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
