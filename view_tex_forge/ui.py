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

        layout.label(text="Version 0.3.4")
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

        box = layout.box()
        box.label(text="Save")
        box.prop(settings, 'output_dir')
        row = box.row(align=True)
        row.operator('viewtexforge.show_output_explorer', text='Show Explorer', icon='FILE_FOLDER')

        layout.separator()
        layout.operator('viewtexforge.capture', icon='RENDER_STILL')

        comfy = layout.box()
        comfy.label(text="ComfyUI Generation")
        comfy.prop(settings, 'comfyui_server_url', text='Server URL')

        status = settings.comfyui_connection_status
        if status == 'CONNECTED':
            comfy.label(text='Status: Connected', icon='CHECKMARK')
        elif status == 'CHECKING':
            comfy.label(text='Status: Checking...', icon='TIME')
        elif status == 'FAILED':
            comfy.label(text='Status: Connection Failed', icon='ERROR')
        else:
            comfy.label(text='Status: Unknown', icon='QUESTION')

        comfy.separator()
        workflow_status = settings.comfyui_workflow_status
        if workflow_status == 'VALID':
            comfy.label(text='Workflow Status: Valid', icon='CHECKMARK')
        elif workflow_status == 'CHECKING':
            comfy.label(text='Workflow Status: Checking...', icon='TIME')
        elif workflow_status == 'ERROR':
            error_row = comfy.row()
            error_row.alert = True
            error_row.label(text='Workflow Status: Error', icon='ERROR')
        else:
            comfy.label(text='Workflow Status: Unknown', icon='QUESTION')

        comfy.prop(settings, 'comfyui_reference_image', text='Reference Image')
        comfy.prop(settings, 'comfyui_seed_mode', text='Seed Mode')
        if settings.comfyui_seed_mode != 'RANDOM':
            comfy.prop(settings, 'comfyui_base_seed', text='Base Seed')
        else:
            comfy.label(text='Seed is resolved by ViewTexForge at run time')

        if settings.comfyui_is_running or settings.comfyui_progress > 0.0:
            comfy.separator()
            comfy.label(text=f"Status: {settings.comfyui_status_text}")
            comfy.prop(settings, 'comfyui_progress', text='Estimated Progress', slider=True)
            if settings.comfyui_resolved_seed:
                comfy.label(text=f"Resolved Seed: {settings.comfyui_resolved_seed}")

        row = comfy.row()
        row.enabled = not settings.comfyui_is_running
        row.operator('viewtexforge.comfyui_generate', icon='PLAY')
