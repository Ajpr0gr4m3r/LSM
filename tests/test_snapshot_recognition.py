import base64
import types
import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import cv2
import numpy as np
import test_finger_geometry as fixture
from recognition_features import fit_hand_guard, regions
from snapshot_recognition import build_snapshot, classify_snapshot
from capture_quality import hand_image_quality, image_quality
from web_app import Runtime

# Ayudante de prueba para SnapshotTests.
class SnapshotTests(unittest.TestCase):
    # Prepara el estado temporal aislado que necesita cada prueba.
    def setUp(self):
        self.a=fixture.FingerGeometryTests().hand()
        self.b=fixture.FingerGeometryTests().hand(True)
        raw=np.stack([self.a]*4+[self.b]*4);self.y=np.repeat([0,1],4)
        self.meta={'labels':[{'id':'a','text':'A'},{'id':'b','text':'B'}],
                   'hand_guard':fit_hand_guard(raw,self.y,raw,self.y,True),
                   'motion_profile':{'moving_classes':[]}}
        self.frames=raw[:,15]

    # Prueba automatizada: verifica preparation uses only unique frozen validation recordings.
    def test_preparation_uses_only_unique_frozen_validation_recordings(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'a').mkdir();(root/'b').mkdir()
            c=self.a.copy();c[:,0]+=.001
            arrays={'one.npz':self.a,'copy.npz':self.a,'training.npz':self.b,'test.npz':c}
            for name in arrays:(root/'a'/name).touch()
            digest=lambda points:hashlib.sha256(points.tobytes()).hexdigest()
            metadata={**self.meta,'split_hashes':{'validation':[digest(self.a),digest(self.b),digest(c)],
                       'train':[digest(self.b)],'test':[digest(c)]}}
            runtime=Runtime();sentinel={'prepared':True}
            with patch('web_app.model_metadata',return_value=(root,metadata)),patch.object(runtime,'model_signature',return_value='fixed'),patch('sign_languages.dataset_dir',return_value=root),patch('web_dataset.load_sequence',side_effect=lambda path:arrays[path.name]),patch('snapshot_recognition.build_snapshot',return_value=sentinel) as build:
                self.assertIs(runtime.prepare_snapshot('lsm'),sentinel)
                validation,targets=build.call_args.args[1:]
                self.assertEqual(len(validation),1);self.assertEqual(targets,[0])
                runtime.prepare_snapshot('lsm');self.assertEqual(build.call_count,1)

    # Prueba automatizada: verifica photo compares static shape and rejects unknown or unvalidated.
    def test_photo_compares_static_shape_and_rejects_unknown_or_unvalidated(self):
        bundle=build_snapshot(self.meta,self.frames,self.y)
        result=classify_snapshot(self.a[15],bundle)
        self.assertTrue(result['accepted']);self.assertEqual(result['label']['id'],'a')
        self.assertNotIn('confidence',result)
        unknown=(self.a[15]+self.b[15])/2
        self.assertFalse(classify_snapshot(unknown,bundle)['accepted'])
        unsupported=build_snapshot(self.meta,[],[])
        self.assertFalse(classify_snapshot(self.a[15],unsupported)['accepted'])

    # Prueba automatizada: verifica movement class is not inferred from a pose.
    def test_movement_class_is_not_inferred_from_a_pose(self):
        self.meta['motion_profile']['moving_classes']=[1]
        bundle=build_snapshot(self.meta,self.frames,self.y)
        result=classify_snapshot(self.b[15],bundle)
        self.assertFalse(result['accepted']);self.assertIn('movimiento',result['reason'])
        self.assertIsNone(result['label'])

    # Prueba automatizada: verifica dark wall does not reject a well lit hand.
    def test_dark_wall_does_not_reject_a_well_lit_hand(self):
        image=np.zeros((480,640,3),np.uint8)
        # A focused, bright hand area on a dark full-frame background.
        hand=regions(self.a[15])[2]
        low=hand[:,:2].min(axis=0);high=hand[:,:2].max(axis=0)
        pad=np.maximum((high-low)*.2,.01)
        x0,y0=np.floor((low-pad)*[640,480]).astype(int)
        x1,y1=np.ceil((high+pad)*[640,480]).astype(int)
        grid=np.indices((y1-y0,x1-x0)).sum(axis=0)%2
        image[y0:y1,x0:x1]=np.repeat((70+grid*100)[:,:,None],3,axis=2)
        self.assertIn('Falta luz. Ilumina las manos de frente.',image_quality(image)['warnings'])
        focused=hand_image_quality(image,self.a[15])
        self.assertEqual(focused['scope'],'hands');self.assertEqual(focused['warnings'],[])
        image[:]=0
        self.assertTrue(hand_image_quality(image,self.a[15])['warnings'])

    # Prueba automatizada: verifica recent tracking loss recovers from same image once without old points.
    def test_recent_tracking_loss_recovers_from_same_image_once_without_old_points(self):
        runtime=Runtime();sid=runtime.new_session('lsm');item=runtime.session(sid)
        closed=[];item.holistic=types.SimpleNamespace(close=lambda:closed.append(True))
        item.last_hand_seen=10.
        original=object();recovered=object();image=np.zeros((32,32,3),np.uint8);seen=[]
        fake=types.SimpleNamespace(hands_detected=lambda r:r is recovered,
            extract_keypoints=lambda r:self.a[15],
            mediapipe_detection=lambda frame,detector:(seen.append(frame) or frame,recovered))
        with patch.dict('sys.modules',{'utils':fake}),patch.object(runtime,'image_detector',return_value=object()):
            result,ok=runtime.recover_hand_tracking(item,image,original,10.2)
            self.assertTrue(ok);self.assertIs(result,recovered);self.assertIs(seen[0],image)
            self.assertEqual(closed,[True]);self.assertIsNone(item.holistic)
            result,ok=runtime.recover_hand_tracking(item,image,original,10.3)
            self.assertFalse(ok);self.assertIs(result,original);self.assertEqual(len(seen),1)
        self.assertEqual(len(item.frames),0)

    # Prueba automatizada: verifica phone photo writes draft without fabricating confidence.
    def test_phone_photo_writes_draft_without_fabricating_confidence(self):
        runtime=Runtime();created=runtime.create_conversation('lsm',None)
        room=runtime.conversations[created['room']];room['phone_session']=runtime.new_session('lsm')
        body={'room':room['id'],'key':room['phone_key'],'image':'example'}
        with patch.object(runtime,'analyze_snapshot',return_value={'accepted':True,'label':{'text':'A'}}):
            result=runtime.phone_request('/api/phone/snapshot',body)
        self.assertEqual(result['conversation']['sign_drafts']['phone'],'A')
        room['sign_drafts']['phone']['updated']-=5
        state=runtime.conversation_state(room)
        self.assertIsNone(state['messages'][0]['confidence'])
        with patch.object(runtime,'frame',return_value={'confirmed':None}) as frame:
            runtime.phone_request('/api/phone/frame',{**body,'snapshot_mode':True})
            self.assertEqual(frame.call_args.args[0]['mode'],'preview')

    # Prueba automatizada: verifica snapshot uses independent detector without feeding temporal buffer.
    def test_snapshot_uses_independent_detector_without_feeding_temporal_buffer(self):
        runtime=Runtime();sid=runtime.new_session('lsm');session=runtime.session(sid)
        detector=object();session.snapshot_detector=detector
        fake=types.SimpleNamespace(mediapipe_detection=lambda image,model:(image,object()),extract_keypoints=lambda result:self.a[15])
        image=base64.b64encode(cv2.imencode('.jpg',np.full((32,32,3),100,np.uint8))[1]).decode()
        bundle=build_snapshot(self.meta,self.frames,self.y)
        with patch.dict('sys.modules',{'utils':fake}),patch.object(runtime,'prepare_snapshot',return_value=bundle),patch('web_app.hand_image_quality',return_value={'warnings':[]}):
            result=runtime.analyze_snapshot(sid,image)
        self.assertTrue(result['accepted']);self.assertEqual(len(session.frames),0)
        self.assertIsNone(session.holistic)
