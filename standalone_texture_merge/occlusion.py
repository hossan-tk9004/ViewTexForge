import numpy as np


def _erode8(mask):
    """Binary erosion with an 8-neighbour 3x3 kernel and false outside."""
    mask = np.asarray(mask, dtype=bool)
    h, w = mask.shape
    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    out = np.ones((h, w), dtype=bool)
    for dy in range(3):
        for dx in range(3):
            out &= padded[dy:dy+h, dx:dx+w]
    return out


def mask_boundary_distance_px(mask, max_distance_px):
    """Approximate distance from valid mask pixels to the nearest mask boundary.

    Only distances up to max_distance_px are needed by the merge penalty, so this
    computes a small number of 8-neighbour erosion rings instead of a full distance
    transform. Boundary-touching valid pixel centres are reported as 0.5 px, the
    next ring as 1.5 px, etc. Pixels deeper than the requested range are clamped.
    Invalid pixels remain 0.0.
    """
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("geometry mask must be 2D")
    if not np.isfinite(max_distance_px) or max_distance_px <= 0:
        raise ValueError("max_distance_px must be positive and finite")

    cap = float(max_distance_px)
    distance = np.zeros(mask.shape, dtype=np.float32)
    remaining = mask.copy()
    # Enough rings to reach/past cap when centres are 0.5, 1.5, ... px.
    rings = max(1, int(np.ceil(cap + 0.5)))
    for ring in range(rings):
        if not remaining.any():
            break
        eroded = _erode8(remaining)
        boundary = remaining & ~eroded
        distance[boundary] = min(ring + 0.5, cap)
        remaining = eroded
    distance[remaining] = cap
    return distance


def smoothstep01(t):
    t = np.clip(np.asarray(t, dtype=np.float64), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mask_boundary_confidence(mask, start_px=0.5, full_px=3.0, gamma=1.0):
    """Return [0,1] confidence that increases away from geometry-mask edges.

    Valid pixels at/below start_px receive 0, pixels at/above full_px receive 1,
    and the transition is smoothstep-shaped. Invalid pixels are always 0.
    """
    for name, value in (("start_px", start_px), ("full_px", full_px), ("gamma", gamma)):
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if start_px < 0:
        raise ValueError("start_px must be nonnegative")
    if full_px <= start_px:
        raise ValueError("full_px must be greater than start_px")
    if gamma <= 0:
        raise ValueError("gamma must be positive")

    mask = np.asarray(mask, dtype=bool)
    distance = mask_boundary_distance_px(mask, full_px)
    t = (distance - float(start_px)) / (float(full_px) - float(start_px))
    confidence = smoothstep01(t) ** float(gamma)
    confidence[~mask] = 0.0
    return confidence.astype(np.float32), distance


def view_mask_boundary_confidence(view, settings):
    """Cache mask-boundary confidence per View/settings tuple."""
    key = (float(settings.mask_edge_start_px), float(settings.mask_edge_full_px), float(settings.mask_edge_gamma))
    cached = getattr(view, "_mask_boundary_cache", None)
    if cached is not None and cached[0] == key:
        return cached[1]
    confidence, _ = mask_boundary_confidence(
        view.geometry_mask,
        start_px=settings.mask_edge_start_px,
        full_px=settings.mask_edge_full_px,
        gamma=settings.mask_edge_gamma,
    )
    view._mask_boundary_cache = (key, confidence)
    return confidence


def depth_edge_metric_m(depth, geometry_mask):
    """Local metric-depth discontinuity for valid geometry pixels.

    For each valid pixel, take the maximum absolute CAMERA_Z difference to
    valid 8-neighbour pixels. Invalid/background neighbours are ignored so the
    metric targets internal depth discontinuities rather than duplicating the
    geometry-mask boundary penalty.
    """
    depth = np.asarray(depth, dtype=np.float64)
    mask = np.asarray(geometry_mask, dtype=bool)
    if depth.ndim != 2 or mask.ndim != 2 or depth.shape != mask.shape:
        raise ValueError("depth and geometry mask must be matching 2D arrays")

    valid = mask & np.isfinite(depth) & (depth > 0)
    h, w = depth.shape
    metric = np.zeros((h, w), dtype=np.float64)

    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue

            y0 = max(0, -dy)
            y1 = min(h, h - dy)
            x0 = max(0, -dx)
            x1 = min(w, w - dx)
            ny0, ny1 = y0 + dy, y1 + dy
            nx0, nx1 = x0 + dx, x1 + dx

            center_valid = valid[y0:y1, x0:x1]
            neigh_valid = valid[ny0:ny1, nx0:nx1]
            pair = center_valid & neigh_valid
            if not pair.any():
                continue

            diff = np.abs(depth[y0:y1, x0:x1] - depth[ny0:ny1, nx0:nx1])
            target = metric[y0:y1, x0:x1]
            target[pair] = np.maximum(target[pair], diff[pair])

    metric[~valid] = 0.0
    return metric.astype(np.float32)


def depth_edge_confidence(depth, geometry_mask, pixel_footprint_m,
                          sigma_scale_px=0.5, full_scale_px=1.5, gamma=1.0):
    """Return a soft confidence that falls near internal depth discontinuities.

    sigma/full thresholds are derived from the per-view world-space pixel
    footprint so the behaviour scales with capture resolution and ortho scale.
    A Gaussian soft penalty is used below full_scale; at/above full_scale the
    confidence is clamped to zero for that view.
    """
    for name, value in (("pixel_footprint_m", pixel_footprint_m),
                        ("sigma_scale_px", sigma_scale_px),
                        ("full_scale_px", full_scale_px),
                        ("gamma", gamma)):
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be positive and finite")
    if full_scale_px <= sigma_scale_px:
        raise ValueError("full_scale_px must be greater than sigma_scale_px")

    metric = depth_edge_metric_m(depth, geometry_mask)
    sigma_m = float(pixel_footprint_m) * float(sigma_scale_px)
    full_m = float(pixel_footprint_m) * float(full_scale_px)

    confidence = np.exp(-((metric.astype(np.float64) / sigma_m) ** 2))
    confidence **= float(gamma)
    confidence[metric >= full_m] = 0.0

    valid = (np.asarray(geometry_mask, dtype=bool) & np.isfinite(depth) & (np.asarray(depth) > 0))
    confidence[~valid] = 0.0
    return confidence.astype(np.float32), metric, sigma_m, full_m


def view_depth_edge_confidence(view, settings, pixel_footprint_m):
    """Cache depth-edge confidence per View/settings/pixel-footprint tuple."""
    key = (float(pixel_footprint_m),
           float(settings.depth_edge_sigma_scale_px),
           float(settings.depth_edge_full_scale_px),
           float(settings.depth_edge_gamma))
    cached = getattr(view, "_depth_edge_cache", None)
    if cached is not None and cached[0] == key:
        return cached[1]
    confidence, _, _, _ = depth_edge_confidence(
        view.depth, view.geometry_mask, pixel_footprint_m,
        sigma_scale_px=settings.depth_edge_sigma_scale_px,
        full_scale_px=settings.depth_edge_full_scale_px,
        gamma=settings.depth_edge_gamma,
    )
    view._depth_edge_cache = (key, confidence)
    return confidence
