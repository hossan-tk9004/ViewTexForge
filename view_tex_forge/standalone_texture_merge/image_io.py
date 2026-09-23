"""Read raw numeric pixels through Blender; write PNG without display transforms."""
from pathlib import Path
import struct
import zlib
import numpy as np


def read_image(path):
    import bpy
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        # Generated sRGB bytes stay encoded for SRGB_ENCODED blending. EXR R is
        # raw metric data. In neither case should Blender apply an OCIO transform.
        image.colorspace_settings.name = "Non-Color"
        width, height = image.size
        pixels = np.empty(width*height*image.channels, np.float32)
        image.pixels.foreach_get(pixels)
        return np.flipud(pixels.reshape(height, width, image.channels)).copy()
    finally:
        bpy.data.images.remove(image)


def write_png(path, values, bit_depth=8, srgb=False, integer=False):
    """Lossless PNG, exact encoded RGB or integer diagnostics; no OCIO dependency."""
    array = np.asarray(values)
    channels = 1 if array.ndim == 2 else array.shape[2]
    if channels not in (1, 3):
        raise ValueError("PNG writer supports grayscale or RGB")
    if bit_depth not in (8, 16):
        raise ValueError("PNG writer supports 8 or 16 bits")
    limit = (1 << bit_depth)-1
    data = np.clip(array if integer else np.rint(np.clip(array, 0, 1)*limit), 0, limit)
    data = data.astype(np.uint8 if bit_depth == 8 else ">u2")
    height, width = array.shape[:2]
    def chunk(kind, payload):
        return struct.pack(">I", len(payload))+kind+payload+struct.pack(">I", zlib.crc32(kind+payload) & 0xffffffff)
    stream = b"".join(b"\x00"+row.tobytes() for row in data)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bit_depth, 0 if channels == 1 else 2, 0, 0, 0))
    if srgb:
        png += chunk(b"sRGB", b"\x00")
    png += chunk(b"IDAT", zlib.compress(stream)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def write_exr(path, values, scene):
    """Float32 R/G/B replicated scalar, Non-Color, lossless ZIP."""
    import bpy
    height, width = values.shape
    image = bpy.data.images.new("TextureMergeNumeric", width=width, height=height, alpha=False, float_buffer=True)
    settings = scene.render.image_settings
    saved = {name: getattr(settings, name) for name in ("file_format", "color_depth", "color_mode", "exr_codec")}
    try:
        image.colorspace_settings.name = "Non-Color"
        pixels = np.ones((height, width, 4), np.float32)
        pixels[..., :3] = np.flipud(values)[..., None]
        image.pixels.foreach_set(pixels.ravel())
        settings.file_format = "OPEN_EXR"
        settings.color_depth = "32"
        settings.color_mode = "RGB"
        settings.exr_codec = "ZIP"
        image.save_render(str(path), scene=scene)
    finally:
        for name, value in saved.items():
            setattr(settings, name, value)
        bpy.data.images.remove(image)
