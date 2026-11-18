"""Perfil «LSM · Frases»: tomas de ≈6 s guardadas como 30 fotogramas, sin afectar las letras."""
import base64
import types
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import alphabets
import sign_languages as langs
import vocabulary_catalog
import web_app


class PhraseProfileTests(unittest.TestCase):
    def test_profile_is_separate_from_letters(self):
        self.assertEqual(langs.frame_stride('lsm'), 1)
        self.assertEqual(langs.frame_stride('lsm_frases'), 2)
        self.assertNotEqual(langs.dataset_dir('lsm'), langs.dataset_dir('lsm_frases'))
        self.assertNotEqual(langs.model_dir('lsm'), langs.model_dir('lsm_frases'))
        self.assertIsNone(alphabets.alphabet_status('lsm_frases', [], None))
        texts = [e for c in vocabulary_catalog.catalog_for('lsm_frases') for e in c['entries']]
        self.assertIn('Hola, ¿cómo estás?', texts)
        self.assertNotIn('Hola, ¿cómo estás?', [e for c in vocabulary_catalog.catalog_for('lsm') for e in c['entries']])
        for text in texts:
            self.assertEqual(langs.clean_sign_name(text), text)
        self.assertEqual(len(texts), len({t.casefold() for t in texts}))

    def test_capture_keeps_one_of_every_two_camera_frames(self):
        runtime = web_app.Runtime()
        sid = runtime.new_session('lsm_frases')
        session = runtime.session(sid)
        session.holistic = object()
        session.capture = dict(points=[], hands=0, quality_bad=0, wait_frames=0)
        clock = [10.0]
        session.last_frame = 9.9
        image = base64.b64encode(cv2.imencode('.jpg', np.zeros((32, 32, 3), np.uint8))[1]).decode()
        counter = [0]

        def keypoints(_):
            counter[0] += 1
            return np.full(web_app.FEATURE_DIM, counter[0], np.float32)

        fake = types.SimpleNamespace(mediapipe_detection=lambda image, detector: (image, object()),
                                     extract_keypoints=keypoints, hands_detected=lambda r: True)
        with patch.dict('sys.modules', {'utils': fake}), patch.object(runtime, 'training', return_value=False), \
             patch.object(runtime, 'recover_hand_tracking', side_effect=lambda s, i, r, n: (r, False)), \
             patch('web_app.time.monotonic', side_effect=lambda: clock[0]), \
             patch('web_app.landmark_quality', return_value={'usable': True}), \
             patch('web_app.hand_image_quality', return_value=dict(warnings=[], scope='hands')), \
             patch('web_app.save_draft', return_value='draft') as save:
            for i in range(59):
                clock[0] += .1
                result = runtime.frame({'session': sid, 'image': image, 'mode': 'collect', 'confirmation_ack': None})
                if i < 58:
                    self.assertIsNone(result.get('draft_id'))
                    self.assertEqual(result['captured'], i // 2 + 1)
        self.assertEqual(result['draft_id'], 'draft')
        saved = save.call_args.args[1]
        self.assertEqual(len(saved), 30)
        # Fotogramas 1, 3, 5… 59: la toma cubre 59 fotogramas de cámara (≈6 s a 10 fps).
        self.assertEqual([int(frame[0]) for frame in saved], list(range(1, 60, 2)))

    def test_recognition_waits_for_six_seconds_and_uses_the_same_sampling(self):
        runtime = web_app.Runtime()
        session = web_app.Session('lsm_frases')
        seen = []

        class Model:
            def __call__(self, batch, training=False):
                seen.append(batch)
                return types.SimpleNamespace(numpy=lambda: np.array([[.97, .03]]))

        metadata = {'labels': [{'id': 'a', 'text': 'Hola, ¿cómo estás?'}, {'id': 'b', 'text': 'Gracias'}],
                    'preprocessing': None, 'decision_input': 'single-window-v1', 'stability_frames': 3}
        sequences = []

        def prepare(raw, preprocessing):
            sequences.append(raw.copy())
            return raw

        with patch.object(runtime, 'load_model', return_value=(Model(), metadata)), \
             patch('web_app.prepare_sequence', side_effect=prepare), \
             patch('web_app.decision_details', return_value={'accepted': True, 'reason': None, 'code': None}):
            clock = 100.0
            for i in range(1, 61):
                clock += .1
                output = {'confidence': 0, 'stability': 0}
                result = runtime.recognize(session, np.full(web_app.FEATURE_DIM, i, np.float32), True,
                                           {'usable': True, 'message': ''}, output, clock, {'mode': 'test'})
                if i < 60:
                    self.assertFalse(seen, 'no debe decidir antes de reunir ≈6 s')
                    self.assertEqual(result['buffer'], i // 2)
        self.assertEqual(len(seen), 1)
        window = sequences[-1]
        self.assertEqual(window.shape[0], 30)
        # Termina en el fotograma más reciente y salta de 2 en 2, igual que la captura.
        self.assertEqual([int(f[0]) for f in window], list(range(2, 61, 2)))

    def test_letters_profile_unchanged(self):
        session = web_app.Session('lsm')
        self.assertEqual(session.stride, 1)
        self.assertEqual(session.frames.maxlen, 45)


if __name__ == '__main__':
    unittest.main()
