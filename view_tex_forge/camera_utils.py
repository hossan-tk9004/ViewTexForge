import bpy
from mathutils import Vector
from .constants import CAPTURE_MARGIN, TEMP_VIEWPORT_CAMERA_NAME
from .utils import (
    ensure_camera_collection,
    force_view_layer_update,
    get_bbox_center_and_size,
    get_bbox_world_points,
    get_render_aspect,
)


def look_at(cam_obj, target):
    direction = (target - cam_obj.location)
    if direction.length == 0:
        return
    quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = quat.to_euler()


def find_view3d_context():
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        space = area.spaces.active
                        return window, screen, area, region, space
    return None, None, None, None, None


def fit_camera_clipping_and_depth(scene, cam_obj, world_points):
    force_view_layer_update()
    inv = cam_obj.matrix_world.inverted()
    cam_points = [inv @ p for p in world_points]
    depths = [-p.z for p in cam_points]

    if not depths:
        raise RuntimeError("No points available for camera fit.")

    min_depth = min(depths)
    max_depth = max(depths)

    if max_depth <= 0:
        raise RuntimeError(f"Camera '{cam_obj.name}' does not face the target objects.")

    if min_depth <= 0:
        backward = cam_obj.matrix_world.to_quaternion() @ Vector((0.0, 0.0, 1.0))
        cam_obj.location += backward * (abs(min_depth) + 0.5)
        force_view_layer_update()
        inv = cam_obj.matrix_world.inverted()
        cam_points = [inv @ p for p in world_points]
        depths = [-p.z for p in cam_points]
        min_depth = min(depths)
        max_depth = max(depths)
        if min_depth <= 0:
            raise RuntimeError(f"Failed to place camera '{cam_obj.name}' in front of the target.")

    margin = max((max_depth - min_depth) * 0.1, 0.05)
    cam_obj.data.clip_start = max(0.001, min_depth - margin)
    cam_obj.data.clip_end = max(cam_obj.data.clip_start + 0.1, max_depth + margin)

    return min_depth, max_depth, cam_points, depths


def fit_ortho_camera_to_points(scene, cam_obj, world_points):
    force_view_layer_update()
    min_depth, max_depth, cam_points, depths = fit_camera_clipping_and_depth(scene, cam_obj, world_points)
    xs = [p.x for p in cam_points]
    ys = [p.y for p in cam_points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)

    aspect = get_render_aspect(scene)
    ortho_scale = max(width, height * aspect) * CAPTURE_MARGIN
    if ortho_scale <= 0:
        ortho_scale = 1.0
    cam_obj.data.ortho_scale = ortho_scale
    return min_depth, max_depth


def create_auto_cameras(context, target_objects):
    scene = context.scene
    world_points = get_bbox_world_points(context, target_objects)
    if not world_points:
        raise RuntimeError("No valid target bounds found.")

    center, size, _, _ = get_bbox_center_and_size(world_points)
    radius = max(size.length * 0.5, 1.0)
    distance = radius * 2.5

    coll = ensure_camera_collection(scene)
    cameras = []
    entries = [
        ('Front', Vector((0.0, -1.0, 0.0))),
        ('Back', Vector((0.0, 1.0, 0.0))),
        ('Left', Vector((-1.0, 0.0, 0.0))),
        ('Right', Vector((1.0, 0.0, 0.0))),
    ]

    for label, direction in entries:
        cam_data = bpy.data.cameras.new(f"ViewTexForgeCam_{label}")
        cam_data.type = 'ORTHO'
        cam_obj = bpy.data.objects.new(cam_data.name, cam_data)
        coll.objects.link(cam_obj)
        cam_obj.location = center + (direction * distance)
        look_at(cam_obj, center)
        force_view_layer_update(context)
        depth_near, depth_far = fit_ortho_camera_to_points(scene, cam_obj, world_points)
        cameras.append((label, cam_obj, depth_near, depth_far))

    return cameras


def create_viewport_camera(context, target_objects):
    scene = context.scene
    window, screen, area, region, space = find_view3d_context()
    if area is None or space is None:
        raise RuntimeError("A visible 3D Viewport is required for Viewport Camera mode.")

    region_3d = space.region_3d
    coll = ensure_camera_collection(scene)

    cam_data = bpy.data.cameras.new(TEMP_VIEWPORT_CAMERA_NAME)
    cam_obj = bpy.data.objects.new(TEMP_VIEWPORT_CAMERA_NAME, cam_data)
    coll.objects.link(cam_obj)
    cam_obj.matrix_world = region_3d.view_matrix.inverted()

    if region_3d.view_perspective == 'ORTHO':
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = max(region_3d.view_distance * 2.0, 1.0)
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = getattr(space, 'lens', 50.0)

    force_view_layer_update(context)

    world_points = get_bbox_world_points(context, target_objects)
    near, far, _, _ = fit_camera_clipping_and_depth(scene, cam_obj, world_points)
    if cam_data.type == 'ORTHO':
        fit_ortho_camera_to_points(scene, cam_obj, world_points)

    return [('Viewport', cam_obj, near, far)]


def prepare_specified_camera(context, camera_obj, target_objects):
    if camera_obj is None or camera_obj.type != 'CAMERA':
        raise RuntimeError("Please assign a valid camera object.")

    scene = context.scene
    world_points = get_bbox_world_points(context, target_objects)

    original = {
        'clip_start': camera_obj.data.clip_start,
        'clip_end': camera_obj.data.clip_end,
        'ortho_scale': camera_obj.data.ortho_scale if camera_obj.data.type == 'ORTHO' else None,
    }

    near, far, _, _ = fit_camera_clipping_and_depth(scene, camera_obj, world_points)
    if camera_obj.data.type == 'ORTHO':
        fit_ortho_camera_to_points(scene, camera_obj, world_points)

    return [('Specified', camera_obj, near, far)], original
