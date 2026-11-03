"""The actual HTTP server must serve every script referenced by the entry page."""
import re
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
import web_app

class StaticAssetsTests(unittest.TestCase):
    def test_local_page_has_no_login_gate_and_serves_every_script(self):
        class Quiet(web_app.Handler):
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Quiet)
        server.local_mode = True
        server.local_csrf = 'test-local-csrf'
        server.public_origin = None
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            html = urllib.request.urlopen(base).read().decode()
            self.assertRegex(html, r'<section id="account-gate" hidden')
            scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
            self.assertIn('/static/speech.js', scripts)
            for path in scripts:
                with self.subTest(script=path), urllib.request.urlopen(base + path) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn('javascript', response.headers['Content-Type'])
            import json
            status = json.load(urllib.request.urlopen(base + '/api/auth/status'))
            self.assertTrue(status['user']['local'])
            self.assertFalse(status['setup_required'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
