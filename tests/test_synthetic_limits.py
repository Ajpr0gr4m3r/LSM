"""Límites grandes y búsqueda de duplicados equivalente a la comprobación completa."""
import unittest
from unittest.mock import patch

import numpy as np

from synthetic_generator import DuplicateIndex
from synthetic_jobs import SyntheticStudio
from test_synthetic import sequence


class GenerationLimitTests(unittest.TestCase):
    def test_accepts_ten_thousand_and_rejects_above_the_limit(self):
        studio = SyntheticStudio()
        studio.sources['source'] = {'id':'source', 'language':'lsm', 'kind':'dataset',
                                    'label_text':'Prueba', 'state':'ready', 'static':False}
        with patch.object(studio, '_label_is_dynamic', return_value=False), \
             patch('synthetic_jobs.threading.Thread') as thread:
            job = studio.start('lsm', 'Prueba', ['source'], 10000, 'equilibrado', 42)
            self.assertEqual(job['count'], 10000)
            thread.return_value.start.assert_called_once()
        with self.assertRaisesRegex(ValueError, '10000'):
            studio.start('lsm', 'Prueba', ['source'], 10001, 'equilibrado', 42)
        with self.assertRaises(ValueError):
            studio.start('lsm', 'Prueba', ['source'], True, 'equilibrado', 42)

    def test_index_matches_full_rms_before_and_after_tree_rebuild(self):
        rng = np.random.default_rng(42)
        vectors = rng.normal(0, .1, (260, 257)).astype(np.float32)
        index = DuplicateIndex(vectors[0], .008)
        for vector in vectors[1:]:
            index.add(vector)
        queries = [vectors[3], vectors[240], vectors[130] + .001,
                   vectors[130] + .02, np.ones(257, np.float32)]
        for vector in queries:
            expected = any(np.sqrt(np.mean((vector - old)**2)) < .008 for old in vectors)
            self.assertEqual(index.contains(vector), expected)

    def test_late_cancellation_interrupts_a_large_generation(self):
        import synthetic_generator as generator
        calls = 0
        def cancelled():
            nonlocal calls
            calls += 1
            return calls > 3
        result = generator.generate(sequence(), 10000, scenarios=True, cancelled=cancelled)
        self.assertTrue(result.cancelled)
        self.assertLess(result.attempts, 25)


if __name__ == '__main__':
    unittest.main()
