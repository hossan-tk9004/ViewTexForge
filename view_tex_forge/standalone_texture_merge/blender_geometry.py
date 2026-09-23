"""Adapted from ViewTexForge v0.2.1 contract_capture.py (MIT; see THIRD_PARTY).

Preserves its actual RENDER handler / evaluated_get / to_mesh acquisition path.
Differences: specified UV layer, no ID writes, no camera capture or digest build.
No VIEWPORT graph or alternate RenderEngine fallback is permitted.
"""
import bpy


def _uv_value(layer, index):
    try:
        uv = layer.uv[index].vector
    except AttributeError:
        uv = layer.data[index].uv
    return float(uv[0]), float(uv[1])


def resolve_targets(scene, targets):
    resolved = []
    for target in targets:
        matches = [obj for obj in scene.objects
                   if obj.get("viewtexforge_object_id") == target["object_id"]]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous object identifier: {target['object_id']}")
        # Name resolution permits an explicit capture name when no persisted ID exists.
        obj = matches[0] if matches else scene.objects.get(target["object_name"])
        if obj is None:
            raise RuntimeError(f"Target Object not found: {target['object_name']}")
        resolved.append((target, obj))
    return resolved


def _capture_target(target, obj, depsgraph):
    obj_eval = obj.evaluated_get(depsgraph)
    matrix = obj_eval.matrix_world.copy()
    mesh = None
    try:
        mesh = obj_eval.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        if mesh is None:
            raise RuntimeError(f"Cannot obtain evaluated mesh: {obj.name}")
        mesh.calc_loop_triangles()
        layer = mesh.uv_layers.get(target["uv_layer"])
        if layer is None:
            raise RuntimeError(f"Specified UV Layer not found: {obj.name}/{target['uv_layer']}")
        return dict(object_id=target["object_id"], object_name=obj.name,
                    uv_layer=layer.name,
                    vertices_local=[tuple(v.co) for v in mesh.vertices],
                    triangles=[tuple(t.vertices) for t in mesh.loop_triangles],
                    corner_uv=[tuple(_uv_value(layer, i) for i in t.loops) for t in mesh.loop_triangles],
                    matrix_world=[list(row) for row in matrix])
    finally:
        if mesh is not None:
            obj_eval.to_mesh_clear()


class RenderGeometryCollector:
    def __init__(self, scene, targets):
        self.scene = scene
        self.targets = targets
        self.result = None
        self.error = None
        self._capturing = False

    def _capture(self, scene, depsgraph):
        if self.result is not None or self._capturing or scene != self.scene:
            return
        if depsgraph is None or getattr(depsgraph, "mode", None) != "RENDER":
            return
        self._capturing = True
        try:
            self.result = [_capture_target(target, obj, depsgraph) for target, obj in self.targets]
        except Exception as exc:
            self.error = exc
        finally:
            self._capturing = False

    def _depsgraph_handler(self, scene, depsgraph):
        self._capture(scene, depsgraph)

    def _frame_handler(self, scene, depsgraph=None):
        self._capture(scene, depsgraph)

    def __enter__(self):
        bpy.app.handlers.depsgraph_update_post.append(self._depsgraph_handler)
        bpy.app.handlers.frame_change_post.append(self._frame_handler)
        return self

    def __exit__(self, *args):
        for handlers, handler in (
            (bpy.app.handlers.depsgraph_update_post, self._depsgraph_handler),
            (bpy.app.handlers.frame_change_post, self._frame_handler),
        ):
            if handler in handlers:
                handlers.remove(handler)

    def require_result(self):
        if self.result is None:
            raise RuntimeError("Could not acquire EVALUATED_RENDER geometry from a RENDER depsgraph. "
                               f"Last error: {self.error}") from self.error
        return self.result


def collect_render_geometry(scene, targets):
    resolved = resolve_targets(scene, targets)
    collector = RenderGeometryCollector(scene, resolved)
    compositing = scene.render.use_compositing
    try:
        scene.render.use_compositing = False
        with collector:
            bpy.ops.render.render(write_still=False, use_viewport=False, scene=scene.name)
        return collector.require_result()
    finally:
        scene.render.use_compositing = compositing
