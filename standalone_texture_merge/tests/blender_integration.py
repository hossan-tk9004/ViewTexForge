"""Run in an isolated Blender 5.1 background process, never the interactive scene.

Optional VTF_SOURCE verifies against the installed v0.2.1 capture implementation.
All generated fixtures are confined to a new diagnostics directory.
"""
import json
from pathlib import Path
import sys
import tempfile
import numpy as np
import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from standalone_texture_merge.blender_geometry import collect_render_geometry, resolve_targets
from standalone_texture_merge.image_io import read_image, write_png, write_exr
from standalone_texture_merge.dataset_io import load_dataset
from standalone_texture_merge.run_texture_merge import run
from standalone_texture_merge.settings import Settings


def integration(vtf_source=None):
    assert bpy.app.background, "Run this fixture in a separate background process"
    assert bpy.app.version[:2] == (5, 1)
    root = Path(tempfile.mkdtemp(prefix="texture_merge_core_", dir=ROOT/"diagnostics"))
    scene = bpy.data.scenes.new("TextureMergeCoreIntegration")
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 32, 24
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1.25
    scene.render.use_compositing = True
    scene.unit_settings.scale_length = 0.01
    mesh = bpy.data.meshes.new("TextureMergeFixture")
    mesh.from_pydata([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1)], [], [(0,1,2,3)])
    layer = mesh.uv_layers.new(name="UVMap")
    for li, uv in enumerate(((0,0),(1,0),(1,1),(0,1))):
        layer.uv[li].vector = uv
    obj = bpy.data.objects.new("TextureMergeFixture", mesh)
    obj["viewtexforge_object_id"] = "integration-quad"
    scene.collection.objects.link(obj)
    modifier = obj.modifiers.new("RenderLevelDifference", "SUBSURF")
    modifier.subdivision_type = "SIMPLE"
    modifier.levels, modifier.render_levels = 0, 1
    camera_data = bpy.data.cameras.new("TextureMergeFixtureCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 4
    camera_data.shift_x, camera_data.shift_y = 0.0625, -0.04
    camera = bpy.data.objects.new("TextureMergeFixtureCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    targets = [dict(object_id="integration-quad",object_name=obj.name,uv_layer="UVMap")]
    before_handlers = (list(bpy.app.handlers.depsgraph_update_post), list(bpy.app.handlers.frame_change_post))
    before_objects = set(scene.objects)
    settings_before = (scene.render.image_settings.file_format, scene.render.image_settings.color_depth,
                       scene.render.image_settings.color_mode, scene.render.image_settings.exr_codec)
    checks = []
    try:
        snapshot = collect_render_geometry(scene, targets)[0]
        assert len(snapshot["vertices_local"]) == 9, len(snapshot["vertices_local"])
        assert len(snapshot["triangles"]) == 8
        assert modifier.levels == 0 and modifier.render_levels == 1
        checks.append("actual RENDER subdivision 9 vertices / 8 triangles, viewport level 0")
        if vtf_source:
            sys.path.insert(0, str(vtf_source))
            from view_tex_forge.contract_capture import RenderContractCollector
            from view_tex_forge.contract_raster import render_texture_merge_contract_pass
            with RenderContractCollector(scene, camera, [obj]) as collector:
                bpy.ops.render.render(write_still=False,use_viewport=False,scene=scene.name)
            original = collector.require_result()["targets"][0]
            for key in ("vertices_local", "triangles", "corner_uv", "matrix_world"):
                np.testing.assert_array_equal(snapshot[key], original[key])
            capture = render_texture_merge_contract_pass(scene,camera,str(root/"depth_raw.exr"),str(root/"geometry_mask.png"),[obj])
            camera_meta = capture["camera"]
            checks.append("exact geometry array equality with ViewTexForge v0.2.1; actual VTF Depth/Mask export")
        else:
            raise RuntimeError("Pass vtf_source to exercise the actual ViewTexForge v0.2.1 exporter")

        # Asymmetric encoded pixels catch vertical inversion AND unwanted sRGB decoding.
        test_rgb = np.array([[[0.2,0.4,0.8],[1,0.5,0]],[[0.1,0.7,0.3],[0,0,0]]],np.float32)
        for bits in (8,16):
            write_png(root/f"encoded_{bits}.png",test_rgb,bits,srgb=True)
            actual = read_image(root/f"encoded_{bits}.png")[...,:3]
            np.testing.assert_allclose(actual,test_rgb,atol=1/((1<<bits)-1)+1e-7)
        numeric = np.array([[0,0.01,2.5],[0.002,30,0.12345]],np.float32)
        write_exr(root/"roundtrip.exr",numeric,scene)
        np.testing.assert_array_equal(read_image(root/"roundtrip.exr")[...,0],numeric)
        checks.append("PNG 8/16 encoded RGB and float32 EXR exact orientation/value roundtrips")

        color = np.empty((24,32,3),np.float32);color[:]=(0.2,0.4,0.8)
        write_png(root/"color.png",color,srgb=True)
        meta = dict(schema_version="2.0.0", view_id="front",camera=camera_meta,
                    render=dict(resolution=[32,24],pixel_aspect=[1.25,1]),meters_per_world_unit=0.01,
                    targets=targets,images=dict(depth_raw=dict(path="depth_raw.exr",resolution=[32,24]),
                                               geometry_mask=dict(path="geometry_mask.png",resolution=[32,24])))
        (root/"camera.json").write_text(json.dumps(meta))
        manifest = dict(views=[dict(view_id="front", camera_json_path="camera.json",
                                  color=dict(path="color.png",resolution=[32,24]),
                                  registration=dict(status="ALIGNED",mapping="IDENTITY_PIXEL"))])
        (root/"manifest.json").write_text(json.dumps(manifest))
        outputs = run(root/"manifest.json",root/"normal",Settings(resolution=(8,8),padding_radius=1),scene)
        normal_files = list((root/"normal").rglob("*.*"))
        assert len(normal_files)==1 and normal_files[0].name=="basecolor.png", normal_files
        actual=read_image(outputs[0])[...,:3]
        np.testing.assert_allclose(actual,np.broadcast_to([0.2,0.4,0.8],actual.shape),atol=1/255)
        checks.append("end-to-end capture dataset -> RENDER mesh -> basecolor only")
        debug_outputs=run(root/"manifest.json",root/"debug_mode",Settings(resolution=(8,8),debug_output=True),scene)
        debug=Path(debug_outputs[0]).parent/"debug"
        assert {p.name for p in debug.iterdir()} == {"direct_coverage.png","padding_area.png","weight_sum.exr","dominant_view.npy","merge_report.json"}
        assert (np.load(debug/"dominant_view.npy")==1).all()
        assert (read_image(debug/"direct_coverage.png")[...,0]==1).all()
        assert not (read_image(debug/"padding_area.png")[...,0]>0).any()
        np.testing.assert_allclose(read_image(debug/"weight_sum.exr")[...,0],1,atol=1e-6)
        checks.append("debug-only coverage/weights/view/padding/report; no filled_area")

        try:
            resolve_targets(scene,[dict(object_id="missing",object_name="missing",uv_layer="UVMap")])
        except RuntimeError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("Missing object was accepted")
        try:
            collect_render_geometry(scene,[dict(targets[0],uv_layer="missing")])
        except RuntimeError as exc:
            assert "UV Layer not found" in str(exc)
        else:
            raise AssertionError("Missing UV was accepted")
        assert before_handlers==(list(bpy.app.handlers.depsgraph_update_post),list(bpy.app.handlers.frame_change_post))
        assert scene.render.use_compositing and set(scene.objects)==before_objects
        assert settings_before==(scene.render.image_settings.file_format,scene.render.image_settings.color_depth,
                                 scene.render.image_settings.color_mode,scene.render.image_settings.exr_codec)
        checks.append("missing Object/UV fail; handlers/render settings restored on success and failure")
        result=dict(blender=bpy.app.version_string,checks=checks,fixture_directory=str(root))
        (root/"verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        return result
    finally:
        bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.objects.remove(camera,do_unlink=True)
        bpy.data.meshes.remove(mesh)
        bpy.data.cameras.remove(camera_data)
        bpy.data.scenes.remove(scene)


if __name__=="__main__":
    print(json.dumps(integration(sys.argv[-1]),indent=2))
