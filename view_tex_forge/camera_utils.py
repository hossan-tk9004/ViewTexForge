import math

import bpy
from mathutils import Vector

from .constants import TEMP_VIEWPORT_CAMERA_NAME
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


def _direction_from_yaw_pitch(yaw_deg, pitch_deg):
    yaw = math.radians(float(yaw_deg))
    pitch = math.radians(float(pitch_deg))
    cos_pitch = math.cos(pitch)
    return Vector((
        math.sin(yaw) * cos_pitch,
        -math.cos(yaw) * cos_pitch,
        math.sin(pitch),
    ))


def _auto_grid_dimensions(view_count):
    """Return the intended ComfyUI tile layout for an Auto Camera view count."""
    view_count = int(view_count)
    layouts = {
        4: (2, 2),
        6: (3, 2),
        9: (3, 3),
        12: (4, 3),
        16: (4, 4),
    }
    try:
        return layouts[view_count]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported Auto Camera view count: {view_count}") from exc


def _auto_view_definitions(view_count):
    """Return deterministic Auto Camera definitions. view_0001 is always Front."""
    view_count = int(view_count)

    equator = [
        ("Front", 0.0, 0.0),
        ("FrontRight", 45.0, 0.0),
        ("Right", 90.0, 0.0),
        ("BackRight", 135.0, 0.0),
        ("Back", 180.0, 0.0),
        ("BackLeft", 225.0, 0.0),
        ("Left", 270.0, 0.0),
        ("FrontLeft", 315.0, 0.0),
    ]

    if view_count == 4:
        # Preserve the existing 4-camera behavior exactly: Front / Right / Back / Left.
        return [
            ("Front", 0.0, 0.0),
            ("Right", 90.0, 0.0),
            ("Back", 180.0, 0.0),
            ("Left", 270.0, 0.0),
        ]

    if view_count == 6:
        # Six orthogonal directions: Front / Right / Back / Left / Top / Bottom.
        return [
            ("Front", 0.0, 0.0),
            ("Right", 90.0, 0.0),
            ("Back", 180.0, 0.0),
            ("Left", 270.0, 0.0),
            ("Top", 0.0, 90.0),
            ("Bottom", 0.0, -90.0),
        ]

    if view_count == 9:
        # Legacy 9-view set restored for validation: eight horizontal views plus Top.
        return equator + [
            ("Top", 0.0, 90.0),
        ]

    if view_count == 12:
        # 4 horizontal + 4 upper diagonal + 4 lower cardinal views.
        # This layout intentionally keeps the lower ring on the cardinal axes
        # so each major direction receives direct underside coverage while the
        # upper ring supplies the diagonal coverage missing from the equator.
        return [
            # Horizontal
            ("Front", 0.0, 0.0),
            ("Right", 90.0, 0.0),
            ("Back", 180.0, 0.0),
            ("Left", 270.0, 0.0),
            # Upper diagonal
            ("UpperFrontRight", 45.0, 45.0),
            ("UpperBackRight", 135.0, 45.0),
            ("UpperBackLeft", 225.0, 45.0),
            ("UpperFrontLeft", 315.0, 45.0),
            # Lower cardinal
            ("LowerFront", 0.0, -35.0),
            ("LowerRight", 90.0, -35.0),
            ("LowerBack", 180.0, -35.0),
            ("LowerLeft", 270.0, -35.0),
        ]

    if view_count == 16:
        # Legacy 16-view set restored for validation. This matches the earlier
        # multi-view layout family while keeping the newer projected 2D BBox fit.
        return equator + [
            ("UpperFront", 0.0, 35.0),
            ("UpperRight", 90.0, 35.0),
            ("UpperBack", 180.0, 35.0),
            ("UpperLeft", 270.0, 35.0),
            ("LowerFrontRight", 45.0, -25.0),
            ("LowerBackRight", 135.0, -25.0),
            ("LowerBackLeft", 225.0, -25.0),
            ("LowerFrontLeft", 315.0, -25.0),
        ]

    raise RuntimeError(f"Unsupported Auto Camera view count: {view_count}")

def get_evaluated_geometry_world_points(context, target_objects):
    """Collect evaluated geometry vertices in world space for Auto Camera fitting.

    The function intentionally uses the evaluated dependency graph instead of
    object bounding-box corners, so oblique views are fitted to the actual
    projected target silhouette rather than the empty corners of a 3D AABB.
    """
    depsgraph = context.evaluated_depsgraph_get()
    points = []
    fallback_objects = []

    for obj in target_objects:
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = None
        try:
            mesh = obj_eval.to_mesh(
                preserve_all_data_layers=False,
                depsgraph=depsgraph,
            )
            if mesh is None or len(mesh.vertices) == 0:
                fallback_objects.append(obj)
                continue

            matrix_world = obj_eval.matrix_world.copy()
            points.extend(matrix_world @ vertex.co for vertex in mesh.vertices)
        except Exception as exc:
            print(
                f"[ViewTexForge] Auto Camera geometry fit fallback for "
                f"'{obj.name}': {exc}"
            )
            fallback_objects.append(obj)
        finally:
            if mesh is not None:
                try:
                    obj_eval.to_mesh_clear()
                except Exception:
                    pass

    # Keep Auto Camera creation robust for object types/builds that cannot be
    # converted to an evaluated mesh. Only those objects fall back to their
    # evaluated bounding-box corners.
    if fallback_objects:
        depsgraph = context.evaluated_depsgraph_get()
        for obj in fallback_objects:
            obj_eval = obj.evaluated_get(depsgraph)
            try:
                matrix_world = obj_eval.matrix_world.copy()
                bbox = [Vector(corner) for corner in obj_eval.bound_box]
            except Exception:
                matrix_world = obj.matrix_world.copy()
                bbox = [Vector(corner) for corner in obj.bound_box]
            points.extend(matrix_world @ corner for corner in bbox)

    return points


