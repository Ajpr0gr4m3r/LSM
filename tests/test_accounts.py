"""Cuentas y aislamiento con un servidor HTTP real y datos temporales."""
import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

import numpy as np
import sign_languages as languages
import web_app
import web_dataset
from accounts import Accounts
from config import FEATURE_DIM

PASSWORD = 'fixture-password-only-123'


# Ayudante de prueba para AccountsTests.
class AccountsTests(unittest.TestCase):
    # Prueba automatizada: verifica persistence rotation revocation passwords and single use invite.
    def test_persistence_rotation_revocation_passwords_and_single_use_invite(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'users.sqlite3'; store=Accounts(path)
            admin=store.register('owner','Dueño',PASSWORD,bootstrap=True)
            with self.assertRaises(PermissionError): store.register('other','Otro',PASSWORD,bootstrap=True)
            invite=store.invite(admin)
            member=store.register('alice','Alicia',PASSWORD,invite)
            with self.assertRaises(PermissionError): store.register('bob','Bob',PASSWORD,invite)
            token,csrf=store.issue(member)
            self.assertEqual(Accounts(path).session(token)['user']['id'],member)
            rotated,_=store.issue(member,previous=token)
            self.assertIsNone(store.session(token))
            self.assertNotIn(PASSWORD,path.read_bytes().decode(errors='ignore'))
            self.assertNotIn(rotated,path.read_bytes().decode(errors='ignore'))
            store.disable(member,admin)
            self.assertIsNone(store.session(rotated))
            with self.assertRaises(PermissionError):store.login('alice',PASSWORD)
            store.enable(member);self.assertEqual(store.login('ALICE',PASSWORD)['id'],member)
            for _ in range(10):store.throttle('fixture-ip')
            with self.assertRaises(PermissionError):store.throttle('fixture-ip')
            with self.assertRaises(ValueError):store.disable(admin,admin)


# Ayudante de prueba para TeamHTTPTests.
class TeamHTTPTests(unittest.TestCase):
    # Prepara el estado temporal aislado que necesita cada prueba.
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();root=Path(self.folder.name)
        self.patches=[patch.object(languages,'WEB_DATA',root/'data'),
                      patch.object(languages,'WEB_MODELS',root/'models'),
                      patch.object(web_app,'WEB_DATA',root/'data')]
        for item in self.patches:item.start()
        self.runtime=web_app.Runtime()
        # Ayudante de prueba para verify.
        def verify(value):
            if value!='fixture-admin-secret':raise PermissionError('Contraseña incorrecta.')
        self.runtime.admin.verify=verify
        self.store=Accounts(root/'accounts.sqlite3')
        self.patches.extend([patch.object(web_app,'RUNTIME',self.runtime),patch.object(web_app,'ACCOUNTS',self.store)])
        for item in self.patches[-2:]:item.start()
        # Ayudante de prueba para Quiet.
        class Quiet(web_app.Handler):
            # Evita escribir los registros HTTP de las peticiones simuladas en las pruebas.
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Quiet)
        self.server.public_origin=None
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.owner=self.client();self.alice=self.client();self.bob=self.client()
        for client in (self.owner,self.alice,self.bob):self.get(client,'/api/auth/status')
        status,result=self.post(self.owner,'/api/auth/setup',dict(username='owner',name='Dueño',password=PASSWORD,shared_consent=True))
        self.assertEqual(status,200);self.owner['csrf']=result['csrf']
        for name,client in (('alice',self.alice),('bob',self.bob)):
            _,invite=self.post(self.owner,'/api/auth/invite',{})
            code,result=self.post(client,'/api/auth/register',dict(username=name,name=name,password=PASSWORD,invite=invite['invite'],shared_consent=True))
            self.assertEqual(code,200);client['csrf']=result['csrf'];client['id']=result['user']['id']

    # Elimina los recursos temporales creados durante la prueba.
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        for item in reversed(self.patches):item.stop()
        self.folder.cleanup()

    # Ayudante de prueba para client.
    def client(self):
        jar=http.cookiejar.CookieJar()
        return {'opener':urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)),'jar':jar}

    # Ayudante de prueba para request.
    def request(self,client,path,body=None,csrf=None,origin=None):
        headers={'Origin':origin or self.base}
        if body is not None:headers.update({'Content-Type':'application/json','X-LSM-Token':csrf if csrf is not None else client.get('csrf','')})
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with client['opener'].open(req) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)

    # Ayudante de prueba para get.
    def get(self,client,path):
        status,data=self.request(client,path)
        if 'csrf' in data:client['csrf']=data['csrf']
        return status,data

    # Ayudante de prueba para post.
    def post(self,client,path,body,**kwargs):return self.request(client,path,body,**kwargs)

    # Prueba automatizada: verifica authentication csrf roles and cookie protection.
    def test_authentication_csrf_roles_and_cookie_protection(self):
        anonymous=self.client()
        self.assertEqual(self.get(anonymous,'/api/state')[0],401)
        self.assertEqual(self.post(self.alice,'/api/session',{'language':'lsm','shared_consent':True},csrf=self.bob['csrf'])[0],403)
        self.assertEqual(self.post(self.alice,'/api/session',{'language':'lsm'},origin='https://foreign.example')[0],403)
        for route in ('/api/train','/api/models/activate','/api/admin/delete-recordings','/api/dataset/import','/api/auth/invite','/api/auth/users'):
            self.assertEqual(self.post(self.alice,route,{'password':'fixture-admin-secret'})[0],403,route)
        cookie=next(iter(self.alice['jar']))
        self.assertIn('HttpOnly',cookie._rest);self.assertEqual(cookie._rest['SameSite'],'Strict')
        self.assertEqual(self.post(self.alice,'/api/auth/logout',{})[0],200)
        self.assertEqual(self.get(self.alice,'/api/state')[0],401)

    # Prueba automatizada: verifica drafts and cameras private saved examples shared.
    def test_drafts_and_cameras_private_saved_examples_shared(self):
        code,created=self.post(self.alice,'/api/session',{'language':'lsm','participant':'fake-bob','shared_consent':True})
        self.assertEqual(code,200);sid=created['session'];capture=self.runtime.session(sid)
        self.assertEqual(capture.owner_id,self.alice['id'])
        self.assertEqual(capture.provenance['participant'],'user:'+self.alice['id'])
        self.assertEqual(self.post(self.bob,'/api/reset',{'session':sid})[0],403)
        self.assertEqual(self.post(self.bob,'/api/close',{'session':sid})[0],403)
        self.assertIn(sid,self.runtime.sessions)
        points=np.ones((30,FEATURE_DIM),np.float32)
        draft=web_dataset.save_draft('lsm',points,capture.provenance)
        other=web_dataset.save_draft('lsm',points,{'owner_id':self.bob['id']})
        # Other people's pending drafts do not block Alice's capture.
        self.assertEqual(self.post(self.alice,'/api/capture',{'session':sid,'consecutive':True})[0],200)
        for client,ids in ((self.alice,[draft]),(self.bob,[other])):
            code,state=self.get(client,'/api/state');self.assertEqual(code,200)
            profile=next(p for p in state['profiles'] if p['id']=='lsm')
            self.assertEqual([d['id'] for d in profile['drafts']],ids)
        self.assertEqual(self.post(self.bob,'/api/capture/save',{'language':'lsm','draft_id':draft,'name':'Hola'})[0],403)
        self.assertEqual(self.post(self.bob,'/api/capture/discard',{'language':'lsm','draft_id':draft})[0],403)
        code,saved=self.post(self.alice,'/api/capture/save',{'language':'lsm','draft_id':draft,'name':'Hola'});self.assertEqual(code,200)
        self.assertEqual(self.post(self.bob,'/api/capture/save',{'language':'lsm','draft_id':draft,'name':'Hola'})[0],403)
        self.assertEqual(self.post(self.alice,'/api/capture/save',{'language':'lsm','draft_id':draft,'name':'Hola'})[1],saved)
        for client in (self.alice,self.bob):
            _,state=self.get(client,'/api/state');lsm=next(p for p in state['profiles'] if p['id']=='lsm')
            self.assertEqual(next(x for x in lsm['labels'] if x['id']=='hola')['samples'],1)
            self.assertEqual(sum(x['samples'] for p in state['profiles'] if p['id']!='lsm' for x in p['labels']),0)
        meta=web_dataset.sequence_metadata(languages.dataset_dir('lsm')/'hola'/saved['sample'])
        self.assertEqual(meta['owner_id'],self.alice['id'])
        self.assertEqual(self.post(self.owner,'/api/auth/disable',{'user_id':self.alice['id']})[0],200)
        self.assertNotIn(sid,self.runtime.sessions)
        self.assertEqual(self.get(self.alice,'/api/state')[0],401)

    # Prueba automatizada: verifica expired camera does not block reconnect.
    def test_expired_camera_does_not_block_reconnect(self):
        code,created=self.post(self.alice,'/api/session',{'language':'lsm','shared_consent':True})
        self.assertEqual(code,200)
        self.runtime.session(created['session']).touched -= 20
        code,reconnected=self.post(self.alice,'/api/session',{'language':'lsm','shared_consent':True})
        self.assertEqual(code,200)
        self.assertNotEqual(created['session'],reconnected['session'])
        self.assertNotIn(created['session'],self.runtime.sessions)

    # Prueba automatizada: verifica training in progress after restart blocks capture without reloading job per frame.
    def test_training_in_progress_after_restart_blocks_capture_without_reloading_job_per_frame(self):
        with patch.object(self.runtime,'job',return_value={'state':'running','pid':123456}), patch.object(web_app.os,'kill',side_effect=[None,OSError()]):
            self.assertTrue(self.runtime.training())
            self.assertFalse(self.runtime.training())
            self.assertEqual(self.runtime.job.call_count,1)

    # Prueba automatizada: verifica first account cannot be claimed through public deployment.
    def test_first_account_cannot_be_claimed_through_public_deployment(self):
        import types
        handler=types.SimpleNamespace(server=types.SimpleNamespace(public_origin='https://senas.example'),
                                      client_address=('127.0.0.1',1234),headers={})
        with self.assertRaises(PermissionError):
            web_app.team_access.auth_post(handler,'/api/auth/setup',
                {'username':'newowner','name':'Nuevo','password':PASSWORD,'shared_consent':True},
                self.store,self.runtime,{'user':None,'csrf':'fixture'})

    # Prueba automatizada: verifica host validation and secure cookie for public origin.
    def test_host_validation_and_secure_cookie_for_public_origin(self):
        handler=web_app.Handler.__new__(web_app.Handler);handler.server=self.server
        handler.server.public_origin='https://senas.example';handler.headers={'Host':'senas.example'}
        self.assertTrue(handler.trusted_host());handler.headers={'Host':'foreign.example'};self.assertFalse(handler.trusted_host())
        web_app.team_access.set_session(handler,'fixture');self.assertIn('; Secure',handler.session_cookie)
        self.server.public_origin=None
