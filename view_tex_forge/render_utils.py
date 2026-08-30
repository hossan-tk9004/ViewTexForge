import os
import bpy
from .constants import CLAY_VIEWPORT_COLOR, MATCAP_NAME
from .camera_utils import find_view3d_context
from .utils import ensure_dir


def get_first_matcap_name():
    prefs = bpy.context.preferences
    matcaps = [sl.name for sl in prefs.studio_lights if getattr(sl, 'type', '') == 'MATCAP']
    return matcaps[0] if matcaps else None


class TemporaryNodeSetup:
    def __init__(self, scene):
        self.scene = scene
        self.tree = scene.node_tree

    def __enter__(self):
        self.scene.use_nodes = True
        self.tree = self.scene.node_tree
        self.tree.nodes.clear()
        return self.tree

    def __exit__(self, exc_type, exc, tb):
        self.tree.nodes.clear()
        return False


def _rename_file_output(base_dir, slot_prefix, final_name):
    for fname in os.listdir(base_dir):
        if fname.startswith(slot_prefix) and fname.lower().endswith('.png'):
            src = os.path.join(base_dir, fname)
            dst = os.path.join(base_dir, final_name)
            if os.path.exists(dst):
                os.remove(dst)
            os.replace(src, dst)
            return dst
    raise RuntimeError(f"Expected output file with prefix '{slot_prefix}' was not generated in {base_dir}")


def render_clay_viewport(scene, cam_obj, output_path):
    window, screen, area, region, space = find_view3d_context()
    if area is None or region is None or space is None:
        raise RuntimeError("A 3D Viewport is required to output clay images.")

    ensure_dir(os.path.dirname(output_path))

    region_3d = space.region_3d
    shading = space.shading
    overlay = space.overlay
    render = scene.render

    saved = {
        'scene_camera': scene.camera,
        'filepath': render.filepath,
        'file_format': render.image_settings.file_format,
        'color_mode': render.image_settings.color_mode,
        'color_depth': render.image_settings.color_depth,
        'view_perspective': region_3d.view_perspective,
        'view_camera_zoom': region_3d.view_camera_zoom,
        'view_camera_offset': tuple(region_3d.view_camera_offset),
        'shading_type': shading.type,
        'shading_light': shading.light,
        'shading_color_type': shading.color_type,
        'single_color': tuple(shading.single_color),
        'studio_light': shading.studio_light,
        'show_overlays': overlay.show_overlays,
        'show_xray': shading.show_xray,
        'show_cavity': shading.show_cavity,
        'show_shadows': shading.show_shadows,
        'show_object_outline': shading.show_object_outline,
    }

    try:
        scene.camera = cam_obj
        render.filepath = output_path
        render.image_settings.file_format = 'PNG'
        render.image_settings.color_mode = 'RGB'
        render.image_settings.color_depth = '8'

        region_3d.view_perspective = 'CAMERA'
        region_3d.view_camera_zoom = 0.0
        region_3d.view_camera_offset = (0.0, 0.0)

        shading.type = 'SOLID'
        shading.light = 'MATCAP'
        shading.color_type = 'SINGLE'
        shading.single_color = CLAY_VIEWPORT_COLOR
        chosen_matcap = MATCAP_NAME or get_first_matcap_name()
        if chosen_matcap:
            shading.studio_light = chosen_matcap

        overlay.show_overlays = False
        shading.show_xray = False
        shading.show_cavity = False
        shading.show_shadows = False
        shading.show_object_outline = False

        with bpy.context.temp_override(
            window=window,
            screen=screen,
            area=area,
            region=region,
            scene=scene,
            space_data=space,
        ):
            bpy.ops.render.opengl(write_still=True, view_context=True)
    finally:
        scene.camera = saved['scene_camera']
        render.filepath = saved['filepath']
        render.image_settings.file_format = saved['file_format']
        render.image_settings.color_mode = saved['color_mode']
        render.image_settings.color_depth = saved['color_depth']
        region_3d.view_perspective = saved['view_perspective']
        region_3d.view_camera_zoom = saved['view_camera_zoom']
        region_3d.view_camera_offset = saved['view_camera_offset']
        shading.type = saved['shading_type']
        shading.light = saved['shading_light']
        shading.color_type = saved['shading_color_type']
        shading.single_color = saved['single_color']
        shading.studio_light = saved['studio_light']
        overlay.show_overlays = saved['show_overlays']
        shading.show_xray = saved['show_xray']
        shading.show_cavity = saved['show_cavity']
        shading.show_shadows = saved['show_shadows']
        shading.show_object_outline = saved['show_object_outline']


