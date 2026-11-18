import base64
import types
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from config import FEATURE_DIM
from recognition_features import regions
from rig_overlay import rig_payload
from web_app import Runtime


# Ayudante de prueba para RigTests.
class RigTests(unittest.TestCase):
    # Prueba automatizada: verifica coordinates are not mirrored twice and absent points are hidden.
    def test_coordinates_are_not_mirrored_twice_and_absent_points_are_hidden(self):
        points = np.zeros(FEATURE_DIM, dtype=np.float32)
        pose, face, left, _ = regions(points)
        pose[11] = [.2, .3, .01, .9]
        pose[12] = [.8, .3, .01, .1]
        left[0] = [.7, .6, .01]
        face[0] = [np.nan, .5, 0]
        result = rig_payload(points, 640, 480)
        self.assertAlmostEqual(result['left'][0][0], .7)
        self.assertIsNotNone(result['pose'][11])
        self.assertIsNone(result['pose'][12])
        self.assertIsNone(result['face'][0])
        self.assertTrue(all(p is None for p in result['right']))
        self.assertEqual((result['width'], result['height']), (640,480))

    # Prueba automatizada: verifica frame returns rig only when requested without a trained model.
    def test_frame_returns_rig_only_when_requested_without_a_trained_model(self):
        runtime = Runtime()
        sid = runtime.new_session('lsm')
        runtime.session(sid).holistic = object()
        points = np.zeros(FEATURE_DIM, dtype=np.float32)
        regions(points)[2][0] = [.7,.6,.01]
        landmarks = [types.SimpleNamespace(x=.2, y=.4, visibility=0) for _ in range(33)]
        landmarks[0] = types.SimpleNamespace(x=.55, y=.2, visibility=.9)
        landmarks[11] = types.SimpleNamespace(x=.3, y=.4, visibility=.8)
        landmarks[23] = types.SimpleNamespace(x=.25, y=1.2, visibility=.9)
        tracked = types.SimpleNamespace(
            pose_landmarks=types.SimpleNamespace(landmark=landmarks),
            left_hand_landmarks=None, right_hand_landmarks=None,
        )
        fake = types.SimpleNamespace(mediapipe_detection=lambda image, model: (image, tracked),
                                     extract_keypoints=lambda result: points,
                                     hands_detected=lambda result: False)
        image = cv2.imencode('.jpg', np.zeros((16,32,3), np.uint8))[1].tobytes()
        payload = {'session': sid, 'image': base64.b64encode(image).decode(), 'mode': 'train'}
        with patch.dict('sys.modules', {'utils': fake}), patch.object(
            runtime, 'recover_hand_tracking', return_value=(tracked, False)
        ):
            self.assertNotIn('body_rig', runtime.frame(payload))
            for mode in ('train', 'test'):
                result = runtime.frame({**payload, 'mode': mode, 'show_hand_rig': True})
                self.assertEqual(result['body_rig'], {0: [.55, .2], 11: [.3, .4]})
                self.assertEqual(result['hand_rig'], [])
                self.assertIsNone(result['candidate'])
