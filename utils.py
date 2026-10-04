import os
import tempfile
import bpy
from mathutils import Vector
from .constants import VALID_OBJECT_TYPES, AUTO_CAMERA_COLLECTION_NAME


def force_view_layer_update(context=None):
    if context is None:
        context = bpy.context
    try:
        context.view_layer.update()
    except Exception:
        depsgraph = context.evaluated_depsgraph_get()
        depsgraph.update()


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def validate_output_directory(path_value, create=True):
    """Resolve and verify a user-selected writable output directory.

    Blender-relative // paths are only accepted when the current .blend has
    been saved, so an unset/default path can never silently resolve against
    Blender's process/add-on directory.
    """
    raw = (path_value or "").strip()
    generic_error = (
        "Output Directory is not correctly specified or cannot be accessed. "
        "Please select a valid writable folder."
    )
    if not raw:
        return False, None, generic_error
    if raw.startswith("//") and not bpy.data.is_saved:
        return False, None, generic_error

    try:
        resolved = os.path.abspath(bpy.path.abspath(raw))
    except Exception:
        return False, None, generic_error

    if not resolved or not os.path.isabs(resolved):
        return False, None, generic_error

    try:
        if os.path.exists(resolved) and not os.path.isdir(resolved):
            return False, resolved, generic_error
        if create:
            os.makedirs(resolved, exist_ok=True)
        elif not os.path.isdir(resolved):
            return False, resolved, generic_error

        # os.access alone is not reliable enough on Windows. A tiny temporary
        # file verifies that the directory is actually writable and is removed
        # immediately by the context manager.
        with tempfile.NamedTemporaryFile(prefix=".viewtexforge_write_test_", dir=resolved, delete=True):
            pass
    except Exception:
        return False, resolved, generic_error

    return True, resolved, ""


def reset_runtime_locks(settings, include_execution=False):
    """Release transient UI locks after success, failure, or cancellation."""
    if hasattr(settings, "capture_is_running"):
        settings.capture_is_running = False
    if hasattr(settings, "texture_merge_is_running"):
        settings.texture_merge_is_running = False
    if hasattr(settings, "comfyui_is_running"):
        settings.comfyui_is_running = False
    if include_execution and hasattr(settings, "execution_is_running"):
        settings.execution_is_running = False


class DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def is_renderable_object(obj):
    if obj.type not in VALID_OBJECT_TYPES:
        return False
    if obj.hide_render:
        return False
    try:
        if not obj.visible_get():
            return False
    except Exception:
        pass
    return True


def get_target_objects(context, settings):
    scene = context.scene
    if settings.target_mode == 'ALL_RENDERABLE':
        targets = [obj for obj in scene.objects if is_renderable_object(obj)]
    else:
        targets = []
        for obj in context.selected_objects:
            if obj.type in VALID_OBJECT_TYPES and not obj.hide_render:
                targets.append(obj)

    unique = []
    seen = set()
    for obj in targets:
        if obj.name_full in seen:
            continue
        seen.add(obj.name_full)
        unique.append(obj)
    return unique


def get_bbox_world_points(context, objects):
    depsgraph = context.evaluated_depsgraph_get()
    points = []
    for obj in objects:
        obj_eval = obj.evaluated_get(depsgraph)
        try:
            mat = obj_eval.matrix_world.copy()
            bbox = [Vector(corner) for corner in obj_eval.bound_box]
        except Exception:
            mat = obj.matrix_world.copy()
            bbox = [Vector(corner) for corner in obj.bound_box]
        for corner in bbox:
            points.append(mat @ corner)
    return points


def get_bbox_center_and_size(points):
    min_v = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    max_v = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    center = (min_v + max_v) * 0.5
    size = max_v - min_v
    return center, size, min_v, max_v


def get_render_aspect(scene):
    rx = scene.render.resolution_x * scene.render.pixel_aspect_x
    ry = scene.render.resolution_y * scene.render.pixel_aspect_y
    if ry == 0:
        return 1.0
    return rx / ry


def matrix_to_list(mat):
    return [[float(v) for v in row] for row in mat]


def ensure_camera_collection(scene):
    coll = bpy.data.collections.get(AUTO_CAMERA_COLLECTION_NAME)
    if coll is None:
        coll = bpy.data.collections.new(AUTO_CAMERA_COLLECTION_NAME)
        scene.collection.children.link(coll)
    return coll


def remove_if_empty_collection(name):
    coll = bpy.data.collections.get(name)
    if coll and not coll.objects and not coll.children:
        bpy.data.collections.remove(coll)


def cleanup_temp_cameras(camera_objects):
    names = {obj.name_full for obj in camera_objects if obj is not None}
    for name in list(names):
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        cam_data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if cam_data and cam_data.users == 0:
            bpy.data.cameras.remove(cam_data)
    remove_if_empty_collection(AUTO_CAMERA_COLLECTION_NAME)


class VisibilityScope:
    def __init__(self, scene, target_objects):
        self.scene = scene
        self.target_names = {obj.name_full for obj in target_objects}
        self.original_states = []

    def __enter__(self):
        for obj in self.scene.objects:
            self.original_states.append((obj, obj.hide_render, obj.hide_viewport))
            if obj.name_full not in self.target_names and obj.type in VALID_OBJECT_TYPES:
                obj.hide_render = True
                obj.hide_viewport = True
        force_view_layer_update()
        return self

    def __exit__(self, exc_type, exc, tb):
        for obj, hide_render, hide_viewport in self.original_states:
            obj.hide_render = hide_render
            obj.hide_viewport = hide_viewport
        force_view_layer_update()
        return False


class RenderSettingsScope:
    def __init__(self, scene):
        self.scene = scene
        self.saved = {}

    def __enter__(self):
        render = self.scene.render
        self.saved = {
            'filepath': render.filepath,
            'engine': render.engine,
            'film_transparent': render.film_transparent,
            'file_format': render.image_settings.file_format,
            'color_mode': render.image_settings.color_mode,
            'color_depth': render.image_settings.color_depth,
            'use_compositing': render.use_compositing,
            'camera': self.scene.camera,
            'resolution_x': render.resolution_x,
            'resolution_y': render.resolution_y,
            'resolution_percentage': render.resolution_percentage,
        }
        return self

    def __exit__(self, exc_type, exc, tb):
        render = self.scene.render
        render.filepath = self.saved['filepath']
        render.engine = self.saved['engine']
        render.film_transparent = self.saved['film_transparent']
        render.image_settings.file_format = self.saved['file_format']
        render.image_settings.color_mode = self.saved['color_mode']
        render.image_settings.color_depth = self.saved['color_depth']
        render.use_compositing = self.saved['use_compositing']
        self.scene.camera = self.saved['camera']
        render.resolution_x = self.saved['resolution_x']
        render.resolution_y = self.saved['resolution_y']
        render.resolution_percentage = self.saved['resolution_percentage']
        return False
