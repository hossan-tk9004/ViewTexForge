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

    min_weight_sum: float = 0.00001
    view_priority: dict = field(default_factory=dict)
    padding_radius: int = 16
    png_bit_depth: int = 8
    visibility_mode: str = "LEGACY"  # "LEGACY" | "STRICT"
    visibility_chunk_size: int = 65536
    surface_sample_mode: str = "OFF"  # OFF | LOCAL_NEAREST
    sample_guard_px: int = -1  # -1 derives a conservative capture-pixel guard from provenance
    fill_mode: str = "OFF"  # OFF | SMALL_HOLES
    fill_vertex_group: str = ""
    fill_max_hole_texels: int = 8
    fill_max_surface_fraction: float = 0.002
    fill_min_confidence: float = 0.05
    fill_max_color_range: float = 0.18

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
            "min_weight_sum",
        ):
            value = getattr(self, key)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be positive and finite")
        if any(not math.isfinite(v) or v < 0 for v in self.view_priority.values()):
            raise ValueError("view_priority must be nonnegative and finite")
        if type(self.padding_radius) is not int or self.padding_radius < 0:
            raise ValueError("padding_radius must be a nonnegative integer")
        if self.png_bit_depth not in (8, 16):
            raise ValueError("png_bit_depth must be 8 or 16")
        if self.visibility_mode not in ("LEGACY", "STRICT"):
            raise ValueError("visibility_mode must be LEGACY or STRICT")
        if type(self.visibility_chunk_size) is not int or self.visibility_chunk_size <= 0:
            raise ValueError("visibility_chunk_size must be a positive integer")
        if self.surface_sample_mode not in ("OFF", "LOCAL_NEAREST"):
            raise ValueError("surface_sample_mode must be OFF or LOCAL_NEAREST")
        if self.fill_mode not in ("OFF", "SMALL_HOLES"):
            raise ValueError("fill_mode must be OFF or SMALL_HOLES")
        if (self.surface_sample_mode != "OFF" or self.fill_mode != "OFF") and self.visibility_mode != "STRICT":
            raise ValueError("Stage 2 surface sampling and fill require STRICT visibility")
        if type(self.sample_guard_px) is not int or not -1 <= self.sample_guard_px <= 8:
            raise ValueError("sample_guard_px must be an integer from -1 (auto) to 8")
        if type(self.fill_max_hole_texels) is not int or not 1 <= self.fill_max_hole_texels <= 64:
            raise ValueError("fill_max_hole_texels must be an integer from 1 to 64")
        if not isinstance(self.fill_vertex_group, str):
            raise ValueError("fill_vertex_group must be a string")
        if not math.isfinite(self.fill_max_surface_fraction) or not 0 < self.fill_max_surface_fraction <= 0.1:
            raise ValueError("fill_max_surface_fraction must be in (0, 0.1]")
        if not math.isfinite(self.fill_min_confidence) or not 0 < self.fill_min_confidence <= 1:
            raise ValueError("fill_min_confidence must be in (0, 1]")
        if not math.isfinite(self.fill_max_color_range) or not 0 < self.fill_max_color_range <= 1:
            raise ValueError("fill_max_color_range must be in (0, 1]")
