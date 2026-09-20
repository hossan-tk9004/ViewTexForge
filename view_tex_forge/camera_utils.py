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
    direction = target - cam_obj.location
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


def _get_cube_bounds(world_points):
    center, size, _min_v, _max_v = get_bbox_center_and_size(world_points)
    cube_size = max(size.x, size.y, size.z, 0.001)
    half = cube_size * 0.5
    cube_min = center - Vector((half, half, half))
    cube_max = center + Vector((half, half, half))
    return center, cube_size, cube_min, cube_max


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


def fit_auto_ortho_camera(scene, cam_obj, world_points, margin_multiplier):
    """Fit an Auto4 orthographic camera to the longest-axis cube."""
    force_view_layer_update()
    min_depth, max_depth, _cam_points, _depths = fit_camera_clipping_and_depth(
        scene, cam_obj, world_points
    )

    _center, cube_size, _cube_min, _cube_max = _get_cube_bounds(world_points)
    aspect = max(get_render_aspect(scene), 1e-8)
    margin = max(1.0, float(margin_multiplier))

    # Blender's ortho_scale is the vertical span. Horizontal span is
    # ortho_scale * aspect, so portrait output needs extra vertical scale;
    # landscape/square output does not.
    aspect_fit = max(1.0, 1.0 / aspect)
    cam_obj.data.ortho_scale = max(cube_size * aspect_fit * margin, 0.001)
    return min_depth, max_depth


def create_auto_cameras(context, target_objects):
    scene = context.scene
    settings = scene.viewtexforge_settings
    world_points = get_bbox_world_points(context, target_objects)
    if not world_points:
        raise RuntimeError("No valid target bounds found.")

    center, cube_size, _cube_min, _cube_max = _get_cube_bounds(world_points)
    distance = max(cube_size * 1.5, 1.0)

    coll = ensure_camera_collection(scene)
    cameras = []
    # View order is authored here. The first entry is always the canonical
    # front/primary view. Persistent capture identity is numeric (view_####);
    # natural-language direction labels are intentionally not stored.
    directions = [
        Vector((0.0, -1.0, 0.0)),  # canonical front / view_0001
        Vector((0.0, 1.0, 0.0)),
        Vector((-1.0, 0.0, 0.0)),
        Vector((1.0, 0.0, 0.0)),
    ]

    for index, direction in enumerate(directions, start=1):
        view_id = f"view_{index:04d}"
        cam_data = bpy.data.cameras.new(f"ViewTexForgeCam_{view_id}")
        cam_data.type = 'ORTHO'
        cam_obj = bpy.data.objects.new(cam_data.name, cam_data)
        coll.objects.link(cam_obj)
        cam_obj.location = center + (direction * distance)
        look_at(cam_obj, center)
        force_view_layer_update(context)
        depth_near, depth_far = fit_auto_ortho_camera(
            scene,
            cam_obj,
            world_points,
            settings.camera_fit_margin,
        )
        cameras.append((view_id, cam_obj, depth_near, depth_far))

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
        # Preserve the user's viewport framing. Camera Margin is Auto4-only.
        cam_data.ortho_scale = max(region_3d.view_distance * 2.0, 1.0)
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = getattr(space, 'lens', 50.0)

    force_view_layer_update(context)

    world_points = get_bbox_world_points(context, target_objects)
    near, far, _, _ = fit_camera_clipping_and_depth(scene, cam_obj, world_points)
    return [('view_0001', cam_obj, near, far)]


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

    # Preserve the explicitly authored camera framing. Only clipping is adjusted.
    near, far, _, _ = fit_camera_clipping_and_depth(scene, camera_obj, world_points)
    return [('view_0001', camera_obj, near, far)], original
