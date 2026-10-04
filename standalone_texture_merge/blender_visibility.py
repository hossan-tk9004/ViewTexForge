"""Blender-only first-surface visibility for the capture target set.

The merge core receives this as an injected predicate; importing the NumPy
modules does not require bpy/mathutils. A single BVH is reused for all views.
"""
import math
import heapq
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .projection import project, pixel_footprint_m

try:
    from ..geometry_digest import build_geometry_digest
except ImportError:  # standalone_texture_merge imported as a top-level package
    from geometry_digest import build_geometry_digest


def _capture_target_records(view):
    meta = view.metadata
    capture = meta.get("capture") or {}
    if (capture.get("geometry_source") != "EVALUATED_RENDER"
            or capture.get("geometry_camera_independent") is not True
            or capture.get("surface_policy") != "OPAQUE_DOUBLE_SIDED_TRIANGLES"
            or capture.get("occlusion_scope") != "TARGET_SET_ONLY"):
        raise ValueError(f"STRICT needs matching opaque target-set render geometry: {view.view_id}")
    records = meta.get("targets") or []
    result = {record.get("object_id"): record for record in records}
    if not result or None in result or len(result) != len(records):
        raise ValueError(f"STRICT target IDs are missing or ambiguous: {view.view_id}")
    return result


