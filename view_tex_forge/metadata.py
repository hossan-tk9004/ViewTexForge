import hashlib
import json
import os

import bpy

SCHEMA_VERSION = "2.0.0"
INPUT_CONTRACT = "STANDALONE_TEXTURE_MERGE_V1"
PRODUCER_VERSION = "0.5.10"
CAPTURE_MANIFEST_VERSION = "1.0.0"


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_hash_string():
    value = getattr(bpy.app, "build_hash", "")
    if isinstance(value, bytes):
        try:
            return value.decode("ascii", errors="replace")
        except Exception:
            return repr(value)
    return str(value)


def _rel_from_json(output_path, target_path):
    base_dir = os.path.dirname(output_path)
    return os.path.relpath(target_path, base_dir).replace(os.sep, "/")


def _optional_image_record(path, relative_path, encoding, color_space, fmt="PNG", bit_depth=None):
    if not path or not os.path.exists(path):
        return None
    record = {
        "path": relative_path,
        "sha256": _sha256_file(path),
        "format": fmt,
        "color_space": color_space,
        "encoding": encoding,
    }
    if bit_depth is not None:
        record["bit_depth"] = int(bit_depth)
    return record


def _final_resolution(scene):
    percentage = max(float(scene.render.resolution_percentage), 0.0) / 100.0
    return [
        max(1, int(round(scene.render.resolution_x * percentage))),
        max(1, int(round(scene.render.resolution_y * percentage))),
    ]


def _motion_blur_enabled(scene):
    return bool(getattr(scene.render, "use_motion_blur", False))


