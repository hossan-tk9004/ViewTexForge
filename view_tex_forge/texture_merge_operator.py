import json
import os
from pathlib import Path

import bpy

from .standalone_texture_merge.output_io import object_directory
from .standalone_texture_merge.run_texture_merge import run as run_texture_merge_core
from .standalone_texture_merge.settings import Settings as TextureMergeSettings


NODE_NAME_MERGED_BASECOLOR = 'ViewTexForge_MergedBaseColor'
MATERIAL_SUFFIX = '_VTF'


def _read_json(path):
    with open(path, 'r', encoding='utf-8-sig') as handle:
        return json.load(handle)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=4, ensure_ascii=False)


def _relpath(path, base_dir):
    return os.path.relpath(os.path.abspath(path), os.path.abspath(base_dir)).replace('\\', '/')


def _resolve_relative(path_value, base_dir):
    if os.path.isabs(path_value):
        return os.path.abspath(path_value)
    return os.path.abspath(os.path.join(base_dir, path_value))


def _camera_resolution(camera_json_path):
    data = _read_json(camera_json_path)
    resolution = ((data.get('render') or {}).get('resolution'))
    if not isinstance(resolution, (list, tuple)) or len(resolution) != 2:
        raise RuntimeError(f"camera.json has no valid render.resolution: {camera_json_path}")
    return [int(resolution[0]), int(resolution[1])]


def build_texture_merge_manifest(output_dir):
    """Return a Standalone Texture Merge compatible manifest path.

    ViewTexForge's generated manifest keeps generation provenance. The merge
    core consumes a smaller `views[]` contract, so this function preserves the
    generation manifest and writes a deterministic derived manifest beside it.
    """
    generated_dir = os.path.join(output_dir, 'generated')
    source_manifest_path = os.path.join(generated_dir, 'generated_manifest.json')
    if not os.path.isfile(source_manifest_path):
        raise RuntimeError(
            "Generated manifest not found. Run ComfyUI generation first: " + source_manifest_path
        )

    source = _read_json(source_manifest_path)
    capture_id = source.get('capture_id')
    views = source.get('views')

    # Newer ViewTexForge manifests may already contain the merge contract.
    if isinstance(views, list) and views:
        normalized_views = views
    else:
        outputs = source.get('outputs') or []
        if not outputs:
            raise RuntimeError("generated_manifest.json contains neither views[] nor outputs[].")

        normalized_views = []
        source_manifest_dir = os.path.dirname(source_manifest_path)
        for item in outputs:
            view_id = item.get('view_id')
            camera_value = item.get('camera_json') or item.get('camera_json_path')
            color_value = item.get('generated_image')
            if not view_id or not camera_value or not color_value:
                raise RuntimeError(f"Incomplete generated manifest entry: {item}")

            # Current ViewTexForge outputs[] paths are relative to Output Directory,
            # not to generated_manifest.json. Resolve them against output_dir.
            camera_abs = _resolve_relative(camera_value, output_dir)
            color_abs = _resolve_relative(color_value, output_dir)
            if not os.path.isfile(camera_abs):
                raise RuntimeError(f"Camera JSON not found for {view_id}: {camera_abs}")
            if not os.path.isfile(color_abs):
                raise RuntimeError(f"Generated color not found for {view_id}: {color_abs}")

            normalized_views.append({
                'view_id': view_id,
                'camera_json_path': _relpath(camera_abs, source_manifest_dir),
                'color': {
                    'path': _relpath(color_abs, source_manifest_dir),
                    'resolution': _camera_resolution(camera_abs),
                    'color_space': 'SRGB',
                },
                'registration': {
                    'status': 'ALIGNED',
                    'mapping': 'IDENTITY_PIXEL',
                    'reference': 'CAPTURE_PIXEL_GRID',
                },
            })

    merge_manifest = {
        'schema_version': '1.0.0',
        'capture_id': capture_id,
        'views': normalized_views,
    }
    merge_manifest_path = os.path.join(generated_dir, 'texture_merge_manifest.json')
    _write_json(merge_manifest_path, merge_manifest)
    return merge_manifest_path


