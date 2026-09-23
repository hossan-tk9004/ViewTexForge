"""Only load the fields Core consumes; no digest or registration validator."""
import json
from pathlib import Path
from dataclasses import dataclass
import numpy as np


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def require_file(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Required input does not exist: {path}")
    return path


@dataclass
class View:
    view_id: str
    metadata: dict
    color: np.ndarray
    depth: np.ndarray
    geometry_mask: np.ndarray
    color_valid_mask: np.ndarray


def load_dataset(manifest_path, image_reader):
    """Camera/color paths relative to manifest; capture passes relative to camera.json.

    Manifest entries bind aligned generated images explicitly to capture views.
    Registration metadata is intentionally not interpreted or applied.
    """
    manifest_path = require_file(manifest_path)
    manifest = read_json(manifest_path)
    views, targets = [], {}
    for entry in sorted(manifest["views"], key=lambda e: e["view_id"]):
        camera_path = require_file(manifest_path.parent / entry["camera_json_path"])
        meta = read_json(camera_path)
        if meta["camera"]["camera_type"] != "ORTHO":
            raise NotImplementedError("Texture Merge v1 supports ORTHO only")
        # Do not recompute projection from ortho_scale: saved P includes shift,
        # pixel aspect, sensor fit and the actual capture resolution.
        meta["camera"]["projection_matrix"]
        width, height = meta["render"]["resolution"]
        paths = {
            "color": require_file(manifest_path.parent / entry["color"]["path"]),
            "depth": require_file(camera_path.parent / meta["images"]["depth_raw"]["path"]),
            "geometry_mask": require_file(camera_path.parent / meta["images"]["geometry_mask"]["path"]),
        }
        if "color_valid_mask" in entry:
            paths["color_valid_mask"] = require_file(manifest_path.parent / entry["color_valid_mask"]["path"])
        arrays = {}
        for name, path in paths.items():
            array = image_reader(path)
            if array.shape[:2] != (height, width):
                raise ValueError(f"Resolution mismatch: {path}: {array.shape[:2]} != {(height, width)}")
            arrays[name] = array
        for record in (entry["color"], meta["images"]["depth_raw"], meta["images"]["geometry_mask"], entry.get("color_valid_mask", {})):
            if "resolution" in record and list(record["resolution"]) != [width, height]:
                raise ValueError(f"Declared resolution mismatch: view {entry['view_id']}")
        views.append(View(entry["view_id"], meta, arrays["color"][..., :3],
                          arrays["depth"][..., 0], arrays["geometry_mask"][..., 0] > 0.5,
                          arrays["color_valid_mask"][..., 0] > 0.5 if "color_valid_mask" in arrays
                          else np.ones((height, width), bool)))
        for target in meta["targets"]:
            targets.setdefault(target["object_id"], target)
    if not views:
        raise ValueError("Generated color manifest contains no views")
    return views, [targets[key] for key in sorted(targets)]
