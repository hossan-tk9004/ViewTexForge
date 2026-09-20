import bpy
from mathutils import Vector

from .camera_utils import look_at
from .constants import AUTO_LIGHT_COLLECTION_NAME
from .utils import (
    force_view_layer_update,
    get_bbox_center_and_size,
    get_bbox_world_points,
    remove_if_empty_collection,
)

AUTO_LIGHT_OFFSET_RATIO = 0.05
AUTO_LIGHT_MIN_OFFSET = 0.05
AUTO_LIGHT_SIZE_PAD_RATIO = 0.0


def ensure_light_collection(scene):
    coll = bpy.data.collections.get(AUTO_LIGHT_COLLECTION_NAME)
    if coll is None:
        coll = bpy.data.collections.new(AUTO_LIGHT_COLLECTION_NAME)
        scene.collection.children.link(coll)
    return coll


def cleanup_existing_auto_lights():
    coll = bpy.data.collections.get(AUTO_LIGHT_COLLECTION_NAME)
    if coll is None:
        return

    for obj in list(coll.objects):
        light_data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if light_data and light_data.users == 0:
            bpy.data.lights.remove(light_data)

    remove_if_empty_collection(AUTO_LIGHT_COLLECTION_NAME)


class AutoLightingScope:
    """Create a temporary 5-light rig around target objects and restore state."""

    def __init__(self, context, target_objects, settings):
        self.context = context
        self.scene = context.scene
        self.target_objects = target_objects
        self.settings = settings
        self.created_lights = []
        self.light_states = []
        self.old_world = None
        self.temp_world = None

    def __enter__(self):
        cleanup_existing_auto_lights()
        self._create_auto_lights()
        self._hide_existing_lights_except_created()
        self._apply_black_world()
        force_view_layer_update(self.context)
        return self

    def __exit__(self, exc_type, exc, tb):
        self._restore_world()
        self._restore_existing_lights()
        if not getattr(self.settings, 'keep_auto_lights_debug', False):
            self._cleanup_created_lights()
        else:
            print('[ViewTexForge] Debug: keeping auto lights in scene.')
            for obj in self.created_lights:
                if obj is None or obj.name_full not in bpy.data.objects:
                    continue
                data = obj.data
                normalize = getattr(data, 'normalize', None)
                exposure = getattr(data, 'exposure', None)
                use_shadow = getattr(data, 'use_shadow', None)
                print(
                    '[ViewTexForge] AutoLight',
                    obj.name,
                    'location=', tuple(round(v, 5) for v in obj.location),
                    'rotation=', tuple(round(v, 5) for v in obj.rotation_euler),
                    'shape=', data.shape,
                    'size=', round(float(data.size), 5),
                    'power=', round(float(data.energy), 5),
                    'normalize=', normalize,
                    'exposure=', exposure,
                    'use_shadow=', use_shadow,
                    'hide_render=', obj.hide_render,
                )
        force_view_layer_update(self.context)
        return False

    def _apply_black_world(self):
        self.old_world = self.scene.world
        world = bpy.data.worlds.new("__VTF_AUTO_LIGHT_WORLD__")
        world.use_nodes = False
        world.color = (0.0, 0.0, 0.0)
        self.scene.world = world
        self.temp_world = world

    def _restore_world(self):
        self.scene.world = self.old_world
        if self.temp_world and self.temp_world.users == 0:
            bpy.data.worlds.remove(self.temp_world)
        self.temp_world = None
        self.old_world = None

    def _hide_existing_lights_except_created(self):
        created_names = {obj.name_full for obj in self.created_lights}
        for obj in self.scene.objects:
            if obj.type != 'LIGHT':
                continue
            self.light_states.append((obj, obj.hide_render, obj.hide_viewport))
            if obj.name_full not in created_names:
                obj.hide_render = True
                obj.hide_viewport = True

    def _restore_existing_lights(self):
        for obj, hide_render, hide_viewport in self.light_states:
            if obj.name_full in bpy.data.objects:
                obj.hide_render = hide_render
                obj.hide_viewport = hide_viewport
        self.light_states.clear()

    def _cleanup_created_lights(self):
        names = {obj.name_full for obj in self.created_lights if obj is not None}
        for name in list(names):
            obj = bpy.data.objects.get(name)
            if obj is None:
                continue
            light_data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if light_data and light_data.users == 0:
                bpy.data.lights.remove(light_data)
        self.created_lights.clear()
        remove_if_empty_collection(AUTO_LIGHT_COLLECTION_NAME)

    def _create_auto_lights(self):
        world_points = get_bbox_world_points(self.context, self.target_objects)
        if not world_points:
            raise RuntimeError("No valid target bounds found for auto lighting.")

        center, size, _min_v, _max_v = get_bbox_center_and_size(world_points)
        cube_size = max(size.x, size.y, size.z, 0.001)
        half_cube = cube_size * 0.5
        offset = max(cube_size * AUTO_LIGHT_OFFSET_RATIO, AUTO_LIGHT_MIN_OFFSET)
        light_size = max(cube_size * (1.0 + AUTO_LIGHT_SIZE_PAD_RATIO), 0.01)

        coll = ensure_light_collection(self.scene)

        entries = [
            ('Front', Vector((center.x, center.y - half_cube - offset, center.z)), self.settings.light_exposure_front),
            ('Back', Vector((center.x, center.y + half_cube + offset, center.z)), self.settings.light_exposure_back),
            ('Left', Vector((center.x - half_cube - offset, center.y, center.z)), self.settings.light_exposure_left),
            ('Right', Vector((center.x + half_cube + offset, center.y, center.z)), self.settings.light_exposure_right),
            ('Top', Vector((center.x, center.y, center.z + half_cube + offset)), self.settings.light_exposure_top),
        ]

        for label, location, exposure in entries:
            light_data = bpy.data.lights.new(f"ViewTexForgeLight_{label}", type='AREA')
            light_data.shape = 'SQUARE'
            light_data.size = light_size
            light_data.energy = float(self.settings.light_power)
            light_data.color = tuple(self.settings.light_color)
            if hasattr(light_data, 'normalize'):
                light_data.normalize = bool(self.settings.light_normalize)
            if hasattr(light_data, 'exposure'):
                light_data.exposure = float(exposure)
            if hasattr(light_data, 'use_shadow'):
                light_data.use_shadow = bool(self.settings.light_use_shadow)

            light_obj = bpy.data.objects.new(light_data.name, light_data)
            coll.objects.link(light_obj)
            light_obj.location = location
            look_at(light_obj, center)
            self.created_lights.append(light_obj)
