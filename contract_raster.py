import hashlib
import math
import os
from array import array

import bpy
import numpy as np

from .contract_capture import RenderContractCollector


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _matrix_np(matrix_rows):
    return np.asarray(matrix_rows, dtype=np.float64)


def _world_vertices(snapshot):
    local = np.asarray(snapshot["vertices_local"], dtype=np.float64)
    ones = np.ones((local.shape[0], 1), dtype=np.float64)
    local_h = np.concatenate((local, ones), axis=1)
    matrix = _matrix_np(snapshot["matrix_world"])
    world_h = local_h @ matrix.T
    w = world_h[:, 3:4]
    return world_h[:, :3] / w


def _project_vertices(world, camera):
    cam_world = _matrix_np(camera["matrix_world"])
    world_to_cam = np.linalg.inv(cam_world)
    ones = np.ones((world.shape[0], 1), dtype=np.float64)
    world_h = np.concatenate((world, ones), axis=1)
    cam_h = world_h @ world_to_cam.T
    depth_bu = -cam_h[:, 2]

    projection = _matrix_np(camera["projection_matrix"])
    clip = cam_h @ projection.T
    cw = clip[:, 3]
    if np.any(np.abs(cw) < 1.0e-15):
        raise RuntimeError("projection produced zero homogeneous W")
    ndc = clip[:, :3] / cw[:, None]

    width, height = camera["resolution"]
    sx = (ndc[:, 0] + 1.0) * 0.5 * width
    sy = (1.0 - ndc[:, 1]) * 0.5 * height
    return sx, sy, depth_bu


def rasterize_contract(snapshot_bundle):
    camera = snapshot_bundle["camera"]
    if camera["camera_type"] != "ORTHO":
        raise RuntimeError("Standalone Texture Merge v1 requires an ORTHO camera")

    width, height = camera["resolution"]
    clip_start = float(camera["clip_start"])
    clip_end = float(camera["clip_end"])
    meters = float(snapshot_bundle["meters_per_world_unit"])

    depth_bu_buffer = np.full((height, width), np.inf, dtype=np.float64)
    eps = 1.0e-10

    for snapshot in snapshot_bundle["targets"]:
        world = _world_vertices(snapshot)
        sx, sy, vertex_depth_bu = _project_vertices(world, camera)
        triangles = snapshot["triangles"]

        for tri in triangles:
            i0, i1, i2 = tri
            x0, x1, x2 = sx[i0], sx[i1], sx[i2]
            y0, y1, y2 = sy[i0], sy[i1], sy[i2]
            d0, d1, d2 = vertex_depth_bu[i0], vertex_depth_bu[i1], vertex_depth_bu[i2]

            denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if not math.isfinite(float(denom)) or abs(float(denom)) <= 1.0e-15:
                continue

            xmin = max(0, int(math.ceil(min(x0, x1, x2) - 0.5)))
            xmax = min(width - 1, int(math.floor(max(x0, x1, x2) - 0.5)))
            ymin = max(0, int(math.ceil(min(y0, y1, y2) - 0.5)))
            ymax = min(height - 1, int(math.floor(max(y0, y1, y2) - 0.5)))
            if xmin > xmax or ymin > ymax:
                continue

            px = np.arange(xmin, xmax + 1, dtype=np.float64) + 0.5
            for py_index in range(ymin, ymax + 1):
                py = float(py_index) + 0.5
                w0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / denom
                w1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / denom
                w2 = 1.0 - w0 - w1
                inside = (w0 >= -eps) & (w1 >= -eps) & (w2 >= -eps)
                if not np.any(inside):
                    continue

                depth = w0 * d0 + w1 * d1 + w2 * d2
                valid = inside & np.isfinite(depth) & (depth >= clip_start) & (depth <= clip_end)
                if not np.any(valid):
                    continue

                row = depth_bu_buffer[py_index, xmin:xmax + 1]
                closer = valid & (depth < row)
                if np.any(closer):
                    row[closer] = depth[closer]

    mask = np.isfinite(depth_bu_buffer)
    depth_m = np.zeros((height, width), dtype=np.float32)
    depth_m[mask] = (depth_bu_buffer[mask] * meters).astype(np.float32)

    if not np.all(np.isfinite(depth_m)):
        raise RuntimeError("Raw CAMERA_Z contains NaN or Infinity")
    if np.any(depth_m < 0.0):
        raise RuntimeError("Raw CAMERA_Z contains negative values")
    if not np.array_equal(mask, depth_m > 0.0):
        raise RuntimeError("Geometry Mask invariant failed: Mask=255 iff Depth>0")

    return depth_m, mask


