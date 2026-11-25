"""Selección de originales sin usar datos reservados ni saltar filtros."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from synthetic_dataset import digest
from synthetic_seeds import seed_options, select_seed


class SeedTests(unittest.TestCase):
    def metadata(self):
        return {
            'labels': [{'id': 'A', 'text': 'A'}, {'id': 'B', 'text': 'B'}],
            'validation_by_class': [
                {'id': 'A', 'accepted_precision': .98, 'accepted': 12, 'support': 20},
                {'id': 'B', 'accepted_precision': .80, 'accepted': 10, 'support': 20}],
            'decision_policy': {'classes': {'0': {'supported': True}, '1': {'supported': True}}},
        }

    def test_orders_by_validation_without_minimum_support_or_confidence(self):
        metadata = self.metadata()
        metadata['validation_by_class'][0].update(accepted_precision=.01, accepted=0)
        metadata['decision_policy']['classes']['0']['supported'] = False
        self.assertEqual([row['id'] for row in seed_options(metadata)], ['B', 'A'])
        metadata['validation_by_class'][1]['accepted_precision'] = None
        self.assertEqual([row['id'] for row in seed_options(metadata)], ['A', 'B'])

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
                return np.tile([.12, .88], (len(sequences), 1))
            with patch('synthetic_seeds.dataset_dir', return_value=root), \
                 patch('synthetic_seeds.load_sequence', side_effect=lambda path: train if path.name == 'train.npz' else reserved), \
                 patch('synthetic_seeds.seed_probabilities', side_effect=predictions):
                confidence, path, points = select_seed('lsm', 'A', (None, metadata))
                self.assertEqual(path.name, 'train.npz')
                self.assertEqual(len(seen), 1)
                self.assertEqual(confidence, .12)
                np.testing.assert_array_equal(points, train)



if __name__ == '__main__':
    unittest.main()
