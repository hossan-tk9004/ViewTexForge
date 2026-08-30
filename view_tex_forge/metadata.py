import json
from .utils import matrix_to_list


def write_camera_json(output_path, scene, cam_obj, depth_near, depth_far, target_objects, settings, label):
    data = {
        "format_version": 1,
        "view_id": label,
        "camera_name": cam_obj.name,
        "camera_type": cam_obj.data.type,
        "matrix_world": matrix_to_list(cam_obj.matrix_world),
        "location": [float(v) for v in cam_obj.location],
        "rotation_euler": [float(v) for v in cam_obj.rotation_euler],
        "rotation_mode": cam_obj.rotation_mode,
        "lens_mm": float(cam_obj.data.lens),
        "sensor_width": float(cam_obj.data.sensor_width),
        "sensor_height": float(cam_obj.data.sensor_height),
        "sensor_fit": cam_obj.data.sensor_fit,
        "shift_x": float(cam_obj.data.shift_x),
        "shift_y": float(cam_obj.data.shift_y),
        "clip_start": float(cam_obj.data.clip_start),
        "clip_end": float(cam_obj.data.clip_end),
        "ortho_scale": float(cam_obj.data.ortho_scale) if cam_obj.data.type == 'ORTHO' else None,
        "render_resolution_x": int(scene.render.resolution_x),
        "render_resolution_y": int(scene.render.resolution_y),
        "render_resolution_percentage": int(scene.render.resolution_percentage),
        "final_resolution_x": int(scene.render.resolution_x * scene.render.resolution_percentage / 100),
        "final_resolution_y": int(scene.render.resolution_y * scene.render.resolution_percentage / 100),
        "pixel_aspect_x": float(scene.render.pixel_aspect_x),
        "pixel_aspect_y": float(scene.render.pixel_aspect_y),
        "frame_current": int(scene.frame_current),
        "scene_name": scene.name,
        "target_mode": settings.target_mode,
        "camera_mode": settings.camera_mode,
        "target_objects": [obj.name for obj in target_objects],
        "depth_normalize_near": float(depth_near),
        "depth_normalize_far": float(depth_far),
        "normal_encoding": "world_normal * 0.5 + 0.5",
        "depth_encoding": "near=1.0, far=0.0",
        "clay_encoding": "viewport_solid_matcap",
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
