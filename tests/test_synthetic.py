"""Generador de Dataset Sintético: motor, validación, importación y separación sin fugas."""
import base64
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

import sign_languages
import synthetic_dataset
import synthetic_generator as sg
import synthetic_media as media
from config import FEATURE_DIM, SEQUENCE_LENGTH


def hand(wrist=(.5, .6), size=.08, spread=1.):
    """Mano plausible: palma y cinco dedos rectos en abanico."""
    points = np.zeros((21, 3), np.float32)
    points[0, :2] = wrist
    for f, angle in enumerate(np.deg2rad([-60, -25, -8, 8, 25]) * spread):
        direction = np.array([np.sin(angle), -np.cos(angle)])
        base = np.array(wrist) + direction * size * (.45 if f == 0 else 1.)
        points[[1, 5, 9, 13, 17][f], :2] = base
        for j, joint in enumerate(sg.FINGERS[f][1:], start=1):
            points[joint, :2] = base + direction * size * .35 * j
    points[:, 2] = np.linspace(0, -.02, 21)
    return points


def sequence(moving=False, both=False):
    frames = np.zeros((SEQUENCE_LENGTH, FEATURE_DIM), np.float32)
    for t in range(SEQUENCE_LENGTH):
        pose = np.zeros((33, 4), np.float32)
        pose[[0, 11, 12, 13, 14, 15, 16], :2] = [[.5, .2], [.4, .4], [.6, .4], [.35, .55], [.65, .55], [.42, .6], [.58, .6]]
        pose[:, 3] = .9
        frames[t, :132] = pose.reshape(-1)
        frames[t, 132:366] = np.tile([.5, .25, 0], 78)
        shift = .004 * t if moving else 0.
        frames[t, 429:492] = hand((.55 + shift, .6)).reshape(-1)
        if both:
            frames[t, 366:429] = hand((.4, .62)).reshape(-1)
    return frames


