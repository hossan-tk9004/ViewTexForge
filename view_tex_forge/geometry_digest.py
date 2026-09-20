import hashlib
import math
import struct
import unicodedata

SERIALIZATION = "VTFGEOM1_LE_F64_U64"
HASH_ALGORITHM = "SHA256"
MAGIC = b"VTFGEOM1"


def _finite_f64(value, label):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} contains NaN or Infinity")
    if value == 0.0:
        value = 0.0  # normalize -0.0 to +0.0
    return value


def _pack_f64(value, label):
    return struct.pack("<d", _finite_f64(value, label))


def _pack_u32(value, label):
    value = int(value)
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError(f"{label} is outside uint32 range")
    return struct.pack("<I", value)


def _pack_u64(value, label):
    value = int(value)
    if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"{label} is outside uint64 range")
    return struct.pack("<Q", value)


def serialize_vtfgeom1(snapshot, meters_per_world_unit):
    """Serialize one evaluated object exactly as VTFGEOM1_LE_F64_U64."""
    uv_name = unicodedata.normalize("NFC", snapshot["uv_layer"])
    uv_bytes = uv_name.encode("utf-8")
    vertices = snapshot["vertices_local"]
    triangles = snapshot["triangles"]
    corner_uv = snapshot["corner_uv"]
    matrix_world = snapshot["matrix_world"]

    if len(corner_uv) != len(triangles):
        raise ValueError("corner UV triangle count does not match triangle count")

    out = bytearray()
    out += MAGIC
    out += _pack_f64(meters_per_world_unit, "meters_per_world_unit")
    out += _pack_u32(len(uv_bytes), "uv name byte length")
    out += uv_bytes
    out += _pack_u64(len(vertices), "vertex count")
    out += _pack_u64(len(triangles), "triangle count")

    for vi, vertex in enumerate(vertices):
        if len(vertex) != 3:
            raise ValueError(f"vertex {vi} does not have XYZ")
        for axis, value in zip("XYZ", vertex):
            out += _pack_f64(value, f"vertex[{vi}].{axis}")

    for ti, tri in enumerate(triangles):
        if len(tri) != 3:
            raise ValueError(f"triangle {ti} does not have 3 corners")
        for ci, index in enumerate(tri):
            out += _pack_u64(index, f"triangle[{ti}][{ci}]")

    for ti, tri_uv in enumerate(corner_uv):
        if len(tri_uv) != 3:
            raise ValueError(f"corner_uv triangle {ti} does not have 3 corners")
        for ci, uv in enumerate(tri_uv):
            if len(uv) != 2:
                raise ValueError(f"corner_uv[{ti}][{ci}] does not have UV")
            out += _pack_f64(uv[0], f"corner_uv[{ti}][{ci}].U")
            out += _pack_f64(uv[1], f"corner_uv[{ti}][{ci}].V")

    if len(matrix_world) != 4 or any(len(row) != 4 for row in matrix_world):
        raise ValueError("matrix_world is not 4x4")
    for row in range(4):
        for col in range(4):
            out += _pack_f64(matrix_world[row][col], f"matrix_world[{row}][{col}]")

    return bytes(out)


def build_geometry_digest(snapshot, meters_per_world_unit):
    payload = serialize_vtfgeom1(snapshot, meters_per_world_unit)
    return {
        "algorithm": HASH_ALGORITHM,
        "serialization": SERIALIZATION,
        "value": hashlib.sha256(payload).hexdigest(),
    }
