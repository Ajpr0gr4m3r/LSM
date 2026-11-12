import base64
import types
import unittest
from unittest.mock import patch
import cv2
import numpy as np
import web_app


class FrameTimingTests(unittest.TestCase):
    def run_capture(self, interrupt=False):
        runtime = web_app.Runtime()
        sid = runtime.new_session('lsm')
        session = runtime.session(sid)
        session.holistic = object()
        session.capture = dict(points=[], hands=0, quality_bad=0, wait_frames=0)
        clock = [10.0]
        session.last_frame = 9.9
        image = base64.b64encode(cv2.imencode('.jpg', np.zeros((32,32,3), np.uint8))[1]).decode()
        points = np.ones(web_app.FEATURE_DIM, np.float32)
        def detect(image, detector):
            clock[0] += 2.5  # Equipo lento: no confundir procesamiento con red.
            return image, object()
        def quality(image, points):
            clock[0] += 1.5  # Trabajo posterior a MediaPipe también debe excluirse.
            return dict(warnings=[], scope='hands')
        fake = types.SimpleNamespace(mediapipe_detection=detect, extract_keypoints=lambda r:points,
                                     hands_detected=lambda r:True)
        with patch.dict('sys.modules', {'utils':fake}), patch.object(runtime, 'training', return_value=False), \
             patch.object(runtime, 'recover_hand_tracking', side_effect=lambda s,i,r,n:(r,False)), \
             patch('web_app.time.monotonic', side_effect=lambda:clock[0]), \
             patch('web_app.landmark_quality', return_value={'usable':True}), \
             patch('web_app.hand_image_quality', side_effect=quality), \
             patch('web_app.save_draft', return_value='draft') as save:
            for i in range(30):
                clock[0] += 2 if interrupt and i == 2 else .1
                result = runtime.frame({'session':sid, 'image':image, 'mode':'collect', 'confirmation_ack':None})
                self.assertEqual(session.last_frame, clock[0])
                if interrupt and i == 2:
                    self.assertEqual(result['phase'], 'capture-interrupted')
                    self.assertIsNone(session.capture)
                    save.assert_not_called()
                    self.assertIsNotNone(session.holistic)
                    return
                self.assertEqual(result['captured'], i+1)
            self.assertEqual(result['draft_id'], 'draft')
            save.assert_called_once()
            self.assertEqual(len(save.call_args.args[1]),30)

    def test_slow_processing_completes_all_thirty_frames(self):
        self.run_capture()

    def test_real_gap_discards_partial_take_without_closing_camera(self):
        self.run_capture(interrupt=True)

    def test_brief_tracking_gap_preserves_buffer_but_long_gap_clears_it(self):
        session = web_app.Session('lsm')
        session.frames.extend(['frame-1', 'frame-2'])
        session.stable_label, session.stable_count = 'hola', 2

        self.assertEqual(session.update_recognition_tracking(False, False, 10), 'tracking-gap')
        self.assertEqual(session.update_recognition_tracking(True, False, 10.2), 'tracking-gap')
        self.assertEqual(list(session.frames), ['frame-1', 'frame-2'])
        self.assertEqual(session.stable_count, 2)
        self.assertEqual(session.update_recognition_tracking(True, True, 10.4), 'observing')
        self.assertEqual(len(session.frames), 2)

        session.update_recognition_tracking(False, False, 11)
        session.update_recognition_tracking(True, True, 11.6)
        self.assertFalse(session.frames)
        self.assertIsNone(session.stable_label)
        self.assertEqual(session.stable_count, 0)

        session.gesture_confirmed = True
        session.last_confirmed = 'hola'
        for frame in range(5):
            session.update_recognition_tracking(False, False, 12 + frame * .1)
        self.assertFalse(session.gesture_confirmed)
        self.assertIsNone(session.last_confirmed)

    def test_completion_time_recorded_after_failure(self):
        runtime=web_app.Runtime();sid=runtime.new_session('lsm')
        with patch.object(runtime,'_process_frame',side_effect=ValueError('failed')), \
             patch('web_app.time.monotonic',return_value=42):
            with self.assertRaises(ValueError):runtime._frame({'session':sid})
        self.assertEqual(runtime.session(sid).last_frame,42)