class EngineTests(unittest.TestCase):
    def test_reproducible_and_seed_dependent(self):
        source = sequence(moving=True)
        a = sg.generate(source, 8, 'equilibrado', seed=11)
        b = sg.generate(source, 8, 'equilibrado', seed=11)
        c = sg.generate(source, 8, 'equilibrado', seed=12)
        self.assertEqual(len(a.samples), 8)
        for x, y in zip(a.samples, b.samples):
            np.testing.assert_array_equal(x, y)
        self.assertFalse(np.allclose(a.samples[0], c.samples[0]))

    def test_shape_and_values_preserved(self):
        for level in sg.LEVELS:
            result = sg.generate(sequence(both=True), 10, level, seed=1)
            self.assertEqual(len(result.samples), 10, (level, result.rejected))
            for sample in result.samples:
                self.assertEqual(sample.shape, (SEQUENCE_LENGTH, FEATURE_DIM))
                self.assertEqual(sample.dtype, np.float32)
                self.assertTrue(np.isfinite(sample).all())

    def test_anatomy_bone_directions_and_handedness_kept(self):
        source = sequence(both=True)
        params = sg.Params(hands=[dict(scale=1.12, palm=.95, fingers=[1.05, .96, 1.04, 1., .97],
                                       spread=[0] * 5, roll=0, yaw=0)] * 2, noise=0)
        out = sg.apply(source, params)
        for region in sg.HANDS:
            a, b = source[0, region].reshape(21, 3), out[0, region].reshape(21, 3)
            for x, y in sg.BONES:
                da, db = a[y, :2] - a[x, :2], b[y, :2] - b[x, :2]
                cos = da @ db / (np.linalg.norm(da) * np.linalg.norm(db))
                self.assertGreater(cos, .9999, 'cada hueso conserva su dirección')
        # Nunca se intercambian ni reflejan las manos.
        self.assertLess(out[0, 366], out[0, 429])
        missing = sequence()  # solo mano derecha
        out = sg.generate(missing, 5, 'avanzado', seed=3).samples
        for sample in out:
            self.assertFalse(np.any(sample[:, 366:429]), 'no aparece una mano que no existía')

    def test_static_photo_gets_no_invented_motion(self):
        static = np.repeat(sequence()[:1], SEQUENCE_LENGTH, axis=0)
        result = sg.generate(static, 20, 'avanzado', seed=5, static=True)
        self.assertEqual(len(result.samples), 20)
        palm = .08
        for sample in result.samples:
            # Solo temblor de detección (< 1/4 de palma) y sin desplazamiento sostenido.
            self.assertLess(sg.motion_extent(sample), palm / 4)
            wrist = sample[:, 429:431]
            self.assertLess(np.linalg.norm(wrist[:5].mean(0) - wrist[-5:].mean(0)), palm / 10)
        self.assertEqual([p.speed for p in result.params], [1.] * 20)
        self.assertEqual([p.offset for p in result.params], [0] * 20)

    def test_validator_rejects_invalid_and_deformed(self):
        source = sequence()
        validator = sg.Validator(sg.LEVELS['equilibrado'])
        bad = source.copy(); bad[3, 430] = np.nan
        self.assertEqual(validator.check(source, bad), 'valores_invalidos')
        self.assertEqual(validator.check(source, source[:10]), 'dimensiones')
        deformed = source.copy()
        for t in range(SEQUENCE_LENGTH):
            h = deformed[t, 429:492].reshape(21, 3)
            h[8, :2] = h[7, :2] + (h[8, :2] - h[7, :2]) * 2.5  # punta del índice imposible
            deformed[t, 429:492] = h.reshape(-1)
        self.assertIn(validator.check(source, deformed), ('deformacion', 'proporciones', 'forma_de_seña'))
        outside = source.copy(); outside[:, 429:492:3] += .8
        self.assertEqual(validator.check(source, outside), 'fuera_de_cuadro')
        self.assertIsNone(validator.check(source, source))

    def test_duplicates_rejected_and_counted(self):
        source = sequence()
        with patch.object(sg, 'sample_params', side_effect=lambda *a, **k: sg.Params(
                hands=[dict(scale=1, palm=1, fingers=[1] * 5, spread=[0] * 5, roll=0, yaw=0)] * 2, noise=0)):
            result = sg.generate(source, 3, 'conservador', seed=1)
        self.assertEqual(result.samples, [])
        self.assertGreater(result.rejected['duplicado'], 0)

    def test_confusable_signs_use_smaller_finger_changes(self):
        rng = np.random.default_rng(0)
        normal = [sg.sample_params(sg.LEVELS['avanzado'], rng, False, False) for _ in range(200)]
        rng = np.random.default_rng(0)
        strict = [sg.sample_params(sg.LEVELS['avanzado'], rng, False, True) for _ in range(200)]
        spread = lambda ps: max(abs(f - 1) for p in ps for h in p.hands for f in h['fingers'])
        self.assertLessEqual(spread(strict), sg.LEVELS['conservador'].finger + 1e-9)
        self.assertGreater(spread(normal), sg.LEVELS['conservador'].finger)
        self.assertTrue(all(s == 0 for p in strict for h in p.hands for s in h['spread']))
        for label in ('B', 'E', 'G', 'H', 'M', 'N', 'Ñ'):
            self.assertTrue(sg.label_is_confusable(label))

    def test_semantic_check_discards(self):
        result = sg.generate(sequence(), 4, 'equilibrado', seed=2,
                             semantic_check=lambda batch: [False] * len(batch), max_attempts_factor=2)
        self.assertEqual(result.samples, [])
        self.assertGreater(result.rejected['modelo_no_la_reconoce'], 0)

    def test_cancel(self):
        result = sg.generate(sequence(), 50, 'equilibrado', seed=2, cancelled=lambda: True)
        self.assertTrue(result.cancelled)

    def test_compatible_with_training_features(self):
        from recognition_features import CHEST_PREPROCESSING, FINGER_PREPROCESSING, feature_dimension, prepare_sequence
        sample = sg.generate(sequence(both=True), 1, 'equilibrado', seed=4).samples[0]
        for preprocessing in (FINGER_PREPROCESSING, CHEST_PREPROCESSING):
            self.assertEqual(prepare_sequence(sample, preprocessing).shape,
                             (SEQUENCE_LENGTH, feature_dimension(preprocessing)))


class StoreAndLeakTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(Path(__file__).resolve().parents[1] / 'web_data' / 'vocabulary', self.tmp / 'vocabulary')
        self.patches = [patch.object(sign_languages, 'WEB_DATA', self.tmp),
                        patch.object(synthetic_dataset, 'WEB_DATA', self.tmp)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_stored_separately_with_provenance_and_never_in_real_dataset(self):
        from web_dataset import read_dataset
        synthetic_dataset.save_synthetic('lsm', 'hola', sequence(), {'origin': 'image', 'source_digest': 'abc',
                                                                    'transform': {'seed': 1}})
        self.assertEqual(synthetic_dataset.inventory('lsm'), {'hola': 1})
        path = next((self.tmp / 'synthetic' / 'lsm' / 'hola').glob('*.npz'))
        points, meta = synthetic_dataset.read_synthetic(path)
        self.assertTrue(meta['synthetic'])
        self.assertEqual(meta['source_digest'], 'abc')
        self.assertFalse((self.tmp / 'datasets').exists(), 'el dataset real no se toca')

    def test_dataset_view_includes_saved_generation_and_training_can_select_it(self):
        synthetic_dataset.save_synthetic('lsm', 'hola', sequence(), {
            'origin': 'dataset', 'source_digest': 'training-source'})
        rows = synthetic_dataset.with_synthetic_counts('lsm', [
            {'id': 'hola', 'text': 'Hola', 'samples': 30},
            {'id': 'gracias', 'text': 'Gracias', 'samples': 40},
        ])
        self.assertEqual(rows[0]['synthetic_samples'], 1)
        self.assertEqual(rows[0]['total_samples'], 31)
        self.assertEqual(rows[0]['samples'], 30)
        self.assertEqual(rows[1]['synthetic_samples'], 0)
        points, targets, summary = synthetic_dataset.select_for_training(
            'lsm', ['hola', 'gracias'], {'training-source'}, {'reserved-source'},
            [20, 30], mode='mixed')
        self.assertEqual(len(points), 1)
        self.assertEqual(summary['used'], {'hola': 1, 'gracias': 0})
        np.testing.assert_array_equal(targets, [0])

    def test_no_leak_between_training_and_evaluation(self):
        train_src, eval_src = sequence(), sequence(moving=True)
        dt, de = synthetic_dataset.digest(train_src), synthetic_dataset.digest(eval_src)
        for i, (origin, source) in enumerate([('dataset', dt), ('dataset', dt), ('dataset', de), ('video', de),
                                              ('image', 'foto-independiente'), ('dataset', 'otra-toma')]):
            synthetic_dataset.save_synthetic('lsm', 'hola', sequence(), {'origin': origin, 'source_digest': source},
                                             sample_id=f'{i:032x}')
        points, targets, summary = synthetic_dataset.select_for_training(
            'lsm', ['hola'], train_digests={dt}, eval_digests={de}, real_train_counts=[10], mode='mixed', ratio=1.)
        self.assertEqual(len(points), 3)  # 2 de la toma de entrenamiento + 1 foto independiente
        self.assertEqual(summary['excluded_leak'], 2)
        self.assertEqual(summary['excluded_other_source'], 1)
        _, _, limited = synthetic_dataset.select_for_training(
            'lsm', ['hola'], {dt}, {de}, real_train_counts=[1], mode='mixed', ratio=1.)
        self.assertEqual(limited['used'], {'hola': 1}, 'la proporción limita las sintéticas')
        empty, _, real = synthetic_dataset.select_for_training('lsm', ['hola'], {dt}, {de}, [10], mode='real')
        self.assertEqual(len(empty), 0)


class MediaTests(unittest.TestCase):
    """La detección real usa MediaPipe; aquí se simula para probar el resto del flujo."""

    def fake_detector(self, plan):
        frames = iter(plan)

        class Fake:
            def __init__(self, language, static):
                pass

            def __call__(self, image, mirror=True):
                has_hand = next(frames)
                points = sequence()[0] if has_hand else np.zeros(FEATURE_DIM, np.float32)
                if not has_hand:
                    points[:132] = sequence()[0, :132]
                return {'points': points, 'hands': [False, has_hand], 'any_hand': has_hand,
                        'quality': {'usable': has_hand}, 'rig': {'hands': [None, None], 'body': {}}}

            def close(self):
                pass
        return Fake

    def test_image_import_builds_static_sequence(self):
        image = cv2.imencode('.png', np.full((120, 160, 3), 200, np.uint8))[1].tobytes()
        with patch.object(media, 'Detector', self.fake_detector([True])):
            result = media.image_source(image, 'lsm')
        self.assertTrue(result['static'])
        self.assertEqual(result['sequence'].shape, (SEQUENCE_LENGTH, FEATURE_DIM))
        self.assertTrue(np.all(result['sequence'] == result['sequence'][0]))
        with patch.object(media, 'Detector', self.fake_detector([False])):
            with self.assertRaises(media.MediaError):
                media.image_source(image, 'lsm')
        with self.assertRaises(media.MediaError):
            media.decode_image(b'no es una imagen')

    def test_video_import_samples_at_capture_rate_and_trims(self):
        path = Path(tempfile.mkdtemp()) / 'clip.avi'
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 30, (160, 120))
        for i in range(90):  # 3 s a 30 fps
            writer.write(np.full((120, 160, 3), i % 255, np.uint8))
        writer.release()
        plan = [False] * 3 + [True] * 24 + [False] * 3  # 30 fotogramas muestreados a 10 fps
        with patch.object(media, 'Detector', self.fake_detector(plan)):
            result = media.video_source(path.read_bytes(), 'lsm', suffix='.avi')
        self.assertEqual(result['frames_read'], 30, 'muestrea a 10 fps como la cámara')
        self.assertEqual(result['sequence'].shape, (SEQUENCE_LENGTH, FEATURE_DIM))
        self.assertFalse(result['static'])
        with patch.object(media, 'Detector', self.fake_detector([False] * 30)):
            with self.assertRaises(media.MediaError):
                media.video_source(path.read_bytes(), 'lsm', suffix='.avi')
        shutil.rmtree(path.parent)

    def test_camera_recording_is_processed_like_a_live_take(self):
        jpeg = cv2.imencode('.jpg', np.full((480, 640, 3), 90, np.uint8))[1].tobytes()
        plan = [False] * 2 + [True] * 26 + [False] * 2  # 3 s a 10 fps
        with patch.object(media, 'Detector', self.fake_detector(plan)):
            result = media.camera_source([jpeg] * 30, 'lsm')
        self.assertEqual(result['kind'], 'camera')
        self.assertFalse(result['static'])
        self.assertEqual(result['sequence'].shape, (SEQUENCE_LENGTH, FEATURE_DIM))
        # Perfil de frases: 6 s a 10 fps → 1 de cada 2 fotogramas.
        with patch.object(media, 'Detector', self.fake_detector([True] * 60)):
            phrase = media.camera_source([jpeg] * 60, 'lsm_frases')
        self.assertEqual(phrase['sequence'].shape, (SEQUENCE_LENGTH, FEATURE_DIM))
        with self.assertRaises(media.MediaError):
            media.camera_source([], 'lsm')
        with self.assertRaises(media.MediaError):
            media.camera_source([jpeg] * (media.MAX_CAMERA_FRAMES + 1), 'lsm')

    def test_studio_accepts_recordings_and_rejects_bad_payloads(self):
        import synthetic_jobs
        studio = synthetic_jobs.SyntheticStudio()
        jpeg = base64.b64encode(cv2.imencode('.jpg', np.zeros((48, 64, 3), np.uint8))[1].tobytes()).decode()
        with patch.object(media, 'Detector', self.fake_detector([True] * 30)):
            source = studio.add_source('lsm', None, None, None, frames=[jpeg] * 30)
            for _ in range(100):
                if studio.sources[source['id']]['state'] != 'processing':
                    break
                time.sleep(.05)
        stored = studio.sources[source['id']]
        self.assertEqual((stored['kind'], stored['state']), ('camera', 'ready'))
        self.assertTrue(stored['name'].startswith('Grabación'))
        for bad in ([], ['%%%'], 'texto'):
            with self.assertRaises(ValueError):
                studio.add_source('lsm', 'x', None, None, frames=bad)

    def test_real_mediapipe_runs_on_images(self):
        """MediaPipe real: una imagen sin personas no produce manos (no inventa detecciones)."""
        image = cv2.imencode('.jpg', np.full((240, 320, 3), 127, np.uint8))[1].tobytes()
        with self.assertRaises(media.MediaError):
            media.image_source(image, 'lsm')


