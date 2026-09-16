bl_info = {
    "name": "ViewTexForge",
    "author": "OpenAI",
    "version": (0, 2, 1),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > ViewTexForge",
    "description": "Camera-based capture tools for AI texture generation workflows",
    "category": "3D View",
}

import bpy
from .props import VIEWTEXFORGE_PG_Settings
from .operators import VIEWTEXFORGE_OT_capture
from .ui import VIEWTEXFORGE_PT_panel
from .preview import remove_preview_handler

classes = (
    VIEWTEXFORGE_PG_Settings,
    VIEWTEXFORGE_OT_capture,
    VIEWTEXFORGE_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.viewtexforge_settings = bpy.props.PointerProperty(type=VIEWTEXFORGE_PG_Settings)


def unregister():
    remove_preview_handler()
    if hasattr(bpy.types.Scene, "viewtexforge_settings"):
        del bpy.types.Scene.viewtexforge_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
