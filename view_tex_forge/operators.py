import os
import bpy
from .camera_utils import create_auto_cameras, create_viewport_camera, prepare_specified_camera
from .metadata import write_camera_json
from .render_utils import render_clay_viewport, render_normal_pass, render_depth_pass, render_mask_pass
from .utils import (
    DummyContext,
    RenderSettingsScope,
    VisibilityScope,
    cleanup_temp_cameras,
    ensure_dir,
    force_view_layer_update,
    get_target_objects,
)


class VIEWTEXFORGE_OT_capture(bpy.types.Operator):
    bl_idname = "viewtexforge.capture"
    bl_label = "Capture Images"
    bl_description = "Capture clay / normal / depth / mask images"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.viewtexforge_settings
        scene = context.scene

        if not (settings.output_clay or settings.output_normal or settings.output_depth or settings.output_mask):
            self.report({'ERROR'}, "Please enable at least one output image type.")
            return {'CANCELLED'}

        output_dir = bpy.path.abspath(settings.output_dir)
        ensure_dir(output_dir)

        target_objects = get_target_objects(context, settings)
        if not target_objects:
            self.report({'ERROR'}, "No valid target objects found for the current mode.")
            return {'CANCELLED'}

        created_temp_cameras = []
        specified_camera_restore = None

        try:
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

            with context_manager:
                with RenderSettingsScope(scene):
                    size = int(settings.render_size_preset)
                    scene.render.resolution_x = size
                    scene.render.resolution_y = size
                    scene.render.resolution_percentage = 100

                    for label, cam_obj, depth_near, depth_far in camera_infos:
                        label_dir = os.path.join(output_dir, label)
                        ensure_dir(label_dir)

                        if settings.output_clay:
                            render_clay_viewport(scene, cam_obj, os.path.join(label_dir, 'clay.png'))
                        if settings.output_normal:
                            render_normal_pass(scene, cam_obj, os.path.join(label_dir, 'normal.png'))
                        if settings.output_depth:
                            render_depth_pass(scene, cam_obj, os.path.join(label_dir, 'depth.png'), depth_near, depth_far)
                        if settings.output_mask:
                            render_mask_pass(scene, cam_obj, os.path.join(label_dir, 'mask.png'))

                        write_camera_json(
                            os.path.join(label_dir, 'camera.json'),
                            scene,
                            cam_obj,
                            depth_near,
                            depth_far,
                            target_objects,
                            settings,
                            label,
                        )

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
