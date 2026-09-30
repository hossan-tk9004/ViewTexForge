import numpy as np
from .uv_rasterizer import rasterize
from .projection import sample_weight, resolve_depth_tolerance
from .uv_padding import pad


def srgb_to_linear(rgb):
    return np.where(rgb <= 0.04045, rgb/12.92, ((rgb+0.055)/1.055)**2.4)


def linear_to_srgb(rgb):
    return np.where(rgb <= 0.0031308, rgb*12.92, 1.055*np.maximum(rgb, 0)**(1/2.4)-0.055)


def merge(snapshot, views, settings, visibility_provider=None):
    if settings.visibility_mode == "STRICT" and visibility_provider is None:
        raise ValueError("STRICT requires validated Blender render geometry; no legacy fallback")
    raster = rasterize(snapshot, settings.resolution)
    yy, xx = raster["yy"], raster["xx"]
    total = np.zeros((len(yy), 3), np.float64)
    weight_sum = np.zeros(len(yy), np.float64)
    dominant = np.zeros(len(yy), np.uint32) if settings.debug_output else None
    best = np.zeros(len(yy), np.float64) if settings.debug_output else None
    candidates = np.zeros(len(yy), np.uint16) if settings.debug_output else None
    order, stats = [], []
    for index, view in enumerate(sorted(views, key=lambda v: v.view_id), 1):
        order.append(view.view_id)
        if not any(t["object_id"] == snapshot["object_id"] for t in view.metadata["targets"]):
            continue
        visibility = (visibility_provider.visible(raster["points"], view)
                      if settings.visibility_mode == "STRICT" else None)
        if settings.debug_output:
            color, weight, rejection = sample_weight(
                raster, view, settings, visibility=visibility, return_diagnostics=True)
        else:
            color, weight = sample_weight(raster, view, settings, visibility=visibility)
        if settings.blend_space == "SCENE_LINEAR":
            color = srgb_to_linear(color)
        # Do not let rejected nonfinite color samples poison the accumulator.
        used = weight > 0
        total[used] += color[used] * weight[used, None]
        weight_sum += weight
        if settings.debug_output:
            candidates += (weight > settings.min_weight_sum).astype(np.uint16)
            stronger = weight > best
            dominant[stronger], best[stronger] = index, weight[stronger]
            sigma_m, cutoff_m, footprint_m = resolve_depth_tolerance(view.metadata, settings)
            stats.append(dict(
                view_id=view.view_id,
                contributing_texels=int(used.sum()),
                depth_tolerance_mode=settings.depth_tolerance_mode,
                pixel_footprint_m=footprint_m,
                depth_sigma_m=sigma_m,
                depth_cutoff_m=cutoff_m,
                rejection=rejection,
            ))
    covered = weight_sum > settings.min_weight_sum
    height, width = raster["owner"].shape
    rgb = np.zeros((height, width, 3), np.float32)
    combined = total[covered] / weight_sum[covered, None]
    if settings.blend_space == "SCENE_LINEAR":
        combined = linear_to_srgb(combined)
    rgb[yy[covered], xx[covered]] = combined
    direct = np.zeros((height, width), bool)
    direct[yy[covered], xx[covered]] = True
    rgb, padding = pad(rgb, direct, raster["owner"] >= 0, raster["islands"], settings.padding_radius)
    result = dict(basecolor=rgb)
    if settings.debug_output:
        weight_image = np.zeros((height, width), np.float32)
        weight_image[yy, xx] = weight_sum
        dominant_image = np.zeros((height, width), np.uint32)
        dominant_image[yy[covered], xx[covered]] = dominant[covered]
        candidate_image = np.zeros((height, width), np.uint16)
        candidate_image[yy, xx] = candidates
        confidence_image = np.zeros((height, width), np.float32)
        confidence_image[yy, xx] = best
        unobserved = (raster["owner"] >= 0) & ~direct
        result.update(direct_coverage=direct, padding_area=padding, weight_sum=weight_image,
                      dominant_view=dominant_image, candidate_count=candidate_image,
                      confidence_max=confidence_image, unobserved=unobserved,
                      report=dict(object_id=snapshot["object_id"], view_index={str(i): v for i, v in enumerate(order, 1)},
                                  occupied_texels=len(yy), direct_texels=int(direct.sum()),
                                  unobserved_texels=int(len(yy)-direct.sum()), padding_texels=int(padding.sum()),
                                  views=stats, geometry_source="EVALUATED_RENDER",
                                  visibility_mode=settings.visibility_mode,
                                  confidence_definition="MAX_UNNORMALIZED_VIEW_WEIGHT_NOT_PROBABILITY",
                                  candidate_count_definition="VIEW_WEIGHT_GT_MIN_WEIGHT_SUM",
                                  direct_coverage_definition="WEIGHT_SUM_GT_MIN_WEIGHT_SUM",
                                  ray_hit_tolerance_world=getattr(visibility_provider, "hit_tolerance_world", None),
                                  overlap_ownership="LOWEST_LOOP_TRIANGLE_INDEX", blend_space=settings.blend_space,
                                  depth_tolerance_mode=settings.depth_tolerance_mode,
                                  depth_sigma_scale_px=settings.depth_sigma_scale_px if settings.depth_tolerance_mode == "AUTO" else None,
                                  depth_cutoff_scale_px=settings.depth_cutoff_scale_px if settings.depth_tolerance_mode == "AUTO" else None,
                                  manual_depth_sigma_m=settings.depth_sigma_m if settings.depth_tolerance_mode == "MANUAL" else None,
                                  manual_depth_cutoff_m=settings.depth_cutoff_m if settings.depth_tolerance_mode == "MANUAL" else None))
    return result
