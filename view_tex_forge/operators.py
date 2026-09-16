import os
import uuid

import bpy

from .camera_utils import create_auto_cameras, create_viewport_camera, prepare_specified_camera
from .metadata import write_camera_json
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
)


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


class VIEWTEXFORGE_OT_capture(bpy.types.Operator):
    bl_idname = "viewtexforge.capture"
    bl_label = "Capture Images"
    bl_description = "Capture AI texture images and Standalone Texture Merge v1 contract data"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.viewtexforge_settings
        scene = context.scene

        if not (settings.output_clay or settings.output_normal or settings.output_depth or settings.output_mask):
            self.report({'ERROR'}, "Please enable at least one legacy output image type.")
            return {'CANCELLED'}

        output_dir = bpy.path.abspath(settings.output_dir)
        ensure_dir(output_dir)

        target_objects = get_target_objects(context, settings)
        if not target_objects:
            self.report({'ERROR'}, "No valid target objects found for the current mode.")
            return {'CANCELLED'}

        capture_id = str(uuid.uuid4())
        created_temp_cameras = []
        specified_camera_restore = None
        pending_views = []
        contract_warnings = []

        try:
            with RenderSettingsScope(scene):
                size = int(settings.render_size_preset)
                scene.render.resolution_x = size
                scene.render.resolution_y = size
                scene.render.resolution_percentage = 100

                if settings.camera_mode == 'AUTO4':
                    camera_infos = create_auto_cameras(context, target_objects)
                    created_temp_cameras = [info[1] for info in camera_infos]
                elif settings.camera_mode == 'VIEWPORT':
                    camera_infos = create_viewport_camera(context, target_objects)
                    created_temp_cameras = [info[1] for info in camera_infos]
                else:
                    camera_infos, specified_camera_restore = prepare_specified_camera(
                        context,
                        settings.specified_camera,
                        target_objects,
                    )

                force_view_layer_update(context)

                visibility_scope = VisibilityScope(scene, target_objects) if settings.target_mode == 'SELECTED_ONLY' else None
                context_manager = visibility_scope if visibility_scope else DummyContext()

                lighting_scope = DummyContext()
                if settings.output_clay and settings.clay_render_mode == 'LIT' and settings.lighting_mode == 'AUTO':
                    lighting_scope = AutoLightingScope(context, target_objects, settings)

                with context_manager:
                    with lighting_scope:
                        for label, cam_obj, depth_near, depth_far in camera_infos:
                            label_dir = os.path.join(output_dir, label)
                            ensure_dir(label_dir)

                            if settings.output_clay:
                                if settings.clay_render_mode == 'SOLID':
                                    render_clay_viewport(scene, cam_obj, os.path.join(label_dir, 'clay.png'))
                                else:
                                    render_clay_lit(scene, cam_obj, os.path.join(label_dir, 'clay.png'), settings)
                            if settings.output_normal:
                                render_normal_pass(scene, cam_obj, os.path.join(label_dir, 'normal.png'))
                            if settings.output_depth:
                                render_depth_pass(scene, cam_obj, os.path.join(label_dir, 'depth.png'), depth_near, depth_far)
                            if settings.output_mask:
                                render_mask_pass(scene, cam_obj, os.path.join(label_dir, 'mask.png'))

                            try:
                                contract_info = render_texture_merge_contract_pass(
                                    scene,
                                    cam_obj,
                                    os.path.join(label_dir, 'depth_raw.exr'),
                                    os.path.join(label_dir, 'geometry_mask.png'),
                                    target_objects,
                                )
                            except Exception as exc:
                                contract_info = {"error": str(exc)}
                                contract_warnings.append(f"{label}: {exc}")

                            pending_views.append({
                                "label": label,
                                "label_dir": label_dir,
                                "contract_info": contract_info,
                            })

                fingerprints = [_geometry_fingerprint(item["contract_info"]) for item in pending_views]
                geometry_camera_independent = (
                    len(fingerprints) > 0
                    and all(fp is not None for fp in fingerprints)
                    and len(set(fingerprints)) == 1
                )

                for item in pending_views:
                    compatible, errors = write_camera_json(
                        os.path.join(item["label_dir"], 'camera.json'),
                        scene,
                        settings,
                        item["label"],
                        capture_id,
                        item["contract_info"],
                        geometry_camera_independent,
                    )
                    if not compatible:
                        contract_warnings.append(
                            f"{item['label']}: " + "; ".join(errors)
                        )

            if contract_warnings:
                self.report(
                    {'WARNING'},
                    "Capture completed, but Texture Merge v1 compatibility is false for one or more views. "
                    "See camera.json contract_error and Blender Console.",
                )
                for warning in contract_warnings:
                    print(f"[ViewTexForge] Texture Merge contract warning: {warning}")
            else:
                self.report({'INFO'}, f"Capture complete: {output_dir}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        finally:
            if specified_camera_restore and settings.specified_camera and settings.specified_camera.type == 'CAMERA':
                cam_data = settings.specified_camera.data
                cam_data.clip_start = specified_camera_restore['clip_start']
                cam_data.clip_end = specified_camera_restore['clip_end']
                if cam_data.type == 'ORTHO' and specified_camera_restore['ortho_scale'] is not None:
                    cam_data.ortho_scale = specified_camera_restore['ortho_scale']

            if created_temp_cameras:
                cleanup_temp_cameras(created_temp_cameras)