def render_normal_pass(scene, cam_obj, output_path):
    ensure_dir(os.path.dirname(output_path))
    scene.camera = cam_obj
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '16'

    view_layer = scene.view_layers[0]
    old_normal_pass = view_layer.use_pass_normal
    view_layer.use_pass_normal = True

    try:
        with TemporaryNodeSetup(scene) as nt:
            render_layers = nt.nodes.new('CompositorNodeRLayers')
            sep_xyz = nt.nodes.new('CompositorNodeSepRGBA')
            comb = nt.nodes.new('CompositorNodeCombRGBA')
            map_x = nt.nodes.new('CompositorNodeMapRange')
            map_y = nt.nodes.new('CompositorNodeMapRange')
            map_z = nt.nodes.new('CompositorNodeMapRange')
            file_out = nt.nodes.new('CompositorNodeOutputFile')

            file_out.base_path = os.path.dirname(output_path)
            file_out.format.file_format = 'PNG'
            file_out.format.color_mode = 'RGB'
            file_out.format.color_depth = '16'
            file_out.file_slots.clear()
            slot = file_out.file_slots.new('normal_')
            slot.path = 'normal_'

            nt.links.new(render_layers.outputs['Normal'], sep_xyz.inputs['Image'])
            for map_node in (map_x, map_y, map_z):
                map_node.inputs[1].default_value = -1.0
                map_node.inputs[2].default_value = 1.0
                map_node.inputs[3].default_value = 0.0
                map_node.inputs[4].default_value = 1.0
                map_node.clamp = True

            nt.links.new(sep_xyz.outputs['R'], map_x.inputs[0])
            nt.links.new(sep_xyz.outputs['G'], map_y.inputs[0])
            nt.links.new(sep_xyz.outputs['B'], map_z.inputs[0])
            nt.links.new(map_x.outputs[0], comb.inputs['R'])
            nt.links.new(map_y.outputs[0], comb.inputs['G'])
            nt.links.new(map_z.outputs[0], comb.inputs['B'])
            nt.links.new(comb.outputs['Image'], file_out.inputs[0])

            bpy.ops.render.render(write_still=False, use_viewport=False)
    finally:
        view_layer.use_pass_normal = old_normal_pass

    _rename_file_output(os.path.dirname(output_path), 'normal_', os.path.basename(output_path))


def render_depth_pass(scene, cam_obj, output_path, depth_near, depth_far):
    ensure_dir(os.path.dirname(output_path))
    scene.camera = cam_obj
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'BW'
    scene.render.image_settings.color_depth = '16'

    view_layer = scene.view_layers[0]
    old_z_pass = view_layer.use_pass_z
    view_layer.use_pass_z = True

    try:
        with TemporaryNodeSetup(scene) as nt:
            render_layers = nt.nodes.new('CompositorNodeRLayers')
            map_range = nt.nodes.new('CompositorNodeMapRange')
            file_out = nt.nodes.new('CompositorNodeOutputFile')

            file_out.base_path = os.path.dirname(output_path)
            file_out.format.file_format = 'PNG'
            file_out.format.color_mode = 'BW'
            file_out.format.color_depth = '16'
            file_out.file_slots.clear()
            slot = file_out.file_slots.new('depth_')
            slot.path = 'depth_'

            map_range.inputs[1].default_value = depth_near
            map_range.inputs[2].default_value = depth_far
            map_range.inputs[3].default_value = 1.0
            map_range.inputs[4].default_value = 0.0
            map_range.clamp = True

            nt.links.new(render_layers.outputs['Depth'], map_range.inputs[0])
            nt.links.new(map_range.outputs[0], file_out.inputs[0])

            bpy.ops.render.render(write_still=False, use_viewport=False)
    finally:
        view_layer.use_pass_z = old_z_pass

    _rename_file_output(os.path.dirname(output_path), 'depth_', os.path.basename(output_path))
