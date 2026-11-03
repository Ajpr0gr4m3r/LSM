import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from validation_protocol import calibration_split, validation_support, wilson_interval


# Ayudante de prueba para ValidationProtocolTests.
class ValidationProtocolTests(unittest.TestCase):
    # Ayudante de prueba para data.
    def data(self):
        # Eight independent validation sessions, each with both classes twice.
        y = np.tile([0, 0, 1, 1], 8)
        groups = np.repeat([f'group-{i}' for i in range(8)], 4)
        return y, groups, np.arange(len(y)), [f'hash-{i}' for i in range(len(y))]

    # Prueba automatizada: verifica reserves whole groups and persists roles when classes grow.
    def test_reserves_whole_groups_and_persists_roles_when_classes_grow(self):
        y, g, validation, hashes = self.data()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'roles.json'
            a, b, info = calibration_split(y, g, validation, path, hashes)
            self.assertTrue(info['independent'])
            self.assertFalse(set(g[a]) & set(g[b]))
            self.assertEqual(set(a) | set(b), set(validation))
            extended_y = np.r_[y, np.full(24, 2)]
            extended_g = np.r_[g, np.repeat([f'new-{i}' for i in range(8)], 3)]
            c, d, _ = calibration_split(extended_y, extended_g, np.arange(len(extended_y)), path,
                                         hashes + [f'new-hash-{i}' for i in range(24)])
            self.assertTrue(set(a) <= set(c))
            self.assertTrue(set(b) <= set(d))
            self.assertEqual(json.loads(path.read_text())['version'], 1)

    # Prueba automatizada: verifica insufficient groups are explicit and do not create ledger.
    def test_insufficient_groups_are_explicit_and_do_not_create_ledger(self):
        y = np.tile([0, 1], 30)
        groups = np.repeat(['one', 'two', 'three'], 20)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'roles.json'
            a, b, info = calibration_split(y, groups, np.arange(len(y)), path)
            self.assertFalse(info['independent'])
            self.assertEqual(info['mode'], 'shared_validation')
            np.testing.assert_array_equal(a, b)
            self.assertFalse(path.exists())

    # Prueba automatizada: verifica failed growth does not mutate historical roles.
    def test_failed_growth_does_not_mutate_historical_roles(self):
        y, g, validation, hashes = self.data()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'roles.json'
            calibration_split(y, g, validation, path, hashes)
            before = path.read_bytes()
            yy = np.r_[y, [2] * 10]
            gg = np.r_[g, ['new-one'] * 10]
            _, _, info = calibration_split(yy, gg, np.arange(len(yy)), path, hashes + [f'new-{i}' for i in range(10)])
            self.assertFalse(info['independent'])
            self.assertEqual(path.read_bytes(), before)

    # Prueba automatizada: verifica regrouping cannot move reserved samples between roles.
    def test_regrouping_cannot_move_reserved_samples_between_roles(self):
        y, g, validation, hashes = self.data()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'roles.json'
            a, b, _ = calibration_split(y, g, validation, path, hashes)
            before = path.read_bytes()
            changed = g.copy()
            changed[np.isin(g, [g[a[0]], g[b[0]]])] = 'merged'
            _, _, info = calibration_split(y, changed, validation, path, hashes)
            self.assertEqual(info['reason'], 'historical_role_conflict')
            self.assertEqual(path.read_bytes(), before)

    # Prueba automatizada: verifica outer train and test never enter subsplit.
    def test_outer_train_and_test_never_enter_subsplit(self):
        y, g, validation, hashes = self.data()
        yy = np.r_[[0, 1], y, [0, 1]]
        gg = np.r_[['train', 'train'], g, ['test', 'test']]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'roles.json'
            a, b, _ = calibration_split(yy, gg, validation + 2, path)
            self.assertEqual(set(a) | set(b), set(validation + 2))
            gg[0] = g[0]
            with self.assertRaises(ValueError):
                calibration_split(yy, gg, validation + 2, path)

    # Prueba automatizada: verifica duplicate recordings never inflate independent group count.
    def test_duplicate_recordings_never_inflate_independent_group_count(self):
        y, g, validation, hashes = self.data()
        # Every group's first recording is one copy. They form one unit.
        for i in range(0, len(hashes), 4):
            hashes[i] = 'same-recording'
        with tempfile.TemporaryDirectory() as folder:
            _, _, info = calibration_split(y, g, validation, Path(folder) / 'roles.json', hashes)
            self.assertFalse(info['independent'])

    # Prueba automatizada: verifica small perfect sample does not claim high certainty.
    def test_small_perfect_sample_does_not_claim_high_certainty(self):
        interval = wilson_interval(3, 3)
        self.assertEqual(interval['estimate'], 1.)
        self.assertLess(interval['lower'], .5)
        self.assertIsNone(wilson_interval(0, 0)['estimate'])

    # Prueba automatizada: verifica support counts sequences and groups not frames.
    def test_support_counts_sequences_and_groups_not_frames(self):
        y = np.array([0, 0, 1, 1])
        groups = np.array(['one', 'one', 'two', 'two'])
        result = validation_support(y, groups, [{'id': 'a'}, {'id': 'b'}],
                                    predicted=np.array([0, 1, 1, 1]), accepted=np.array([1, 1, 1, 0], bool))
        overall = result['overall']
        self.assertEqual(overall['samples'], 4)
        self.assertEqual(overall['groups'], 2)
        self.assertFalse(overall['sequence_intervals_independent'])
        self.assertEqual(overall['accepted_precision']['total'], 3)
        self.assertEqual(overall['accepted_precision']['successes'], 2)
        self.assertEqual(overall['group_intervals']['groups_without_false_accepts']['total'], 2)
        self.assertEqual(overall['group_intervals']['groups_without_false_accepts']['successes'], 1)
        b = result['by_class'][1]
        self.assertEqual(b['accepted_precision']['total'], 2)
        self.assertEqual(b['coverage']['total'], 2)
        self.assertEqual(b['coverage']['successes'], 1)


if __name__ == '__main__':
    unittest.main()
