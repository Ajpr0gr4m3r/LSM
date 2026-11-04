import unittest
import numpy as np
from config import FEATURE_DIM
from posture_vote import summary, combine, apply_vote


class PostureVoteTests(unittest.TestCase):
    def test_shape_is_preserved_and_reversing_a_track_changes_its_direction(self):
        sequence = np.zeros((1, 30, FEATURE_DIM + 158), dtype=np.float32)
        sequence[:, :, FEATURE_DIM:] = 1
        sequence[0, :, FEATURE_DIM-126] = np.arange(30)
        forward = summary(sequence)[0]
        reverse = summary(sequence[:, ::-1])[0]
        np.testing.assert_array_equal(forward[:474], reverse[:474])
        np.testing.assert_allclose(forward[474:], -reverse[474:])
        self.assertGreater(np.max(forward[474:]), 0.)

    def test_no_change_for_legacy_uncertain_or_agreeing_evidence(self):
        p = np.array([[.1,.9], [.6,.4]])
        self.assertIs(apply_vote(None,p,None),p)
        np.testing.assert_allclose(combine(p,np.array([[.2,.8],[.48,.52]]),.7),p)

    def test_batch_and_single_camera_window_use_identical_vote(self):
        seq = np.ones((2,30,FEATURE_DIM+158),np.float32)
        weights = np.zeros((2,summary(seq).shape[1]))
        vote = dict(weights=weights,bias=[4.,0.],threshold=.7)
        p = np.array([[.05,.95],[.9,.1]])
        batch = apply_vote(seq,p,vote)
        self.assertEqual(batch[0].argmax(),0)
        for i in range(len(p)):
            np.testing.assert_allclose(batch[i],apply_vote(seq[i],p[i],vote))
