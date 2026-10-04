"""Small-hole interpolation over UV pixels that are locally mesh connected.

Only original direct samples are sources. UV proximity alone never connects
different islands or triangles lacking a shared mesh edge.
"""
from collections import deque
import heapq
import numpy as np


def _face_neighbors(triangles):
    neighbors = [set() for _ in triangles]
    edges = {}
    for face, tri in enumerate(triangles):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((int(tri[a]), int(tri[b]))))
            for other in edges.get(edge, ()):
                neighbors[face].add(other)
                neighbors[other].add(face)
            edges.setdefault(edge, []).append(face)
    return neighbors


def fill_small_holes(snapshot, raster, rgb, direct, max_weight, settings):
    height, width = direct.shape
    owner = raster["owner"]
    island = raster["islands"]
    occupied = owner >= 0
    unknown = occupied & ~direct
    filled = np.zeros((height, width), bool)
    allowed_faces = np.asarray(snapshot.get("fill_face_allowed",
                               [True]*len(snapshot["triangles"])), bool)
    if len(allowed_faces) != len(snapshot["triangles"]):
        raise ValueError("Fill face group does not match evaluated render triangles")
    safe_owner = np.maximum(owner, 0)
    allowed = occupied & allowed_faces[safe_owner]
    vertices = np.asarray(snapshot["vertices_local"], np.float64)
    matrix = np.asarray(snapshot["matrix_world"], np.float64)
    world = vertices @ matrix[:3, :3].T + matrix[:3, 3]
    max_path = float(np.linalg.norm(np.ptp(world, axis=0))) * settings.fill_max_surface_fraction
    if max_path <= 0:
        raise ValueError("Cannot fill a zero-size target mesh")
    points = np.zeros((height*width, 3), np.float32)
    points[raster["yy"]*width+raster["xx"]] = raster["points"]
    owner_flat = owner.ravel()
    island_flat = island.ravel()
    allowed_flat = allowed.ravel()
    unknown_flat = unknown.ravel()
    direct_flat = direct.ravel()
    weight_flat = max_weight.ravel()
    color_flat = rgb.reshape(-1, 3)
    visited = np.zeros(height*width, bool)
    face_neighbors = _face_neighbors(snapshot["triangles"])
    max_area = settings.fill_max_hole_texels
    report = dict(initial_unresolved=int(unknown.sum()),
                  semantic_excluded=int((unknown & ~allowed).sum()),
                  oversized_holes=0, oversized_texels=0,
                  no_reliable_boundary_texels=0, color_conflict_texels=0,
                  distance_rejected_texels=0, filled_texels=0,
                  max_surface_distance_world=max_path,
                  source_weight_threshold=settings.fill_min_confidence,
                  max_source_color_range=settings.fill_max_color_range,
                  semantic_source=("VERTEX_GROUP:"+settings.fill_vertex_group
                                   if settings.fill_vertex_group else "MESH_EDGE_AND_UV_ISLAND"))

    def neighbors(index):
        y, x = divmod(index, width)
        for nxt in ((index-1,) if x else ()) + ((index+1,) if x+1 < width else ()) + \
                   ((index-width,) if y else ()) + ((index+width,) if y+1 < height else ()):
            if not allowed_flat[nxt] or island_flat[nxt] != island_flat[index]:
                continue
            a, b = int(owner_flat[index]), int(owner_flat[nxt])
            if a != b and b not in face_neighbors[a]:
                continue
            distance = float(np.linalg.norm(points[index]-points[nxt]))
            if np.isfinite(distance) and distance <= max_path:
                yield nxt, distance

    for initial in np.flatnonzero(unknown_flat & allowed_flat):
        if visited[initial]:
            continue
        visited[initial] = True
        queue = deque([int(initial)])
        component = []
        source = set()
        area = 0
        while queue:
            index = queue.popleft()
            area += 1
            if area <= max_area:
                component.append(index)
            for nxt, _ in neighbors(index):
                if unknown_flat[nxt]:
                    if not visited[nxt]:
                        visited[nxt] = True
                        queue.append(nxt)
                elif area <= max_area and direct_flat[nxt] and weight_flat[nxt] >= settings.fill_min_confidence:
                    source.add(nxt)
        if area > max_area:
            report["oversized_holes"] += 1
            report["oversized_texels"] += area
            continue
        if len(source) < 2:
            report["no_reliable_boundary_texels"] += area
            continue
        source = sorted(source)
        colors = color_flat[source]
        if float(np.max(np.ptp(colors, axis=0))) > settings.fill_max_color_range:
            report["color_conflict_texels"] += area
            continue
        component_set = set(component)
        total = {index: np.zeros(3, np.float64) for index in component}
        weights = {index: 0.0 for index in component}
        counts = {index: 0 for index in component}
        for start in source:
            heap = [(0.0, start)]
            best = {start: 0.0}
            while heap:
                distance, index = heapq.heappop(heap)
                if distance != best[index] or distance > max_path:
                    continue
                if index in component_set:
                    strength = 1.0/max(distance, 1e-8)
                    total[index] += color_flat[start]*strength
                    weights[index] += strength
                    counts[index] += 1
                for nxt, step in neighbors(index):
                    if nxt not in component_set:
                        continue
                    new_distance = distance + step
                    if new_distance <= max_path and new_distance < best.get(nxt, float('inf')):
                        best[nxt] = new_distance
                        heapq.heappush(heap, (new_distance, nxt))
        for index in component:
            if counts[index] < 2:
                report["distance_rejected_texels"] += 1
                continue
            color_flat[index] = total[index]/weights[index]
            filled.ravel()[index] = True
            report["filled_texels"] += 1
    return rgb, filled, report
