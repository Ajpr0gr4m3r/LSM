import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from recognition_analysis import (confusion_analysis, evaluate, calibrate_policy, accepted_mask,
    hard_weights, regression_check, temperature_probabilities, deduplicate)
from recognition_features import (DISCRIMINATIVE_PREPROCESSING,FINGER_PREPROCESSING,prepare_sequence,regions,feature_dimension)
from dataset_tools import persistent_split
from test_finger_geometry import FingerGeometryTests


# Ayudante de prueba para DiscriminativeTests.
class DiscriminativeTests(unittest.TestCase):
    # Prueba automatizada: verifica geometry preserves legacy channels and distinguishes order.
    def test_geometry_preserves_legacy_channels_and_distinguishes_order(self):
        raw=FingerGeometryTests().hand()
        h=regions(raw)[2];h[:,:,0]+=np.linspace(0,.12,30)[:,None]
        new=prepare_sequence(raw,DISCRIMINATIVE_PREPROCESSING)
        old=prepare_sequence(raw,FINGER_PREPROCESSING)
        np.testing.assert_array_equal(new[:,:old.shape[1]],old)
        self.assertEqual(new.shape,(30,feature_dimension(DISCRIMINATIVE_PREPROCESSING)))
        self.assertFalse(np.allclose(new[:,-86:],prepare_sequence(raw[::-1],DISCRIMINATIVE_PREPROCESSING)[:,-86:]))
        absent=prepare_sequence(np.zeros_like(raw),DISCRIMINATIVE_PREPROCESSING)
        self.assertTrue(np.all(absent==0))
        self.assertTrue(np.isfinite(new).all())

    # Prueba automatizada: verifica orientation retained and no hand swap.
    def test_orientation_retained_and_no_hand_swap(self):
        raw=FingerGeometryTests().hand();rotated=raw.copy();h=regions(rotated)[2]
        x=h[:,:,0].copy();h[:,:,0]=1-h[:,:,1];h[:,:,1]=x
        a=prepare_sequence(raw,DISCRIMINATIVE_PREPROCESSING);b=prepare_sequence(rotated,DISCRIMINATIVE_PREPROCESSING)
        self.assertFalse(np.allclose(a,b))
        self.assertTrue(np.all(a[:,-86+41:-4]==0))

    # Prueba automatizada: verifica confusions bidirectional and groups.
    def test_confusions_bidirectional_and_groups(self):
        labels=[{'id':str(i),'text':str(i)} for i in range(4)]
        result=confusion_analysis([[5,3,0,0],[2,5,2,0],[0,1,5,0],[0,0,0,8]],labels)
        self.assertEqual(result['pairs'][0]['errors'],5)
        self.assertEqual(set(result['groups'][0]),{'0','1','2'})

    # Prueba automatizada: verifica ambiguous class is disabled and unknown not fabricated.
    def test_ambiguous_class_is_disabled_and_unknown_not_fabricated(self):
        p=np.tile([.51,.49],(8,1));y=np.array([0,1]*4)
        policy=calibrate_policy(p,y,np.ones(8,bool))
        self.assertFalse(accepted_mask(p,policy).any())
        report=evaluate(p,y,[{'id':'a','text':'a'},{'id':'b','text':'b'}],policy)
        self.assertEqual(report['rejected'],8);self.assertIsNone(report['unknown_false_accept_rate'])

    # Prueba automatizada: verifica mining preserves equal class weight.
    def test_mining_preserves_equal_class_weight(self):
        y=np.array([0]*8+[1]*2);p=np.array([[.99,.01]]*7+[[.01,.99],[.01,.99],[.9,.1]])
        w=hard_weights(p,y)
        self.assertAlmostEqual(float(w[y==0].sum()),float(w[y==1].sum()),places=5)
        self.assertGreater(w[7],w[0]);self.assertLessEqual(w[7]/w[0],3)

    # Prueba automatizada: verifica temperature and dedup.
    def test_temperature_and_dedup(self):
        p=np.array([[.9,.1],[.2,.8]])
        np.testing.assert_allclose(temperature_probabilities(p,1),p)
        self.assertLess(temperature_probabilities(p,2)[0,0],.9)
        raw=np.ones((3,30,4));raw[-1]*=2
        points,targets,removed=deduplicate(raw,np.array([0,0,1]))
        self.assertEqual(removed,1);self.assertEqual(len(points),2)
        with self.assertRaises(ValueError):deduplicate(raw,np.array([0,1,1]))

    # Prueba automatizada: verifica holdout groups remain reserved when vocabulary grows.
    def test_holdout_groups_remain_reserved_when_vocabulary_grows(self):
        y=np.array([0,1]*30);groups=np.array([f'g{i//2}' for i in range(60)])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'split.json'
            first=persistent_split(y,groups,path)
            second=persistent_split(np.r_[y,[2]*40],np.r_[groups,[f'new{i}' for i in range(40)]],path)
            for before,after in zip(first,second):self.assertTrue(set(before)<=set(after))
            for a,b in ((second[0],second[1]),(second[0],second[2]),(second[1],second[2])):self.assertFalse(set(a)&set(b))

    def test_new_session_replenishes_training_without_moving_old_reserves(self):
        import json
        roles = ('train', 'validation', 'test')
        targets, groups, mapping = [], [], {}
        for label, counts in enumerate(((4, 60, 60), (100, 3, 3), (100, 3, 3), (100, 3, 3))):
            for role, count in zip(roles, counts):
                group = f'{label}-{role}'
                targets.extend([label] * count)
                groups.extend([group] * count)
                mapping[group] = role
        old_size = len(targets)
        for label, count in enumerate((11, 25, 25, 25)):
            targets.extend([label] * count)
            groups.extend(['new-session'] * count)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'split.json'
            path.write_text(json.dumps({'version': 1, 'groups': mapping}))
            parts = persistent_split(np.array(targets), np.array(groups), path)
            self.assertTrue(set(range(old_size, len(targets))) <= set(parts[0]))
            for role, indices in zip(roles, parts):
                self.assertTrue(all(mapping[groups[i]] == role for i in indices if i < old_size))

    # Prueba automatizada: verifica single class regression cannot hide in average.
    def test_single_class_regression_cannot_hide_in_average(self):
        old={'macro_f1':.9,'false_accept_rate':0.,'by_class':[{'id':'a','recall':1.,'accepted_recall':.9}]}
        new={'macro_f1':.95,'false_accept_rate':0.,'by_class':[{'id':'a','recall':.8,'accepted_recall':.8}]}
        self.assertFalse(regression_check(new,old)['passed'])

    # Prueba automatizada: verifica contrastive gradient and save reload standard inference.
    def test_contrastive_gradient_and_save_reload_standard_inference(self):
        import tensorflow as tf
        from discriminative_learning import supervised_contrastive_loss
        z=tf.Variable([[1.,.2],[.9,.1],[.1,1.],[.2,.9]])
        with tf.GradientTape() as tape:loss=supervised_contrastive_loss(tf.constant([0,0,1,1]),z)
        grad=tape.gradient(loss,z)
        self.assertTrue(np.isfinite(grad.numpy()).all())
        self.assertGreater(float(tf.reduce_sum(tf.abs(grad))),0)
        from model import build_web_model
        model=build_web_model(2,input_dim=feature_dimension(DISCRIMINATIVE_PREPROCESSING))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.keras';model.save(path)
            loaded=tf.keras.models.load_model(path,compile=False,safe_mode=True)
            self.assertEqual(loaded.input_shape,model.input_shape)

    # Prueba automatizada: verifica regrouping cannot leak old holdout samples.
    def test_regrouping_cannot_leak_old_holdout_samples(self):
        y=np.array([0,1]*30);groups=np.array([f'g{i//2}' for i in range(60)]);hashes=[str(i) for i in range(60)]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'split.json'
            train,val,test=persistent_split(y,groups,path,fingerprints=hashes)
            regroup=groups.copy();regroup[train[0]]='merged';regroup[test[0]]='merged'
            with self.assertRaises(ValueError):persistent_split(y,regroup,path,fingerprints=hashes)

    # Prueba automatizada: verifica live inference uses versioned features policy and stability.
    def test_live_inference_uses_versioned_features_policy_and_stability(self):
        import base64,cv2,types
        from unittest.mock import patch
        import web_app
        raw=FingerGeometryTests().hand()[0]
        current=[raw];seen=[]
        fake=types.SimpleNamespace(mediapipe_detection=lambda image,model:(image,object()),extract_keypoints=lambda r:current[0],hands_detected=lambda r:bool(np.any(current[0])))
        # Ayudante de prueba para Model.
        class Model:
            # Ayudante de prueba para   call  .
            def __call__(self,x,training=False):
                seen.append(x.copy())
                return types.SimpleNamespace(numpy=lambda:np.array([[.9,.1]],np.float32))
        runtime=web_app.Runtime();sid=runtime.new_session('lsm','test');session=runtime.session(sid);session.holistic=object()
        metadata={'labels':[{'id':'a','text':'A'},{'id':'b','text':'B'}],'preprocessing':DISCRIMINATIVE_PREPROCESSING,'created_at':'test','decision_input':'single-window-v1','stability_frames':3,
                  'decision_policy':{'threshold':.7,'margin':.1}}
        encoded=base64.b64encode(cv2.imencode('.jpg',np.full((32,32,3),100,np.uint8))[1]).decode()
        clock=[100.]
        # Ayudante de prueba para now.
        def now():return clock[0]
        with patch.dict('sys.modules', {'utils': fake}), \
             patch.object(runtime, 'load_model', return_value=(Model(), metadata)), \
             patch.object(runtime, 'image_detector', return_value=object()), \
             patch('web_app.time.monotonic', side_effect=now):
            outputs=[]
            for _ in range(36):
                clock[0]+=.2;outputs.append(runtime.frame({'session':sid,'image':encoded,'mode':'test'}))
            self.assertEqual(sum(bool(o['confirmed']) for o in outputs),1)
            self.assertTrue(outputs[31]['confirmed'])
            np.testing.assert_allclose(seen[0][0],prepare_sequence(np.stack([raw]*30),DISCRIMINATIVE_PREPROCESSING))
            current[0]=np.zeros_like(raw);clock[0]+=.2
            runtime.frame({'session':sid,'image':encoded,'mode':'test'})
            self.assertEqual(len(session.frames),0)

    # Prueba automatizada: verifica training selection keeps existing classes.
    def test_training_selection_keeps_existing_classes(self):
        from unittest.mock import patch
        import web_train
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);version='c'*32;(root/version).mkdir()
            (root/'current.json').write_text(json.dumps({'version':version}))
            (root/version/'metadata.json').write_text(json.dumps({'pipeline':web_train.pipeline_spec(),'labels':[{'id':'old'}]}))
            with patch.object(web_train,'model_dir',return_value=root),patch('web_dataset.inventory',return_value=[{'id':'old','samples':40}]):
                self.assertEqual(web_train.retained_label_ids('lsm',['new','another']),['new','another','old'])


    # Prueba automatizada: verifica incomplete participants never claim person independence.
    def test_incomplete_participants_never_claim_person_independence(self):
        from unittest.mock import patch
        from dataset_tools import training_provenance,digest
        raw=np.stack([np.full((30,feature_dimension(None)),i+1,np.float32) for i in range(4)])
        rows=[{'label':'a','valid':True,'sha256':digest(p),'conflict':False,
               'metadata':{'session_id':str(i),**({'participant':str(i)} if i<3 else {})}} for i,p in enumerate(raw)]
        with patch('dataset_tools.sample_rows',return_value=rows):
            groups,info=training_provenance('lsm',raw,np.zeros(4,int),[{'id':'a'}])
        self.assertFalse(info['person_independent']);self.assertEqual(info['split_unit'],'session')
