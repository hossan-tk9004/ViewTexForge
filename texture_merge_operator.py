import json
import os
from pathlib import Path

import bpy

from .standalone_texture_merge.output_io import object_directory
from .standalone_texture_merge.run_texture_merge import (
    run as run_texture_merge_core,
    run_iter as run_texture_merge_core_iter,
)
from .utils import validate_output_directory
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
        # Release workflow contract: Strict Ray visibility is fixed.
        visibility_mode='STRICT',
        surface_sample_mode=s.texture_merge_surface_sample_mode,
        sample_guard_px=int(s.texture_merge_sample_guard_px),
        fill_mode=s.texture_merge_fill_mode,
        fill_vertex_group=s.texture_merge_fill_vertex_group,
        fill_max_hole_texels=int(s.texture_merge_fill_max_hole_texels),
        fill_max_surface_fraction=float(s.texture_merge_fill_max_surface_fraction),
        fill_min_confidence=float(s.texture_merge_fill_min_confidence),
        fill_max_color_range=float(s.texture_merge_fill_max_color_range),
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
        'visibility_mode': settings.visibility_mode,
        'surface_sample_mode': settings.surface_sample_mode,
        'sample_guard_px': settings.sample_guard_px,
        'fill_mode': settings.fill_mode,
        'fill_vertex_group': settings.fill_vertex_group,
        'fill_max_hole_texels': settings.fill_max_hole_texels,
        'fill_max_surface_fraction': settings.fill_max_surface_fraction,
        'fill_min_confidence': settings.fill_min_confidence,
        'fill_max_color_range': settings.fill_max_color_range,
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


def run_texture_merge_iter(scene):
    s = scene.viewtexforge_settings
    valid, output_dir, message = validate_output_directory(s.output_dir, create=False)
    if not valid:
        raise RuntimeError(message)

    yield {'progress': 2.0, 'status': 'Preparing Texture Merge manifest...'}
    manifest_path = build_texture_merge_manifest(output_dir)
    settings = settings_from_scene(scene)
    generated_dir = os.path.join(output_dir, 'generated')
    _write_json(os.path.join(generated_dir, 'merge_settings.json'), settings_dict(settings))

    subdir = (s.texture_merge_output_subdir or 'merged').strip().strip('/\\') or 'merged'
    merge_output_dir = os.path.join(output_dir, subdir)
    os.makedirs(merge_output_dir, exist_ok=True)

    print(f"[ViewTexForge][Texture Merge] Manifest: {manifest_path}")
    print(f"[ViewTexForge][Texture Merge] Output: {merge_output_dir}")

    runner = run_texture_merge_core_iter(
        manifest_path=manifest_path,
        output_root=merge_output_dir,
        settings=settings,
        scene=scene,
    )
    while True:
        try:
            event = next(runner)
            core_progress = max(0.0, min(1.0, float(event.get('progress', 0.0))))
            yield {
                'progress': 5.0 + 85.0 * core_progress,
                'status': event.get('status', 'Running Texture Merge...'),
            }
        except StopIteration as stop:
            outputs = stop.value
            break

    yield {'progress': 94.0, 'status': 'Applying merged textures to materials...'}
    apply_report = apply_merged_textures_to_materials(scene, manifest_path, merge_output_dir)
    yield {'progress': 99.0, 'status': 'Finalizing Texture Merge...'}
    return outputs, manifest_path, merge_output_dir, apply_report


def _consume_generator(generator):
    while True:
        try:
            next(generator)
        except StopIteration as stop:
            return stop.value


def run_texture_merge(scene):
    """Synchronous compatibility wrapper used by non-modal callers/tests."""
    return _consume_generator(run_texture_merge_iter(scene))


