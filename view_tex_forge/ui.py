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

        layout.label(text="Version 0.2.1")
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
        box.label(text="Clay Rendering")
        box.prop(settings, 'clay_render_mode', text="Mode")
        if settings.clay_render_mode == 'LIT':
            box.prop(settings, 'lighting_mode', text="Lighting")

            header = box.row(align=True)
            icon = 'TRIA_DOWN' if settings.show_lighting_options else 'TRIA_RIGHT'
            header.prop(settings, 'show_lighting_options', text='Lighting Options', icon=icon, emboss=False, toggle=False)

            if settings.show_lighting_options:
                sub = box.box()
                if settings.lighting_mode == 'AUTO':
                    sub.label(text='Auto Light Placement: Cube Bounds')
                    sub.label(text='Auto Light Shape: Square')
                    sub.prop(settings, 'light_power')
                    sub.prop(settings, 'light_normalize')
                    sub.prop(settings, 'light_use_shadow')
                    sub.prop(settings, 'light_exposure_front')
                    sub.prop(settings, 'light_exposure_back')
                    sub.prop(settings, 'light_exposure_left')
                    sub.prop(settings, 'light_exposure_right')
                    sub.prop(settings, 'light_exposure_top')
                    sub.prop(settings, 'keep_auto_lights_debug')
                sub.prop(settings, 'light_color')

        box = layout.box()
        box.label(text="Camera")
        box.prop(settings, 'camera_mode', expand=True)
        if settings.camera_mode == 'AUTO4':
            box.prop(settings, 'camera_fit_margin', text='Camera Margin')
        if settings.camera_mode == 'SPECIFIED':
            box.prop(settings, 'specified_camera')
        elif settings.camera_mode == 'VIEWPORT':
            box.prop(settings, 'preview_mode')
            if settings.preview_mode:
                box.label(text='Overlay shows final output frame', icon='INFO')

        contract_box = layout.box()
        contract_box.label(text="Texture Merge Contract")
        contract_box.label(text="Camera JSON v2 / EVALUATED_RENDER", icon='CHECKMARK')
        contract_box.label(text="Raw CAMERA_Z EXR + Geometry Mask")

        box = layout.box()
        box.label(text="Save")
        box.prop(settings, 'output_dir')

        layout.separator()
        layout.operator('viewtexforge.capture', icon='RENDER_STILL')
