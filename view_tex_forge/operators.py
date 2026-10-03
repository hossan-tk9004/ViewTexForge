import os
import re
import uuid
import subprocess
import sys
from contextlib import ExitStack

import bpy

from .camera_utils import create_auto_cameras, create_viewport_camera, prepare_specified_camera
from .metadata import write_camera_json, write_capture_manifest
from .lighting_utils import AutoLightingScope
from .render_utils import (
    render_clay_viewport,
    render_clay_lit,
    render_normal_pass,
    render_depth_pass,
    render_mask_pass,
)
from .contract_raster import render_texture_merge_contract_pass
from .utils import (
    DummyContext,
    RenderSettingsScope,
    VisibilityScope,
    cleanup_temp_cameras,
    ensure_dir,
    force_view_layer_update,
    get_target_objects,
    validate_output_directory,
)


OUTPUT_FOLDERS = {
    "clay": "clay",
    "normal": "normal",
    "depth": "depth",
    "mask": "mask",
    "depth_raw": "raw_depth",
    "geometry_mask": "geometry_mask",
    "camera": "camera",
}

_VIEW_FILE_RE = re.compile(r"^view_\d{4}\.(?:png|exr|json)$", re.IGNORECASE)


class VIEWTEXFORGE_OT_show_output_explorer(bpy.types.Operator):
    bl_idname = "viewtexforge.show_output_explorer"
    bl_label = "Show Explorer"
    bl_description = "Open the configured ViewTexForge output directory in the system file browser"

    def execute(self, context):
        settings = context.scene.viewtexforge_settings
        valid, output_dir, message = validate_output_directory(settings.output_dir, create=True)
        if not valid:
            self.report({'WARNING'}, message)
            return {'CANCELLED'}
        try:
            if sys.platform.startswith("win"):
                os.startfile(output_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", output_dir])
            else:
                subprocess.Popen(["xdg-open", output_dir])
        except Exception as exc:
            self.report({'ERROR'}, f"Could not open output directory: {exc}")
            return {'CANCELLED'}
        return {'FINISHED'}


def _geometry_fingerprint(contract_info):
    if not contract_info or contract_info.get("error"):
        return None
    items = []
    for target in contract_info.get("targets") or []:
        digest = (target.get("geometry_digest") or {}).get("value")
        object_id = target.get("object_id")
        if not digest or not object_id:
            return None
        items.append((object_id, digest))
    return tuple(sorted(items))


def _path_for(output_dir, kind, view_id, extension):
    folder = os.path.join(output_dir, OUTPUT_FOLDERS[kind])
    ensure_dir(folder)
    return os.path.join(folder, f"{view_id}.{extension}")


def _root_relative(output_dir, path):
    return os.path.relpath(path, output_dir).replace(os.sep, "/")


def _clear_managed_capture_outputs(output_dir):
    """Remove stale managed view files while leaving unrelated user/generated files alone."""
    for folder_name in OUTPUT_FOLDERS.values():
        folder = os.path.join(output_dir, folder_name)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not _VIEW_FILE_RE.match(name):
                continue
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                os.remove(path)
    manifest_path = os.path.join(output_dir, "capture.json")
    if os.path.isfile(manifest_path):
        os.remove(manifest_path)


class VIEWTEXFORGE_OT_capture(bpy.types.Operator):
    bl_idname = "viewtexforge.capture"
    bl_label = "Capture Images"
    bl_description = "Capture AI texture images and Standalone Texture Merge v1 contract data"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _stack = None
    _tasks = None
    _task_index = 0
    _camera_infos = None
    _created_temp_cameras = None
    _specified_camera_restore = None
    _pending_views = None
    _contract_warnings = None
    _manifest_views = None
    _capture_id = None
    _output_dir = None
    _target_objects = None
    _direct_status = False
    _phase = 'IDLE'

    def execute(self, context):
        settings = context.scene.viewtexforge_settings
        scene = context.scene

        if settings.capture_is_running or settings.comfyui_is_running or settings.texture_merge_is_running:
            self.report({'WARNING'}, "A ViewTexForge operation is already running.")
            return {'CANCELLED'}

        if not (settings.output_clay or settings.output_normal or settings.output_depth or settings.output_mask):
            self.report({'ERROR'}, "Please enable at least one legacy output image type.")
            return {'CANCELLED'}

        valid, output_dir, message = validate_output_directory(settings.output_dir, create=True)
        if not valid:
            settings.execution_current_stage = "Failed"
            settings.execution_stage_progress = 0.0
            settings.execution_status_text = message
            settings.capture_last_result = 'FAILED'
            self.report({'WARNING'}, message)
            return {'CANCELLED'}

        target_objects = get_target_objects(context, settings)
        if not target_objects:
            message = "No valid target objects found for the current mode."
            settings.execution_current_stage = "Failed"
            settings.execution_status_text = message
            settings.capture_last_result = 'FAILED'
            self.report({'ERROR'}, message)
            return {'CANCELLED'}

        self._direct_status = not settings.execution_is_running
        self._capture_id = str(uuid.uuid4())
        self._output_dir = output_dir
        self._target_objects = target_objects
        self._created_temp_cameras = []
        self._specified_camera_restore = None
        self._pending_views = []
        self._contract_warnings = []
        self._manifest_views = []
        self._tasks = []
        self._task_index = 0
        self._phase = 'CAPTURE'
        self._stack = ExitStack()

        # Release workflow contract: capture always uses the supported Auto Camera layouts.
        settings.camera_mode = 'AUTO4'
        if settings.auto_camera_grid not in {'4', '9'}:
            settings.auto_camera_grid = '4'

        settings.capture_is_running = True
        settings.capture_last_result = 'RUNNING'
        settings.execution_current_stage = "Capture"
        settings.execution_stage_progress = 0.0
        if self._direct_status:
            settings.execution_overall_progress = 0.0
        settings.execution_status_text = "Preparing capture..."

        try:
            _clear_managed_capture_outputs(output_dir)

            self._stack.enter_context(RenderSettingsScope(scene))
            size = int(settings.render_size_preset)
            scene.render.resolution_x = size
            scene.render.resolution_y = size
            scene.render.resolution_percentage = 100

            if settings.camera_mode == 'AUTO4':
                self._camera_infos = create_auto_cameras(context, target_objects)
                self._created_temp_cameras = [info[1] for info in self._camera_infos]
            elif settings.camera_mode == 'VIEWPORT':
                self._camera_infos = create_viewport_camera(context, target_objects)
                self._created_temp_cameras = [info[1] for info in self._camera_infos]
            else:
                self._camera_infos, self._specified_camera_restore = prepare_specified_camera(
                    context,
                    settings.specified_camera,
                    target_objects,
                )

            force_view_layer_update(context)

            if settings.target_mode == 'SELECTED_ONLY':
                self._stack.enter_context(VisibilityScope(scene, target_objects))
            if settings.output_clay and settings.clay_render_mode == 'LIT' and settings.lighting_mode == 'AUTO':
                self._stack.enter_context(AutoLightingScope(context, target_objects, settings))

            for view_ordinal, (view_id, cam_obj, depth_near, depth_far, view_meta) in enumerate(self._camera_infos, start=1):
                paths = {
                    "clay": _path_for(output_dir, "clay", view_id, "png") if settings.output_clay else None,
                    "normal": _path_for(output_dir, "normal", view_id, "png") if settings.output_normal else None,
                    "depth": _path_for(output_dir, "depth", view_id, "png") if settings.output_depth else None,
                    "mask": _path_for(output_dir, "mask", view_id, "png") if settings.output_mask else None,
                    "depth_raw": _path_for(output_dir, "depth_raw", view_id, "exr"),
                    "geometry_mask": _path_for(output_dir, "geometry_mask", view_id, "png"),
                    "camera": _path_for(output_dir, "camera", view_id, "json"),
                }
                item = {
                    "view_id": view_id,
                    "view_meta": view_meta,
                    "paths": paths,
                    "contract_info": None,
                    "cam_obj": cam_obj,
                    "depth_near": depth_near,
                    "depth_far": depth_far,
                    "view_ordinal": view_ordinal,
                    "total_views": len(self._camera_infos),
                }
                self._pending_views.append(item)
                if settings.output_clay:
                    self._tasks.append((item, 'CLAY'))
                if settings.output_normal:
                    self._tasks.append((item, 'NORMAL'))
                if settings.output_depth:
                    self._tasks.append((item, 'DEPTH'))
                if settings.output_mask:
                    self._tasks.append((item, 'MASK'))
                self._tasks.append((item, 'CONTRACT'))

            self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
            context.window_manager.modal_handler_add(self)
            self._redraw_all(context)
            return {'RUNNING_MODAL'}
        except Exception as exc:
            return self._fail(context, exc)

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        try:
            if self._phase == 'CAPTURE':
                if self._task_index < len(self._tasks):
                    item, task = self._tasks[self._task_index]
                    self._set_task_status(context, item, task, self._task_index, len(self._tasks))
                    self._run_capture_task(context, item, task)
                    self._task_index += 1
                    settings = context.scene.viewtexforge_settings
                    settings.execution_stage_progress = 5.0 + 70.0 * (self._task_index / max(1, len(self._tasks)))
                    if self._direct_status:
                        settings.execution_overall_progress = settings.execution_stage_progress
                    self._redraw_all(context)
                    return {'RUNNING_MODAL'}

                fingerprints = [_geometry_fingerprint(item["contract_info"]) for item in self._pending_views]
                self._geometry_camera_independent = (
                    len(fingerprints) > 0
                    and all(fp is not None for fp in fingerprints)
                    and len(set(fingerprints)) == 1
                )
                self._phase = 'METADATA'
                self._task_index = 0
                context.scene.viewtexforge_settings.execution_status_text = 'Writing camera metadata...'
                self._redraw_all(context)
                return {'RUNNING_MODAL'}

            if self._phase == 'METADATA':
                if self._task_index < len(self._pending_views):
                    item = self._pending_views[self._task_index]
                    self._write_view_metadata(context, item)
                    self._task_index += 1
                    settings = context.scene.viewtexforge_settings
                    settings.execution_stage_progress = 75.0 + 20.0 * (
                        self._task_index / max(1, len(self._pending_views))
                    )
                    if self._direct_status:
                        settings.execution_overall_progress = settings.execution_stage_progress
                    settings.execution_status_text = (
                        f"Writing camera metadata ({self._task_index}/{len(self._pending_views)})..."
                    )
                    self._redraw_all(context)
                    return {'RUNNING_MODAL'}

                self._phase = 'MANIFEST'
                context.scene.viewtexforge_settings.execution_status_text = 'Writing capture manifest...'
                self._redraw_all(context)
                return {'RUNNING_MODAL'}

            if self._phase == 'MANIFEST':
                write_capture_manifest(
                    os.path.join(self._output_dir, "capture.json"),
                    context.scene,
                    context.scene.viewtexforge_settings,
                    self._capture_id,
                    self._manifest_views,
                )
                return self._complete(context)

            return self._fail(context, RuntimeError(f"Unknown capture phase: {self._phase}"))
        except Exception as exc:
            return self._fail(context, exc)

    def _run_capture_task(self, context, item, task):
        settings = context.scene.viewtexforge_settings
        scene = context.scene
        cam_obj = item['cam_obj']
        paths = item['paths']
        if task == 'CLAY':
            if settings.clay_render_mode == 'SOLID':
                render_clay_viewport(scene, cam_obj, paths['clay'])
            else:
                render_clay_lit(scene, cam_obj, paths['clay'], settings)
        elif task == 'NORMAL':
            render_normal_pass(scene, cam_obj, paths['normal'])
        elif task == 'DEPTH':
            render_depth_pass(scene, cam_obj, paths['depth'], item['depth_near'], item['depth_far'])
        elif task == 'MASK':
            render_mask_pass(scene, cam_obj, paths['mask'])
        elif task == 'CONTRACT':
            try:
                item['contract_info'] = render_texture_merge_contract_pass(
                    scene,
                    cam_obj,
                    paths['depth_raw'],
                    paths['geometry_mask'],
                    self._target_objects,
                )
            except Exception as exc:
                item['contract_info'] = {"error": str(exc)}
                self._contract_warnings.append(f"{item['view_id']}: {exc}")
        else:
            raise RuntimeError(f"Unknown capture task: {task}")

    def _set_task_status(self, context, item, task, task_index, task_count):
        labels = {
            'CLAY': 'Rendering Clay',
            'NORMAL': 'Rendering Normal',
            'DEPTH': 'Rendering Depth',
            'MASK': 'Rendering Mask',
            'CONTRACT': 'Rendering Texture Merge Contract',
        }
        settings = context.scene.viewtexforge_settings
        settings.execution_current_stage = 'Capture'
        settings.execution_status_text = (
            f"{labels.get(task, task)} - {item['view_id']} "
            f"({item['view_ordinal']}/{item['total_views']})"
        )
        settings.execution_stage_progress = 5.0 + 70.0 * (task_index / max(1, task_count))
        if self._direct_status:
            settings.execution_overall_progress = settings.execution_stage_progress
        self._redraw_all(context)

    def _write_view_metadata(self, context, item):
        settings = context.scene.viewtexforge_settings
        compatible, errors = write_camera_json(
            item['paths']['camera'],
            context.scene,
            settings,
            item['view_id'],
            item['view_meta'],
            self._capture_id,
            item['contract_info'],
            self._geometry_camera_independent,
            item['paths'],
        )
        if not compatible:
            self._contract_warnings.append(f"{item['view_id']}: " + "; ".join(errors))

        view_meta = item['view_meta']
        files = {}
        for kind, path in item['paths'].items():
            if path and os.path.exists(path):
                files[kind] = _root_relative(self._output_dir, path)

        self._manifest_views.append({
            'view_id': item['view_id'],
            'view_index': int(view_meta.get('view_index', 1)),
            'view_label': view_meta.get('view_label'),
            'yaw_deg': view_meta.get('yaw_deg'),
            'pitch_deg': view_meta.get('pitch_deg'),
            'texture_merge_v1_compatible': bool(compatible),
            'files': files,
        })

    def _complete(self, context):
        settings = context.scene.viewtexforge_settings
        if self._contract_warnings:
            self.report(
                {'WARNING'},
                "Capture completed, but Texture Merge v1 compatibility is false for one or more views. "
                "See camera JSON contract_error and Blender Console.",
            )
            for warning in self._contract_warnings:
                print(f"[ViewTexForge] Texture Merge contract warning: {warning}")
        else:
            self.report({'INFO'}, f"Capture complete: {self._output_dir}")

        settings.capture_last_result = 'FINISHED'
        settings.execution_stage_progress = 100.0
        settings.execution_status_text = 'Capture completed'
        if self._direct_status:
            settings.execution_current_stage = 'Completed'
            settings.execution_overall_progress = 100.0
        self._cleanup(context)
        return {'FINISHED'}

    def _fail(self, context, exc):
        settings = context.scene.viewtexforge_settings
        message = str(exc)
        settings.capture_last_result = 'FAILED'
        settings.execution_current_stage = 'Failed'
        settings.execution_stage_progress = 0.0
        settings.execution_status_text = f"Capture failed: {message}"
        print(f"[ViewTexForge][Capture][ERROR] {message}")
        self._cleanup(context)
        self.report({'ERROR'}, message)
        return {'CANCELLED'}

    def _cleanup(self, context):
        settings = context.scene.viewtexforge_settings
        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None

        if self._stack is not None:
            try:
                self._stack.close()
            except Exception as exc:
                print(f"[ViewTexForge][Capture][Cleanup][WARN] {exc}")
            self._stack = None

        if self._specified_camera_restore and settings.specified_camera and settings.specified_camera.type == 'CAMERA':
            try:
                cam_data = settings.specified_camera.data
                cam_data.clip_start = self._specified_camera_restore['clip_start']
                cam_data.clip_end = self._specified_camera_restore['clip_end']
                if cam_data.type == 'ORTHO' and self._specified_camera_restore['ortho_scale'] is not None:
                    cam_data.ortho_scale = self._specified_camera_restore['ortho_scale']
            except Exception as exc:
                print(f"[ViewTexForge][Capture][Camera Restore][WARN] {exc}")

        if self._created_temp_cameras:
            try:
                cleanup_temp_cameras(self._created_temp_cameras)
            except Exception as exc:
                print(f"[ViewTexForge][Capture][Camera Cleanup][WARN] {exc}")

        settings.capture_is_running = False
        self._redraw_all(context)

    @staticmethod
    def _redraw_all(context):
        screen = getattr(context, 'screen', None)
        if screen:
            for area in screen.areas:
                try:
                    area.tag_redraw()
                except Exception:
                    pass

    def cancel(self, context):
        settings = context.scene.viewtexforge_settings
        settings.capture_last_result = 'FAILED'
        settings.execution_current_stage = 'Failed'
        settings.execution_status_text = 'Capture cancelled'
        self._cleanup(context)
