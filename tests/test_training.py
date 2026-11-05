"""Pruebas del ciclo de guardado con datos sintéticos exclusivamente temporales."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import sign_languages as langs
import web_train


# Ayudante de prueba para TrainingTests.
class TrainingTests(unittest.TestCase):
    # Prueba automatizada: verifica candidate cannot replace a better validation model.
    def test_candidate_cannot_replace_a_better_validation_model(self):
        reference = {'accuracy':1., 'macro_f1':1., 'accepted_accuracy':1., 'coverage':1.}
        self.assertTrue(web_train.candidate_is_not_worse(reference, reference))
        for key in reference:
            worse = {**reference, key:.9}
            self.assertFalse(web_train.candidate_is_not_worse(worse, reference))
        self.assertTrue(web_train.candidate_is_not_worse(reference, None))

    # Prueba automatizada: verifica training publishes complete bundle.
    def test_training_publishes_complete_bundle(self, strategy="discriminative"):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.environ['MPLCONFIGDIR'] = str(root / 'cache')
            import tensorflow as tf
            import model
            from web_app import Runtime
            from config import SEQUENCE_LENGTH, FEATURE_DIM

            # Ayudante de prueba para tiny model.
            def tiny_model(num_classes, input_dim=FEATURE_DIM):
                result = tf.keras.Sequential([
                    tf.keras.layers.Input((SEQUENCE_LENGTH, input_dim)),
                    tf.keras.layers.GlobalAveragePooling1D(),
                    tf.keras.layers.Dense(num_classes, activation='softmax'),
                ])
                result.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
                return result

            points = np.ones((24, SEQUENCE_LENGTH, FEATURE_DIM), dtype=np.float32)
            targets = np.array([0] * 12 + [1] * 12)
            points[12:] *= .25
            points += np.random.default_rng(7).normal(0, .0001, points.shape).astype(np.float32)
            labels = langs.labels_for('lsm')[:2]
            with patch.object(langs, 'WEB_MODELS', root / 'models'), \
                 patch.object(web_train, 'WEB_DATA', root / 'data'), \
                 patch.object(web_train, 'MIN_SAMPLES', 5), \
                 patch.object(web_train, 'read_dataset', return_value=(points, targets, labels)), \
                 patch.object(web_train, 'training_provenance', return_value=(np.arange(len(targets)).astype(str), {'note':'Fixture sintética independiente'})), \
                 patch.object(web_train, 'persistent_split', side_effect=lambda y,g,path,**kwargs:__import__('web_dataset').split_per_class(y)), \
                 patch.object(model, 'build_web_model', side_effect=tiny_model), \
                 contextlib.redirect_stdout(io.StringIO()):
                web_train.train_language('lsm', 1, 'b' * 32, strategy=strategy, activate=False)
                runtime = Runtime()
                bundle = root / 'models' / 'lsm' / ('b' * 32)
                metadata = json.loads((bundle / 'metadata.json').read_text())
                loaded = tf.keras.models.load_model(bundle / 'model.keras', compile=False, safe_mode=True)
                self.assertEqual(metadata['language'], 'lsm')
                self.assertEqual(metadata['preprocessing'], 'articulation-motion-v5')
                self.assertEqual(loaded.input_shape[-1], FEATURE_DIM + 244)
                self.assertIsInstance(metadata['activated'], bool)
                if strategy == 'robust':
                    self.assertEqual(metadata['hand_guard']['descriptor_version'], 'finger-articulation-v3')
                    self.assertEqual(metadata['augmentation']['distance_scale'], [.72, 1.12])
                if strategy in ('trajectory', 'robust'):
                    self.assertEqual(metadata['temporal_guard']['descriptor_version'], 'trajectory-v2')
                    self.assertTrue(metadata['augmentation']['temporal_warp']['direction_preserved'])
                self.assertTrue(metadata['history'])
                self.assertIn('val_macro_f1', metadata['history'][0])
                self.assertIn('val_min_recall', metadata['history'][0])
                self.assertEqual(len(metadata['validation_by_class']), 2)
                self.assertEqual(len(metadata['split_hashes']['test']), metadata['split']['test'])
                self.assertTrue(metadata['augmentation']['training_only'])
                self.assertEqual(metadata['augmentation']['variants_per_original'], 8)
                self.assertEqual(metadata['augmentation']['camera_roll_degrees'], [4, 10])
                self.assertEqual(len(metadata['labels']), 2)
                self.assertEqual(sum(metadata['split'].values()), 24)
                self.assertEqual(loaded.output_shape[-1], 2)
                self.assertIsNone(runtime.load_model('lsm'))
                progress = json.loads((root / 'data' / 'jobs' / ('b' * 32 + '.json')).read_text())
                self.assertEqual(progress['state'], 'completed')
                for label in labels:
                    self.assertIn(f'{label["text"]} (8)', progress['data_warning'])

    # Prueba automatizada: verifica robust training publishes versioned guard.
    def test_robust_training_publishes_versioned_guard(self):
        self.test_training_publishes_complete_bundle(strategy='robust')

    # Prueba automatizada: verifica trajectory training publishes versioned guard.
    def test_trajectory_training_publishes_versioned_guard(self):
        self.test_training_publishes_complete_bundle(strategy='trajectory')

    # Prueba automatizada: verifica desktop loader skips empty and partial folders.
    def test_desktop_loader_skips_empty_and_partial_folders(self):
        import train
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'hola' / '0').mkdir(parents=True)
            (root / 'hola' / '1').mkdir(parents=True)
            (root / 'gracias' / '0').mkdir(parents=True)
            for i in range(train.SEQUENCE_LENGTH):
                np.save(root / 'hola' / '0' / f'frame_{i:03d}.npy', np.ones(train.FEATURE_DIM))
            np.save(root / 'gracias' / '0' / 'frame_000.npy', np.ones(train.FEATURE_DIM))
            with patch.object(train, 'DATA_PATH', str(root)), \
                 patch.object(train, 'ACTIONS', np.array(['hola', 'gracias'])), \
                 patch.object(train, 'NUM_SEQUENCES', 2), contextlib.redirect_stdout(io.StringIO()):
                X, y, _ = train.load_dataset()
            self.assertEqual(len(X), 1)
            self.assertEqual(y.tolist(), [0])


if __name__ == '__main__':
    unittest.main()