def get_projected_camera_bounds(cam_obj, world_points):
    """Return target bounds in the orthographic camera's local X/Y plane."""
    if not world_points:
        raise RuntimeError("No points available for projected camera bounds.")

    inv = cam_obj.matrix_world.inverted()
    cam_points = [inv @ point for point in world_points]
    xs = [point.x for point in cam_points]
    ys = [point.y for point in cam_points]

    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    return {
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "width": max_x - min_x,
        "height": max_y - min_y,
        "center_x": (min_x + max_x) * 0.5,
        "center_y": (min_y + max_y) * 0.5,
    }


def center_camera_on_projected_bounds(context, cam_obj, bounds):
    """Translate an orthographic camera so projected target bounds are centered."""
    local_offset = Vector((bounds["center_x"], bounds["center_y"], 0.0))
    if local_offset.length_squared <= 1.0e-20:
        return

    world_offset = cam_obj.matrix_world.to_quaternion() @ local_offset
    cam_obj.location += world_offset
    force_view_layer_update(context)


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


def fit_auto_ortho_camera(context, cam_obj, world_points, margin_multiplier):
    """Fit an Auto orthographic camera to actual projected evaluated geometry.

    The target's evaluated vertices are projected into the camera local X/Y
    plane. The camera is then translated laterally so that projected bounds are
    centered, and ortho_scale is derived from those 2D bounds plus Camera Margin.
    """
    scene = context.scene
    force_view_layer_update(context)

    # Ensure the camera is safely in front of the whole evaluated target and
    # establish valid clipping before measuring projected bounds.
    fit_camera_clipping_and_depth(scene, cam_obj, world_points)

    initial_bounds = get_projected_camera_bounds(cam_obj, world_points)
    center_camera_on_projected_bounds(context, cam_obj, initial_bounds)

    # Recompute after lateral centering. This also refreshes final clip planes
    # from the exact geometry used by the fit.
    min_depth, max_depth, _cam_points, _depths = fit_camera_clipping_and_depth(
        scene, cam_obj, world_points
    )
    bounds = get_projected_camera_bounds(cam_obj, world_points)

    aspect = max(get_render_aspect(scene), 1.0e-8)
    margin = max(1.0, float(margin_multiplier))
    required_vertical_span = max(
        bounds["height"],
        bounds["width"] / aspect,
        0.001,
    )
    cam_obj.data.ortho_scale = required_vertical_span * margin

    occupancy = required_vertical_span / max(cam_obj.data.ortho_scale, 1.0e-8)
    print(
        f"[ViewTexForge] Auto Camera fit '{cam_obj.name}': "
        f"projected={bounds['width']:.6f}x{bounds['height']:.6f}, "
        f"aspect={aspect:.6f}, ortho_scale={cam_obj.data.ortho_scale:.6f}, "
        f"margin={margin:.4f}, long-axis occupancy={occupancy * 100.0:.2f}%"
    )

    return min_depth, max_depth


def create_auto_cameras(context, target_objects):
    scene = context.scene
    settings = scene.viewtexforge_settings
    world_points = get_bbox_world_points(context, target_objects)
    if not world_points:
        raise RuntimeError("No valid target bounds found.")

    fit_world_points = get_evaluated_geometry_world_points(context, target_objects)
    if not fit_world_points:
        raise RuntimeError("No evaluated target geometry found for Auto Camera fit.")

    center, cube_size, _cube_min, _cube_max = _get_cube_bounds(world_points)
    distance = max(cube_size * 1.5, 1.0)
    view_count = int(settings.auto_camera_grid)
    grid_columns, grid_rows = _auto_grid_dimensions(view_count)
    definitions = _auto_view_definitions(view_count)

    coll = ensure_camera_collection(scene)
    cameras = []

    for index, (label, yaw_deg, pitch_deg) in enumerate(definitions, start=1):
        view_id = f"view_{index:04d}"
        direction = _direction_from_yaw_pitch(yaw_deg, pitch_deg)

        cam_data = bpy.data.cameras.new(f"ViewTexForgeCam_{view_id}_{label}")
        cam_data.type = 'ORTHO'
        cam_obj = bpy.data.objects.new(cam_data.name, cam_data)
        coll.objects.link(cam_obj)
        cam_obj.location = center + (direction * distance)
        look_at(cam_obj, center)
        force_view_layer_update(context)
        depth_near, depth_far = fit_auto_ortho_camera(
            context,
            cam_obj,
            fit_world_points,
            settings.camera_fit_margin,
        )
        cameras.append((
            view_id,
            cam_obj,
            depth_near,
            depth_far,
            {
                "view_index": index,
                "view_label": label,
                "yaw_deg": float(yaw_deg),
                "pitch_deg": float(pitch_deg),
                "view_count": view_count,
                "grid_columns": grid_columns,
                "grid_rows": grid_rows,
            },
        ))

    return cameras


def create_viewport_camera(context, target_objects):
    scene = context.scene
    _window, _screen, area, _region, space = find_view3d_context()
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
    return [(
        'view_0001',
        cam_obj,
        near,
        far,
        {
            "view_index": 1,
            "view_label": "Viewport",
            "yaw_deg": None,
            "pitch_deg": None,
            "grid_size": None,
        },
    )]


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
    return [(
        'view_0001',
        camera_obj,
        near,
        far,
        {
            "view_index": 1,
            "view_label": "Specified",
            "yaw_deg": None,
            "pitch_deg": None,
            "grid_size": None,
        },
    )], original
