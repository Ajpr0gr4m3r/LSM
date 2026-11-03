import base64
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen

import cv2
import web_app


# Ayudante de prueba para ConversationTests.
class ConversationTests(unittest.TestCase):
    # Prepara el estado temporal aislado que necesita cada prueba.
    def setUp(self):
        self.runtime = web_app.Runtime()

    # Prueba automatizada: verifica signs accumulate and send once after pause.
    def test_signs_accumulate_and_send_once_after_pause(self):
        created = self.runtime.create_conversation('lsm', None)
        room = self.runtime.conversations[created['room']]
        with patch('web_app.time.monotonic', return_value=10):
            self.runtime.append_conversation_sign(room, 'phone', 'H', .95)
        with patch('web_app.time.monotonic', return_value=12):
            self.runtime.append_conversation_sign(room, 'phone', 'O', .96)
        with patch('web_app.time.monotonic', return_value=15):
            state = self.runtime.conversation_state(room)
            self.assertEqual(state['sign_drafts']['phone'], 'HO')
            self.assertEqual(len(state['messages']), 0)
        with patch('web_app.time.monotonic', return_value=16):
            state = self.runtime.conversation_state(room)
            self.assertEqual([m['text'] for m in state['messages']], ['HO'])
            self.assertEqual(state['sign_drafts'], {})
            self.runtime.conversation_state(room)
            self.assertEqual(len(room['messages']), 1)
            self.runtime.append_conversation_sign(room, 'desktop', 'Hola', .95)
            self.runtime.append_conversation_sign(room, 'desktop', 'amigo', .95)
            self.assertEqual(room['sign_drafts']['desktop']['text'], 'Hola amigo')

    # Prueba automatizada: verifica room keys are independent and messages are temporary.
    def test_room_keys_are_independent_and_messages_are_temporary(self):
        created = self.runtime.create_conversation('lsm', None)
        self.assertIsNone(created['phone_url'])
        self.assertIsNone(created['qr_png'])
        room = self.runtime.conversation(created['room'], created['desktop_key'], 'desktop')
        self.assertEqual(room['language'], 'lsm')
        with self.assertRaisesRegex(ValueError, 'venció'):
            self.runtime.conversation(created['room'], created['desktop_key'], 'phone')
        self.runtime.conversation_message(room, 'Computadora', '  Hola   ¿cómo estás? ')
        self.assertEqual(self.runtime.conversation_state(room)['messages'][0]['text'], 'Hola ¿cómo estás?')
        incoming = self.runtime.phone_request('/api/phone/state', {
            'room': created['room'], 'key': self.runtime.conversations[created['room']]['phone_key']})
        self.assertEqual(incoming['messages'][0]['text'], 'Hola ¿cómo estás?')
        self.runtime.phone_request('/api/phone/message', {
            'room': created['room'], 'key': self.runtime.conversations[created['room']]['phone_key'], 'text': 'Sí, te veo'})
        self.assertEqual(self.runtime.conversation_state(room)['messages'][1]['sender'], 'Teléfono')
        with self.assertRaisesRegex(ValueError, '300 caracteres'):
            self.runtime.conversation_message(room, 'Teléfono', 'x' * 301)
        self.runtime.close_conversation(room['id'])
        self.assertNotIn(room['id'], self.runtime.conversations)

    # Prueba automatizada: verifica qr is generated offline and encodes the mobile token.
    def test_qr_is_generated_offline_and_encodes_the_mobile_token(self):
        created = self.runtime.create_conversation('lsm', 'https://sena.example.ts.net')
        phone_key = self.runtime.conversations[created['room']]['phone_key']
        self.assertEqual(created['phone_url'], f"https://sena.example.ts.net/phone/{created['room']}/{phone_key}")
        image = cv2.imdecode(__import__('numpy').frombuffer(base64.b64decode(created['qr_png']), dtype='uint8'), cv2.IMREAD_COLOR)
        decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
        self.assertEqual(decoded, created['phone_url'])

    # Prueba automatizada: verifica expired room is removed and phone session closed.
    def test_expired_room_is_removed_and_phone_session_closed(self):
        created = self.runtime.create_conversation('lsm', None)
        room = self.runtime.conversations[created['room']]
        sid = self.runtime.new_session('lsm')
        room['phone_session'] = sid
        room['expires'] = 0
        with patch('web_app.time.monotonic', return_value=1):
            with self.assertRaisesRegex(ValueError, 'venció'):
                self.runtime.conversation(created['room'], self.runtime.conversations[created['room']]['phone_key'], 'phone')
        self.assertNotIn(sid, self.runtime.sessions)
        self.assertNotIn(created['room'], self.runtime.conversations)

    # Prueba automatizada: verifica http routes create room and exchange messages both ways.
    def test_http_routes_create_room_and_exchange_messages_both_ways(self):
        old_runtime = web_app.RUNTIME
        web_app.RUNTIME = self.runtime
        server = ThreadingHTTPServer(('127.0.0.1', 0), web_app.Handler)
        server.local_mode = True; server.local_csrf = 'test-csrf'
        server.public_origin = None; server.phone_origin = 'https://sena.example.ts.net'
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            session = json.load(urlopen(base + '/api/auth/status'))
            # Ayudante de prueba para post.
            def post(path, body, host=None, origin=None):
                headers = {'Content-Type': 'application/json', 'X-LSM-Token': session['csrf']}
                if host: headers['Host'] = host
                else: headers['Origin'] = base
                if origin: headers['Origin'] = origin
                request = Request(base + path, data=json.dumps(body).encode(), headers=headers, method='POST')
                return json.load(urlopen(request))
            created = post('/api/conversation/create', {'language': 'lsm', 'shared_consent': True})
            self.assertIn('/phone/', created['phone_url'])
            post('/api/conversation/message', {'room': created['room'], 'key': created['desktop_key'], 'text': 'Hola'})
            token = self.runtime.conversations[created['room']]['phone_key']
            post('/api/phone/message', {'room': created['room'], 'key': token, 'text': 'Hola, te escucho'},
                 host='sena.example.ts.net', origin=server.phone_origin)
            state = post('/api/conversation/state', {'room': created['room'], 'key': created['desktop_key']})
            self.assertEqual([item['sender'] for item in state['messages']], ['Computadora', 'Teléfono'])
        finally:
            server.shutdown(); server.server_close(); thread.join()
            web_app.RUNTIME = old_runtime

    # Prueba automatizada: verifica phone page and assets require the configured host and valid link.
    def test_phone_page_and_assets_require_the_configured_host_and_valid_link(self):
        old_runtime = web_app.RUNTIME
        web_app.RUNTIME = self.runtime
        server = ThreadingHTTPServer(('127.0.0.1', 0), web_app.Handler)
        server.local_mode = True
        server.local_csrf = 'test-csrf'
        server.public_origin = None
        server.phone_origin = 'https://sena.example.ts.net'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            room = self.runtime.create_conversation('lsm', server.phone_origin)
            phone_key = self.runtime.conversations[room['room']]['phone_key']
            url = f'http://127.0.0.1:{server.server_port}/phone/{room["room"]}/{phone_key}'
            headers = {'Host': 'sena.example.ts.net'}
            with urlopen(Request(url, headers=headers)) as response:
                self.assertIn(b'Conecta tu tel', response.read())
            resource = f'http://127.0.0.1:{server.server_port}/static/phone.js'
            with urlopen(Request(resource, headers=headers)) as response:
                self.assertIn(b'getUserMedia', response.read())
            speech = f'http://127.0.0.1:{server.server_port}/static/speech.js'
            with urlopen(Request(speech, headers=headers)) as response:
                self.assertIn(b'class SenaSpeechQueue', response.read())
            font = f'http://127.0.0.1:{server.server_port}/static/vendor/manrope.woff2'
            with urlopen(Request(font, headers=headers)) as response:
                self.assertEqual(response.status, 200)
            try:
                urlopen(Request(url.replace(phone_key, 'wrong'), headers=headers))
                self.fail('Un código incorrecto no debe abrir la página móvil.')
            except Exception as error:
                self.assertTrue(getattr(error, 'code', None) in (410, 404))
            try:
                urlopen(Request(f'http://127.0.0.1:{server.server_port}/', headers=headers))
                self.fail('El origen móvil no debe servir la página principal.')
            except Exception as error:
                self.assertEqual(getattr(error, 'code', None), 403)
        finally:
            server.shutdown(); server.server_close(); thread.join()
            web_app.RUNTIME = old_runtime


if __name__ == '__main__':
    unittest.main()
