import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from motion_features import longer_motion_windows
from web_app import Runtime,Session

class LongerMotionTests(unittest.TestCase):
    def test_windows_preserve_order_endpoints_and_source_frames(self):
        history=np.arange(45,dtype=np.float32)[:,None]
        windows=longer_motion_windows(history)
        self.assertEqual(len(windows),2)
        self.assertEqual([len(w) for w in windows],[30,30])
        self.assertEqual(windows[0][0,0],0)
        for w in windows:
            self.assertEqual(w[-1,0],44)
            self.assertTrue(np.all(np.diff(w[:,0])>0))
        self.assertEqual(longer_motion_windows(history[:44]),[])

    def retry(self, probabilities, accepted=True):
        model=lambda *a,**kw:SimpleNamespace(numpy=lambda:np.array(probabilities))
        metadata={'motion_profile':{'moving_classes':[1]}}
        with patch('web_app.prepare_sequence',side_effect=lambda w,p:w),patch('web_app.decision_details',return_value={'accepted':accepted}):
            return Runtime().retry_longer_motion(np.zeros((45,1)),model,metadata,False)

    def test_requires_two_accepted_dynamic_predictions(self):
        self.assertIsNotNone(self.retry([[.01,.99],[.02,.98]]))
        self.assertIsNone(self.retry([[.01,.99],[.99,.01]]))
        self.assertIsNone(self.retry([[.99,.01],[.98,.02]]))
        self.assertIsNone(self.retry([[.01,.99],[.02,.98]],False))

    def test_short_history_does_not_call_model_and_reset_discards_motion(self):
        model=lambda *a,**kw:self.fail('should not infer')
        self.assertIsNone(Runtime().retry_longer_motion(np.zeros((30,1)),model,{'motion_profile':{'moving_classes':[1]}},False))
        s=Session('lsm')
        s.frames.extend(range(60));self.assertEqual(len(s.frames),45)
        s.reset();self.assertFalse(s.frames)
