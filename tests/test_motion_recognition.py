import unittest
import numpy as np
from test_studio import points
from motion_features import trajectory_descriptor, motion_summary, fit_motion_profile, augment_timing
from recognition_features import regions, fit_temporal_guard, temporal_guard_accept
from recognition_decision import decision_details

class MotionRecognitionTests(unittest.TestCase):
    def sequence(self, moving=False, settled=False):
        raw=points()
        if moving:
            n=24 if settled else 30
            t=np.linspace(0,1,n)
            path=np.c_[.3*t,.12*np.sin(t*np.pi)]
            if settled:path=np.r_[path,np.repeat(path[-1:],30-n,axis=0)]
            regions(raw)[2][:,:,:2]+=path[:,None,:]
        return raw

    def test_same_posture_different_path_and_direction_are_distinguishable(self):
        static=self.sequence();moving=self.sequence(True)
        self.assertFalse(np.allclose(trajectory_descriptor(static),trajectory_descriptor(moving)))
        self.assertFalse(np.allclose(trajectory_descriptor(moving),trajectory_descriptor(moving[::-1])))
        # A wrist-local shape descriptor is identical for this translated hand.
        from recognition_features import local_hands
        np.testing.assert_allclose(local_hands(static),local_hands(moving),atol=1e-5)

    def test_absent_hand_has_no_fabricated_trajectory(self):
        raw=self.sequence(True);regions(raw)[2][10:20]=0
        result=trajectory_descriptor(raw)
        self.assertTrue(np.isfinite(result).all())
        self.assertTrue(np.all(result==0))

    def test_completion_learned_without_label_names(self):
        raw=np.stack([self.sequence()]*4+[self.sequence(True,True)]*4);y=np.repeat([0,1],4)
        profile=fit_motion_profile(raw,y)
        self.assertEqual(profile['moving_classes'],[1])
        warped,targets=augment_timing(raw,y)
        self.assertEqual(len(warped),3*len(raw))
        np.testing.assert_array_equal(warped[:len(raw)],raw)
        np.testing.assert_allclose(warped[-1,-1],raw[-1,-1])
        self.assertTrue(np.isfinite(warped).all())

    def test_versioned_guard_checks_order_and_preserves_legacy(self):
        static=self.sequence();moving=self.sequence(True)
        raw=np.stack([static]*4+[moving]*4);y=np.repeat([0,1],4)
        guard=fit_temporal_guard(raw,y,raw,y,descriptor_version='trajectory-v2')
        self.assertTrue(temporal_guard_accept(moving,1,guard))
        self.assertFalse(temporal_guard_accept(static,1,guard))
        result=decision_details(static,[.01,.99],{'temporal_guard':guard,'decision_threshold':.9},test_mode=True)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['code'],'temporal')
        self.assertTrue(temporal_guard_accept(moving,1,None))
        self.assertIsNone(fit_temporal_guard(raw,y,raw,y).get('descriptor_version'))

    def test_translation_and_camera_scale_do_not_change_path(self):
        raw=self.sequence(True);varied=raw.copy()
        for r in regions(varied):
            present=np.any(r[...,:3]!=0,axis=-1)
            r[...,:2]=np.where(present[...,None],r[...,:2]*.8+.05,0)
        np.testing.assert_allclose(trajectory_descriptor(raw),trajectory_descriptor(varied),atol=1e-5)
