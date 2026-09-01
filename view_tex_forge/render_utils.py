import os
import bpy

from .constants import CLAY_VIEWPORT_COLOR, MATCAP_NAME
from .camera_utils import find_view3d_context
from .utils import ensure_dir


# -----------------------------------------------------------------------------
# Render engine compatibility
# -----------------------------------------------------------------------------

def _get_available_render_engines(scene):
    """Return render-engine identifiers exposed by the running Blender build."""
    try:
        prop = scene.render.bl_rna.properties['engine']
        return {item.identifier for item in prop.enum_items}
    except Exception:
        return set()


def _set_compatible_eevee_engine(scene):
    """Select the Eevee identifier that actually exists in this Blender build."""
    available = _get_available_render_engines(scene)

    # Blender builds have used both identifiers. Never probe by assigning an
    # unsupported enum; inspect the RNA enum first.
    for engine_id in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        if engine_id in available:
            scene.render.engine = engine_id
            print(f"[ViewTexForge] Render engine: {engine_id}")
            return engine_id

    raise RuntimeError(
        "ViewTexForge could not find an Eevee render engine. "
        f"Available engines: {sorted(available)}"
    )


# -----------------------------------------------------------------------------
# Blender 5.1 compositor helpers
# -----------------------------------------------------------------------------

class TemporaryCompositorSetup:
    """
    Create a temporary Blender 5.1 CompositorNodeTree without touching the
    user's compositor tree.

    Blender 5.1 stores the compositor as an independent node-group datablock
    assigned through Scene.compositing_node_group. Scene.node_tree/use_nodes
    are not used here.
    """

    def __init__(self, scene, name="__VIEWTEXFORGE_COMP__"):
        self.scene = scene
        self.name = name
        self.old_tree = None
        self.old_use_compositing = None
        self.tree = None

    def __enter__(self):
        self.old_tree = self.scene.compositing_node_group
        self.old_use_compositing = self.scene.render.use_compositing

        self.tree = bpy.data.node_groups.new(
            name=self.name,
            type='CompositorNodeTree',
        )
        self.scene.compositing_node_group = self.tree
        self.scene.render.use_compositing = True
        return self.tree

    def __exit__(self, exc_type, exc, tb):
        self.scene.compositing_node_group = self.old_tree
        self.scene.render.use_compositing = self.old_use_compositing

        tree = self.tree
        self.tree = None
        if tree is not None and tree.name in bpy.data.node_groups:
            bpy.data.node_groups.remove(tree)
        return False


def _create_render_layers_and_group_output(tree, scene):
    """Create the minimum valid Blender 5.1 compositor group structure."""
    render_layers = tree.nodes.new('CompositorNodeRLayers')
    render_layers.label = 'Render Layers'
    render_layers.scene = scene
    render_layers.location = (-700, 0)

    # Blender 5.1 compositor trees are node groups and use Group Output.
    tree.interface.new_socket(
        name='Image',
        in_out='OUTPUT',
        socket_type='NodeSocketColor',
    )
    group_output = tree.nodes.new('NodeGroupOutput')
    group_output.location = (650, -350)
    tree.links.new(render_layers.outputs['Image'], group_output.inputs['Image'])

    return render_layers


def _create_file_output(
    tree,
    directory,
    file_name,
    socket_type,
    color_mode,
    color_depth,
    save_as_render=False,
):
    """Create a Blender 5.1 File Output node configured for PNG."""
    node = tree.nodes.new('CompositorNodeOutputFile')
    node.directory = directory
    node.file_name = file_name

    # Blender 5.1 File Output API.
    node.format.media_type = 'IMAGE'
    node.format.file_format = 'PNG'
    node.format.color_mode = color_mode
    node.format.color_depth = color_depth

    node.file_output_items.clear()
    item = node.file_output_items.new(socket_type, 'Image')
    item.save_as_render = save_as_render
    return node


def _rename_file_output(base_dir, slot_prefix, final_name):
    candidates = sorted(
        fname
        for fname in os.listdir(base_dir)
        if fname.startswith(slot_prefix) and fname.lower().endswith('.png')
    )

    if not candidates:
        raise RuntimeError(
            f"Expected output file with prefix '{slot_prefix}' "
            f"was not generated in {base_dir}"
        )

    src = os.path.join(base_dir, candidates[0])
    dst = os.path.join(base_dir, final_name)
    if os.path.exists(dst):
        os.remove(dst)
    os.replace(src, dst)
    return dst


def _add_normal_remap_nodes(tree, normal_socket):
    """Remap Normal [-1, 1] to PNG-friendly [0, 1] in Blender 5.1."""
    separate = tree.nodes.new('ShaderNodeSeparateXYZ')
    separate.label = 'Separate Normal'
    separate.location = (-350, 100)
    tree.links.new(normal_socket, separate.inputs[0])

    combine = tree.nodes.new('ShaderNodeCombineXYZ')
    combine.label = 'Encoded Normal 0..1'
    combine.location = (100, 100)

    for index, axis in enumerate(('X', 'Y', 'Z')):
        multiply = tree.nodes.new('ShaderNodeMath')
        multiply.operation = 'MULTIPLY'
        multiply.inputs[1].default_value = 0.5
        multiply.location = (-160, 180 - index * 100)

        add = tree.nodes.new('ShaderNodeMath')
        add.operation = 'ADD'
        add.inputs[1].default_value = 0.5
        add.location = (-20, 180 - index * 100)

        tree.links.new(separate.outputs[axis], multiply.inputs[0])
        tree.links.new(multiply.outputs[0], add.inputs[0])
        tree.links.new(add.outputs[0], combine.inputs[index])

    return combine.outputs[0]


