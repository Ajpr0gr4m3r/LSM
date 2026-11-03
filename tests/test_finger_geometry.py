import unittest
import numpy as np
from config import FEATURE_DIM
from recognition_features import (regions, finger_geometry, prepare_sequence, feature_dimension,
    FINGER_PREPROCESSING, STABLE_PREPROCESSING, fit_hand_guard, hand_guard_accept)
from web_train import class_decisions


class FingerGeometryTests(unittest.TestCase):
    def hand(self, folded=False):
        points = np.zeros((30, FEATURE_DIM), np.float32)
        hand = regions(points)[2]
        hand[:, 0] = [.5, .8, 0]
        for finger, base in enumerate((1, 5, 9, 13, 17)):
            for joint in range(4):
                y = .72 - .03 * joint
                if folded and joint > 1: y = .72 + .01 * joint
                hand[:, base+joint] = [.43 + .035 * finger, y, .002 * joint]
        return points

    def test_geometry_distinguishes_flexion_and_retains_missing_hand(self):
        straight, folded = self.hand(), self.hand(True)
        geometry = finger_geometry(straight)
        self.assertEqual(geometry.shape, (30, 30))
        self.assertTrue(np.all(geometry[:, :5] > finger_geometry(folded)[:, :5]))
        self.assertTrue(np.all(geometry[:, 15:] == 0))
        self.assertTrue(np.all(finger_geometry(np.zeros_like(straight)) == 0))
        moved = straight.copy()
        hand = regions(moved)[2]
        hand[:] = hand * .7 + [.1, .12, .03]
        np.testing.assert_allclose(geometry, finger_geometry(moved), atol=1e-5)

    def test_new_version_preserves_all_old_channels_and_load_dimensions(self):
        points = self.hand()
        old = prepare_sequence(points, STABLE_PREPROCESSING)
        new = prepare_sequence(points, FINGER_PREPROCESSING)
        np.testing.assert_array_equal(old, new[:, :FEATURE_DIM+128])
        self.assertEqual(new.shape[-1], feature_dimension(FINGER_PREPROCESSING))
        self.assertTrue(np.isfinite(new).all())
        self.assertEqual(feature_dimension(None), FEATURE_DIM)

    def test_competing_class_rejected_even_inside_wide_radius(self):
        a,b = self.hand(),self.hand(True)
        examples=np.stack([a]*4+[b]*4); targets=np.array([0]*4+[1]*4)
        guard=fit_hand_guard(examples,targets,examples,targets,contrastive=True)
        self.assertTrue(hand_guard_accept(a,0,guard))
        self.assertTrue(hand_guard_accept(b,1,guard))
        for item in guard['classes']: item['max_distance']=1e6
        self.assertFalse(hand_guard_accept(b,0,guard))
        self.assertFalse(hand_guard_accept(a,1,guard))
        ambiguous=fit_hand_guard(np.stack([a]*8),targets,np.stack([a]*8),targets,contrastive=True)
        self.assertFalse(hand_guard_accept(a,0,ambiguous))

    def test_class_metrics_expose_confusion_hidden_by_aggregate(self):
        probabilities=np.array([[.99,.01],[.99,.01],[.99,.01],[.01,.99]])
        result=class_decisions(probabilities,np.array([0,0,1,1]),[True]*4,.85,.15,[{'id':'a','text':'A'},{'id':'b','text':'B'}])
        self.assertAlmostEqual(result[0]['precision'],2/3)
        self.assertEqual(result[1]['recall'],.5)
        self.assertEqual(result[1]['accepted'],1)

    def test_group_split_balances_classes_without_starving_training(self):
        from dataset_tools import grouped_split
        # Two large consecutive batches and two single examples of class 0.
        y=np.array([0]*62+[1]*80)
        groups=np.array(['a']*30+['b']*30+['c','d']+[f'other-{i}' for i in range(80)])
        train,val,test=grouped_split(y,groups)
        self.assertGreaterEqual(np.sum(y[train]==0),24)
        self.assertGreaterEqual(np.sum(y[val]==0),3)
        for a,b in ((train,val),(train,test),(val,test)):
            self.assertFalse(set(groups[a]) & set(groups[b]))
