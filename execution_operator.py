import bpy

from .utils import reset_runtime_locks


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
    _waiting_for_capture = False
    _waiting_for_comfy = False
    _waiting_for_merge = False

    def execute(self, context):
        settings = context.scene.viewtexforge_settings
        if (settings.execution_is_running or settings.comfyui_is_running
                or settings.capture_is_running or settings.texture_merge_is_running):
            self.report({'WARNING'}, 'A ViewTexForge operation is already running.')
            return {'CANCELLED'}

        self._stages = MODE_STAGES.get(settings.execution_mode)
        if not self._stages:
            self.report({'ERROR'}, 'Unknown execution mode.')
            return {'CANCELLED'}

        self._stage_index = 0
        self._waiting_for_capture = False
        self._waiting_for_comfy = False
        self._waiting_for_merge = False
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
        try:
            if self._waiting_for_capture:
                settings.execution_current_stage = 'Capture'
                self._update_overall(settings)
                if settings.capture_is_running:
                    self._redraw(context)
                    return {'RUNNING_MODAL'}
                if settings.capture_last_result != 'FINISHED':
                    return self._fail(context, settings.execution_status_text or 'Capture failed.')
                settings.execution_stage_progress = 100.0
                self._waiting_for_capture = False
                self._stage_index += 1
                self._update_overall(settings)
                self._redraw(context)
                return {'RUNNING_MODAL'}

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

            if self._waiting_for_merge:
                settings.execution_current_stage = 'Texture Merge'
                self._update_overall(settings)
                if settings.texture_merge_is_running:
                    self._redraw(context)
                    return {'RUNNING_MODAL'}
                if settings.texture_merge_last_result != 'FINISHED':
                    return self._fail(context, settings.execution_status_text or 'Texture Merge failed.')
                settings.execution_stage_progress = 100.0
                self._waiting_for_merge = False
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
                settings.execution_status_text = 'Starting capture...'
                try:
                    result = bpy.ops.viewtexforge.capture('EXEC_DEFAULT')
                except Exception as exc:
                    return self._fail(context, f'Capture failed: {exc}')
                if 'RUNNING_MODAL' not in result:
                    return self._fail(context, settings.execution_status_text or 'Capture could not be started.')
                self._waiting_for_capture = True
                self._redraw(context)
                return {'RUNNING_MODAL'}

            if stage == 'COMFYUI':
                settings.execution_status_text = 'Starting ComfyUI generation...'
                try:
                    result = bpy.ops.viewtexforge.comfyui_generate('EXEC_DEFAULT')
                except Exception as exc:
                    return self._fail(context, f'ComfyUI failed: {exc}')
                if 'RUNNING_MODAL' not in result:
                    return self._fail(context, settings.execution_status_text or 'ComfyUI generation could not be started.')
                self._waiting_for_comfy = True
                self._redraw(context)
                return {'RUNNING_MODAL'}

            if stage == 'MERGE':
                settings.execution_status_text = 'Starting Texture Merge...'
                try:
                    result = bpy.ops.viewtexforge.texture_merge('EXEC_DEFAULT')
                except Exception as exc:
                    return self._fail(context, f'Texture Merge failed: {exc}')
                if 'RUNNING_MODAL' not in result:
                    return self._fail(context, settings.execution_status_text or 'Texture Merge could not be started.')
                self._waiting_for_merge = True
                self._redraw(context)
                return {'RUNNING_MODAL'}

            return self._fail(context, f'Unknown stage: {stage}')
        except Exception as exc:
            return self._fail(context, f'Pipeline failed: {exc}')

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
        reset_runtime_locks(settings, include_execution=True)
        self._waiting_for_capture = False
        self._waiting_for_comfy = False
        self._waiting_for_merge = False
        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        self._redraw(context)

    @staticmethod
    def _redraw(context):
        screen = getattr(context, 'screen', None)
        if screen:
            for area in screen.areas:
                try:
                    area.tag_redraw()
                except Exception:
                    pass

    def cancel(self, context):
        self._finish(context)