class VIEWTEXFORGE_OT_texture_merge(bpy.types.Operator):
    bl_idname = 'viewtexforge.texture_merge'
    bl_label = 'Run Texture Merge'
    bl_description = 'Project generated camera colors and merge them into UV base-color textures'

    _timer = None
    _runner = None
    _direct_status = False

    def execute(self, context):
        settings = context.scene.viewtexforge_settings
        if settings.texture_merge_is_running or settings.capture_is_running or settings.comfyui_is_running:
            self.report({'WARNING'}, 'A ViewTexForge operation is already running.')
            return {'CANCELLED'}

        valid, _output_dir, message = validate_output_directory(settings.output_dir, create=False)
        if not valid:
            settings.texture_merge_last_result = 'FAILED'
            settings.execution_current_stage = 'Failed'
            settings.execution_stage_progress = 0.0
            settings.execution_status_text = message
            self.report({'WARNING'}, message)
            return {'CANCELLED'}

        self._direct_status = not settings.execution_is_running
        settings.texture_merge_is_running = True
        settings.texture_merge_last_result = 'RUNNING'
        settings.execution_current_stage = 'Texture Merge'
        settings.execution_stage_progress = 0.0
        if self._direct_status:
            settings.execution_overall_progress = 0.0
        settings.execution_status_text = 'Preparing Texture Merge...'

        try:
            self._runner = run_texture_merge_iter(context.scene)
            self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
            context.window_manager.modal_handler_add(self)
            self._redraw_all(context)
            return {'RUNNING_MODAL'}
        except Exception as exc:
            return self._fail(context, exc)

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        settings = context.scene.viewtexforge_settings
        try:
            progress = next(self._runner)
            percent = max(0.0, min(100.0, float(progress.get('progress', 0.0))))
            settings.execution_current_stage = 'Texture Merge'
            settings.execution_stage_progress = percent
            if self._direct_status:
                settings.execution_overall_progress = percent
            settings.execution_status_text = progress.get('status', 'Running Texture Merge...')
            self._redraw_all(context)
            return {'RUNNING_MODAL'}
        except StopIteration as stop:
            return self._complete(context, stop.value)
        except Exception as exc:
            return self._fail(context, exc)

    def _complete(self, context, result):
        settings = context.scene.viewtexforge_settings
        outputs, _manifest, output_dir, apply_report = result
        apply_mode = apply_report.get('mode', 'NONE')
        if apply_mode == 'NONE':
            message = f'Texture Merge completed ({len(outputs)} texture(s))'
        else:
            message = (
                f"Texture Merge completed ({len(outputs)} texture(s)); "
                f"applied to {apply_report.get('objects', 0)} object(s) / "
                f"{apply_report.get('materials_applied', 0)} material(s)"
            )
        settings.texture_merge_last_result = 'FINISHED'
        settings.execution_stage_progress = 100.0
        settings.execution_status_text = message
        if self._direct_status:
            settings.execution_current_stage = 'Completed'
            settings.execution_overall_progress = 100.0
        self._cleanup(context)
        self.report({'INFO'}, f'Texture Merge complete: {output_dir}')
        return {'FINISHED'}

    def _fail(self, context, exc):
        settings = context.scene.viewtexforge_settings
        message = str(exc)
        settings.texture_merge_last_result = 'FAILED'
        settings.execution_current_stage = 'Failed'
        settings.execution_stage_progress = 0.0
        settings.execution_status_text = f'Failed: {message}'
        print(f"[ViewTexForge][Texture Merge][ERROR] {message}")
        self._cleanup(context)
        self.report({'ERROR'}, message)
        return {'CANCELLED'}

    def _cleanup(self, context):
        settings = context.scene.viewtexforge_settings
        settings.texture_merge_is_running = False
        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        self._runner = None
        self._redraw_all(context)

    @staticmethod
    def _redraw_all(context):
        screen = getattr(context, 'screen', None)
        if screen:
            for area in screen.areas:
                try:
                    area.tag_redraw()
                except Exception:
                    pass

    def cancel(self, context):
        settings = context.scene.viewtexforge_settings
        settings.texture_merge_last_result = 'FAILED'
        settings.execution_current_stage = 'Failed'
        settings.execution_status_text = 'Texture Merge cancelled'
        self._cleanup(context)
