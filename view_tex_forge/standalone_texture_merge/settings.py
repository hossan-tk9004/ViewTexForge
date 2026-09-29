from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    resolution: tuple = (2048, 2048)
    debug_output: bool = False
    blend_space: str = "SRGB_ENCODED"
    facing_exponent: float = 4.0
    face_gate_gain: float = 12.0

    # Depth tolerance can be derived from the capture pixel footprint or set
    # explicitly in meters. AUTO is the recommended/default mode for ORTHO v1.
    depth_tolerance_mode: str = "AUTO"  # "AUTO" | "MANUAL"
    depth_sigma_scale_px: float = 0.65
    depth_cutoff_scale_px: float = 1.70
    depth_sigma_m: float = 0.0012
    depth_cutoff_m: float = 0.003

    # Phase 1 occlusion handling: reduce color contribution close to the
    # geometry-mask silhouette/boundary. This is a soft penalty, not a reject.
    mask_boundary_penalty_enabled: bool = True
    mask_edge_start_px: float = 0.5
    mask_edge_full_px: float = 3.0
    mask_edge_gamma: float = 1.0

    min_weight_sum: float = 0.00001
    view_priority: dict = field(default_factory=dict)
    padding_radius: int = 16
    png_bit_depth: int = 8

    def __post_init__(self):
        # Settings domain checks, not Capture Contract validation.
        if len(self.resolution) != 2 or any(type(v) is not int or v <= 0 for v in self.resolution):
            raise ValueError("resolution must contain two positive integers")
        if self.blend_space not in ("SRGB_ENCODED", "SCENE_LINEAR"):
            raise ValueError("unsupported blend_space")
        if self.depth_tolerance_mode not in ("AUTO", "MANUAL"):
            raise ValueError("depth_tolerance_mode must be AUTO or MANUAL")

        import math
        for key in (
            "facing_exponent",
            "face_gate_gain",
            "depth_sigma_scale_px",
            "depth_cutoff_scale_px",
            "depth_sigma_m",
            "depth_cutoff_m",
            "mask_edge_gamma",
            "min_weight_sum",
        ):
            value = getattr(self, key)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be positive and finite")
        if not math.isfinite(self.mask_edge_start_px) or self.mask_edge_start_px < 0:
            raise ValueError("mask_edge_start_px must be nonnegative and finite")
        if not math.isfinite(self.mask_edge_full_px) or self.mask_edge_full_px <= self.mask_edge_start_px:
            raise ValueError("mask_edge_full_px must be finite and greater than mask_edge_start_px")
        if any(not math.isfinite(v) or v < 0 for v in self.view_priority.values()):
            raise ValueError("view_priority must be nonnegative and finite")
        if type(self.padding_radius) is not int or self.padding_radius < 0:
            raise ValueError("padding_radius must be a nonnegative integer")
        if self.png_bit_depth not in (8, 16):
            raise ValueError("png_bit_depth must be 8 or 16")
