import numpy as np
from .uv_rasterizer import normalize


def project(points, metadata):
    camera = metadata["camera"]
    matrix = np.asarray(camera["matrix_world"], np.float64)
    q = np.c_[points, np.ones(len(points))] @ np.linalg.inv(matrix).T
    clip = q @ np.asarray(camera["projection_matrix"], np.float64).T
    ndc = clip[:, :3] / clip[:, 3, None]
    width, height = metadata["render"]["resolution"]
    xy = np.column_stack(((ndc[:, 0]+1)*width/2, (1-ndc[:, 1])*height/2))
    depth_bu = -q[:, 2]
    return xy, depth_bu, normalize(matrix[:3, 2])


def pixel_footprint_m(metadata):
    """Return a conservative world-space pixel footprint for an ORTHO capture.

    The saved projection matrix is authoritative. For an orthographic matrix,
    one image pixel corresponds to 2/(resolution * projection_scale) camera
    units on each axis. We use the larger X/Y footprint so non-square pixels,
    aspect ratio and shifted captures remain conservative. Shift terms do not
    affect the scale. The result is converted to meters using the capture unit.

    A metadata ortho_scale fallback is kept for robustness if the projection
    scale is unusable, but normal v1 datasets should use the matrix path.
    """
    camera = metadata["camera"]
    width, height = metadata["render"]["resolution"]
    meters = float(metadata["meters_per_world_unit"])
    p = np.asarray(camera["projection_matrix"], np.float64)

    sx = abs(float(p[0, 0])) if p.shape == (4, 4) else 0.0
    sy = abs(float(p[1, 1])) if p.shape == (4, 4) else 0.0
    footprints = []
    if np.isfinite(sx) and sx > 0 and width > 0:
        footprints.append(2.0 / (width * sx))
    if np.isfinite(sy) and sy > 0 and height > 0:
        footprints.append(2.0 / (height * sy))

    if footprints:
        value_bu = max(footprints)
    else:
        ortho_scale = float(camera.get("ortho_scale", 0.0))
        if not np.isfinite(ortho_scale) or ortho_scale <= 0 or height <= 0:
            raise ValueError("Cannot derive AUTO depth tolerance pixel footprint")
        value_bu = ortho_scale / height

    value_m = value_bu * meters
    if not np.isfinite(value_m) or value_m <= 0:
        raise ValueError("AUTO depth tolerance pixel footprint must be positive and finite")
    return float(value_m)


def resolve_depth_tolerance(metadata, settings):
    """Resolve (sigma_m, cutoff_m, pixel_footprint_m) for one capture view."""
    if settings.depth_tolerance_mode == "MANUAL":
        return float(settings.depth_sigma_m), float(settings.depth_cutoff_m), None

    footprint = pixel_footprint_m(metadata)
    sigma = footprint * settings.depth_sigma_scale_px
    cutoff = footprint * settings.depth_cutoff_scale_px
    return float(sigma), float(cutoff), float(footprint)


def pixel_center_plane_depth(raster, metadata, xy, depth_bu):
    """Depth of the UV triangle's plane at its sampled ORTHO pixel center.

    Capture depth is stored at pixel centers, while a UV point can project
    anywhere inside that pixel. Comparing those different rays creates a
    sawtooth error on sloped surfaces. This prediction stays on the target
    face's local plane; it does not accept a foreground hit at another depth.
    """
    camera = metadata["camera"]
    if camera["camera_type"] != "ORTHO":
        raise ValueError("Pixel-center plane depth requires ORTHO capture")
    projection = np.asarray(camera["projection_matrix"], np.float64)
    if (projection.shape != (4, 4) or not np.allclose(projection[:2, 2], 0, atol=1e-8)):
        raise ValueError("Unsupported orthographic projection shear")
    width, height = metadata["render"]["resolution"]
    safe_xy = np.where(np.isfinite(xy), xy, -1)
    ix = np.floor(np.clip(safe_xy[:, 0], 0, width-1))
    iy = np.floor(np.clip(safe_xy[:, 1], 0, height-1))
    ndc_offset = np.column_stack((2*(ix+0.5-safe_xy[:, 0])/width,
                                  -2*(iy+0.5-safe_xy[:, 1])/height))
    camera_xy_offset = ndc_offset @ np.linalg.inv(projection[:2, :2]).T
    rotation = np.asarray(camera["matrix_world"], np.float64)[:3, :3]
    normal_camera = np.asarray(raster["face_normals"], np.float64) @ rotation
    denominator = normal_camera[:, 2]
    usable = np.isfinite(camera_xy_offset).all(axis=1) & (np.abs(denominator) > 1e-7)
    expected = np.full(len(depth_bu), np.nan, np.float64)
    expected[usable] = (depth_bu[usable] +
        np.einsum("ij,ij->i", normal_camera[usable, :2], camera_xy_offset[usable])
        / denominator[usable])
    return expected