def write_camera_json(
    output_path,
    scene,
    settings,
    view_id,
    view_meta,
    capture_id,
    contract_info,
    geometry_camera_independent,
    image_paths,
    extra_contract_errors=None,
):
    errors = list(extra_contract_errors or [])

    resolution = _final_resolution(scene)
    contract_info = contract_info or {}
    camera = contract_info.get("camera")
    targets = contract_info.get("targets") or []
    meters = contract_info.get("meters_per_world_unit")
    depsgraph_mode = contract_info.get("depsgraph_mode")
    contract_error = contract_info.get("error")
    if contract_error:
        errors.append(str(contract_error))

    if depsgraph_mode != "RENDER":
        errors.append("depsgraph_mode is not RENDER")
    if not camera:
        errors.append("missing RENDER-evaluated camera snapshot")
    if not targets:
        errors.append("missing EVALUATED_RENDER targets")
    if not geometry_camera_independent:
        errors.append("geometry_camera_independent check failed across views")

    full_frame = not bool(getattr(scene.render, "use_border", False))
    if not full_frame:
        errors.append("Render Border is enabled")
    motion_blur = _motion_blur_enabled(scene)
    if motion_blur:
        errors.append("Motion Blur is enabled")

    if camera:
        if camera.get("camera_type") != "ORTHO":
            errors.append("camera is not ORTHO")
        if not camera.get("rigid_transform"):
            errors.append("camera matrix_world contains scale/shear or invalid handedness")
        if camera.get("dof_enabled"):
            errors.append("Depth of Field is enabled")
        if camera.get("resolution") != resolution:
            errors.append("RENDER camera resolution does not match final output resolution")

    clay_path = image_paths.get("clay")
    clay = _optional_image_record(
        clay_path,
        _rel_from_json(output_path, clay_path) if clay_path else None,
        encoding="CLAY_CAPTURE",
        color_space="SRGB",
        fmt="PNG",
        bit_depth=8,
    )
    if clay is None:
        errors.append("required images.clay is missing")

    depth_raw_path = image_paths.get("depth_raw")
    geometry_mask_path = image_paths.get("geometry_mask")
    if not depth_raw_path or not os.path.exists(depth_raw_path):
        errors.append("required images.depth_raw is missing")
    if not geometry_mask_path or not os.path.exists(geometry_mask_path):
        errors.append("required images.geometry_mask is missing")

    depth_raw = None
    if depth_raw_path and os.path.exists(depth_raw_path):
        depth_raw = {
            "path": _rel_from_json(output_path, depth_raw_path),
            "sha256": contract_info.get("depth_sha256") or _sha256_file(depth_raw_path),
            "resolution": resolution,
            "format": "OPEN_EXR",
            "color_space": "NON_COLOR",
            "encoding": "FLOAT32_RAW",
            "definition": "CAMERA_Z",
            "unit": "METERS",
            "channel": "R",
            "bit_depth": 32,
            "invalid_value": 0.0,
            "sampling": "PIXEL_CENTER_SINGLE",
            "generator": "EVALUATED_TRIANGLE_CAMERA_Z_V1",
        }

    geometry_mask = None
    if geometry_mask_path and os.path.exists(geometry_mask_path):
        geometry_mask = {
            "path": _rel_from_json(output_path, geometry_mask_path),
            "sha256": contract_info.get("mask_sha256") or _sha256_file(geometry_mask_path),
            "resolution": resolution,
            "format": "PNG",
            "color_space": "NON_COLOR",
            "encoding": "BINARY_GEOMETRY_MASK_0_255",
            "bit_depth": 8,
            "sampling": "PIXEL_CENTER_SINGLE",
            "generator": "EVALUATED_TRIANGLE_CAMERA_Z_V1",
        }

    target_records = []
    for target in targets:
        digest = target.get("geometry_digest") or {}
        if digest.get("serialization") != "VTFGEOM1_LE_F64_U64":
            errors.append(f"target {target.get('object_name')} has wrong geometry serialization")
        if not digest.get("value"):
            errors.append(f"target {target.get('object_name')} has no geometry digest")
        target_records.append({
            "object_id": target.get("object_id"),
            "object_name": target.get("object_name"),
            "uv_layer": target.get("uv_layer"),
            "geometry_source": "EVALUATED_RENDER",
            "capture_matrix_world": target.get("matrix_world"),
            "vertex_count": int(target.get("vertex_count", 0)),
            "triangle_count": int(target.get("triangle_count", 0)),
            "geometry_digest": {
                "algorithm": digest.get("algorithm"),
                "serialization": digest.get("serialization"),
                "value": digest.get("value"),
            },
        })

    compatible = len(errors) == 0
    camera_record = None
    if camera:
        camera_record = {
            "name": camera.get("name"),
            "camera_type": camera.get("camera_type"),
            "matrix_world": camera.get("matrix_world"),
            "ortho_scale": camera.get("ortho_scale"),
            "shift": camera.get("shift"),
            "clip_start": camera.get("clip_start"),
            "clip_end": camera.get("clip_end"),
            "projection_matrix": camera.get("projection_matrix"),
            "projection_convention": "OPENGL_NDC_NEG1_POS1",
            "sensor_fit": camera.get("sensor_fit"),
        }

    def optional_record(key, encoding, color_space, bit_depth):
        path = image_paths.get(key)
        return _optional_image_record(
            path,
            _rel_from_json(output_path, path) if path else None,
            encoding,
            color_space,
            "PNG",
            bit_depth,
        )

    data = {
        "schema_version": SCHEMA_VERSION,
        "input_contract": INPUT_CONTRACT,
        "capture_id": capture_id,
        "view_id": view_id,
        "view_index": int(view_meta.get("view_index", 1)),
        "view_label": view_meta.get("view_label"),
        "yaw_deg": view_meta.get("yaw_deg"),
        "pitch_deg": view_meta.get("pitch_deg"),
        "coordinate_system": "BLENDER_RH_Z_UP_CAMERA_NEG_Z",
        "meters_per_world_unit": meters,
        "matrix_convention": "ROW_ARRAY_COLUMN_VECTOR",
        "image_origin": "TOP_LEFT",
        "pixel_center_offset": [0.5, 0.5],
        "producer": {
            "name": "ViewTexForge",
            "version": PRODUCER_VERSION,
            "blender_version": bpy.app.version_string,
            "blender_build_hash": _build_hash_string(),
        },
        "capture": {
            "scene_name": scene.name,
            "view_layer_name": scene.view_layers[0].name,
            "render_engine": scene.render.engine,
            "frame": int(scene.frame_current),
            "subframe": float(getattr(scene, "frame_subframe", 0.0)),
            "geometry_source": "EVALUATED_RENDER",
            "depsgraph_mode": depsgraph_mode,
            "geometry_camera_independent": bool(geometry_camera_independent),
            "surface_policy": "OPAQUE_DOUBLE_SIDED_TRIANGLES",
            "occlusion_scope": "TARGET_SET_ONLY",
        },
        "camera": camera_record,
        "render": {
            "resolution": resolution,
            "pixel_aspect": [
                float(scene.render.pixel_aspect_x),
                float(scene.render.pixel_aspect_y),
            ],
            "full_frame": full_frame,
            "motion_blur": motion_blur,
            "depth_of_field": bool(camera.get("dof_enabled")) if camera else None,
        },
        "targets": target_records,
        "images": {
            "clay": clay,
            "depth_raw": depth_raw,
            "geometry_mask": geometry_mask,
            "normal_comfy": optional_record("normal", "WORLD_NORMAL_ENCODED_0_1", "NON_COLOR", 16),
            "depth_normalized_comfy": optional_record("depth", "NORMALIZED_DEPTH_NEAR1_FAR0_RGB_DUPLICATED", "NON_COLOR", 8),
            "mask_comfy": optional_record("mask", "BINARY_MASK_RGB_DUPLICATED", "NON_COLOR", 8),
        },
        "texture_merge_v1_compatible": compatible,
        "contract_error": None if compatible else errors,
        "extensions": {
            "viewtexforge": {
                "target_mode": settings.target_mode,
                "camera_mode": settings.camera_mode,
                "auto_camera_view_count": int(settings.auto_camera_grid) if settings.camera_mode == "AUTO4" else None,
                "auto_camera_grid": (
                    {4: [2, 2], 6: [3, 2], 9: [3, 3], 12: [4, 3], 16: [4, 4]}.get(int(settings.auto_camera_grid))
                    if settings.camera_mode == "AUTO4" else None
                ),
                "output_size_preset": settings.render_size_preset,
                "clay_render_mode": settings.clay_render_mode,
                "lighting_mode": settings.lighting_mode,
                "camera_fit_margin": float(settings.camera_fit_margin)
                    if settings.camera_mode == "AUTO4" else None,
                "camera_fit_method": "EVALUATED_GEOMETRY_PROJECTED_BBOX"
                    if settings.camera_mode == "AUTO4" else None,
            }
        },
    }

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4, ensure_ascii=False)

    return compatible, errors