# -----------------------------------------------------------------------------
# MatCap clay capture
# -----------------------------------------------------------------------------

def get_first_matcap_name():
    prefs = bpy.context.preferences
    matcaps = [
        sl.name
        for sl in prefs.studio_lights
        if getattr(sl, 'type', '') == 'MATCAP'
    ]
    return matcaps[0] if matcaps else None


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
        'window_scene': window.scene,
        'space_camera': space.camera,
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
        window.scene = scene
        scene.camera = cam_obj
        space.camera = cam_obj
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
            try:
                shading.studio_light = chosen_matcap
            except Exception as exc:
                print(
                    f"[ViewTexForge] Could not set MatCap '{chosen_matcap}': "
                    f"{exc}. Keeping the current MatCap."
                )

        overlay.show_overlays = False
        shading.show_xray = False
        shading.show_cavity = False
        shading.show_shadows = False
        shading.show_object_outline = False

        area.tag_redraw()
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
        window.scene = saved['window_scene']
        space.camera = saved['space_camera']
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


# -----------------------------------------------------------------------------
# Normal / depth passes
# -----------------------------------------------------------------------------

def render_normal_pass(scene, cam_obj, output_path):
    ensure_dir(os.path.dirname(output_path))
    scene.camera = cam_obj
    _set_compatible_eevee_engine(scene)
    scene.render.film_transparent = True

    view_layer = scene.view_layers[0]
    old_normal_pass = view_layer.use_pass_normal
    view_layer.use_pass_normal = True

    prefix = '__vtf_normal_'

    try:
        with TemporaryCompositorSetup(
            scene,
            name='__VIEWTEXFORGE_COMP_NORMAL__',
        ) as tree:
            render_layers = _create_render_layers_and_group_output(tree, scene)
            encoded_normal = _add_normal_remap_nodes(
                tree,
                render_layers.outputs['Normal'],
            )

            file_out = _create_file_output(
                tree=tree,
                directory=os.path.dirname(output_path),
                file_name=prefix,
                socket_type='VECTOR',
                color_mode='RGB',
                color_depth='16',
                save_as_render=False,
            )
            file_out.label = 'Normal PNG'
            file_out.location = (350, 100)
            tree.links.new(encoded_normal, file_out.inputs[0])

            bpy.ops.render.render(
                write_still=False,
                use_viewport=False,
                scene=scene.name,
            )
    finally:
        view_layer.use_pass_normal = old_normal_pass

    _rename_file_output(
        os.path.dirname(output_path),
        prefix,
        os.path.basename(output_path),
    )




def render_mask_pass(scene, cam_obj, output_path):
    ensure_dir(os.path.dirname(output_path))
    scene.camera = cam_obj
    _set_compatible_eevee_engine(scene)
    scene.render.film_transparent = True

    prefix = '__vtf_mask_'

    with TemporaryCompositorSetup(
        scene,
        name='__VIEWTEXFORGE_COMP_MASK__',
    ) as tree:
        render_layers = _create_render_layers_and_group_output(tree, scene)

        file_out = _create_file_output(
            tree=tree,
            directory=os.path.dirname(output_path),
            file_name=prefix,
            socket_type='FLOAT',
            color_mode='BW',
            color_depth='8',
            save_as_render=False,
        )
        file_out.label = 'Mask PNG'
        file_out.location = (350, 550)
        tree.links.new(render_layers.outputs['Alpha'], file_out.inputs[0])

        bpy.ops.render.render(
            write_still=False,
            use_viewport=False,
            scene=scene.name,
        )

    _rename_file_output(
        os.path.dirname(output_path),
        prefix,
        os.path.basename(output_path),
    )


def render_depth_pass(scene, cam_obj, output_path, depth_near, depth_far):
    ensure_dir(os.path.dirname(output_path))
    scene.camera = cam_obj
    _set_compatible_eevee_engine(scene)
    scene.render.film_transparent = True

    view_layer = scene.view_layers[0]
    old_z_pass = view_layer.use_pass_z
    view_layer.use_pass_z = True

    prefix = '__vtf_depth_'

    try:
        with TemporaryCompositorSetup(
            scene,
            name='__VIEWTEXFORGE_COMP_DEPTH__',
        ) as tree:
            render_layers = _create_render_layers_and_group_output(tree, scene)

            map_range = tree.nodes.new('ShaderNodeMapRange')
            map_range.label = 'Normalize Depth'
            map_range.location = (-150, 350)
            map_range.data_type = 'FLOAT'
            map_range.interpolation_type = 'LINEAR'
            map_range.clamp = True
            map_range.inputs['From Min'].default_value = float(depth_near)
            map_range.inputs['From Max'].default_value = float(depth_far)
            map_range.inputs['To Min'].default_value = 1.0
            map_range.inputs['To Max'].default_value = 0.0
            tree.links.new(render_layers.outputs['Depth'], map_range.inputs['Value'])

            file_out = _create_file_output(
                tree=tree,
                directory=os.path.dirname(output_path),
                file_name=prefix,
                socket_type='FLOAT',
                color_mode='BW',
                color_depth='16',
                save_as_render=False,
            )
            file_out.label = 'Depth PNG'
            file_out.location = (350, 350)
            tree.links.new(map_range.outputs['Result'], file_out.inputs[0])

            bpy.ops.render.render(
                write_still=False,
                use_viewport=False,
                scene=scene.name,
            )
    finally:
        view_layer.use_pass_z = old_z_pass

    _rename_file_output(
        os.path.dirname(output_path),
        prefix,
        os.path.basename(output_path),
    )
