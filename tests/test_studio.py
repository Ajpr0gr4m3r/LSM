import base64
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile
import numpy as np
import cv2
import sign_languages as langs
import web_app
import web_dataset as data
from dataset_tools import audit_dataset, export_dataset, import_dataset, grouped_split, training_provenance
from capture_quality import landmark_quality, sequence_quality
from recognition_features import regions, prepare_sequence, STABLE_PREPROCESSING, HAND_PREPROCESSING, calibrate_decision, temporal_descriptor


# Ayudante de prueba para points.
def points():
    output=np.zeros((30,data.FEATURE_DIM),np.float32)
    pose,_,left,_=regions(output)
    pose[:,11]=[.4,.4,0,1];pose[:,12]=[.6,.4,0,1]
    for i in range(21):
        left[:,i]=[.5+.014*(i%4),.7-.02*(i//4),.001*(i%3)]
    return output


# Ayudante de prueba para StudioTests.
class StudioTests(unittest.TestCase):
    # Prepara el estado temporal aislado que necesita cada prueba.
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patches=[patch.object(langs,'WEB_DATA',self.root),patch.object(langs,'WEB_MODELS',self.root/'models'),patch.object(web_app,'WEB_DATA',self.root)]
        for p in self.patches:p.start()
        self.raw=points()
    # Elimina los recursos temporales creados durante la prueba.
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    # Prueba automatizada: verifica metadata survives draft commit and legacy still loads.
    def test_metadata_survives_draft_commit_and_legacy_still_loads(self):
        sid=data.save_draft('lsm',self.raw,{'session_id':'session-1','participant':'person-1','batch_id':'batch-1'})
        saved=data.commit_draft('lsm',sid,'A')
        path=langs.dataset_dir('lsm')/saved['label']['id']/saved['sample']
        self.assertEqual(data.sequence_metadata(path)['participant'],'person-1')
        old=path.with_name('old.npz');np.savez(old,points=self.raw,pipeline=json.dumps(langs.pipeline_spec()))
        self.assertEqual(data.sequence_metadata(old),{})
        np.testing.assert_array_equal(data.load_sequence(old),self.raw)

    # Prueba automatizada: verifica audit duplicates conflicts and export language isolation.
    def test_audit_duplicates_conflicts_and_export_language_isolation(self):
        data.save_sequence('lsm','hola',self.raw)
        data.save_sequence('lsm','hola',self.raw)
        data.save_sequence('lsm','gracias',self.raw)
        audit=audit_dataset('lsm')['summary']
        self.assertEqual(audit['duplicates'],2);self.assertGreater(audit['conflicts'],0)
        packet=export_dataset('lsm')
        with self.assertRaises(ValueError):import_dataset('asl',packet['data'])
        self.assertEqual(sum(r['samples'] for r in data.inventory('asl')),0)
        with self.assertRaises(ValueError):import_dataset('lsm',packet['data'])

    # Prueba automatizada: verifica roundtrip unicode import deduplicates and preserves metadata.
    def test_roundtrip_unicode_import_deduplicates_and_preserves_metadata(self):
        label=langs.register_label('jsl','こんにちは ★')
        data.save_sequence('jsl',label['id'],self.raw,metadata={'session_id':'original-session'})
        packet=export_dataset('jsl')
        self.assertEqual(import_dataset('jsl',packet['data'])['skipped_duplicates'],1)
        other=self.root/'other';other.mkdir()
        with patch.object(langs,'WEB_DATA',other):
            result=import_dataset('jsl',packet['data']);self.assertEqual(result['imported'],1)
            row=next(r for r in audit_dataset('jsl')['samples'] if r['valid'])
            self.assertEqual(row['text'],'こんにちは ★');self.assertEqual(row['metadata']['session_id'],'original-session')

    # Prueba automatizada: verifica import rejects unsafe zip and all or nothing bad example.
    def test_import_rejects_unsafe_zip_and_all_or_nothing_bad_example(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:z.writestr('../outside',b'bad')
        with self.assertRaises(ValueError):import_dataset('lsm',base64.b64encode(buffer.getvalue()).decode())
        self.assertFalse((self.root/'outside').exists())
        with self.assertRaises(ValueError):import_dataset('lsm','not base64')

    # Prueba automatizada: verifica group split never shares person or duplicate content.
    def test_group_split_never_shares_person_or_duplicate_content(self):
        y=np.tile(np.repeat([0,1],10),6);groups=np.repeat([f'person-{i}' for i in range(6)],20)
        train,val,test=grouped_split(y,groups)
        sets=[set(groups[i]) for i in (train,val,test)]
        self.assertFalse(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
        self.assertEqual(set(np.concatenate([train,val,test])),set(range(len(y))))
        with self.assertRaises(ValueError):grouped_split(np.array([0,1]),np.array(['same','same']))

    # Prueba automatizada: verifica quality and new preprocessing preserve old models and time.
    def test_quality_and_new_preprocessing_preserve_old_models_and_time(self):
        self.assertTrue(landmark_quality(self.raw[0])['usable'])
        outside=self.raw.copy();regions(outside)[2][:,0,0]=1.2
        self.assertFalse(sequence_quality(outside)['usable_ratio']==1)
        old=prepare_sequence(self.raw,HAND_PREPROCESSING)
        new=prepare_sequence(self.raw,STABLE_PREPROCESSING)
        self.assertEqual(old.shape,new.shape);self.assertTrue(np.isfinite(new).all())
        missing=self.raw.copy();regions(missing)[2][10:15]=0
        processed=prepare_sequence(missing,STABLE_PREPROCESSING)
        self.assertTrue(np.all(processed[10:15,-128:-65]==0))
        moving=self.raw.copy();regions(moving)[2][:,:,0]+=np.linspace(0,.1,30)[:,None]
        self.assertFalse(np.allclose(temporal_descriptor(moving),temporal_descriptor(moving[::-1])))
        np.testing.assert_array_equal(self.raw,points())

    # Prueba automatizada: verifica calibration uses margin and can reject all.
    def test_calibration_uses_margin_and_can_reject_all(self):
        probabilities=np.array([[.99,.01],[.02,.98],[.96,.04],[.5,.5]])
        report=calibrate_decision(probabilities,np.array([0,1,0,1]),[True]*4)
        self.assertEqual(report['accepted'],3)
        self.assertEqual(calibrate_decision(probabilities,np.array([0,1,0,1]),[False]*4)['accepted'],0)

    # Prueba automatizada: verifica inference rejects ambiguity and confirms once until release.
    def test_inference_rejects_ambiguity_and_confirms_once_until_release(self):
        runtime=web_app.Runtime();sid=runtime.new_session('lsm');session=runtime.session(sid);session.holistic=object()
        fake=types.SimpleNamespace(mediapipe_detection=lambda image,model:(image,object()),extract_keypoints=lambda r:self.raw[0],hands_detected=lambda r:True)
        # Ayudante de prueba para Model.
        class Model:
            probabilities=np.array([.99,.01],np.float32)
            # Ayudante de prueba para   call  .
            def __call__(self,*args,**kwargs):return types.SimpleNamespace(numpy=lambda:self.probabilities[None])
        model=Model();meta={'created_at':'new','preprocessing':HAND_PREPROCESSING,'labels':[{'id':'a','text':'A'},{'id':'b','text':'B'}]}
        encoded=base64.b64encode(cv2.imencode('.jpg',np.ones((32,32,3),np.uint8)*100)[1]).decode()
        clock=[100.]
        # Ayudante de prueba para tick.
        def tick():clock[0]+=.25;return clock[0]
        confirms=[]
        with patch.dict('sys.modules',{'utils':fake}),patch.object(runtime,'load_model',return_value=(model,meta)),patch('web_app.time.monotonic',side_effect=tick):
            for i in range(45):
                r=runtime.frame({'session':sid,'image':encoded,'mode':'test'});confirms+= [r['confirmed']] if r['confirmed'] else []
            model.probabilities=np.array([.01,.99],np.float32)
            for i in range(15):
                r=runtime.frame({'session':sid,'image':encoded,'mode':'test'});confirms+= [r['confirmed']] if r['confirmed'] else []
            self.assertEqual([r['id'] for r in confirms],['a'])
            fake.hands_detected=lambda r:False
            for i in range(5):runtime.frame({'session':sid,'image':encoded,'mode':'test'})
            fake.hands_detected=lambda r:True
            for i in range(38):
                r=runtime.frame({'session':sid,'image':encoded,'mode':'test'});confirms+= [r['confirmed']] if r['confirmed'] else []
            self.assertEqual([r['id'] for r in confirms],['a','b'])
            model.probabilities=np.array([.5,.5],np.float32)
            for i in range(7):r=runtime.frame({'session':sid,'image':encoded,'mode':'test'})
            self.assertIsNone(r['candidate']);self.assertIsNone(r['confirmed']);self.assertTrue(r['rejection_reason'])

    # Prueba automatizada: verifica capture waits for quality then saves provenance without images.
    def test_capture_waits_for_quality_then_saves_provenance_without_images(self):
        runtime=web_app.Runtime();sid=runtime.new_session('lsm','person-1',quality_gate=True);session=runtime.session(sid);session.holistic=object();runtime.start_capture(sid,True,'batch-1')
        current=[np.zeros(data.FEATURE_DIM,np.float32)]
        fake=types.SimpleNamespace(mediapipe_detection=lambda image,model:(image,object()),extract_keypoints=lambda r:current[0],hands_detected=lambda r:bool(np.any(current[0])))
        encoded=base64.b64encode(cv2.imencode('.jpg',np.ones((32,32,3),np.uint8)*100)[1]).decode()
        with patch.dict('sys.modules',{'utils':fake}),patch('web_app.image_quality',return_value={'warnings':[]}):
            for _ in range(3):self.assertEqual(runtime.frame({'session':sid,'image':encoded})['phase'],'waiting-for-hands')
            self.assertEqual(len(session.capture['points']),0)
            current[0]=self.raw[0]
            for _ in range(30):result=runtime.frame({'session':sid,'image':encoded})
            draft=result['draft_id'];self.assertTrue(draft)
        path=data.draft_dir('lsm')/(draft+'.npz')
        self.assertEqual(data.sequence_metadata(path)['participant'],'person-1')
        self.assertEqual(list(path.parent.glob('*.jpg')),[])

    # Prueba automatizada: verifica sample review returns timeline not images or landmarks.
    def test_sample_review_returns_timeline_not_images_or_landmarks(self):
        from dataset_tools import inspect_sample
        filename=data.save_sequence('lsm','hola',self.raw)
        result=inspect_sample('lsm',Path(filename).stem)
        self.assertEqual(len(result['timeline']),30)
        self.assertIn('motion',result['timeline'][0]);self.assertNotIn('points',result)
        with self.assertRaises(ValueError):inspect_sample('asl',Path(filename).stem)

    # Prueba automatizada: verifica admin sample mutations recover and keep other languages.
    def test_admin_sample_mutations_recover_and_keep_other_languages(self):
        from studio_services import dataset_operation
        from test_admin import configure
        configure(self.root/'admin'/'auth.json')
        runtime=web_app.Runtime()
        filename=data.save_sequence('lsm','hola',self.raw)
        data.save_sequence('asl','hola',self.raw)
        payload={'language':'lsm','samples':[Path(filename).stem],'target':'gracias','confirmed':True}
        with self.assertRaises(PermissionError):dataset_operation(runtime,'/api/dataset/move',payload)
        payload['password']='test-only-password'
        dataset_operation(runtime,'/api/dataset/move',payload)
        self.assertEqual(data.inventory('lsm')[0]['samples'],0)
        self.assertEqual(data.inventory('lsm')[1]['samples'],1)
        dataset_operation(runtime,'/api/dataset/delete',payload)
        self.assertEqual(data.inventory('lsm')[1]['samples'],0)
        self.assertEqual(data.inventory('asl')[0]['samples'],1)
        self.assertTrue(list((self.root/'trash'/'lsm').glob('*/*/*.npz')))

    # Prueba automatizada: verifica restore checks removed classes and loads legacy model.
    def test_restore_checks_removed_classes_and_loads_legacy_model(self):
        import tensorflow as tf
        from studio_services import activate_version,versions
        version='a'*32;root=langs.model_dir('lsm');bundle=root/version;bundle.mkdir(parents=True)
        model=tf.keras.Sequential([tf.keras.layers.Input((30,data.FEATURE_DIM)),tf.keras.layers.GlobalAveragePooling1D(),tf.keras.layers.Dense(2,activation='softmax')])
        model.save(bundle/'model.keras')
        metadata={'language':'lsm','pipeline':langs.pipeline_spec(),'labels':langs.labels_for('lsm')[:2],'preprocessing':None,'created_at':'2026-10-27T12:00:00Z','samples':60,'test_accuracy':.5}
        (bundle/'metadata.json').write_text(json.dumps(metadata))
        with self.assertRaises(ValueError):activate_version('lsm',version)
        for label in ('hola','gracias'):
            for _ in range(30):data.save_sequence('lsm',label,self.raw)
        self.assertTrue(activate_version('lsm',version)['activated'])
        self.assertTrue(versions('lsm')[0]['active'])
        loaded,meta=web_app.Runtime().load_model('lsm')
        self.assertEqual(loaded.output_shape[-1],2);self.assertIsNone(meta['preprocessing'])

    # Prueba automatizada: verifica duplicate sessions are unioned before splitting.
    def test_duplicate_sessions_are_unioned_before_splitting(self):
        records=[];labels=langs.labels_for('lsm')[:1]
        for i in range(2):
            filename=data.save_sequence('lsm','hola',self.raw,metadata={'session_id':f'session-{i}'})
            records.append(filename)
        different=self.raw.copy();regions(different)[2][:,:,0]+=.05
        data.save_sequence('lsm','hola',different,metadata={'session_id':'session-1'})
        raw=np.stack([self.raw,self.raw,different]);groups,_=training_provenance('lsm',raw,np.array([0,0,0]),labels)
        self.assertEqual(len(set(groups)),1)