def _save_numeric_image(scene, path, values, file_format, color_depth, color_mode, exr_codec=None):
    height, width = values.shape
    image = bpy.data.images.new(
        name="__VTF_CONTRACT_IMAGE__",
        width=width,
        height=height,
        alpha=False,
        float_buffer=True,
    )

    render = scene.render
    settings = render.image_settings
    saved = {
        "file_format": settings.file_format,
        "color_depth": settings.color_depth,
        "color_mode": settings.color_mode,
        "exr_codec": getattr(settings, "exr_codec", None),
    }

    try:
        try:
            image.colorspace_settings.name = 'Non-Color'
        except Exception:
            pass

        # Blender image buffers are bottom-up; contract arrays use TOP_LEFT.
        flipped = np.flipud(values).astype(np.float32, copy=False)
        rgba = np.empty((height, width, 4), dtype=np.float32)
        rgba[..., 0] = flipped
        rgba[..., 1] = flipped
        rgba[..., 2] = flipped
        rgba[..., 3] = 1.0
        image.pixels.foreach_set(rgba.reshape(-1))

        settings.file_format = file_format
        settings.color_depth = color_depth
        settings.color_mode = color_mode
        if exr_codec is not None and hasattr(settings, "exr_codec"):
            settings.exr_codec = exr_codec
        image.save_render(path, scene=scene)
    finally:
        settings.file_format = saved["file_format"]
        settings.color_depth = saved["color_depth"]
        settings.color_mode = saved["color_mode"]
        if saved["exr_codec"] is not None and hasattr(settings, "exr_codec"):
            settings.exr_codec = saved["exr_codec"]
        bpy.data.images.remove(image)


def write_contract_images(scene, depth_m, mask, raw_depth_path, geometry_mask_path):
    os.makedirs(os.path.dirname(raw_depth_path), exist_ok=True)
    os.makedirs(os.path.dirname(geometry_mask_path), exist_ok=True)

    _save_numeric_image(
        scene,
        raw_depth_path,
        depth_m,
        file_format='OPEN_EXR',
        color_depth='32',
        color_mode='RGB',
        exr_codec='ZIP',
    )
    _save_numeric_image(
        scene,
        geometry_mask_path,
        mask.astype(np.float32),
        file_format='PNG',
        color_depth='8',
        color_mode='BW',
    )

    return {
        "depth_sha256": _sha256_file(raw_depth_path),
        "mask_sha256": _sha256_file(geometry_mask_path),
    }


def render_texture_merge_contract_pass(
    scene,
    cam_obj,
    raw_depth_path,
    geometry_mask_path,
    target_objects,
):
    """Capture RENDER geometry/camera, then generate Depth+Mask from those exact triangles."""
    if cam_obj.type != 'CAMERA' or cam_obj.data.type != 'ORTHO':
        raise RuntimeError("Standalone Texture Merge v1 requires an ORTHO camera")

    scene.camera = cam_obj
    old_compositing = scene.render.use_compositing
    collector = RenderContractCollector(scene, cam_obj, target_objects)
    try:
        scene.render.use_compositing = False
        with collector:
            bpy.ops.render.render(
                write_still=False,
                use_viewport=False,
                scene=scene.name,
            )
        snapshot_bundle = collector.require_result()
    finally:
        scene.render.use_compositing = old_compositing

    depth_m, mask = rasterize_contract(snapshot_bundle)
    checksums = write_contract_images(
        scene,
        depth_m,
        mask,
        raw_depth_path,
        geometry_mask_path,
    )

    compact_targets = []
    for target in snapshot_bundle["targets"]:
        compact_targets.append({
            "object_id": target["object_id"],
            "object_name": target["object_name"],
            "uv_layer": target["uv_layer"],
            "matrix_world": target["matrix_world"],
            "vertex_count": len(target["vertices_local"]),
            "triangle_count": len(target["triangles"]),
            "geometry_digest": target["geometry_digest"],
        })

    camera = dict(snapshot_bundle["camera"])
    camera.pop("matrix_world_mathutils", None)
    camera.pop("projection_matrix_mathutils", None)

    return {
        "depsgraph_mode": snapshot_bundle["depsgraph_mode"],
        "meters_per_world_unit": snapshot_bundle["meters_per_world_unit"],
        "targets": compact_targets,
        "camera": camera,
        "depth_raw_path": raw_depth_path,
        "geometry_mask_path": geometry_mask_path,
        "depth_sha256": checksums["depth_sha256"],
        "mask_sha256": checksums["mask_sha256"],
        "error": None,
    }
