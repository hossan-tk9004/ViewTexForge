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
from .merge_core import merge, merge_iter
from .output_io import save_result


def run_iter(manifest_path, output_root, settings=None, scene=None):
    """Incremental Texture Merge runner for Blender modal UI progress."""
    import bpy
    settings = settings or Settings()
    scene = scene or bpy.context.scene

    yield {"progress": 0.02, "status": "Loading generated views..."}
    views, targets = load_dataset(manifest_path, read_image)

    yield {"progress": 0.10, "status": "Collecting evaluated geometry..."}
    snapshots = collect_render_geometry(
        scene,
        targets,
        settings.fill_vertex_group if settings.fill_mode != "OFF" else "",
    )

    visibility_provider = None
    if settings.visibility_mode == "STRICT":
        yield {"progress": 0.18, "status": "Building strict visibility data..."}
        from .blender_visibility import StrictVisibility
        visibility_provider = StrictVisibility(
            snapshots, views, scene.unit_settings.scale_length, settings.visibility_chunk_size)

    outputs = []
    object_count = max(1, len(snapshots))
    for object_index, snapshot in enumerate(snapshots, 1):
        object_start = 0.22 + 0.68 * ((object_index - 1) / object_count)
        object_span = 0.68 / object_count
        runner = merge_iter(snapshot, views, settings, visibility_provider=visibility_provider)
        while True:
            try:
                event = next(runner)
                local = float(event.get("progress", 0.0))
                yield {
                    "progress": object_start + object_span * local,
                    "status": f"{snapshot['object_name']}: {event.get('status', 'Merging...')}",
                }
            except StopIteration as stop:
                result = stop.value
                break

        yield {
            "progress": object_start + object_span * 0.97,
            "status": f"Saving texture: {snapshot['object_name']}...",
        }
        path = save_result(result, output_root, snapshot, settings, scene)
        outputs.append(str(path.resolve()))
        print(f"Texture Merge: {snapshot['object_name']} -> {path}", flush=True)

    yield {"progress": 0.92, "status": "Texture merge calculation complete"}
    return outputs


def _consume(generator):
    while True:
        try:
            next(generator)
        except StopIteration as stop:
            return stop.value


def run(manifest_path, output_root, settings=None, scene=None):
    return _consume(run_iter(manifest_path, output_root, settings=settings, scene=scene))


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
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
