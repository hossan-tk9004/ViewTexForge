import numpy as np


def normalize(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-20)


def fragments(tri, width, height):
    """Pixel centers, inclusive epsilon; owner selection resolves shared edges."""
    lo = np.maximum(np.ceil(tri.min(axis=0) - 0.5).astype(int), (0, 0))
    hi = np.minimum(np.floor(tri.max(axis=0) - 0.5).astype(int), (width-1, height-1))
    if np.any(lo > hi):
        return None
    a, b, c = tri
    den = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
    if abs(den) < 1e-12:
        return None
    yy, xx = np.mgrid[lo[1]:hi[1]+1, lo[0]:hi[0]+1]
    x, y = xx+0.5, yy+0.5
    u = ((b[1]-c[1])*(x-c[0]) + (c[0]-b[0])*(y-c[1]))/den
    v = ((c[1]-a[1])*(x-c[0]) + (a[0]-c[0])*(y-c[1]))/den
    inside = (u >= -1e-7) & (v >= -1e-7) & (u+v <= 1+1e-7)
    return yy[inside], xx[inside], np.stack((u[inside], v[inside], 1-u[inside]-v[inside]), axis=1)


def uv_islands(triangles, uv):
    """Shared mesh edge + identical endpoint UVs; ID is lowest triangle index."""
    parent = list(range(len(triangles)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    edges = {}
    for ti, triangle in enumerate(triangles):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            endpoints = sorted(((int(triangle[a]), *uv[ti, a]), (int(triangle[b]), *uv[ti, b])))
            key = tuple(endpoints)
            if key in edges:
                ra, rb = root(ti), root(edges[key])
                parent[max(ra, rb)] = min(ra, rb)
            else:
                edges[key] = ti
    return np.array([root(i) for i in range(len(triangles))], np.int32)


def rasterize(snapshot, resolution):
    width, height = resolution
    local = np.asarray(snapshot["vertices_local"], np.float64).reshape(-1, 3)
    triangles = np.asarray(snapshot["triangles"], np.int32).reshape(-1, 3)
    uv = np.asarray(snapshot["corner_uv"], np.float64).reshape(-1, 3, 2)
    matrix = np.asarray(snapshot["matrix_world"], np.float64)
    world = local @ matrix[:3, :3].T + matrix[:3, 3]
    positions = world[triangles]
    face_normals = normalize(np.cross(positions[:, 1]-positions[:, 0], positions[:, 2]-positions[:, 0]))
    # A reflected object transform reverses cross-product winding. Preserve the
    # surface orientation of the evaluated mesh under its inverse-transpose map.
    if np.linalg.det(matrix[:3, :3]) < 0:
        face_normals *= -1
    vertex_normals = np.zeros_like(world)
    for corner in range(3):
        np.add.at(vertex_normals, triangles[:, corner], face_normals)
    vertex_normals = normalize(vertex_normals)
    owner = np.full((height, width), -1, np.int32)
    barycentric = np.zeros((height, width, 3), np.float32)
    for ti, triangle in enumerate(uv * (width, -height) + (0, height)):
        frag = fragments(triangle, width, height)
        if frag is None:
            continue
        yy, xx, bary = frag
        # Fixed overlap rule: lowest evaluated loop_triangle index always wins.
        # No coverage/overlap validator or camera-dependent ownership here.
        take = owner[yy, xx] < 0
        yy, xx = yy[take], xx[take]
        owner[yy, xx] = ti
        barycentric[yy, xx] = bary[take]
    yy, xx = np.where(owner >= 0)
    ids, bary = owner[yy, xx], barycentric[yy, xx].astype(np.float64)
    points = np.einsum("ni,nij->nj", bary, positions[ids])
    smooth = normalize(np.einsum("ni,nij->nj", bary, vertex_normals[triangles[ids]]))
    islands = uv_islands(triangles, uv)
    island_image = np.full_like(owner, -1)
    island_image[yy, xx] = islands[ids]
    return dict(owner=owner, islands=island_image, yy=yy, xx=xx,
                points=points, normals=smooth, face_normals=face_normals[ids])
