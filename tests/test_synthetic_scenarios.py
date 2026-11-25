"""Escenarios con coordenadas coherentes e iluminación aplicada a imágenes."""
import unittest
from unittest.mock import patch
import numpy as np

import synthetic_generator as generator
import synthetic_media as media
from synthetic_jobs import SyntheticStudio
from test_synthetic import sequence


class ScenarioTests(unittest.TestCase):
    def test_scenarios_cover_distance_size_position_and_are_reproducible(self):
        original = sequence(moving=True, both=True)
        a = generator.generate(original, 39, seed=42, scenarios=True)
        b = generator.generate(original, 39, seed=42, scenarios=True)
        self.assertEqual(len(a.samples), 39)
        names = {params.scenario for params in a.params}
        self.assertTrue({'cerca', 'lejos', 'mano_pequena', 'mano_grande',
                         'izquierda', 'derecha', 'arriba', 'abajo'}.issubset(names))
        for left, right in zip(a.samples, b.samples):
            np.testing.assert_array_equal(left, right)
        self.assertEqual(a.params[0].summary(), b.params[0].summary())

    def test_camera_variants_are_distinct_and_missing_points_stay_missing(self):
        original = sequence()
        original[:, 4:8] = 0
        hands = [dict(scale=1, palm=1, fingers=[1]*5, spread=[0]*5, roll=0, yaw=0)]*2
        close = generator.Params(body_scale=1.15, hands=hands)
        far = generator.Params(body_scale=.85, hands=hands)
        first, second = generator.apply(original, close), generator.apply(original, far)
        self.assertFalse(np.any(first[:, 4:8]))
        self.assertFalse(np.any(first[:, generator.HANDS[0]]))
        difference = np.sqrt(np.mean((generator.hand_vector(first)-generator.hand_vector(second))**2))
        self.assertGreater(difference, generator.Validator(generator.LEVELS['equilibrado']).min_distance)
        self.assertNotEqual(generator.sample_id('source', close, 'equilibrado'),
                            generator.sample_id('source', far, 'equilibrado'))

    def test_lighting_changes_pixels_and_preserves_original(self):
        image = np.full((20, 40, 3), 140, np.uint8)
        dim = media.change_lighting(image, 'luz_baja')
        bright = media.change_lighting(image, 'luz_intensa')
        shadow = media.change_lighting(image, 'sombra_lateral')
        self.assertLess(dim.mean(), image.mean())
        self.assertGreater(bright.mean(), image.mean())
        self.assertLess(shadow[:, 0].mean(), shadow[:, -1].mean())
        np.testing.assert_array_equal(image, np.full_like(image, 140))
        with self.assertRaises(media.MediaError):
            media.change_lighting(image, 'inexistente')

    def test_image_is_redetected_under_each_lighting_condition(self):
        studio = SyntheticStudio()
        studio.sources['source'] = {
            'id':'source', 'kind':'image', 'language':'lsm', 'name':'test.png',
            'state':'processing', 'lighting_requested':True, 'cancel':False}
        original = sequence()
        def detected(*args, **kwargs):
            return {'sequence':original.copy(), 'static':True, 'warnings':[],
                    'hands':[False, True], 'frames_read':1, 'frames_with_hands':1}
        with patch('synthetic_media.image_source', side_effect=detected) as extract:
            studio._process_source('source', b'image', True)
        self.assertEqual(extract.call_count, 4)
        self.assertEqual([call.kwargs['lighting'] for call in extract.call_args_list],
                         [None, *media.LIGHTING_PROFILES])
        self.assertEqual(studio.sources['source']['state'], 'ready')
        self.assertEqual(studio.sources['source']['lighting_profiles'], list(media.LIGHTING_PROFILES))

    def test_lighting_variants_keep_original_provenance_in_generated_job(self):
        studio = SyntheticStudio()
        original = sequence()
        source = {'id':'source', 'kind':'dataset', 'sequence':original, 'static':False,
                  'lighting_sequences':[{'sequence':original.copy(), 'illumination':'luz_baja'}]}
        job = {'id':'job', 'language':'lsm', 'label':'Test', 'count':8, 'level':'equilibrado',
               'seed':42, 'state':'running', 'samples':[], 'done':0, 'attempts':0,
               'rejected':generator.Counter(), 'cancel':False, 'scenarios':True}
        studio._run(job, [source], None)
        self.assertEqual(job['state'], 'done', job.get('error'))
        self.assertEqual(job['done'], 8)
        self.assertEqual({row['params'].illumination for row in job['samples']}, {'original','luz_baja'})
        self.assertTrue(all(row['source']=='source' for row in job['samples']))


if __name__ == '__main__':
    unittest.main()