def sample_weight(raster, view, settings, visibility=None, return_diagnostics=False):
    xy, depth_bu, direction = project(raster["points"], view.metadata)
    height, width = view.depth.shape
    finite = np.isfinite(xy).all(axis=1) & np.isfinite(depth_bu)
    safe_xy = np.where(np.isfinite(xy), xy, -1)
    inframe = finite & (safe_xy[:, 0] >= 0) & (safe_xy[:, 0] < width) & (safe_xy[:, 1] >= 0) & (safe_xy[:, 1] < height)
    ix = np.floor(np.clip(safe_xy[:, 0], 0, width-1)).astype(int)
    iy = np.floor(np.clip(safe_xy[:, 1], 0, height-1)).astype(int)
    raw = view.depth[iy, ix]
    camera = view.metadata["camera"]
    image_valid = (inframe & view.geometry_mask[iy, ix] & view.color_valid_mask[iy, ix]
             & np.isfinite(raw) & (raw > 0)
             & (depth_bu >= camera["clip_start"]) & (depth_bu <= camera["clip_end"]))
    # LEGACY remains byte-for-byte compatible. STRICT compares the captured
    # center depth with the target surface at that same center ray.
    if settings.visibility_mode == "STRICT":
        comparison_depth = pixel_center_plane_depth(raster, view.metadata, xy, depth_bu)
    else:
        comparison_depth = depth_bu
    delta = np.abs(raw - comparison_depth * view.metadata["meters_per_world_unit"])
    depth_sigma_m, depth_cutoff_m, _ = resolve_depth_tolerance(view.metadata, settings)
    valid = image_valid & np.isfinite(delta) & (delta < depth_cutoff_m)
    facing = np.clip(raster["normals"] @ direction, 0, 1)
    # OPAQUE_DOUBLE_SIDED_TRIANGLES describes the captured depth/occlusion
    # surface only. COLOR is strictly front-facing: backside weight is zero.
    face_gate = np.clip((raster["face_normals"] @ direction) * settings.face_gate_gain, 0, 1)
    weight = np.zeros(len(raw), np.float64)
    weight[valid] = (settings.view_priority.get(view.view_id, 1.0)
                     * facing[valid] ** settings.facing_exponent * face_gate[valid]
                     * np.exp(-(delta[valid]/depth_sigma_m)**2))
    legacy_accepted = weight > settings.min_weight_sum
    if visibility is not None:
        if visibility.shape != weight.shape or visibility.dtype != np.dtype(bool):
            raise ValueError("STRICT visibility mask must be boolean and match the UV point count")
        weight[~visibility] = 0.0
    if return_diagnostics:
        report = dict(
            image_or_clip_rejected=int((~image_valid).sum()),
            depth_rejected=int((image_valid & ~valid).sum()),
            legacy_candidates=int(legacy_accepted.sum()),
            geometry_rejected=int((legacy_accepted & ~visibility).sum()) if visibility is not None else 0,
            visible_depth_rejected=int((visibility & image_valid & ~valid).sum()) if visibility is not None else 0,
            retained_candidates=int((weight > settings.min_weight_sum).sum()),
            depth_comparison=("TARGET_PLANE_AT_CAPTURE_PIXEL_CENTER"
                              if settings.visibility_mode == "STRICT" else "UV_POINT_LEGACY"),
            plane_unavailable=int((image_valid & ~np.isfinite(delta)).sum()),
        )
        return view.color[iy, ix], weight, report
    return view.color[iy, ix], weight
