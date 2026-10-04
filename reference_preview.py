import os

import bpy
import bpy.utils.previews

_preview_collection = None
_preview_signature = None


def _collection():
    global _preview_collection
    if _preview_collection is None:
        _preview_collection = bpy.utils.previews.new()
    return _preview_collection


def get_reference_image_icon(path):
    """Return a small preview icon id for the configured reference image."""
    global _preview_signature

    if not path:
        return 0

    try:
        resolved = bpy.path.abspath(path)
    except Exception:
        return 0

    if not resolved or not os.path.isfile(resolved):
        return 0

    try:
        signature = (os.path.normcase(os.path.abspath(resolved)), os.path.getmtime(resolved))
    except OSError:
        return 0

    previews = _collection()
    if _preview_signature != signature:
        previews.clear()
        try:
            previews.load('reference_image', resolved, 'IMAGE', force_reload=True)
        except Exception:
            _preview_signature = None
            return 0
        _preview_signature = signature

    preview = previews.get('reference_image')
    return preview.icon_id if preview is not None else 0


def clear_reference_image_preview():
    global _preview_collection, _preview_signature
    if _preview_collection is not None:
        bpy.utils.previews.remove(_preview_collection)
        _preview_collection = None
    _preview_signature = None
