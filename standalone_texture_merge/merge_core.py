import numpy as np
import math
from .uv_rasterizer import rasterize
from .projection import sample_weight, resolve_depth_tolerance
from .uv_padding import pad
from .surface_fill import fill_small_holes


def srgb_to_linear(rgb):
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(rgb):
    return np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.maximum(rgb, 0) ** (1 / 2.4) - 0.055)


def sample_guard_px(view, settings):
    if settings.sample_guard_px >= 0:
        return settings.sample_guard_px
    geometry = view.metadata.get("generation_geometry") or {}
    scale = geometry.get("output_to_diffusion_scale")
    if (not isinstance(scale, list) or len(scale) != 2
            or any(not math.isfinite(float(v)) or float(v) <= 0 for v in scale)):
        raise ValueError(f"Auto RGB guard needs verified generation scale: {view.view_id}; "
                         "set explicit capture-pixel guard or regenerate metadata")
    guard = int(math.ceil(max(map(float, scale)) / 2))
    if guard > 8:
        raise ValueError(f"Generation scale needs guard >8px: {view.view_id}")
    return guard


def merge_iter(snapshot, views, settings, visibility_provider=None):
    """Incremental merge generator used by the Blender modal operator.

    Yields lightweight progress dictionaries before expensive phases so Blender
    can redraw between chunks. The final merge result is returned through
    StopIteration.value. The numerical merge algorithm itself is unchanged.
    """
    if settings.visibility_mode == "STRICT" and visibility_provider is None:
        raise ValueError("STRICT requires validated Blender render geometry; no legacy fallback")

    yield {"progress": 0.0, "status": "Rasterizing UV..."}
    raster = rasterize(snapshot, settings.resolution)
    yy, xx = raster["yy"], raster["xx"]
    total = np.zeros((len(yy), 3), np.float64)
    weight_sum = np.zeros(len(yy), np.float64)
    dominant = np.zeros(len(yy), np.uint32) if settings.debug_output else None
    best = np.zeros(len(yy), np.float64) if (settings.debug_output or settings.fill_mode != "OFF") else None
    candidates = np.zeros(len(yy), np.uint16) if settings.debug_output else None
    order, stats = [], []

    sorted_views = sorted(views, key=lambda v: v.view_id)
    view_count = max(1, len(sorted_views))
    for index, view in enumerate(sorted_views, 1):
        yield {
            "progress": 0.08 + 0.72 * ((index - 1) / view_count),
            "status": f"Processing {view.view_id} ({index}/{view_count})...",
        }
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
        if settings.surface_sample_mode == "LOCAL_NEAREST":
            guard = sample_guard_px(view, settings)
            surface_ok, surface_report, sample_x, sample_y = visibility_provider.same_surface_at_pixel(
                raster, view, weight > 0, snapshot["object_id"],
                guard_px=guard, return_sample_pixels=True)
            weight[~surface_ok] = 0.0
            color[surface_ok] = view.color[sample_y[surface_ok], sample_x[surface_ok]]
            if settings.debug_output:
                surface_report["effective_guard_capture_px"] = guard
                surface_report["generation_geometry"] = view.metadata.get("generation_geometry")
                rejection["surface_sample"] = surface_report
        if settings.blend_space == "SCENE_LINEAR":
            color = srgb_to_linear(color)
        used = weight > 0
        total[used] += color[used] * weight[used, None]
        weight_sum += weight
        if best is not None:
            stronger = weight > best
            np.maximum(best, weight, out=best)
        if settings.debug_output:
            candidates += (weight > settings.min_weight_sum).astype(np.uint16)
            dominant[stronger] = index
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
    filled = np.zeros((height, width), bool)
    fill_report = None

    if settings.fill_mode == "SMALL_HOLES":
        yield {"progress": 0.84, "status": "Filling small holes..."}
        max_weight = np.zeros((height, width), np.float32)
        max_weight[yy, xx] = best
        rgb, filled, fill_report = fill_small_holes(
            snapshot, raster, rgb, direct, max_weight, settings)

    yield {"progress": 0.92, "status": "Padding texture..."}
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
        unobserved = (raster["owner"] >= 0) & ~direct & ~filled
        result.update(direct_coverage=direct, padding_area=padding, weight_sum=weight_image,
                      dominant_view=dominant_image, candidate_count=candidate_image,
                      confidence_max=confidence_image, unobserved=unobserved, filled_area=filled,
                      report=dict(object_id=snapshot["object_id"], view_index={str(i): v for i, v in enumerate(order, 1)},
                                  occupied_texels=len(yy), direct_texels=int(direct.sum()),
                                  filled_texels=int(filled.sum()),
                                  unresolved_texels=int(unobserved.sum()),
                                  unobserved_texels=int(unobserved.sum()), padding_texels=int(padding.sum()),
                                  views=stats, geometry_source="EVALUATED_RENDER",
                                  visibility_mode=settings.visibility_mode,
                                  surface_sample_mode=settings.surface_sample_mode,
                                  sample_guard_px=settings.sample_guard_px,
                                  fill_mode=settings.fill_mode,
                                  fill_report=fill_report,
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
    yield {"progress": 1.0, "status": "Merge calculation complete"}
    return result


def _consume(generator):
    while True:
        try:
            next(generator)
        except StopIteration as stop:
            return stop.value


def merge(snapshot, views, settings, visibility_provider=None):
    return _consume(merge_iter(snapshot, views, settings, visibility_provider=visibility_provider))
