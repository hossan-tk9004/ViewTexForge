import os
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
            'use_nodes': self.scene.use_nodes,
            'camera': self.scene.camera,
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
        self.scene.use_nodes = self.saved['use_nodes']
        self.scene.camera = self.saved['camera']
        return False
