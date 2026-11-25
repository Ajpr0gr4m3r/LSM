"""Selección de originales sin usar datos reservados ni saltar filtros."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from synthetic_dataset import digest
from synthetic_seeds import seed_options, select_seed, seed_accepts


class SeedTests(unittest.TestCase):
    def metadata(self):
        return {
            'labels': [{'id': 'A', 'text': 'A'}, {'id': 'B', 'text': 'B'}],
            'validation_by_class': [
                {'id': 'A', 'accepted_precision': .98, 'accepted': 12, 'support': 20},
                {'id': 'B', 'accepted_precision': .80, 'accepted': 10, 'support': 20}],
            'decision_policy': {'classes': {'0': {'supported': True}, '1': {'supported': True}}},
        }

    def test_requires_measured_validation_support(self):
        metadata = self.metadata()
        self.assertEqual([row['id'] for row in seed_options(metadata)], ['A'])
        metadata['decision_policy']['classes']['0']['supported'] = False
        self.assertEqual(seed_options(metadata), [])
        metadata['decision_policy']['classes']['0']['supported'] = True
        metadata['validation_by_class'][0]['accepted'] = 2
        self.assertEqual(seed_options(metadata), [])

    def test_selects_only_training_sources_even_if_reserved_is_more_confident(self):
        metadata = self.metadata()
        train = np.ones((30, 492), np.float32)
        reserved = train * 2
        metadata['split_hashes'] = {'train': [digest(train), digest(reserved)],
                                     'validation': [digest(reserved)], 'test': []}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'A').mkdir()
            paths = [root / 'A' / name for name in ('train.npz', 'validation.npz')]
            for path in paths:
                path.touch()
            seen = []
            def predictions(model, meta, sequences):
                seen.extend(sequences)
                return np.tile([.96, .04], (len(sequences), 1))
            with patch('synthetic_seeds.dataset_dir', return_value=root), \
                 patch('synthetic_seeds.load_sequence', side_effect=lambda path: train if path.name == 'train.npz' else reserved), \
                 patch('synthetic_seeds.sequence_quality', return_value={'usable_ratio': 1.}), \
                 patch('synthetic_seeds.seed_probabilities', side_effect=predictions), \
                 patch('synthetic_seeds.decision_details', return_value={'accepted': True}):
                confidence, path, points = select_seed('lsm', 'A', (None, metadata))
                self.assertEqual(path.name, 'train.npz')
                self.assertEqual(len(seen), 1)
                self.assertEqual(confidence, .96)
                np.testing.assert_array_equal(points, train)

    def test_high_confidence_still_requires_filters_and_correct_class(self):
        with patch('synthetic_seeds.decision_details', return_value={'accepted': False}):
            self.assertFalse(seed_accepts(None, np.array([.99, .01]), {}, 0))
        with patch('synthetic_seeds.decision_details', return_value={'accepted': True}):
            self.assertFalse(seed_accepts(None, np.array([.89, .11]), {}, 0))
            self.assertFalse(seed_accepts(None, np.array([.01, .99]), {}, 0))
            self.assertTrue(seed_accepts(None, np.array([.96, .04]), {}, 0))


if __name__ == '__main__':
    unittest.main()
