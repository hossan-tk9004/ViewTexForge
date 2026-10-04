"""Regression cases for capture-center depth alignment and strict rejection."""
import unittest
import numpy as np

from standalone_texture_merge.dataset_io import View
from standalone_texture_merge.projection import sample_weight
from standalone_texture_merge.settings import Settings


class PixelCenterDepthTests(unittest.TestCase):
    def fixture(self):
        metadata = dict(meters_per_world_unit=1.,
            camera=dict(camera_type='ORTHO',matrix_world=np.eye(4).tolist(),
                        projection_matrix=np.diag([1.,1.,-.02,1.]).tolist(),
                        clip_start=.01,clip_end=100.),render=dict(resolution=[64,64]))
        centers=-1+2*(np.arange(64)+.5)/64
        depth=np.tile(5-4*centers,(64,1)).astype(np.float32)
        view=View('slope',metadata,np.ones((64,64,3),np.float32),depth,
                  np.ones((64,64),bool),np.ones((64,64),bool))
        x=np.linspace(.0625,.125,1001,endpoint=False)
        points=np.column_stack((x,np.full(len(x),.125),4*x-5))
        normal=np.array([-4.,0,1.]);normal/=np.linalg.norm(normal)
        raster=dict(points=points,normals=np.tile(normal,(len(x),1)),
                    face_normals=np.tile(normal,(len(x),1)))
        return raster,view

    def test_visible_tilted_plane_retains_uniform_weight(self):
        raster,view=self.fixture()
        settings=Settings(visibility_mode='STRICT')
        _,weight,_=sample_weight(raster,view,settings,
            visibility=np.ones(len(raster['points']),bool),return_diagnostics=True)
        self.assertTrue(np.all(weight>settings.min_weight_sum))
        self.assertLess(float(weight.max()-weight.min()),1e-5)

    def test_wrong_front_depth_still_rejected(self):
        raster,view=self.fixture()
        view.depth[28,35]-=0.1
        settings=Settings(visibility_mode='STRICT')
        _,weight,_=sample_weight(raster,view,settings,
            visibility=np.ones(len(raster['points']),bool),return_diagnostics=True)
        self.assertTrue(np.any(weight==0.))
        self.assertTrue(np.any(weight>settings.min_weight_sum))

    def test_legacy_keeps_old_pixel_depth_rule(self):
        raster,view=self.fixture()
        settings=Settings(visibility_mode='LEGACY')
        _,weight,_=sample_weight(raster,view,settings,return_diagnostics=True)
        self.assertEqual(int((weight<=settings.min_weight_sum).sum()),215)


if __name__=='__main__':
    unittest.main()