def settings_from_scene(scene):
    s = scene.viewtexforge_settings
    resolution = int(s.texture_merge_resolution)
    return TextureMergeSettings(
        resolution=(resolution, resolution),
        debug_output=bool(s.texture_merge_debug_output),
        blend_space='SRGB_ENCODED',
        facing_exponent=float(s.texture_merge_facing_exponent),
        face_gate_gain=float(s.texture_merge_face_gate_gain),
        depth_tolerance_mode=s.texture_merge_depth_tolerance_mode,
        depth_sigma_scale_px=float(s.texture_merge_depth_sigma_scale_px),
        depth_cutoff_scale_px=float(s.texture_merge_depth_cutoff_scale_px),
        depth_sigma_m=float(s.texture_merge_depth_sigma_m),
        depth_cutoff_m=float(s.texture_merge_depth_cutoff_m),
        min_weight_sum=0.00001,
        view_priority={},
        padding_radius=int(s.texture_merge_padding_radius),
        png_bit_depth=int(s.texture_merge_png_bit_depth),
    )


def settings_dict(settings):
    return {
        'resolution': list(settings.resolution),
        'debug_output': settings.debug_output,
        'blend_space': settings.blend_space,
        'facing_exponent': settings.facing_exponent,
        'face_gate_gain': settings.face_gate_gain,
        'depth_tolerance_mode': settings.depth_tolerance_mode,
        'depth_sigma_scale_px': settings.depth_sigma_scale_px,
        'depth_cutoff_scale_px': settings.depth_cutoff_scale_px,
        'depth_sigma_m': settings.depth_sigma_m,
        'depth_cutoff_m': settings.depth_cutoff_m,
        'min_weight_sum': settings.min_weight_sum,
        'view_priority': settings.view_priority,
        'padding_radius': settings.padding_radius,
        'png_bit_depth': settings.png_bit_depth,
    }


def _collect_targets_from_merge_manifest(manifest_path):
    manifest = _read_json(manifest_path)
    manifest_dir = os.path.dirname(manifest_path)
    targets = {}
    ordered = []
    for entry in manifest.get('views') or []:
        camera_value = entry.get('camera_json_path')
        if not camera_value:
            continue
        camera_json_path = _resolve_relative(camera_value, manifest_dir)
        meta = _read_json(camera_json_path)
        for target in meta.get('targets') or []:
            object_id = target.get('object_id')
            if not object_id or object_id in targets:
                continue
            targets[object_id] = target
            ordered.append(target)
    return ordered


def _resolve_target_object(scene, target):
    object_id = target.get('object_id')
    matches = [obj for obj in scene.objects if obj.get('viewtexforge_object_id') == object_id]
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous object identifier: {object_id}")
    if matches:
        return matches[0]
    object_name = target.get('object_name')
    obj = scene.objects.get(object_name)
    if obj is None:
        raise RuntimeError(f"Target Object not found: {object_name}")
    return obj


def _next_unique_material_name(base_name):
    if base_name not in bpy.data.materials:
        return base_name
    index = 1
    while True:
        candidate = f"{base_name}.{index:03d}"
        if candidate not in bpy.data.materials:
            return candidate
        index += 1


def _load_image(path):
    image = bpy.data.images.load(str(Path(path).resolve()), check_existing=True)
    try:
        image.colorspace_settings.name = 'sRGB'
    except Exception:
        pass
    return image


def _ensure_material_output(node_tree):
    for node in node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            return node
    output = node_tree.nodes.new('ShaderNodeOutputMaterial')
    output.location = (300.0, 0.0)
    return output


def _ensure_principled(node_tree):
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node
    principled = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    principled.location = (0.0, 0.0)
    output = _ensure_material_output(node_tree)
    surface = output.inputs.get('Surface')
    if surface is not None:
        for link in list(surface.links):
            node_tree.links.remove(link)
        node_tree.links.new(principled.outputs['BSDF'], surface)
    return principled


