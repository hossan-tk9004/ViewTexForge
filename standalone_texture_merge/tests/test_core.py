import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

from standalone_texture_merge.dataset_io import View, load_dataset
from standalone_texture_merge.settings import Settings
from standalone_texture_merge.merge_core import merge
from standalone_texture_merge.projection import project, sample_weight, pixel_footprint_m, resolve_depth_tolerance
from standalone_texture_merge.uv_rasterizer import rasterize
from standalone_texture_merge.uv_padding import pad
from standalone_texture_merge.image_io import write_png


def mesh():
    return dict(object_id="quad", object_name="Quad", uv_layer="UVMap",
                vertices_local=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1]],
                triangles=[[0,1,2],[0,2,3]],
                corner_uv=[[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]]],
                matrix_world=np.eye(4).tolist())


def view(name="front", rgb=(0.2,0.4,0.8), size=(8,8)):
    w,h = size
    meta = dict(camera=dict(camera_type="ORTHO", matrix_world=np.eye(4).tolist(),
                            projection_matrix=np.diag([1,1,-0.02,1]).tolist(), clip_start=0.01,clip_end=100),
                render=dict(resolution=[w,h]), meters_per_world_unit=1,
                targets=[dict(object_id="quad",object_name="Quad",uv_layer="UVMap")])
    return View(name, meta, np.broadcast_to(rgb,(h,w,3)).copy(), np.ones((h,w)),
                np.ones((h,w),bool), np.ones((h,w),bool))


