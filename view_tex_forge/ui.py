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

        layout.label(text="Version 0.1.5")
        layout.separator()

        box = layout.box()
        box.label(text="Render Target")
        box.prop(settings, 'target_mode', expand=True)

        box = layout.box()
        box.label(text="Output Images")
        col = box.column(align=True)
        col.prop(settings, 'output_clay')
        col.prop(settings, 'output_normal')
        col.prop(settings, 'output_depth')
        col.prop(settings, 'output_mask')

        box = layout.box()
        box.label(text="Output Size")
        box.prop(settings, 'render_size_preset', text="Qwen Preset")

        box = layout.box()
        box.label(text="Camera")
        box.prop(settings, 'camera_mode', expand=True)
        if settings.camera_mode == 'SPECIFIED':
            box.prop(settings, 'specified_camera')
        elif settings.camera_mode == 'VIEWPORT':
            box.prop(settings, 'preview_mode')
            if settings.preview_mode:
                box.label(text='Overlay shows final output frame', icon='INFO')

        box = layout.box()
        box.label(text="Save")
        box.prop(settings, 'output_dir')

        layout.separator()
        layout.operator('viewtexforge.capture', icon='RENDER_STILL')
