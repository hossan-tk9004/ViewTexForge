"""Blender CLI entry point. Does not assign materials or save the input .blend."""
import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .dataset_io import load_dataset, read_json
from .settings import Settings
from .image_io import read_image
from .blender_geometry import collect_render_geometry
from .merge_core import merge
from .output_io import save_result


def run(manifest_path, output_root, settings=None, scene=None):
    import bpy
    settings = settings or Settings()
    scene = scene or bpy.context.scene
    views, targets = load_dataset(manifest_path, read_image)
    snapshots = collect_render_geometry(scene, targets)
    outputs = []
    for snapshot in snapshots:
        result = merge(snapshot, views, settings)
        path = save_result(result, output_root, snapshot, settings, scene)
        outputs.append(str(path.resolve()))
        print(f"Texture Merge: {snapshot['object_name']} -> {path}", flush=True)
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--settings")
    parser.add_argument("--scene", help="Current .blend scene; defaults to active scene")
    parser.add_argument("--debug-output", action="store_true")
    args = parser.parse_args(argv)
    config = read_json(args.settings) if args.settings else {}
    if args.debug_output:
        config["debug_output"] = True
    import bpy
    scene = bpy.data.scenes[args.scene] if args.scene else bpy.context.scene
    return run(args.manifest, args.output, Settings(**config), scene)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
