import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from dataset_tools import persistent_split
from capture_quality import consistent_palm, stable_hand_crop

class RecoveryRegression(unittest.TestCase):
    def test_video_crop_is_stable_and_reframes_at_edge(self):
        points=np.array([[40.,40.],[60.,70.]])
        old=(10,10,100,1.,200,200)
        crop=stable_hand_crop(points,(15,15,90),old,(200,200),1.1)
        self.assertEqual(crop[:3],old[:3])
        self.assertEqual(crop[3],1.1)
        self.assertEqual(stable_hand_crop(points+50,(50,50,100),old,(200,200),1.1)[:3],(50,50,100))
        self.assertEqual(stable_hand_crop(points,(15,15,90),old,(200,200),2.)[:3],(15,15,90))
        self.assertEqual(stable_hand_crop(points,(15,15,90),old,(400,400),1.1)[:3],(15,15,90))

    def test_palm_preserves_orientation_but_allows_fingers(self):
        palm = np.zeros((21,2))
        palm[[5,9,13,17]] = [[-10,30],[0,40],[10,30],[20,20]]
        palm[1:5] = [[-5,5],[-10,10],[-15,15],[-20,20]]
        self.assertTrue(consistent_palm(palm, palm))
        other = palm.copy(); other[8] = [100,100]
        self.assertTrue(consistent_palm(palm, other))
        self.assertFalse(consistent_palm(palm, -palm))
        self.assertFalse(consistent_palm(palm, palm*.1))
        for angle in np.linspace(0,2*np.pi,12):
            rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
            a=palm@rotation
            self.assertTrue(consistent_palm(a,a))

    def test_solver_recovers_when_random_search_misses_coverage(self):
        targets=np.repeat(np.arange(8),9)
        groups=np.array([f'{c}-{s}' for c in range(8) for s in range(3) for _ in range(3)])
        class Unlucky:
            def choice(self, names, size, p): return np.repeat('train', size)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'split.json'
            path.write_text(json.dumps({'groups':{'historic-test':'test'},'samples':{'old':'test'}}))
            with patch('dataset_tools.np.random.default_rng',return_value=Unlucky()):
                parts=persistent_split(targets,groups,path)
            for indices in parts: self.assertEqual(set(targets[indices]),set(range(8)))
            for i in range(3):
                for j in range(i): self.assertFalse(set(groups[parts[i]]) & set(groups[parts[j]]))
            stored=json.loads(path.read_text())
            self.assertEqual(stored['groups']['historic-test'],'test')
            self.assertEqual(stored['samples']['old'],'test')

if __name__=='__main__': unittest.main()
