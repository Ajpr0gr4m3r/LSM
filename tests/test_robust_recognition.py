import unittest
import numpy as np
import test_finger_geometry as fixtures
from recognition_features import (regions, hand_descriptor, fit_hand_guard, hand_guard_accept,
                                  augment_robust, prepare_sequence, DISCRIMINATIVE_PREPROCESSING)
from recognition_decision import evidence

# Ayudante de prueba para RobustRecognitionTests.
class RobustRecognitionTests(unittest.TestCase):
    # Ayudante de prueba para hand.
    def hand(self, folded=False):
        return fixtures.FingerGeometryTests().hand(folded)

    # Prueba automatizada: verifica articulated shape is scale invariant and rejects rival.
    def test_articulated_shape_is_scale_invariant_and_rejects_rival(self):
        straight, folded = self.hand(), self.hand(True)
        moved = straight.copy()
        for region in regions(moved):
            present = np.any(region[..., :3] != 0, axis=-1)
            region[..., :3] = np.where(present[..., None], region[..., :3] * .72 + [.08,.1,0], 0)
        describe = lambda p: hand_descriptor(p, True, 'finger-articulation-v3')
        np.testing.assert_allclose(describe(straight), describe(moved), atol=2e-5)
        self.assertGreater(np.linalg.norm(describe(straight)-describe(folded)), .1)
        raw=np.stack([straight]*4+[folded]*4); y=np.repeat([0,1],4)
        guard=fit_hand_guard(raw,y,raw,y,True,'finger-articulation-v3')
        self.assertTrue(hand_guard_accept(moved,0,guard))
        self.assertFalse(hand_guard_accept(folded,0,guard))
        self.assertLessEqual(evidence(moved,0,{'hand_guard':guard})['hand'],1.)

    # Prueba automatizada: verifica augmentation preserves missing hands labels and training volume.
    def test_augmentation_preserves_missing_hands_labels_and_training_volume(self):
        raw=np.stack([self.hand(),self.hand(True)]); original=raw.copy(); y=np.array([0,1])
        varied,targets=augment_robust(raw,y)
        self.assertEqual(varied.shape,(6,*raw.shape[1:]))
        np.testing.assert_array_equal(targets,np.tile(y,3))
        np.testing.assert_array_equal(raw,original)
        np.testing.assert_array_equal(varied[:2],raw)
        for p in varied:
            self.assertTrue(np.isfinite(prepare_sequence(p,DISCRIMINATIVE_PREPROCESSING)).all())
            np.testing.assert_array_equal(regions(p)[3],0)
        np.testing.assert_array_equal(varied,augment_robust(raw,y)[0])

    # Prueba automatizada: verifica historical descriptor remains unchanged.
    def test_historical_descriptor_remains_unchanged(self):
        p=self.hand()
        from recognition_features import local_hands, finger_geometry
        old=np.concatenate([local_hands(p),2*finger_geometry(p)],axis=-1)
        old=np.concatenate([np.median(old,axis=0),np.std(old,axis=0)])
        np.testing.assert_array_equal(hand_descriptor(p,True),old)
        with self.assertRaises(ValueError): hand_descriptor(p,True,'unknown')