class JobTests(unittest.TestCase):
    def test_dynamic_sign_rejects_photos(self):
        import synthetic_jobs
        studio = synthetic_jobs.SyntheticStudio()
        studio.sources['s'] = {'id': 's', 'language': 'lsm', 'name': 'foto.jpg', 'kind': 'image', 'state': 'ready',
                               'static': True, 'sequence': sequence(), 'digest': 'd', 'cancel': False}
        with patch.object(synthetic_jobs.SyntheticStudio, '_label_is_dynamic', return_value=True):
            with self.assertRaisesRegex(ValueError, 'movimiento'):
                studio.start('lsm', 'J', ['s'], 10, 'equilibrado', 1)
        with patch.object(synthetic_jobs.SyntheticStudio, '_label_is_dynamic', return_value=False):
            job = studio.start('lsm', 'A', ['s'], 5, 'conservador', 1)
            for _ in range(200):
                if studio.jobs[job['id']]['state'] != 'running':
                    break
                time.sleep(.05)
        public = studio.public_job(studio.jobs[job['id']])
        self.assertEqual((public['state'], public['done']), ('done', 5))
        self.assertEqual(len(public['previews']), 5)


if __name__ == '__main__':
    unittest.main()


class TrainingBatchTests(unittest.TestCase):
    def test_batches_cover_every_row_once_per_epoch_with_class_weights(self):
        from web_train import BatchesFromArrays
        x = np.arange(50, dtype=np.float32).reshape(50, 1, 1)
        y = np.eye(2, dtype=np.float32)[np.arange(50) % 2]
        batches = BatchesFromArrays(x, y, 16, {0: 1., 1: 3.})
        self.assertEqual(len(batches), 4)
        seen = np.concatenate([batches[i][0].ravel() for i in range(len(batches))])
        self.assertEqual(sorted(seen.tolist()), list(range(50)))
        xb, yb, wb = batches[0]
        np.testing.assert_array_equal(wb, np.where(yb.argmax(1) == 1, 3., 1.))
        before = batches.order.copy()
        batches.on_epoch_end()
        self.assertFalse(np.array_equal(before, batches.order))