def _find_or_create_image_node(node_tree, image):
    node = node_tree.nodes.get(NODE_NAME_MERGED_BASECOLOR)
    if node is None or node.type != 'TEX_IMAGE':
        node = node_tree.nodes.new('ShaderNodeTexImage')
        node.name = NODE_NAME_MERGED_BASECOLOR
        node.label = 'ViewTexForge Merged BaseColor'
    node.image = image
    return node


def _connect_image_to_base_color(material, image):
    material.use_nodes = True
    node_tree = material.node_tree
    principled = _ensure_principled(node_tree)
    tex = _find_or_create_image_node(node_tree, image)

    try:
        tex.location = (principled.location.x - 320.0, principled.location.y)
    except Exception:
        pass

    base_color = principled.inputs.get('Base Color')
    if base_color is None:
        raise RuntimeError(f"Material has no Principled Base Color socket: {material.name}")

    for link in list(base_color.links):
        node_tree.links.remove(link)
    node_tree.links.new(tex.outputs['Color'], base_color)


def _ensure_material_slot(obj):
    if getattr(obj.data, 'materials', None) is None:
        raise RuntimeError(f"Object has no assignable materials: {obj.name}")
    if len(obj.material_slots) == 0:
        mat = bpy.data.materials.new(name=_next_unique_material_name(f"{obj.name}{MATERIAL_SUFFIX}"))
        obj.data.materials.append(mat)
        return [mat], 1
    materials = []
    created = 0
    for index, slot in enumerate(obj.material_slots):
        if slot.material is None:
            mat = bpy.data.materials.new(name=_next_unique_material_name(f"{obj.name}{MATERIAL_SUFFIX}"))
            obj.material_slots[index].material = mat
            materials.append(mat)
            created += 1
        else:
            materials.append(slot.material)
    return materials, created


def _apply_to_current_materials(obj, image):
    materials, created = _ensure_material_slot(obj)
    applied = 0
    seen = set()
    for mat in materials:
        if mat is None or mat.name_full in seen:
            continue
        seen.add(mat.name_full)
        _connect_image_to_base_color(mat, image)
        applied += 1
    return applied, created


def _apply_to_new_materials(obj, image):
    if getattr(obj.data, 'materials', None) is None:
        raise RuntimeError(f"Object has no assignable materials: {obj.name}")

    applied = 0
    created = 0
    if len(obj.material_slots) == 0:
        new_mat = bpy.data.materials.new(name=_next_unique_material_name(f"{obj.name}{MATERIAL_SUFFIX}"))
        obj.data.materials.append(new_mat)
        _connect_image_to_base_color(new_mat, image)
        return 1, 1

    duplicates = {}
    for index, slot in enumerate(obj.material_slots):
        source_mat = slot.material
        if source_mat is None:
            new_mat = bpy.data.materials.new(name=_next_unique_material_name(f"{obj.name}{MATERIAL_SUFFIX}"))
            created += 1
        else:
            key = source_mat.name_full
            new_mat = duplicates.get(key)
            if new_mat is None:
                new_mat = source_mat.copy()
                new_mat.name = _next_unique_material_name(f"{source_mat.name}{MATERIAL_SUFFIX}")
                duplicates[key] = new_mat
                created += 1
        obj.material_slots[index].material = new_mat
        _connect_image_to_base_color(new_mat, image)
        applied += 1
    return applied, created


