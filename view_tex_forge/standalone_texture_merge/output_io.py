import hashlib
import json
import re
from pathlib import Path
import numpy as np
from .image_io import write_png, write_exr


def object_directory(output_root, object_id):
    # Readable safe prefix + full digest avoids traversal, reserved Windows names
    # and case-insensitive identifier collisions without changing object identity.
    prefix = re.sub(r"[^A-Za-z0-9_-]", "_", object_id)[:48]
    digest = hashlib.sha256(object_id.encode("utf-8")).hexdigest()
    return Path(output_root) / f"object_{prefix}_{digest}"


def save_result(result, output_root, snapshot, settings, scene):
    directory = object_directory(output_root, snapshot["object_id"])
    directory.mkdir(parents=True, exist_ok=True)
    write_png(directory/"basecolor.png", result["basecolor"], settings.png_bit_depth, srgb=True)
    if settings.debug_output:
        debug = directory/"debug"
        debug.mkdir(exist_ok=True)
        for name in ("direct_coverage", "padding_area"):
            write_png(debug/f"{name}.png", result[name])
        write_exr(debug/"weight_sum.exr", result["weight_sum"], scene)
        # NPY retains arbitrary view counts exactly, unlike normalized PNG.
        np.save(debug/"dominant_view.npy", result["dominant_view"], allow_pickle=False)
        (debug/"merge_report.json").write_text(json.dumps(result["report"], indent=2), encoding="utf-8")
    return directory/"basecolor.png"
