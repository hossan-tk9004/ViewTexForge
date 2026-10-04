import unittest
import numpy as np

from standalone_texture_merge.settings import Settings
from standalone_texture_merge.surface_fill import fill_small_holes
from standalone_texture_merge.uv_rasterizer import rasterize
from standalone_texture_merge.merge_core import sample_guard_px


def quad():
    return dict(object_id='test',uv_layer='UVMap',
                vertices_local=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1]],
                triangles=[[0,1,2],[0,2,3]],
                corner_uv=[[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]]],
                matrix_world=np.eye(4).tolist())


class SmallHoleTests(unittest.TestCase):
    def setup_case(self):
        snapshot=quad()
        raster=rasterize(snapshot,(8,8))
        color=np.zeros((8,8,3),np.float32)
        color[:]=(0.8,0.5,0.3)
        direct=np.ones((8,8),bool)
        direct[4,4]=False
        color[4,4]=0
        weight=np.ones((8,8),np.float32)
        settings=Settings(resolution=(8,8),visibility_mode='STRICT',
                          fill_mode='SMALL_HOLES',fill_max_surface_fraction=.1)
        return snapshot,raster,color,direct,weight,settings

    def test_small_hole_only_and_direct_color_unchanged(self):
        snapshot,raster,color,direct,weight,settings=self.setup_case()
        before=color.copy()
        output,filled,report=fill_small_holes(snapshot,raster,color,direct,weight,settings)
        self.assertTrue(filled[4,4])
        self.assertEqual(report['filled_texels'],1)
        np.testing.assert_array_equal(output[direct],before[direct])
        np.testing.assert_allclose(output[4,4],[.8,.5,.3],atol=1e-6)

    def test_conflicting_sources_remain_unknown(self):
        snapshot,raster,color,direct,weight,settings=self.setup_case()
        color[4,5]=(0,0,0)
        _,filled,report=fill_small_holes(snapshot,raster,color,direct,weight,settings)
        self.assertFalse(filled.any())
        self.assertEqual(report['color_conflict_texels'],1)

    def test_semantic_face_filter_does_not_cross(self):
        snapshot,raster,color,direct,weight,settings=self.setup_case()
        snapshot['fill_face_allowed']=[False,False]
        _,filled,report=fill_small_holes(snapshot,raster,color,direct,weight,settings)
        self.assertFalse(filled.any())
        self.assertEqual(report['semantic_excluded'],1)

    def test_large_hole_is_unresolved(self):
        snapshot,raster,color,direct,weight,settings=self.setup_case()
        direct[1:5,1:5]=False
        _,filled,report=fill_small_holes(snapshot,raster,color,direct,weight,settings)
        self.assertFalse(filled[2:4,2:4].any())
        self.assertGreater(report['oversized_texels'],8)

    def test_adjacent_uv_islands_do_not_share_fill_color(self):
        snapshot=quad()
        snapshot['vertices_local'] += [[-1,-1,-1],[1,-1,-1],[1,1,-1]]
        snapshot['triangles'] += [[4,5,6]]
        snapshot['corner_uv'] += [[[0,0],[1,0],[1,1]]]
        raster=dict(owner=np.array([[0,2,2]],np.int32),
                    islands=np.array([[0,2,2]],np.int32),
                    yy=np.array([0,0,0]),xx=np.array([0,1,2]),
                    points=np.array([[0,0,-1],[.001,0,-1],[.002,0,-1]]))
        color=np.zeros((1,3,3),np.float32);color[0,1:]=(1,0,0)
        direct=np.array([[False,True,True]])
        settings=Settings(resolution=(3,1),visibility_mode='STRICT',
                          fill_mode='SMALL_HOLES',fill_max_surface_fraction=.1)
        _,filled,report=fill_small_holes(snapshot,raster,color,direct,
                                        np.ones((1,3),np.float32),settings)
        self.assertFalse(filled.any())
        self.assertEqual(report['no_reliable_boundary_texels'],1)

    def test_generation_scale_controls_auto_guard(self):
        settings=Settings(visibility_mode='STRICT',surface_sample_mode='LOCAL_NEAREST')
        class CameraView:
            view_id='front'
            metadata={'generation_geometry':{'output_to_diffusion_scale':[3.0,3.0]}}
        self.assertEqual(sample_guard_px(CameraView(),settings),2)
        CameraView.metadata={}
        with self.assertRaisesRegex(ValueError,'generation scale'):
            sample_guard_px(CameraView(),settings)


if __name__=='__main__':
    unittest.main()
