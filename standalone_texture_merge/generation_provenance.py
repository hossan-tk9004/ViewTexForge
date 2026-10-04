"""Conservative tile-size provenance for the known 4/9-view workflow branch.

This describes resolution loss, not semantic registration accuracy. Unknown or
modified workflows return None; callers must not invent a scale factor.
"""
import hashlib
import json
import math
from pathlib import Path


def infer_generation_geometry(workflow, view_count, capture_resolution):
    if view_count not in (4, 9):
        return None
    columns = rows = math.isqrt(view_count)
    try:
        for node_id in ("700", "716", "719"):
            node = workflow[node_id]
            if (node["class_type"] != "ResizeImageMaskNode"
                    or node["inputs"]["resize_type.width"] != ["713", 0]
                    or node["inputs"]["resize_type.height"] != ["714", 0]):
                return None
        if (workflow["656"]["inputs"]["expression"] != "a == 6"
                or workflow["658"]["inputs"]["expression"] != "a == 12"):
            return None
        grid_width = int(workflow["713"]["inputs"]["displaytext"])
        grid_height = int(workflow["714"]["inputs"]["displaytext"])
        capture_width, capture_height = map(int, capture_resolution)
        if min(grid_width, grid_height, capture_width, capture_height) <= 0:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return dict(source="INFERRED_KNOWN_WORKFLOW_BRANCH",
                grid=[columns, rows], diffusion_grid_resolution=[grid_width, grid_height],
                effective_tile_resolution=[grid_width/columns, grid_height/rows],
                output_tile_resolution=[capture_width, capture_height],
                output_to_diffusion_scale=[capture_width*columns/grid_width,
                                           capture_height*rows/grid_height],
                accuracy="RESOLUTION_ONLY_NOT_RGB_REGISTRATION")


def read_verified_workflow(generated_manifest):
    record = generated_manifest.get("workflow") or {}
    path, digest = record.get("path"), record.get("sha256")
    if not path or not digest:
        return None
    path = Path(path)
    if not path.is_file():
        return None
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        return None
    return json.loads(data.decode("utf-8-sig"))
