import bpy


def _foldout_header(box, settings, prop_name, label, icon='PREFERENCES'):
    row = box.row(align=True)
    is_open = bool(getattr(settings, prop_name))
    row.prop(
        settings,
        prop_name,
        text=label,
        icon='TRIA_DOWN' if is_open else 'TRIA_RIGHT',
        emboss=False,
    )
    return is_open


class VIEWTEXFORGE_PT_panel(bpy.types.Panel):
    bl_label = "ViewTexForge"
    bl_idname = "VIEWTEXFORGE_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ViewTexForge'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.viewtexforge_settings

        layout.label(text="Version 0.4.1")
        layout.separator()

        save = layout.box()
        save.label(text="Save")
        save.prop(settings, 'output_dir')
        save.operator('viewtexforge.show_output_explorer', text='Show Explorer', icon='FILE_FOLDER')

        capture = layout.box()
        if _foldout_header(capture, settings, 'show_capture_settings', 'Capture Settings'):
            capture.separator()
            capture.label(text="Render Target")
            capture.prop(settings, 'target_mode', expand=True)

            capture.separator()
            capture.label(text="Output Images")
            col = capture.column(align=True)
            col.prop(settings, 'output_clay')
            col.prop(settings, 'output_normal')
            col.prop(settings, 'output_depth')
            col.prop(settings, 'output_mask')

            capture.separator()
            capture.label(text="Output Size")
            capture.prop(settings, 'render_size_preset', text="Qwen Preset")

            capture.separator()
            capture.label(text="Clay Rendering")
            capture.prop(settings, 'clay_render_mode', text="Mode")
            if settings.clay_render_mode == 'LIT':
                capture.prop(settings, 'lighting_mode', text="Lighting")
                header = capture.row(align=True)
                icon = 'TRIA_DOWN' if settings.show_lighting_options else 'TRIA_RIGHT'
                header.prop(
                    settings,
                    'show_lighting_options',
                    text='Lighting Options',
                    icon=icon,
                    emboss=False,
                )
                if settings.show_lighting_options:
                    sub = capture.box()
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

            capture.separator()
            capture.label(text="Camera")
            capture.prop(settings, 'camera_mode', expand=True)
            if settings.camera_mode == 'AUTO4':
                capture.prop(settings, 'camera_fit_margin', text='Camera Margin')
            if settings.camera_mode == 'SPECIFIED':
                capture.prop(settings, 'specified_camera')
            elif settings.camera_mode == 'VIEWPORT':
                capture.prop(settings, 'preview_mode')
                if settings.preview_mode:
                    capture.label(text='Overlay shows final output frame', icon='INFO')

            capture.separator()
            row = capture.row()
            row.enabled = not settings.execution_is_running and not settings.comfyui_is_running
            row.operator('viewtexforge.capture', text='Run Capture', icon='RENDER_STILL')

        comfy = layout.box()
        if _foldout_header(comfy, settings, 'show_comfyui_settings', 'ComfyUI Settings'):
            comfy.separator()
            comfy.prop(settings, 'comfyui_server_url', text='Server URL')
            status = settings.comfyui_connection_status
            if status == 'CONNECTED':
                comfy.label(text='Status: Connected', icon='CHECKMARK')
            elif status == 'CHECKING':
                comfy.label(text='Status: Checking...', icon='TIME')
            elif status == 'FAILED':
                row = comfy.row()
                row.alert = True
                row.label(text='Status: Connection Failed', icon='ERROR')
            else:
                comfy.label(text='Status: Unknown', icon='QUESTION')

            workflow_status = settings.comfyui_workflow_status
            if workflow_status == 'VALID':
                comfy.label(text='Workflow Status: Valid', icon='CHECKMARK')
            elif workflow_status == 'CHECKING':
                comfy.label(text='Workflow Status: Checking...', icon='TIME')
            elif workflow_status == 'ERROR':
                row = comfy.row()
                row.alert = True
                row.label(text='Workflow Status: Error', icon='ERROR')
            else:
                comfy.label(text='Workflow Status: Unknown', icon='QUESTION')

            comfy.separator()
            comfy.prop(settings, 'comfyui_reference_image', text='Reference Image')
            comfy.prop(settings, 'comfyui_seed_mode', text='Seed Mode')
            if settings.comfyui_seed_mode != 'RANDOM':
                comfy.prop(settings, 'comfyui_base_seed', text='Base Seed')
            else:
                comfy.label(text='Seed is resolved by ViewTexForge at run time')

            comfy.separator()
            row = comfy.row()
            row.enabled = not settings.comfyui_is_running and not settings.execution_is_running
            row.operator('viewtexforge.comfyui_generate', text='Run ComfyUI', icon='PLAY')

        merge = layout.box()
        if _foldout_header(merge, settings, 'show_texture_merge_settings', 'Texture Merge Settings'):
            merge.separator()
            merge.prop(settings, 'texture_merge_resolution')
            merge.prop(settings, 'texture_merge_depth_tolerance_mode')
            if settings.texture_merge_depth_tolerance_mode == 'AUTO':
                merge.prop(settings, 'texture_merge_depth_sigma_scale_px')
                merge.prop(settings, 'texture_merge_depth_cutoff_scale_px')
            else:
                merge.prop(settings, 'texture_merge_depth_sigma_m')
                merge.prop(settings, 'texture_merge_depth_cutoff_m')
            merge.prop(settings, 'texture_merge_output_subdir')
            merge.prop(settings, 'texture_merge_material_apply_mode', text='Material Apply')

            row = merge.row(align=True)
            opened = settings.show_texture_merge_advanced
            row.prop(
                settings,
                'show_texture_merge_advanced',
                text='Advanced',
                icon='TRIA_DOWN' if opened else 'TRIA_RIGHT',
                emboss=False,
            )
            if opened:
                advanced = merge.box()
                advanced.prop(settings, 'texture_merge_facing_exponent')
                advanced.prop(settings, 'texture_merge_face_gate_gain')
                advanced.prop(settings, 'texture_merge_padding_radius')
                advanced.prop(settings, 'texture_merge_png_bit_depth')
                advanced.prop(settings, 'texture_merge_debug_output')

            merge.separator()
            row = merge.row()
            row.enabled = not settings.execution_is_running and not settings.comfyui_is_running
            row.operator('viewtexforge.texture_merge', text='Run Texture Merge', icon='NODE_TEXTURE')

        execution = layout.box()
        execution.label(text='Execution')
        execution.prop(settings, 'execution_mode', text='Mode')
        row = execution.row()
        row.scale_y = 1.25
        row.enabled = not settings.execution_is_running and not settings.comfyui_is_running
        row.operator('viewtexforge.run_execution', text='Run Selected Mode', icon='PLAY')

        status_box = layout.box()
        status_box.label(text='Status')
        status_box.label(text=f"Current Stage: {settings.execution_current_stage}")
        status_box.prop(settings, 'execution_overall_progress', text='Overall Progress', slider=True)
        status_box.prop(settings, 'execution_stage_progress', text='Stage Progress', slider=True)
        status_box.label(text=settings.execution_status_text or 'Idle')
        if settings.comfyui_is_running and settings.comfyui_resolved_seed:
            status_box.label(text=f"Resolved Seed: {settings.comfyui_resolved_seed}")
