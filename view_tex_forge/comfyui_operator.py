import os
import queue

import bpy

from .comfyui_client import (
    ComfyUIGenerationWorker,
    request_connection_check,
    resolve_workflow_path,
    validate_workflow_file,
)


_ACTIVE_WORKERS = {}


class VIEWTEXFORGE_OT_comfyui_generate(bpy.types.Operator):
    bl_idname = "viewtexforge.comfyui_generate"
    bl_label = "Generate with ComfyUI"
    bl_description = "Run the configured ComfyUI workflow using the latest ViewTexForge 4-view capture"

    _timer = None
    _events = None
    _worker = None

    def execute(self, context):
        settings = context.scene.viewtexforge_settings
        if settings.comfyui_is_running:
            self.report({'WARNING'}, "A ComfyUI generation job is already running.")
            return {'CANCELLED'}

        workflow_path = resolve_workflow_path(settings)
        reference_path = bpy.path.abspath(settings.comfyui_reference_image)
        output_dir = bpy.path.abspath(settings.output_dir)

        if not settings.comfyui_server_url.strip():
            self.report({'ERROR'}, "ComfyUI Server URL is empty.")
            return {'CANCELLED'}
        valid, errors, _ = validate_workflow_file(workflow_path, log_errors=True)
        settings.comfyui_workflow_status = 'VALID' if valid else 'ERROR'
        settings.comfyui_workflow_error = '' if valid else (errors[0] if errors else 'Unknown workflow error')
        if not valid:
            self.report({'ERROR'}, "Workflow Error. See Blender system console for details.")
            return {'CANCELLED'}
        if not reference_path or not os.path.isfile(reference_path):
            self.report({'ERROR'}, "Please select a valid Reference Image.")
            return {'CANCELLED'}

        self._events = queue.Queue()
        self._worker = ComfyUIGenerationWorker(
            server_url=settings.comfyui_server_url,
            workflow_path=workflow_path,
            reference_path=reference_path,
            output_dir=output_dir,
            seed_mode=settings.comfyui_seed_mode,
            base_seed=settings.comfyui_base_seed,
            event_queue=self._events,
        )

        settings.comfyui_is_running = True
        settings.comfyui_progress = 0.0
        settings.comfyui_status_text = "Starting ComfyUI generation..."
        settings.comfyui_prompt_id = ""
        settings.comfyui_resolved_seed = 0

        _ACTIVE_WORKERS[context.scene.as_pointer()] = self._worker
        self._worker.start()

        window = context.window
        self._timer = context.window_manager.event_timer_add(0.2, window=window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        settings = context.scene.viewtexforge_settings
        finished = False
        failed = False
        done_message = None

        while True:
            try:
                message = self._events.get_nowait()
            except queue.Empty:
                break

            kind = message.get("kind")
            if kind == "progress":
                settings.comfyui_progress = message.get("progress", settings.comfyui_progress)
                settings.comfyui_status_text = message.get("status", settings.comfyui_status_text)
            elif kind == "mapping":
                # Mapping is intentionally hidden from the GUI; the detailed
                # mapping remains available in the Blender system console.
                pass
            elif kind == "prompt":
                settings.comfyui_prompt_id = message.get("prompt_id", "")
            elif kind == "seed":
                settings.comfyui_resolved_seed = int(message.get("seed", 0))
            elif kind == "error":
                settings.comfyui_status_text = "Failed: " + message.get("message", "Unknown error")
                failed = True
                finished = True
            elif kind == "done":
                settings.comfyui_progress = 100.0
                settings.comfyui_status_text = "Completed"
                done_message = message.get("generated_dir")
                finished = True

        if not self._worker.is_alive() and not finished:
            # Drain once more in case the final event arrived between checks.
            try:
                message = self._events.get_nowait()
                if message.get("kind") == "error":
                    settings.comfyui_status_text = "Failed: " + message.get("message", "Unknown error")
                    failed = True
                elif message.get("kind") == "done":
                    settings.comfyui_progress = 100.0
                    settings.comfyui_status_text = "Completed"
                    done_message = message.get("generated_dir")
            except queue.Empty:
                if not settings.comfyui_status_text.startswith("Failed"):
                    settings.comfyui_status_text = "Failed: generation worker ended unexpectedly"
                    failed = True
            finished = True

        if finished:
            self._finish(context)
            request_connection_check()
            if failed:
                self.report({'ERROR'}, settings.comfyui_status_text)
                return {'CANCELLED'}
            self.report({'INFO'}, f"ComfyUI generation complete: {done_message or output_dir_safe(settings)}")
            return {'FINISHED'}

        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        settings = context.scene.viewtexforge_settings
        settings.comfyui_is_running = False
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        _ACTIVE_WORKERS.pop(context.scene.as_pointer(), None)
        if context.area:
            context.area.tag_redraw()

    def cancel(self, context):
        # The v1 worker is not forcibly interrupted; closing the modal handler only
        # detaches UI monitoring. A true ComfyUI queue interrupt can be added later.
        self._finish(context)


def output_dir_safe(settings):
    try:
        return bpy.path.abspath(settings.output_dir)
    except Exception:
        return settings.output_dir