def write_capture_manifest(
    output_path,
    scene,
    settings,
    capture_id,
    view_records,
):
    auto_view_count = int(settings.auto_camera_grid) if settings.camera_mode == "AUTO4" else None
    auto_layout = {4: (2, 2), 6: (3, 2), 9: (3, 3), 12: (4, 3), 16: (4, 4)}.get(auto_view_count)
    compatible_all = bool(view_records) and all(bool(v.get("texture_merge_v1_compatible")) for v in view_records)

    data = {
        "manifest_version": CAPTURE_MANIFEST_VERSION,
        "capture_id": capture_id,
        "producer": {
            "name": "ViewTexForge",
            "version": PRODUCER_VERSION,
        },
        "scene_name": scene.name,
        "camera_mode": settings.camera_mode,
        "view_count": len(view_records),
        "grid_size": auto_layout[0] if auto_layout else None,
        "grid_columns": auto_layout[0] if auto_layout else None,
        "grid_rows": auto_layout[1] if auto_layout else None,
        "primary_view_id": "view_0001" if view_records else None,
        "sort_rule": "view_index_ascending_zero_padded_filename",
        "file_naming": "view_XXXX",
        "folders": {
            "clay": "clay",
            "normal": "normal",
            "depth": "depth",
            "mask": "mask",
            "raw_depth": "raw_depth",
            "geometry_mask": "geometry_mask",
            "camera": "camera",
        },
        "comfyui": {
            "list_loader_sort_method": "numerical",
            "grid_size_from_view_count": "columns=ceil(sqrt(view_count)); rows=ceil(view_count/columns)",
            "recommended_input_folders": ["clay", "depth", "mask"],
        },
        "texture_merge_v1_compatible": compatible_all,
        "views": view_records,
    }

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4, ensure_ascii=False)
