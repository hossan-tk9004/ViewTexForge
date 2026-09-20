import math
import uuid

import bpy

from .geometry_digest import build_geometry_digest

OBJECT_ID_PROP = "viewtexforge_object_id"


def meters_per_world_unit(scene):
    try:
        value = float(scene.unit_settings.scale_length)
    except Exception:
        value = 1.0
    if not math.isfinite(value) or value <= 0.0:
        raise RuntimeError("meters_per_world_unit must be a positive finite value")
    return value


def ensure_object_id(obj):
    value = obj.get(OBJECT_ID_PROP)
    if isinstance(value, str) and value:
        return value
    value = str(uuid.uuid4())
    try:
        obj[OBJECT_ID_PROP] = value
    except Exception as exc:
        raise RuntimeError(
            f"Could not persist ViewTexForge object_id on '{obj.name}': {exc}"
        )
    return value


def _matrix_list(matrix):
    result = []
    for row in matrix:
        values = []
        for value in row:
            value = float(value)
            if not math.isfinite(value):
                raise RuntimeError("matrix contains NaN or Infinity")
            if value == 0.0:
                value = 0.0
            values.append(value)
        result.append(values)
    return result


def _render_uv_layer(mesh):
    layers = getattr(mesh, "uv_layers", None)
    if not layers or len(layers) == 0:
        return None
    for layer in layers:
        try:
            if layer.active_render:
                return layer
        except Exception:
            pass
    return layers.active or layers[0]


def _uv_value(layer, loop_index):
    try:
        uv = layer.uv[loop_index].vector
        return (float(uv[0]), float(uv[1]))
    except Exception:
        uv = layer.data[loop_index].uv
        return (float(uv[0]), float(uv[1]))


def _capture_target(target_obj, depsgraph, meters):
    object_id = ensure_object_id(target_obj)
    obj_eval = target_obj.evaluated_get(depsgraph)
    matrix_world = obj_eval.matrix_world.copy()

    mesh = None
    try:
        mesh = obj_eval.to_mesh(
            preserve_all_data_layers=True,
            depsgraph=depsgraph,
        )
        if mesh is None:
            raise RuntimeError("evaluated target could not be converted to a mesh")
        mesh.calc_loop_triangles()
        uv_layer = _render_uv_layer(mesh)
        if uv_layer is None:
            raise RuntimeError("no render UV layer on evaluated target")
        if len(mesh.vertices) == 0 or len(mesh.loop_triangles) == 0:
            raise RuntimeError("evaluated target has no renderable triangles")

        vertices = [
            (float(v.co.x), float(v.co.y), float(v.co.z))
            for v in mesh.vertices
        ]
        triangles = [tuple(int(i) for i in tri.vertices) for tri in mesh.loop_triangles]
        corner_uv = [
            tuple(_uv_value(uv_layer, li) for li in tri.loops)
            for tri in mesh.loop_triangles
        ]

        snapshot = {
            "object_id": object_id,
            "object_name": target_obj.name,
            "evaluated_object_name": obj_eval.name,
            "uv_layer": uv_layer.name,
            "vertices_local": vertices,
            "triangles": triangles,
            "corner_uv": corner_uv,
            "matrix_world": _matrix_list(matrix_world),
            "matrix_world_mathutils": matrix_world.copy(),
        }
        snapshot["geometry_digest"] = build_geometry_digest(snapshot, meters)
        return snapshot
    finally:
        if mesh is not None:
            try:
                obj_eval.to_mesh_clear()
            except Exception:
                pass


def _camera_rigid_validation(matrix_world, tolerance=1.0e-6):
    m3 = matrix_world.to_3x3()
    cols = [m3.col[i].copy() for i in range(3)]
    lengths = [c.length for c in cols]
    dots = [
        abs(cols[0].dot(cols[1])),
        abs(cols[0].dot(cols[2])),
        abs(cols[1].dot(cols[2])),
    ]
    determinant = float(m3.determinant())
    rigid = (
        all(abs(length - 1.0) <= tolerance for length in lengths)
        and all(dot <= tolerance for dot in dots)
        and determinant > 0.0
        and abs(determinant - 1.0) <= tolerance * 4.0
    )
    return rigid, {
        "axis_lengths": [float(v) for v in lengths],
        "axis_dot_abs": [float(v) for v in dots],
        "determinant": determinant,
    }


def _capture_camera(scene, camera_obj, depsgraph):
    cam_eval = camera_obj.evaluated_get(depsgraph)
    if cam_eval.type != 'CAMERA':
        raise RuntimeError("evaluated capture camera is not a Camera object")

    percentage = max(float(scene.render.resolution_percentage), 0.0) / 100.0
    width = max(1, int(round(scene.render.resolution_x * percentage)))
    height = max(1, int(round(scene.render.resolution_y * percentage)))

    matrix_world = cam_eval.matrix_world.copy()
    projection = cam_eval.calc_matrix_camera(
        depsgraph,
        x=width,
        y=height,
        scale_x=float(scene.render.pixel_aspect_x),
        scale_y=float(scene.render.pixel_aspect_y),
    )
    rigid, rigid_detail = _camera_rigid_validation(matrix_world)
    cam_data = cam_eval.data
    dof = bool(getattr(getattr(cam_data, "dof", None), "use_dof", False))

    return {
        "name": camera_obj.name,
        "camera_type": cam_data.type,
        "matrix_world": _matrix_list(matrix_world),
        "matrix_world_mathutils": matrix_world,
        "projection_matrix": _matrix_list(projection),
        "projection_matrix_mathutils": projection.copy(),
        "ortho_scale": float(cam_data.ortho_scale) if cam_data.type == 'ORTHO' else None,
        "shift": [float(cam_data.shift_x), float(cam_data.shift_y)],
        "clip_start": float(cam_data.clip_start),
        "clip_end": float(cam_data.clip_end),
        "sensor_fit": cam_data.sensor_fit,
        "dof_enabled": dof,
        "rigid_transform": rigid,
        "rigid_detail": rigid_detail,
        "resolution": [width, height],
        "pixel_aspect": [float(scene.render.pixel_aspect_x), float(scene.render.pixel_aspect_y)],
    }


class RenderContractCollector:
    """Snapshot targets and camera from the actual RENDER dependency graph."""

    def __init__(self, scene, camera_obj, target_objects):
        self.scene = scene
        self.camera_obj = camera_obj
        self.target_objects = list(target_objects)
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
            meters = meters_per_world_unit(scene)
            targets = [
                _capture_target(obj, depsgraph, meters)
                for obj in self.target_objects
            ]
            camera = _capture_camera(scene, self.camera_obj, depsgraph)
            self.result = {
                "depsgraph_mode": "RENDER",
                "meters_per_world_unit": meters,
                "targets": targets,
                "camera": camera,
            }
        except Exception as exc:
            self.error = str(exc)
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

    def __exit__(self, exc_type, exc, tb):
        for handler_list, handler in (
            (bpy.app.handlers.depsgraph_update_post, self._depsgraph_handler),
            (bpy.app.handlers.frame_change_post, self._frame_handler),
        ):
            try:
                handler_list.remove(handler)
            except ValueError:
                pass
        return False

    def require_result(self):
        if self.result is not None:
            return self.result
        detail = f" Last error: {self.error}" if self.error else ""
        raise RuntimeError(
            "ViewTexForge could not capture EVALUATED_RENDER contract data "
            "from a RENDER dependency graph." + detail
        )