class CoreTests(unittest.TestCase):
    def settings(self, **kw):
        return Settings(resolution=(8,8),padding_radius=0,**kw)

    def test_encoded_blend_and_default_view_priority(self):
        result = merge(mesh(), [view("front",(0,0,0)),view("back",(1,1,1))], self.settings())
        np.testing.assert_allclose(result["basecolor"],0.5)
        self.assertEqual(set(result), {"basecolor"})

    def test_linear_blend(self):
        result = merge(mesh(), [view("a",(0,0,0)),view("b",(1,1,1))], self.settings(blend_space="SCENE_LINEAR"))
        np.testing.assert_allclose(result["basecolor"],0.73535698,atol=1e-6)

    def test_priority_and_sorted_tie(self):
        result = merge(mesh(), [view("z",(1,0,0)),view("a",(0,0,1))], self.settings(debug_output=True))
        self.assertTrue(np.all(result["dominant_view"]==1))
        np.testing.assert_allclose(result["weight_sum"],2)
        other = merge(mesh(), [view("z",(1,0,0)),view("a",(0,0,1))], self.settings(view_priority={"z":3}))
        np.testing.assert_allclose(other["basecolor"][0,0],(0.75,0,0.25))

    def test_backfaces_have_no_color_even_when_depth_matches(self):
        m=mesh()
        m["triangles"]=[list(reversed(t)) for t in m["triangles"]]
        m["corner_uv"]=[list(reversed(t)) for t in m["corner_uv"]]
        result=merge(m,[view()],self.settings(debug_output=True))
        self.assertFalse(result["direct_coverage"].any())

    def test_depth_invalid_and_masks(self):
        v=view()
        v.depth[0,:]=[0,np.nan,np.inf,1.004,0.996,1,1,1]
        v.geometry_mask[0,5]=False
        v.color_valid_mask[0,6]=False
        result=merge(mesh(),[v],self.settings(debug_output=True, depth_tolerance_mode="MANUAL"))
        self.assertFalse(result["direct_coverage"][0,:7].any())
        self.assertTrue(result["direct_coverage"][0,7])
        self.assertTrue(np.isfinite(result["basecolor"]).all())

    def test_metric_depth_and_exact_gaussian(self):
        v=view()
        v.metadata["meters_per_world_unit"]=0.01
        v.depth[:]=0.0112
        result=merge(mesh(),[v],self.settings(debug_output=True, depth_tolerance_mode="MANUAL"))
        np.testing.assert_allclose(result["weight_sum"],np.exp(-1),rtol=1e-6)

    def test_facing_formula(self):
        r=dict(points=np.array([[0,0,-1.0]]),normals=np.array([[0,0,0.5]]),face_normals=np.array([[0,0,0.025]]))
        _,w=sample_weight(r,view(),self.settings(depth_tolerance_mode="MANUAL"))
        np.testing.assert_allclose(w,[0.5**4*0.3])


    def test_auto_depth_tolerance_from_projection_pixel_footprint(self):
        v=view(size=(1024,1024))
        # ortho_scale ~= 30.9 equivalent projection scale on Y.
        scale=2.0/30.9
        p=np.eye(4);p[0,0]=scale;p[1,1]=scale
        v.metadata["camera"]["projection_matrix"]=p.tolist()
        v.metadata["meters_per_world_unit"]=1.0
        fp=pixel_footprint_m(v.metadata)
        np.testing.assert_allclose(fp,30.9/1024,rtol=1e-12)
        sigma,cutoff,reported=resolve_depth_tolerance(v.metadata,self.settings())
        np.testing.assert_allclose(reported,fp)
        np.testing.assert_allclose(sigma,fp*0.65)
        np.testing.assert_allclose(cutoff,fp*1.7)

    def test_manual_depth_tolerance_preserves_meter_values(self):
        v=view()
        settings=self.settings(depth_tolerance_mode="MANUAL",depth_sigma_m=0.02,depth_cutoff_m=0.05)
        sigma,cutoff,fp=resolve_depth_tolerance(v.metadata,settings)
        self.assertEqual((sigma,cutoff,fp),(0.02,0.05,None))

    def test_projection_uses_saved_shift_non_square_matrix(self):
        v=view(size=(12,6))
        p=np.eye(4);p[0,0]=0.5;p[1,1]=2;p[0,3]=-0.25;p[1,3]=0.5
        v.metadata["camera"]["projection_matrix"]=p.tolist()
        xy,depth,_=project(np.array([[0,0,-1],[1,0.125,-2]]),v.metadata)
        np.testing.assert_allclose(xy,[[4.5,1.5],[7.5,0.75]])
        np.testing.assert_allclose(depth,[1,2])

    def test_out_of_frame_and_clip(self):
        v=view();v.metadata["camera"]["clip_end"]=0.5
        self.assertFalse(merge(mesh(),[v],self.settings(debug_output=True))["direct_coverage"].any())
        v=view();v.metadata["camera"]["projection_matrix"][0][3]=3
        self.assertFalse(merge(mesh(),[v],self.settings(debug_output=True))["direct_coverage"].any())

    def test_overlap_lowest_triangle_wins(self):
        m=mesh()
        m["triangles"]+=m["triangles"]
        m["corner_uv"]+=m["corner_uv"]
        result=rasterize(m,(8,8))
        self.assertTrue((result["owner"]<2).all())
        self.assertTrue((result["owner"]>=0).all())
        np.testing.assert_allclose(result["points"][:,2],-1)

    def test_reflection_keeps_outward_orientation(self):
        m=mesh();m["matrix_world"][0][0]=-1
        result=merge(m,[view()],self.settings(debug_output=True))
        self.assertTrue(result["direct_coverage"].all())

    def test_uv_padding_does_not_fill_hole_or_wrap(self):
        rgb=np.zeros((7,7,3),np.float32)
        occupied=np.zeros((7,7),bool);occupied[1:6,1:6]=True
        direct=occupied.copy();direct[3,3]=False
        rgb[direct]=(1,0,0)
        result,area=pad(rgb,direct,occupied,np.zeros((7,7),np.int32),4)
        self.assertFalse(area[3,3]);np.testing.assert_array_equal(result[3,3],0)
        self.assertTrue(area[0,0])
        direct=np.zeros((3,3),bool);direct[0,0]=True
        _,area=pad(np.ones((3,3,3)),direct,direct,np.zeros((3,3),int),1)
        self.assertEqual(int(area.sum()),2)
        self.assertFalse(area[-1,0])

    def test_padding_island_tie_is_fixed(self):
        rgb=np.zeros((1,5,3));rgb[0,0]=(1,0,0);rgb[0,4]=(0,0,1)
        direct=np.array([[True,False,False,False,True]])
        result,_=pad(rgb,direct,direct,np.array([[3,-1,-1,-1,1]]),2)
        np.testing.assert_array_equal(result[0,2],(0,0,1))

    def test_png_encoding_roundtrip(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"test.png"
            data=np.array([[[0,0.2,1],[0.5,0.1,0.9]]])
            write_png(p,data,srgb=True)
            np.testing.assert_array_equal(np.array(Image.open(p)),np.rint(data*255).astype(np.uint8))
            values=np.array([[0,1000,65535]])
            write_png(p,values,16,integer=True)
            np.testing.assert_array_equal(np.array(Image.open(p)),values)

    def test_missing_files_and_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            camera=view().metadata
            camera["images"]={"depth_raw":{"path":"depth_raw.exr"},"geometry_mask":{"path":"geometry_mask.png"}}
            manifest={"views":[{"view_id":"front","camera_json_path":"camera.json","color":{"path":"color.png"}}]}
            (root/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(FileNotFoundError):load_dataset(root/"manifest.json",lambda p:None)
            (root/"camera.json").write_text(json.dumps(camera))
            for name in ("color.png","depth_raw.exr","geometry_mask.png"):
                with self.assertRaises(FileNotFoundError):load_dataset(root/"manifest.json",lambda p:None)
                (root/name).touch()
            with self.assertRaisesRegex(ValueError,"Resolution mismatch"):
                load_dataset(root/"manifest.json",lambda p:np.zeros((7,8,3)))
            views,targets=load_dataset(root/"manifest.json",lambda p:np.ones((8,8,3)))
            self.assertEqual(targets[0]["object_id"],"quad")
            self.assertEqual(len(views),1)


if __name__=="__main__":
    unittest.main()
