import bpy


class VIEWTEXFORGE_PT_panel(bpy.types.Panel):
    bl_label = "ViewTexForge"
    bl_idname = "VIEWTEXFORGE_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ViewTexForge'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.viewtexforge_settings

        box = layout.box()
        box.label(text="Render Target")
        box.prop(settings, 'target_mode', expand=True)

        box = layout.box()
        box.label(text="Output Images")
        col = box.column(align=True)
        col.prop(settings, 'output_clay')
        col.prop(settings, 'output_normal')
        col.prop(settings, 'output_depth')

        box = layout.box()
        box.label(text="Camera")
        box.prop(settings, 'camera_mode', expand=True)
        if settings.camera_mode == 'SPECIFIED':
            box.prop(settings, 'specified_camera')

        box = layout.box()
        box.label(text="Save")
        box.prop(settings, 'output_dir')

        layout.separator()
        layout.operator('viewtexforge.capture', icon='RENDER_STILL')
