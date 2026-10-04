import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

_draw_handler = None


def get_render_size_from_settings(settings):
    preset = getattr(settings, 'render_size_preset', '1024')
    try:
        size = int(preset)
    except Exception:
        size = 1024
    return size, size


def tag_redraw_all_view3d():
    wm = bpy.context.window_manager
    for window in wm.windows:
        screen = window.screen
        if not screen:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _should_show_preview():
    scene = bpy.context.scene
    if scene is None or not hasattr(scene, 'viewtexforge_settings'):
        return False
    settings = scene.viewtexforge_settings
    return bool(settings.preview_mode and settings.camera_mode == 'VIEWPORT')


def _draw_preview_overlay():
    if not _should_show_preview():
        return

    context = bpy.context
    region = context.region
    area = context.area
    if region is None or area is None or area.type != 'VIEW_3D':
        return
    if region.type != 'WINDOW':
        return

    scene = context.scene
    settings = scene.viewtexforge_settings
    render_w, render_h = get_render_size_from_settings(settings)
    target_aspect = render_w / max(render_h, 1)

    region_w = float(region.width)
    region_h = float(region.height)
    if region_w <= 1 or region_h <= 1:
        return

    margin = 0.08
    max_w = region_w * (1.0 - margin * 2.0)
    max_h = region_h * (1.0 - margin * 2.0)
    region_aspect = region_w / region_h

    if region_aspect >= target_aspect:
        frame_h = max_h
        frame_w = frame_h * target_aspect
    else:
        frame_w = max_w
        frame_h = frame_w / target_aspect

    x0 = (region_w - frame_w) * 0.5
    y0 = (region_h - frame_h) * 0.5
    x1 = x0 + frame_w
    y1 = y0 + frame_h

    coords = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": coords})
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(2.0)
    shader.bind()
    shader.uniform_float('color', (0.10, 0.85, 1.0, 0.95))
    batch.draw(shader)

    tick = min(frame_w, frame_h) * 0.03
    tick_lines = [
        ((x0, y0), (x0 + tick, y0)), ((x0, y0), (x0, y0 + tick)),
        ((x1, y0), (x1 - tick, y0)), ((x1, y0), (x1, y0 + tick)),
        ((x1, y1), (x1 - tick, y1)), ((x1, y1), (x1, y1 - tick)),
        ((x0, y1), (x0 + tick, y1)), ((x0, y1), (x0, y1 - tick)),
    ]
    tick_coords = [p for line in tick_lines for p in line]
    tick_batch = batch_for_shader(shader, 'LINES', {"pos": tick_coords})
    shader.uniform_float('color', (1.0, 1.0, 1.0, 0.95))
    tick_batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')

    label = f"ViewTexForge Preview  {render_w} x {render_h}"
    font_id = 0
    blf.position(font_id, x0 + 8, y1 + 8, 0)
    try:
        blf.size(font_id, 13)
    except TypeError:
        blf.size(font_id, 13, 72)
    blf.color(font_id, 0.10, 0.85, 1.0, 1.0)
    blf.draw(font_id, label)


def ensure_preview_handler():
    global _draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _draw_preview_overlay, (), 'WINDOW', 'POST_PIXEL'
        )


def remove_preview_handler():
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None


def sync_preview_handler(scene=None):
    if _should_show_preview():
        ensure_preview_handler()
    else:
        remove_preview_handler()
    tag_redraw_all_view3d()


def preview_settings_update(self, context):
    sync_preview_handler(context.scene if context else None)
