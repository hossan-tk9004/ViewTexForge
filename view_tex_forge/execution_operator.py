import bpy

from .texture_merge_operator import run_texture_merge


MODE_STAGES = {
    'CAPTURE_ONLY': ('CAPTURE',),
    'CAPTURE_COMFY': ('CAPTURE', 'COMFYUI'),
    'FULL': ('CAPTURE', 'COMFYUI', 'MERGE'),
    'COMFY_ONLY': ('COMFYUI',),
    'COMFY_MERGE': ('COMFYUI', 'MERGE'),
    'MERGE_ONLY': ('MERGE',),
}

STAGE_LABELS = {
    'CAPTURE': 'Capture',
    'COMFYUI': 'ComfyUI',
    'MERGE': 'Texture Merge',
}


class VIEWTEXFORGE_OT_run_execution(bpy.types.Operator):
    bl_idname = 'viewtexforge.run_execution'
    bl_label = 'Run Selected Mode'
    bl_description = 'Run the selected ViewTexForge execution pipeline'

    _timer = None
    _stages = None
    _stage_index = 0
    _waiting_for_comfy = False

    def execute(self, context):
        settings = context.scene.viewtexforge_settings
        if settings.execution_is_running or settings.comfyui_is_running:
            self.report({'WARNING'}, 'A ViewTexForge operation is already running.')
            return {'CANCELLED'}

        self._stages = MODE_STAGES.get(settings.execution_mode)
        if not self._stages:
            self.report({'ERROR'}, 'Unknown execution mode.')
            return {'CANCELLED'}

        self._stage_index = 0
        self._waiting_for_comfy = False
        settings.execution_is_running = True
        settings.execution_overall_progress = 0.0
        settings.execution_stage_progress = 0.0
        settings.execution_current_stage = STAGE_LABELS[self._stages[0]]
        settings.execution_status_text = 'Starting pipeline...'

        self._timer = context.window_manager.event_timer_add(0.2, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        settings = context.scene.viewtexforge_settings

        if self._waiting_for_comfy:
            settings.execution_current_stage = 'ComfyUI'
            settings.execution_stage_progress = settings.comfyui_progress
            settings.execution_status_text = settings.comfyui_status_text
            self._update_overall(settings)

            if settings.comfyui_is_running:
                self._redraw(context)
                return {'RUNNING_MODAL'}

            if settings.comfyui_status_text != 'Completed':
                return self._fail(context, settings.comfyui_status_text or 'ComfyUI generation failed.')

            settings.execution_stage_progress = 100.0
            self._waiting_for_comfy = False
            self._stage_index += 1
            self._update_overall(settings)
            self._redraw(context)
            return {'RUNNING_MODAL'}

        if self._stage_index >= len(self._stages):
            return self._complete(context)

        stage = self._stages[self._stage_index]
        settings.execution_current_stage = STAGE_LABELS[stage]
        settings.execution_stage_progress = 0.0
        self._update_overall(settings)

        if stage == 'CAPTURE':
            settings.execution_status_text = 'Capturing source images...'
            settings.execution_stage_progress = 5.0
            self._redraw(context)
            result = bpy.ops.viewtexforge.capture('EXEC_DEFAULT')
            if 'FINISHED' not in result:
                return self._fail(context, 'Capture failed. See Blender status/console for details.')
            settings.execution_stage_progress = 100.0
            settings.execution_status_text = 'Capture completed'
            self._stage_index += 1
            self._update_overall(settings)
            self._redraw(context)
            return {'RUNNING_MODAL'}

        if stage == 'COMFYUI':
            settings.execution_status_text = 'Starting ComfyUI generation...'
            result = bpy.ops.viewtexforge.comfyui_generate('EXEC_DEFAULT')
            if 'RUNNING_MODAL' not in result:
                return self._fail(context, 'ComfyUI generation could not be started.')
            self._waiting_for_comfy = True
            self._redraw(context)
            return {'RUNNING_MODAL'}

        if stage == 'MERGE':
            settings.execution_status_text = 'Running Texture Merge...'
            settings.execution_stage_progress = 5.0
            self._update_overall(settings)
            self._redraw(context)
            try:
                outputs, _manifest, output_dir, apply_report = run_texture_merge(context.scene)
            except Exception as exc:
                print(f'[ViewTexForge][Execution][Texture Merge][ERROR] {exc}')
                return self._fail(context, f'Texture Merge failed: {exc}')
            settings.execution_stage_progress = 100.0
            if apply_report.get('mode') == 'NONE':
                settings.execution_status_text = f'Texture Merge completed ({len(outputs)} texture(s))'
            else:
                settings.execution_status_text = (
                    f"Texture Merge completed ({len(outputs)} texture(s)); "
                    f"applied to {apply_report.get('objects', 0)} object(s) / "
                    f"{apply_report.get('materials_applied', 0)} material(s)"
                )
            self._stage_index += 1
            self._update_overall(settings)
            print(f'[ViewTexForge][Execution] Texture Merge output: {output_dir}')
            self._redraw(context)
            return {'RUNNING_MODAL'}

        return self._fail(context, f'Unknown stage: {stage}')

    def _update_overall(self, settings):
        count = max(1, len(self._stages or ()))
        completed = min(self._stage_index, count)
        current_fraction = 0.0
        if completed < count:
            current_fraction = max(0.0, min(1.0, settings.execution_stage_progress / 100.0))
        settings.execution_overall_progress = min(100.0, ((completed + current_fraction) / count) * 100.0)

    def _complete(self, context):
        settings = context.scene.viewtexforge_settings
        settings.execution_overall_progress = 100.0
        settings.execution_stage_progress = 100.0
        settings.execution_current_stage = 'Completed'
        settings.execution_status_text = 'Pipeline completed'
        self._finish(context)
        self.report({'INFO'}, 'ViewTexForge pipeline completed.')
        return {'FINISHED'}

    def _fail(self, context, message):
        settings = context.scene.viewtexforge_settings
        settings.execution_status_text = message
        settings.execution_current_stage = 'Failed'
        self._finish(context)
        self.report({'ERROR'}, message)
        return {'CANCELLED'}

    def _finish(self, context):
        settings = context.scene.viewtexforge_settings
        settings.execution_is_running = False
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        self._redraw(context)

    @staticmethod
    def _redraw(context):
        if context.area:
            context.area.tag_redraw()

    def cancel(self, context):
        self._finish(context)