def apply_merged_textures_to_materials(scene, merge_manifest_path, merge_output_dir):
    settings = scene.viewtexforge_settings
    mode = settings.texture_merge_material_apply_mode
    if mode == 'NONE':
        return {
            'mode': mode,
            'objects': 0,
            'materials_applied': 0,
            'materials_created': 0,
            'missing_outputs': [],
        }

    targets = _collect_targets_from_merge_manifest(merge_manifest_path)
    object_count = 0
    materials_applied = 0
    materials_created = 0
    missing_outputs = []

    for target in targets:
        object_id = target.get('object_id')
        object_name = target.get('object_name', object_id)
        texture_path = object_directory(merge_output_dir, object_id) / 'basecolor.png'
        if not texture_path.is_file():
            missing_outputs.append(str(texture_path))
            print(f"[ViewTexForge][Material Apply][WARN] Missing merged texture for {object_name}: {texture_path}")
            continue

        obj = _resolve_target_object(scene, target)
        image = _load_image(texture_path)
        if mode == 'CURRENT':
            applied, created = _apply_to_current_materials(obj, image)
        elif mode == 'NEW':
            applied, created = _apply_to_new_materials(obj, image)
        else:
            raise RuntimeError(f"Unknown material apply mode: {mode}")

        object_count += 1
        materials_applied += applied
        materials_created += created
        print(
            f"[ViewTexForge][Material Apply] {obj.name}: {texture_path.name} | "
            f"mode={mode} | materials_applied={applied} | materials_created={created}"
        )

    return {
        'mode': mode,
        'objects': object_count,
        'materials_applied': materials_applied,
        'materials_created': materials_created,
        'missing_outputs': missing_outputs,
    }


def run_texture_merge(scene):
    s = scene.viewtexforge_settings
    output_dir = bpy.path.abspath(s.output_dir)
    if not os.path.isdir(output_dir):
        raise RuntimeError(f"Output Directory does not exist: {output_dir}")

    manifest_path = build_texture_merge_manifest(output_dir)
    settings = settings_from_scene(scene)
    generated_dir = os.path.join(output_dir, 'generated')
    _write_json(os.path.join(generated_dir, 'merge_settings.json'), settings_dict(settings))

    subdir = (s.texture_merge_output_subdir or 'merged').strip().strip('/\\') or 'merged'
    merge_output_dir = os.path.join(output_dir, subdir)
    os.makedirs(merge_output_dir, exist_ok=True)

    print(f"[ViewTexForge][Texture Merge] Manifest: {manifest_path}")
    print(f"[ViewTexForge][Texture Merge] Output: {merge_output_dir}")
    outputs = run_texture_merge_core(
        manifest_path=manifest_path,
        output_root=merge_output_dir,
        settings=settings,
        scene=scene,
    )
    apply_report = apply_merged_textures_to_materials(scene, manifest_path, merge_output_dir)
    return outputs, manifest_path, merge_output_dir, apply_report


class VIEWTEXFORGE_OT_texture_merge(bpy.types.Operator):
    bl_idname = 'viewtexforge.texture_merge'
    bl_label = 'Run Texture Merge'
    bl_description = 'Project generated camera colors and merge them into UV base-color textures'

    def execute(self, context):
        settings = context.scene.viewtexforge_settings
        if settings.execution_is_running:
            self.report({'WARNING'}, 'A ViewTexForge pipeline is already running.')
            return {'CANCELLED'}

        settings.execution_current_stage = 'Texture Merge'
        settings.execution_stage_progress = 5.0
        settings.execution_overall_progress = 5.0
        settings.execution_status_text = 'Preparing Texture Merge...'
        try:
            outputs, _manifest, output_dir, apply_report = run_texture_merge(context.scene)
        except Exception as exc:
            settings.execution_stage_progress = 0.0
            settings.execution_status_text = f'Failed: {exc}'
            print(f"[ViewTexForge][Texture Merge][ERROR] {exc}")
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        apply_mode = apply_report.get('mode', 'NONE')
        if apply_mode == 'NONE':
            settings.execution_status_text = f'Texture Merge completed ({len(outputs)} texture(s))'
        else:
            settings.execution_status_text = (
                f"Texture Merge completed ({len(outputs)} texture(s)); "
                f"applied to {apply_report.get('objects', 0)} object(s) / "
                f"{apply_report.get('materials_applied', 0)} material(s)"
            )
        settings.execution_current_stage = 'Completed'
        settings.execution_stage_progress = 100.0
        settings.execution_overall_progress = 100.0
        self.report({'INFO'}, f'Texture Merge complete: {output_dir}')
        return {'FINISHED'}
