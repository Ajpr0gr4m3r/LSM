import unittest
from unittest.mock import patch
import numpy as np
from recognition_analysis import accepted_mask
from recognition_decision import calibrate_joint_policy, policy_allowed, rejection_report, decision_details

# Ayudante de prueba para JointDecisionTests.
class JointDecisionTests(unittest.TestCase):
    def test_unsupported_retry_never_runs_model(self):
        from unittest.mock import Mock
        from web_app import Runtime
        model = Mock(side_effect=AssertionError('Unnecessary inference'))
        metadata = {'decision_policy': {'classes': {'0': {'supported': False}}}}
        result = Runtime().retry_viewpoint(None, np.array([.96, .04]), model, metadata, False)
        self.assertIsNone(result)
        model.assert_not_called()

    # Ayudante de prueba para fixture.
    def fixture(self):
        p=np.array([[.8,.2]]*6+[[.2,.8]]*6)
        y=np.repeat([0,1],6)
        scores={'hand':np.full(12,.5),'rival':np.full(12,1.1),'temporal':np.full(12,.5)}
        return p,y,scores

    # Prueba automatizada: verifica static rival does not override correct temporal network without evidence.
    def test_static_rival_does_not_override_correct_temporal_network_without_evidence(self):
        p,y,s=self.fixture()
        guard={'version':'finger-contrast-v2','classes':[{'max_rival_ratio':.8}]*2}
        policy=calibrate_joint_policy(p,y,s,guard)
        self.assertTrue(accepted_mask(p,policy,policy_allowed(p,policy,s)).all())
        self.assertIsNone(policy['classes']['0']['max_rival_ratio'])
        self.assertLess(policy['classes']['0']['margin'],.4)
        # Absolute shape novelty still rejects, even with high network confidence.
        s['hand'][:]=2
        self.assertFalse(policy_allowed(p,policy,s).any())

    # Prueba automatizada: verifica ambiguous or unsupported classes never forced.
    def test_ambiguous_or_unsupported_classes_never_forced(self):
        p,y,s=self.fixture();p[:]=[.51,.49]
        policy=calibrate_joint_policy(p,y,s)
        self.assertFalse(accepted_mask(p,policy,policy_allowed(p,policy,s)).any())
        result=decision_details(None,p[0],{'decision_policy':policy})
        self.assertEqual(result['code'],'unsupported_class')

    # Prueba automatizada: verifica runtime and offline share exact policy and gates.
    def test_runtime_and_offline_share_exact_policy_and_gates(self):
        p,y,s=self.fixture();policy=calibrate_joint_policy(p,y,s)
        for strict in (False,True):
            expected=accepted_mask(p,policy,policy_allowed(p,policy,s),strict)
            for i in range(len(p)):
                with patch('recognition_decision.evidence',return_value={k:v[i] for k,v in s.items()}):
                    self.assertEqual(decision_details(None,p[i],{'decision_policy':policy},strict)['accepted'],bool(expected[i]))

    # Prueba automatizada: verifica reports correct rejections not just confidence.
    def test_reports_correct_rejections_not_just_confidence(self):
        p,y,s=self.fixture();policy=calibrate_joint_policy(p,y,s);s['hand'][0]=2
        report=rejection_report(p,y,[{'id':'a','text':'A'},{'id':'b','text':'B'}],policy,s)
        self.assertEqual(report['stages'][-1]['correct_rejected'],1)
        self.assertEqual(report['stages'][-1]['false_accepts'],0)

    # Prueba automatizada: verifica legacy thresholds are preserved.
    def test_legacy_thresholds_are_preserved(self):
        for p in ([.9,.1],[.6,.4]):
            meta={'decision_threshold':.85,'decision_margin':.15}
            self.assertEqual(decision_details(None,p,meta)['accepted'],bool(accepted_mask(p,{'threshold':.85,'margin':.15})[0]))

    # Prueba automatizada: verifica new live windows do not average previous gesture votes.
    def test_new_live_windows_do_not_average_previous_gesture_votes(self):
        import base64,cv2,types
        import web_app
        from test_studio import points
        from recognition_features import FINGER_PREPROCESSING
        raw=points()[0];prediction=[np.array([.9,.1])]
        fake=types.SimpleNamespace(mediapipe_detection=lambda image,model:(image,object()),
            extract_keypoints=lambda r:raw,hands_detected=lambda r:True)
        # Ayudante de prueba para Model.
        class Model:
            # Ayudante de prueba para   call  .
            def __call__(self,x,training=False):
                return types.SimpleNamespace(numpy=lambda:prediction[0][None,:])
        runtime=web_app.Runtime();sid=runtime.new_session('lsm','test');session=runtime.session(sid);session.holistic=object()
        meta={'labels':[{'id':'a','text':'A'},{'id':'b','text':'B'}],'preprocessing':FINGER_PREPROCESSING,
              'created_at':'test','stability_frames':3,'decision_input':'single-window-v1',
              'decision_policy':{'threshold':.7,'margin':.1}}
        encoded=base64.b64encode(cv2.imencode('.jpg',np.full((32,32,3),100,np.uint8))[1]).decode()
        clock=[100.]
        with patch.dict('sys.modules',{'utils':fake}),patch.object(runtime,'load_model',return_value=(Model(),meta)),patch('web_app.time.monotonic',side_effect=lambda:clock[0]):
            for _ in range(30):
                clock[0]+=.2;runtime.frame({'session':sid,'image':encoded,'mode':'test'})
            prediction[0]=np.array([.1,.9]);clock[0]+=.2
            result=runtime.frame({'session':sid,'image':encoded,'mode':'test'})
            self.assertEqual(result['candidate']['id'],'b')
            self.assertEqual(result['stability'],1)
            self.assertEqual(result['stability_required'],3)
            self.assertAlmostEqual(result['confidence'],.9)
            self.assertIsNone(result['confirmed'])
            events=[]
            # Ayudante de prueba para step.
            def step():
                clock[0]+=.2
                output=runtime.frame({'session':sid,'image':encoded,'mode':'test'})
                if output['confirmed']: events.append(output['confirmed']['id'])
                return output
            step();step()  # B stabilizes while hands remain visible.
            self.assertEqual(events,['b'])
            for _ in range(5): self.assertEqual(step()['phase'],'held')
            prediction[0]=np.array([.9,.1]);step()  # One-frame rival is not a new sign.
            prediction[0]=np.array([.1,.9]);step()
            self.assertEqual(events,['b'])
            prediction[0]=np.array([.9,.1])
            step();step();step()
            self.assertEqual(events,['b','a'])

    # Prueba automatizada: verifica at 90 requires three stable windows then confirms once.
    def test_at_90_requires_three_stable_windows_then_confirms_once(self):
        import base64,cv2,types
        import web_app
        from test_studio import points
        from recognition_features import FINGER_PREPROCESSING
        raw=points()[0];prediction=[np.array([.90,.10])]
        fake=types.SimpleNamespace(mediapipe_detection=lambda image,model:(image,object()),
            extract_keypoints=lambda r:raw,hands_detected=lambda r:True)
        # Ayudante de prueba para Model.
        class Model:
            # Ayudante de prueba para   call  .
            def __call__(self,x,training=False):
                return types.SimpleNamespace(numpy=lambda:prediction[0][None,:])
        runtime=web_app.Runtime();sid=runtime.new_session('lsm','test');session=runtime.session(sid);session.holistic=object()
        meta={'labels':[{'id':'a','text':'A'},{'id':'b','text':'B'}],'preprocessing':FINGER_PREPROCESSING,
              'created_at':'test','stability_frames':3,'decision_input':'single-window-v1',
              'decision_policy':{'threshold':.7,'margin':.1}}
        encoded=base64.b64encode(cv2.imencode('.jpg',np.full((32,32,3),100,np.uint8))[1]).decode()
        clock=[100.]
        with patch.dict('sys.modules',{'utils':fake}),patch.object(runtime,'load_model',return_value=(Model(),meta)),patch('web_app.time.monotonic',side_effect=lambda:clock[0]):
            for _ in range(30):
                clock[0]+=.2;runtime.frame({'session':sid,'image':encoded,'mode':'test'})
            self.assertEqual(session.stable_count,1)
            self.assertFalse(session.gesture_confirmed)
            clock[0]+=.2
            self.assertIsNone(runtime.frame({'session':sid,'image':encoded,'mode':'test'})['confirmed'])
            clock[0]+=.2
            self.assertIsNotNone(runtime.frame({'session':sid,'image':encoded,'mode':'test'})['confirmed'])
            self.assertTrue(session.gesture_confirmed)
            for _ in range(5):
                clock[0]+=.2
                result=runtime.frame({'session':sid,'image':encoded,'mode':'test'})
                self.assertIsNone(result['confirmed'])

    # Prueba automatizada: verifica high confidence keeps novelty and unsupported rejections.
    def test_high_confidence_keeps_novelty_and_unsupported_rejections(self):
        meta={'decision_policy':{'threshold':.98,'margin':.1}}
        self.assertTrue(decision_details(None,[.90,.10],meta,test_mode=True)['accepted'])
        self.assertFalse(decision_details(None,[.899,.101],meta,test_mode=True)['accepted'])
        with patch('recognition_decision.hand_guard_accept',return_value=False):
            self.assertFalse(decision_details(None,[.99,.01],meta,test_mode=True)['accepted'])
        meta['decision_policy']['classes']={'0':{'supported':False}}
        self.assertEqual(decision_details(None,[.99,.01],meta,test_mode=True)['code'],'unsupported_class')
