import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import private_server as server

ORIGIN='https://sena.tail123.ts.net'


def proxy():
    return {'TCP':{'443':{'HTTPS':True}},'Web':{'sena.tail123.ts.net:443':{'Handlers':{'/':{'Proxy':server.TARGET}}}}}


class PrivateServerTests(unittest.TestCase):
    def test_rejects_unknown_public_or_other_proxy_configuration(self):
        self.assertFalse(server.check_proxy({},ORIGIN))
        self.assertTrue(server.check_proxy(proxy(),ORIGIN))
        for changed in [dict(proxy(),AllowFunnel={'sena.tail123.ts.net:443':True}),
                        dict(proxy(),TCP={'8443':{'HTTPS':True}}),{'Web':{'other':{}}},dict(proxy(),Extra='unknown')]:
            with self.assertRaises(server.SetupError):server.check_proxy(changed,ORIGIN)

    def test_origin_is_obtained_only_from_connected_tailscale_and_valid_hostname(self):
        def status(name,online=True):return {'BackendState':'Running','Self':{'Online':online,'DNSName':name}}
        self.assertEqual(server.discover_origin(status('sena.tail123.ts.net.')),ORIGIN)
        for value in ['https://evil.example','evil.example','foo.ts.net/path','x.ts.net:443',';touch /tmp/a','-host.ts.net']:
            with self.assertRaises(server.SetupError):server.discover_origin(status(value))
        with self.assertRaises(server.SetupError):server.discover_origin(status('sena.tail123.ts.net',False))

    def test_enable_checks_existing_admin_and_preserves_config_when_proxy_fails(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server,'CONFIG',Path(temp)/'server.json'):
            with patch.object(server,'training_active',return_value=True):
                with self.assertRaises(server.SetupError):server.configure(True)
            with patch.object(server,'training_active',return_value=False),patch.object(server,'configured_admin',return_value=False):
                with self.assertRaises(server.SetupError):server.configure(True)
            server.write_config(None)
            with patch.object(server,'training_active',return_value=False),patch.object(server,'configured_admin',return_value=True),patch.object(server,'cli_path',return_value='tailscale'),patch.object(server,'read_json_output',side_effect=[{'BackendState':'Running','Self':{'Online':True,'DNSName':'sena.tail123.ts.net'}},{},{}]),patch.object(server,'wait_for_backend'),patch.object(server,'command',side_effect=server.SetupError('fixture failure')):
                with self.assertRaises(server.SetupError):server.configure(True)
            self.assertIsNone(server.current_config()['origin'])

    def test_success_uses_serve_and_loopback_backend_without_funnel(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(server,'CONFIG',Path(temp)/'server.json'),patch.object(server,'training_active',return_value=False),patch.object(server,'configured_admin',return_value=True),patch.object(server,'cli_path',return_value='tailscale'),patch.object(server,'read_json_output',side_effect=[{'BackendState':'Running','Self':{'Online':True,'DNSName':'sena.tail123.ts.net'}},{},proxy()]),patch.object(server,'wait_for_backend'),patch.object(server,'command') as run,contextlib.redirect_stdout(io.StringIO()):
            server.configure(True)
            self.assertEqual(server.current_config()['origin'],ORIGIN)
            command=run.call_args.args[0]
            self.assertEqual(command,['tailscale','serve','--bg','--https=443','--yes',server.TARGET])
            self.assertNotIn('funnel',command)

    def test_launch_agent_uses_exact_current_python_and_one_supervisor(self):
        agent=server.agent_definition()
        self.assertEqual(agent['WorkingDirectory'],str(server.ROOT))
        self.assertEqual(agent['ProgramArguments'][1:], [str(server.ROOT/'private_server.py'),'run'])
        self.assertTrue(agent['KeepAlive']);self.assertTrue(agent['RunAtLoad'])

    def test_corrupted_config_is_not_passed_to_backend(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(server,'CONFIG',Path(temp)/'server.json'):
            server.CONFIG.write_text(json.dumps({'origin':'https://evil.example/--options'}))
            with self.assertRaises(server.SetupError):server.current_config()

    def test_supervisor_restarts_only_its_child_and_closes_it_on_exit(self):
        import subprocess, sys, time, signal, shutil, os
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            shutil.copy2(Path(server.__file__),root/'private_server.py')
            (root/'web_app.py').write_text("import os,sys,json,time\nfrom pathlib import Path\np=Path('started.jsonl')\nwith p.open('a') as f:f.write(json.dumps({'pid':os.getpid(),'args':sys.argv[1:]})+'\\n')\ntime.sleep(60)\n")
            manager=subprocess.Popen([sys.executable,str(root/'private_server.py'),'run'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            def starts(count):
                deadline=time.monotonic()+6
                while time.monotonic()<deadline:
                    file=root/'started.jsonl'
                    rows=[json.loads(line) for line in file.read_text().splitlines()] if file.exists() else []
                    if len(rows)>=count:return rows
                    time.sleep(.05)
                self.fail('El supervisor no inició/reinició el backend.')
            try:
                first=starts(1)[0]
                self.assertNotIn('--public-url',first['args'])
                config=root/'web_data'/'server'/'private.json'
                config.write_text(json.dumps({'origin':ORIGIN}))
                second=starts(2)[1]
                self.assertNotEqual(first['pid'],second['pid'])
                self.assertEqual(second['args'][-2:],['--public-url',ORIGIN])
            finally:
                manager.send_signal(signal.SIGTERM)
                try:manager.wait(timeout=8)
                except subprocess.TimeoutExpired:manager.kill();manager.wait()
            with self.assertRaises(ProcessLookupError):os.kill(second['pid'],0)

    def test_https_check_requires_valid_tls_and_protected_data(self):
        import ssl
        from urllib.error import HTTPError, URLError
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'<section id="account-gate">'
        with patch('urllib.request.urlopen', side_effect=[Response(), HTTPError(ORIGIN+'/api/state',401,'Unauthorized',{},None)]) as request:
            self.assertTrue(server.verify_private_https(ORIGIN))
            self.assertEqual(request.call_args.kwargs['context'].verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(request.call_args.kwargs['context'].check_hostname)
        with patch('urllib.request.urlopen', side_effect=[Response(),Response()]):
            self.assertFalse(server.verify_private_https(ORIGIN))
        with patch('urllib.request.urlopen', side_effect=URLError('invalid certificate')):
            self.assertFalse(server.verify_private_https(ORIGIN))
