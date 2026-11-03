import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import types
import sys
import numpy as np
import web_app
from recognition_features import (prepare_sequence, smooth_landmarks, articulation_motion,
                                  FINGER_PREPROCESSING, DISCRIMINATIVE_PREPROCESSING)

# Ayudante de prueba para RuntimeSpeedTests.
class RuntimeSpeedTests(unittest.TestCase):
    # Prueba automatizada: verifica cached model skips json but changed artifacts reload.
    def test_cached_model_skips_json_but_changed_artifacts_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); directory=root/'a'; directory.mkdir()
            for path in (root/'current.json',directory/'metadata.json',directory/'model.keras'):
                path.write_text('old')
            runtime=web_app.Runtime()
            old=object(); meta={'labels':[{'id':'a'},{'id':'b'}]}
            with patch('web_app.model_dir',return_value=root):
                runtime.models['lsm']=(directory,old,meta)
                runtime.model_signatures['lsm']=runtime.model_signature('lsm',directory)
                with patch('web_app.model_metadata') as reader:
                    self.assertIs(runtime.load_model('lsm')[0],old)
                    reader.assert_not_called()
                (root/'current.json').write_text('disabled')
                with patch('web_app.model_metadata',return_value=None) as reader:
                    self.assertIsNone(runtime.load_model('lsm')); reader.assert_called_once()
                new=types.SimpleNamespace(input_shape=(None,web_app.SEQUENCE_LENGTH,web_app.FEATURE_DIM),output_shape=(None,2))
                fake=types.SimpleNamespace(keras=types.SimpleNamespace(models=types.SimpleNamespace(load_model=lambda *a,**kw:new)))
                with patch('web_app.model_metadata',return_value=(directory,meta)),patch.dict(sys.modules,{'tensorflow':fake}):
                    self.assertIs(runtime.load_model('lsm')[0],new)
                (directory/'model.keras').unlink()
                with patch('web_app.model_metadata',side_effect=ValueError('Falta modelo')):
                    with self.assertRaises(ValueError):runtime.load_model('lsm')

    # Prueba automatizada: verifica http connection is reused and rejected body closes.
    def test_http_connection_is_reused_and_rejected_body_closes(self):
        import http.client
        import threading
        from http.server import ThreadingHTTPServer
        # Ayudante de prueba para Quiet.
        class Quiet(web_app.Handler):
            # Evita escribir los registros HTTP de las peticiones simuladas en las pruebas.
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Quiet)
        server.local_mode=True;server.local_csrf='token';server.public_origin=None
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
        try:
            connection.request('GET','/static/phone.js')
            first=connection.getresponse();first.read()
            self.assertFalse(first.will_close)
            socket=connection.sock
            connection.request('GET','/static/speech.js')
            second=connection.getresponse();second.read()
            self.assertIs(connection.sock,socket)
            connection.request('POST','/api/session',body='{}',headers={'X-LSM-Token':'wrong'})
            rejected=connection.getresponse();rejected.read()
            self.assertEqual(rejected.status,403)
            self.assertTrue(rejected.will_close)
        finally:
            connection.close();server.shutdown();server.server_close();thread.join()

    # Prueba automatizada: verifica v5 preprocessing preserves exact values.
    def test_v5_preprocessing_preserves_exact_values(self):
        from test_finger_geometry import FingerGeometryTests
        points=FingerGeometryTests().hand()
        expected=np.concatenate([prepare_sequence(points,FINGER_PREPROCESSING),articulation_motion(smooth_landmarks(points))],axis=-1)
        np.testing.assert_array_equal(prepare_sequence(points,DISCRIMINATIVE_PREPROCESSING),expected)