class StrictVisibility:
    def __init__(self, snapshots, views, meters_per_world_unit, chunk_size=65536):
        if not snapshots or not views:
            raise ValueError("STRICT requires render snapshots and capture views")
        ids = [s["object_id"] for s in snapshots]
        if len(ids) != len(set(ids)):
            raise ValueError("STRICT render snapshot object IDs are ambiguous")
        self.chunk_size = chunk_size
        self.snapshots = {s["object_id"]: s for s in snapshots}
        meters = float(meters_per_world_unit)
        if not math.isfinite(meters) or meters <= 0:
            raise ValueError("STRICT requires a positive scene unit scale")
        capture_ids = set()
        for view in views:
            meta = view.metadata
            capture_id = meta.get("capture_id")
            if not capture_id:
                raise ValueError(f"STRICT requires capture_id: {view.view_id}")
            capture_ids.add(capture_id)
            if not math.isclose(float(meta["meters_per_world_unit"]), meters,
                                rel_tol=1e-9, abs_tol=0):
                raise ValueError(f"STRICT scene units changed since capture: {view.view_id}")
            records = _capture_target_records(view)
            if set(records) != set(self.snapshots):
                raise ValueError(f"STRICT target set differs from capture: {view.view_id}")
            for object_id, snapshot in self.snapshots.items():
                record = records[object_id]
                digest = record.get("geometry_digest") or {}
                current = build_geometry_digest(snapshot, meters)
                if digest != current or record.get("uv_layer") != snapshot["uv_layer"]:
                    raise ValueError(f"STRICT render geometry/UV differs from capture: "
                                     f"{view.view_id}/{object_id}; recapture required")
                if (record.get("vertex_count") != len(snapshot["vertices_local"])
                        or record.get("triangle_count") != len(snapshot["triangles"])):
                    raise ValueError(f"STRICT geometry counts differ: {view.view_id}/{object_id}")
            camera = meta.get("camera") or {}
            matrix = np.asarray(camera.get("matrix_world"), np.float64)
            projection = np.asarray(camera.get("projection_matrix"), np.float64)
            if (camera.get("camera_type") != "ORTHO" or matrix.shape != (4, 4)
                    or projection.shape != (4, 4) or not np.isfinite(matrix).all()
                    or not np.isfinite(projection).all()
                    or not np.allclose(projection[3], [0, 0, 0, 1], atol=1e-7)
                    or not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-7)):
                raise ValueError(f"STRICT needs finite ORTHO camera matrices: {view.view_id}")
            rotation = matrix[:3, :3]
            if (not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5)
                    or np.linalg.det(rotation) < 0):
                raise ValueError(f"STRICT camera matrix is not rigid: {view.view_id}")
            if not (0 < float(camera["clip_start"]) < float(camera["clip_end"])):
                raise ValueError(f"STRICT camera clip range is invalid: {view.view_id}")
        if len(capture_ids) != 1:
            raise ValueError("STRICT views come from different captures")

        vertices, triangles = [], []
        self.triangle_offsets = {}
        for snapshot in snapshots:
            self.triangle_offsets[snapshot["object_id"]] = len(triangles)
            local = np.asarray(snapshot["vertices_local"], np.float64).reshape(-1, 3)
            matrix = np.asarray(snapshot["matrix_world"], np.float64)
            world = local @ matrix[:3, :3].T + matrix[:3, 3]
            if not np.isfinite(world).all():
                raise ValueError("STRICT geometry has nonfinite world coordinates")
            offset = len(vertices)
            vertices.extend(world.tolist())
            triangles.extend((np.asarray(snapshot["triangles"], np.int64) + offset).tolist())
        if not triangles:
            raise ValueError("STRICT target set has no triangles")
        world = np.asarray(vertices, np.float64)
        diagonal = float(np.linalg.norm(np.ptp(world, axis=0)))
        magnitude = float(np.max(np.abs(world)))
        # Numerical allowance for Blender's float geometry/BVH. This is a world
        # coordinate tolerance, not the capture depth cutoff (1.7 pixels).
        self.hit_tolerance_world = max(diagonal * 1e-6,
                                       magnitude * np.finfo(np.float32).eps * 8,
                                       1e-8)
        self.bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
        self.triangle_vertices = triangles
        positions = world[np.asarray(triangles, np.int64)]
        normals = np.cross(positions[:, 1]-positions[:, 0], positions[:, 2]-positions[:, 0])
        normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-20)
        self.triangle_normals = normals
        self.triangle_centers = positions.mean(axis=1)
        self.neighbors = [set() for _ in triangles]
        edges = {}
        for face, tri in enumerate(triangles):
            for a, b in ((0, 1), (1, 2), (2, 0)):
                edge = tuple(sorted((tri[a], tri[b])))
                for previous in edges.get(edge, ()):
                    self.neighbors[face].add(previous)
                    self.neighbors[previous].add(face)
                edges.setdefault(edge, []).append(face)
        self.face_component = np.full(len(triangles), -1, np.int32)
        component = 0
        for root in range(len(triangles)):
            if self.face_component[root] >= 0:
                continue
            self.face_component[root] = component
            pending = [root]
            while pending:
                for neighbor in self.neighbors[pending.pop()]:
                    if self.face_component[neighbor] < 0:
                        self.face_component[neighbor] = component
                        pending.append(neighbor)
            component += 1
        self.meters_per_world_unit = meters
        self._capture_maps = {}
        self._boundary_guards = {}

    def _capture_surface_map(self, view):
        """Reconstruct the validated first surface at capture pixel centers."""
        key = id(view)
        if key in self._capture_maps:
            return self._capture_maps[key]
        height, width = view.depth.shape
        face_map = np.full((height, width), -1, np.int32)
        point_map = np.zeros((height, width, 3), np.float64)
        valid_map = np.zeros((height, width), bool)
        camera = view.metadata["camera"]
        matrix = np.asarray(camera["matrix_world"], np.float64)
        inv_projection = np.linalg.inv(np.asarray(camera["projection_matrix"], np.float64))
        direction = matrix[:3, 2]
        direction /= np.linalg.norm(direction)
        ray_direction = Vector((-direction).tolist())
        reach = float(camera["clip_end"])-float(camera["clip_start"])+self.hit_tolerance_world
        candidates = np.flatnonzero(view.geometry_mask & view.color_valid_mask)
        for start in range(0, len(candidates), self.chunk_size):
            indices = candidates[start:start+self.chunk_size]
            y, x = np.divmod(indices, width)
            clip = np.column_stack((2*(x+0.5)/width-1, 1-2*(y+0.5)/height,
                                    np.full(len(indices), -1.), np.ones(len(indices))))
            camera_points = clip @ inv_projection.T
            camera_points = camera_points[:, :3]/camera_points[:, 3, None]
            origins = camera_points @ matrix[:3, :3].T + matrix[:3, 3]
            for j, index in enumerate(indices):
                hit, _, face, _ = self.bvh.ray_cast(
                    Vector(origins[j].tolist()), ray_direction, reach)
                if hit is None:
                    continue
                face_map.ravel()[index] = face
                point_map.reshape(-1, 3)[index] = hit[:]
                raw = float(view.depth[y[j], x[j]])
                center_depth = float((matrix[:3, 3]-np.asarray(hit[:])) @ direction)
                tolerance = max(self.hit_tolerance_world*self.meters_per_world_unit*4,
                                abs(raw)*np.finfo(np.float32).eps*8)
                if not np.isfinite(raw) or raw <= 0 or abs(
                        center_depth*self.meters_per_world_unit-raw) > tolerance:
                    continue
                valid_map.ravel()[index] = True
        result = face_map, point_map, valid_map
        self._capture_maps[key] = result
        return result

    def _reachable_faces(self, source, radius, normal_cos):
        """Bounded face-centroid path, independent of subdivision count."""
        distances = {source: 0.}
        heap = [(0., source)]
        normal = self.triangle_normals[source]
        while heap:
            length, face = heapq.heappop(heap)
            if length != distances[face]:
                continue
            for other in self.neighbors[face]:
                if self.triangle_normals[other] @ normal < normal_cos:
                    continue
                next_length = length + float(np.linalg.norm(
                    self.triangle_centers[face]-self.triangle_centers[other]))
                if next_length <= radius and next_length < distances.get(other, float('inf')):
                    distances[other] = next_length
                    heapq.heappush(heap, (next_length, other))
        return distances

    def _locally_connected(self, source, target, source_point, target_point,
                           footprint, camera_axis, normal_cos, path_cache):
        if source == target:
            return True, None
        normal = self.triangle_normals[source]
        if self.triangle_normals[target] @ normal < normal_cos:
            return False, "local_discontinuity"
        max_distance = 2*footprint/max(abs(normal @ camera_axis), .25)
        if np.linalg.norm(source_point-target_point) > max_distance:
            return False, "local_discontinuity"
        if target in self.neighbors[source]:
            return True, None
        if set(self.triangle_vertices[source]).intersection(self.triangle_vertices[target]):
            # A capture pixel can straddle a mesh vertex and land on two
            # triangles separated by several edge hops around its fan.
            return True, None
        # A one-ring rule rejects continuous surfaces when many small faces
        # project into a capture pixel. A short mesh path permits those faces,
        # but cannot jump between disconnected layers or travel around a fold.
        path_radius = 8*footprint
        cache_key = (source, path_radius, normal_cos)
        if cache_key not in path_cache:
            path_cache[cache_key] = self._reachable_faces(source, path_radius, normal_cos)
        if path_cache[cache_key].get(target, float('inf')) > max_distance:
            return False, "different_surface"
        return True, None

    def _internal_boundary_guard(self, view, guard_px, normal_cos, footprint,
                                 camera_axis, path_cache):
        key = (id(view), guard_px, normal_cos)
        if key in self._boundary_guards:
            return self._boundary_guards[key]
        faces, points, valid = self._capture_surface_map(view)
        unsafe = np.zeros(valid.shape, bool)
        pair_count = 0
        reasons = {}
        height, width = valid.shape
        for dy, dx in ((0, 1), (1, 0)):
            ay = slice(0, height-dy); ax = slice(0, width-dx)
            by = slice(dy, height); bx = slice(dx, width)
            pairs = valid[ay, ax] & valid[by, bx] & (faces[ay, ax] != faces[by, bx])
            ys, xs = np.where(pairs)
            for y, x in zip(ys, xs):
                okay, reason = self._locally_connected(
                    int(faces[y, x]), int(faces[y+dy, x+dx]),
                    points[y, x], points[y+dy, x+dx], footprint,
                    camera_axis, normal_cos, path_cache)
                if not okay:
                    first_normal = self.triangle_normals[int(faces[y, x])]
                    second_normal = self.triangle_normals[int(faces[y+dy, x+dx])]
                    displacement = points[y+dy, x+dx]-points[y, x]
                    first_face = int(faces[y, x])
                    second_face = int(faces[y+dy, x+dx])
                    # Continuity across a coarse triangle edge can differ by
                    # nearly half a projected pixel. Disconnected layers get
                    # only a numerical seam allowance, never that allowance.
                    same_component = (self.face_component[first_face]
                                      == self.face_component[second_face])
                    plane_epsilon = max(4*self.hit_tolerance_world,
                                        (.5 if same_component else .02)*footprint)
                    # Imported meshes can duplicate vertex IDs along a
                    # perfectly continuous sheet. Guard classification can
                    # recognize that narrow geometric seam, while candidate
                    # RGB sampling still requires the mesh-path test above.
                    if (first_normal @ second_normal >= (.9 if same_component else .995)
                            and abs(displacement @ first_normal) <= plane_epsilon
                            and abs(displacement @ second_normal) <= plane_epsilon):
                        okay = True
                if not okay:
                    first = float(view.depth[y, x])
                    second = float(view.depth[y+dy, x+dx])
                    # The harmful transfer is usually foreground RGB onto
                    # the receding surface. Seed that side of a real depth
                    # break, retaining foreground detail such as lashes.
                    if abs(first-second) <= .25*footprint*self.meters_per_world_unit:
                        unsafe[y, x] = True
                        unsafe[y+dy, x+dx] = True
                    elif first > second:
                        unsafe[y, x] = True
                    else:
                        unsafe[y+dy, x+dx] = True
                    pair_count += 1
                    reasons[reason] = reasons.get(reason, 0)+1
        # Spread only along the seeded local surface. A plain binary dilation
        # crosses back over the boundary and erases the safe foreground too.
        guarded = unsafe.copy()
        propagation_cache = {}
        for dy in range(-guard_px, guard_px+1):
            for dx in range(-guard_px, guard_px+1):
                if dy == dx == 0:
                    continue
                sy = slice(max(0, -dy), min(height, height-dy))
                sx = slice(max(0, -dx), min(width, width-dx))
                ty = slice(max(0, dy), min(height, height+dy))
                tx = slice(max(0, dx), min(width, width+dx))
                selected = unsafe[sy, sx] & valid[ty, tx] & ~guarded[ty, tx]
                source_y, source_x = np.where(selected)
                source_y += sy.start; source_x += sx.start
                for y, x in zip(source_y, source_x):
                    target_y, target_x = y+dy, x+dx
                    okay, _ = self._locally_connected(
                        int(faces[y, x]), int(faces[target_y, target_x]),
                        points[y, x], points[target_y, target_x],
                        footprint*max(1., guard_px/2), camera_axis,
                        normal_cos, propagation_cache)
                    if okay:
                        guarded[target_y, target_x] = True
        self._boundary_guards[key] = (guarded, pair_count)
        self._boundary_guard_reasons = getattr(self, '_boundary_guard_reasons', {})
        self._boundary_guard_reasons[key] = reasons
        return guarded, pair_count

    def visible(self, points, view):
        count = len(points)
        result = np.zeros(count, bool)
        camera = view.metadata["camera"]
        near, far = float(camera["clip_start"]), float(camera["clip_end"])
        direction = np.asarray(camera["matrix_world"], np.float64)[:3, 2]
        direction /= np.linalg.norm(direction)
        ray_direction = Vector((-direction).tolist())
        height, width = view.depth.shape
        epsilon = self.hit_tolerance_world
        for start in range(0, count, self.chunk_size):
            end = min(start + self.chunk_size, count)
            block = points[start:end]
            xy, depth, _ = project(block, view.metadata)
            eligible = (np.isfinite(xy).all(axis=1) & np.isfinite(depth)
                        & (xy[:, 0] >= 0) & (xy[:, 0] < width)
                        & (xy[:, 1] >= 0) & (xy[:, 1] < height)
                        & (depth >= near) & (depth <= far))
            for local_index in np.flatnonzero(eligible):
                point = block[local_index]
                distance = float(depth[local_index])
                # ORTHO ray through the exact UV surface point, from the camera
                # plane. The nearest hit must coincide with that point. Polygon
                # indices are intentionally ignored at shared edges.
                origin = Vector((point + direction * distance).tolist())
                hit, _, _, _ = self.bvh.ray_cast(origin, ray_direction, distance + epsilon)
                if hit is not None and (Vector(point.tolist()) - hit).length <= epsilon:
                    result[start + local_index] = True
        return result

    def same_surface_at_pixel(self, raster, view, candidate, object_id, normal_cos=0.5,
                              guard_px=0, return_sample_pixels=False):
        """Check the actual nearest RGB pixel's center hit against the UV face.

        Uses the same validated capture BVH. No interpolated RGB taps are used.
        Nearby faces must share a short, compatible mesh path; neither object
        ID nor a globally connected component is sufficient.
        """
        if object_id not in self.triangle_offsets:
            raise ValueError(f"STRICT target is absent from captured geometry: {object_id}")
        count = len(raster["points"])
        accepted = np.zeros(count, bool)
        sample_x = np.full(count, -1, np.int32) if return_sample_pixels else None
        sample_y = np.full(count, -1, np.int32) if return_sample_pixels else None
        report = dict(eligible=int(candidate.sum()), no_center_hit=0,
                      depth_mismatch=0, different_surface=0,
                      local_discontinuity=0, boundary_guard=0,
                      silhouette_guard=0, internal_boundary_guard=0,
                      internal_boundary_pairs=0, guard_resampled=0,
                      accepted=0)
        if not candidate.any():
            return (accepted, report, sample_x, sample_y) if return_sample_pixels else (accepted, report)
        height, width = view.depth.shape
        xy, _, direction = project(raster["points"], view.metadata)
        ix = np.floor(np.clip(xy[:, 0], 0, width-1)).astype(np.int32)
        iy = np.floor(np.clip(xy[:, 1], 0, height-1)).astype(np.int32)
        selected = np.flatnonzero(candidate)
        hit_face, hit_points, center_valid = self._capture_surface_map(view)
        own_faces = self.triangle_offsets[object_id] + raster["owner"][raster["yy"][selected], raster["xx"][selected]]
        footprint_world = pixel_footprint_m(view.metadata)/self.meters_per_world_unit
        path_cache = {}
        guard_mask = None
        internal_guard = None
        if guard_px:
            mask = view.geometry_mask & view.color_valid_mask
            guard_mask = mask.copy()
            for shift in range(1, guard_px+1):
                guard_mask[shift:] &= mask[:-shift]
                guard_mask[:-shift] &= mask[shift:]
                guard_mask[:, shift:] &= mask[:, :-shift]
                guard_mask[:, :-shift] &= mask[:, shift:]
            guard_mask[:guard_px] = False
            guard_mask[-guard_px:] = False
            guard_mask[:, :guard_px] = False
            guard_mask[:, -guard_px:] = False
            internal_guard, report["internal_boundary_pairs"] = self._internal_boundary_guard(
                view, guard_px, normal_cos, footprint_world, direction, path_cache)
        safe_mask = ((guard_mask & ~internal_guard & center_valid)
                     if guard_px else center_valid)
        offsets = []
        if guard_px and return_sample_pixels:
            reach = min(guard_px+2, 10)
            offsets = sorted(((dx*dx+dy*dy, dx, dy)
                              for dy in range(-reach, reach+1)
                              for dx in range(-reach, reach+1)
                              if dx or dy), key=lambda item: item[0])
        for j, point_index in enumerate(selected):
            y, x = iy[point_index], ix[point_index]
            face = int(hit_face[y, x])
            if face < 0:
                report["no_center_hit"] += 1
                continue
            if not center_valid[y, x]:
                report["depth_mismatch"] += 1
                continue
            own = int(own_faces[j])
            okay, reason = self._locally_connected(
                own, face, raster["points"][point_index], hit_points[y, x],
                footprint_world, direction, normal_cos, path_cache)
            if not okay:
                report[reason] += 1
                continue
            if not safe_mask[y, x]:
                if guard_mask is not None and not guard_mask[y, x]:
                    report["silhouette_guard"] += 1
                if internal_guard is not None and internal_guard[y, x]:
                    report["internal_boundary_guard"] += 1
                found = False
                for _, dx, dy in offsets:
                    nx, ny = x+dx, y+dy
                    if not (0 <= nx < width and 0 <= ny < height and safe_mask[ny, nx]):
                        continue
                    alternate = int(hit_face[ny, nx])
                    if alternate < 0:
                        continue
                    radius = max(abs(dx), abs(dy))
                    alternate_ok, _ = self._locally_connected(
                        own, alternate, raster["points"][point_index],
                        hit_points[ny, nx], footprint_world*max(1, radius),
                        direction, normal_cos, path_cache)
                    if alternate_ok:
                        x, y = nx, ny
                        found = True
                        report["guard_resampled"] += 1
                        break
                if not found:
                    report["boundary_guard"] += 1
                    continue
            accepted[point_index] = True
            if return_sample_pixels:
                sample_x[point_index], sample_y[point_index] = x, y
        report["accepted"] = int(accepted.sum())
        return (accepted, report, sample_x, sample_y) if return_sample_pixels else (accepted, report)
