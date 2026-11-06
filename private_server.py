"""Acceso privado del laboratorio: un único backend persistente y Tailscale Serve.

No instala Tailscale, no inicia sesión y no utiliza Funnel. Ejecutar status primero.
"""
from process_status import process_alive
import argparse
import json
import os
import plistlib
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'web_data'
CONFIG = DATA / 'server' / 'private.json'
LABEL = 'mx.sena.laboratorio'
PORT = 8765
TARGET = f'http://127.0.0.1:{PORT}'


# Representa un fallo controlado de la configuración privada heredada.
class SetupError(RuntimeError):
    pass


# Localiza el ejecutable instalado de Tailscale sin instalarlo ni iniciar sesión.
def cli_path():
    for path in ('/Applications/Tailscale.app/Contents/MacOS/Tailscale', shutil.which('tailscale')):
        if path and Path(path).is_file():
            return str(path)
    raise SetupError('Falta instalar Tailscale y completar su inicio de sesión.')


# Ejecuta un comando con tiempo límite y transforma sus fallos en mensajes de configuración.
def command(args, timeout=15):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise SetupError('No se pudo comunicar con el servicio. Comprueba Tailscale y vuelve a intentar.') from None
    if result.returncode:
        raise SetupError('Tailscale no completó la operación. Revisa su aplicación, conexión y autorización de HTTPS.')
    return result.stdout


# Ejecuta una consulta y exige que devuelva un objeto JSON válido.
def read_json_output(args):
    try:
        result = json.loads(command(args))
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise SetupError('Respuesta de Tailscale incompatible; no se modificó su configuración.') from None


# Deriva el origen HTTPS del nombre DNS de una Mac conectada a Tailscale.
def discover_origin(status):
    if status.get('BackendState') != 'Running' or not status.get('Self', {}).get('Online'):
        raise SetupError('Abre Tailscale, inicia sesión y conecta esta Mac a la red del laboratorio.')
    dns = status.get('Self', {}).get('DNSName', '').rstrip('.').lower()
    if len(dns) > 253 or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+ts\.net', dns):
        raise SetupError('No hay un nombre HTTPS válido de Tailscale. Revisa MagicDNS en tu red.')
    return 'https://' + dns


# Comprueba que Serve pertenezca a Seña y que no haya Funnel u otro servicio que se sobrescribiría.
def check_proxy(config, origin):
    """Evitar exposición pública y cambios a otros servicios del equipo."""
    if any(config.get('AllowFunnel', {}).values()):
        raise SetupError('Funnel está activo. No se modificará una configuración con acceso público.')
    if not any(config.values()):
        return False
    authority = origin.removeprefix('https://') + ':443'
    permitted = {'TCP', 'Web', 'AllowFunnel'}
    if (set(config) - permitted or config.get('TCP') != {'443': {'HTTPS': True}}
            or config.get('Web') != {authority: {'Handlers': {'/': {'Proxy': TARGET}}}}):
        raise SetupError('Ya hay otro servicio en Tailscale Serve. Se conserva; no se sobrescribe.')
    return True


# Consulta si existe una cuenta administradora activa para el despliegue autenticado heredado.
def configured_admin():
    path = DATA / 'accounts' / 'team.sqlite3'
    if not path.exists():
        return False
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as db:
        return bool(db.execute("SELECT 1 FROM users WHERE active=1 AND role='admin' LIMIT 1").fetchone())


# Comprueba si el último trabajo de entrenamiento sigue vivo antes de cambiar el servicio.
def training_active():
    files = sorted((DATA / 'jobs').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if files:
        job = json.loads(files[0].read_text())
        if job.get('state') == 'running' and isinstance(job.get('pid'), int):
            return process_alive(job['pid'])
    return False


# Lee y valida la configuración privada persistida en disco.
def current_config():
    if not CONFIG.exists():
        return {'origin': None}
    result = json.loads(CONFIG.read_text())
    origin = result.get('origin')
    if origin is not None:
        # Reuse strict validation without accepting arbitrary CLI options or URLs.
        normalized = discover_origin({'BackendState': 'Running', 'Self': {'Online': True, 'DNSName': origin.removeprefix('https://')}})
        if origin != normalized:
            raise SetupError('La dirección privada guardada no es válida.')
    return result


# Guarda el origen privado de forma atómica y con permisos restringidos.
def write_config(origin):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    temp = CONFIG.with_suffix('.tmp')
    temp.write_text(json.dumps({'origin': origin, 'port': PORT, 'transport': 'tailscale-serve'}, indent=2))
    temp.chmod(0o600)
    os.replace(temp, CONFIG)


# Activa o desactiva el despliegue autenticado heredado preservando configuraciones ajenas.
def configure(enable):
    if training_active():
        raise SetupError('Espera a que termine el entrenamiento antes de cambiar el acceso.')
    if not configured_admin():
        raise SetupError('Crea primero la cuenta administradora en http://127.0.0.1:8765.')
    cli = cli_path()
    origin = discover_origin(read_json_output([cli, 'status', '--json']))
    existing = read_json_output([cli, 'serve', 'status', '--json'])
    ours = check_proxy(existing, origin)
    if not enable:
        if ours:
            command([cli, 'serve', '--bg', '--https=443', 'off'])
        write_config(None)
        print('Acceso privado detenido. Seña vuelve a ' + TARGET)
        return
    old = current_config().get('origin')
    write_config(origin)
    try:
        # The managed backend reads the file and restarts only its own child.
        # It may take a few seconds; do not report success until it accepts Host.
        wait_for_backend(origin)
        command([cli, 'serve', '--bg', '--https=443', '--yes', TARGET], timeout=45)
        if not check_proxy(read_json_output([cli, 'serve', 'status', '--json']), origin):
            raise SetupError('No se confirmó el proxy privado.')
    except Exception:
        write_config(old)
        # A partially enabled mapping can point only to the authenticated backend.
        # Remove solely this exact mapping, preserving any other user's changes.
        try:
            now = read_json_output([cli, 'serve', 'status', '--json'])
            if check_proxy(now, origin) and not ours:
                command([cli, 'serve', '--bg', '--https=443', 'off'])
        except SetupError:
            pass
        raise
    print('Acceso HTTPS configurado para la red privada: ' + origin)
    print('Cada integrante necesita Tailscale y su propia cuenta de Seña.')
    print('Falta comprobar la conexión desde un segundo equipo del laboratorio.')


# Espera a que el backend acepte el Host HTTPS configurado antes de publicar el proxy.
def wait_for_backend(origin, attempts=30):
    from urllib.request import Request, urlopen
    from urllib.parse import urlsplit
    for _ in range(attempts):
        try:
            request = Request(TARGET + '/', headers={'Host': urlsplit(origin).netloc})
            with urlopen(request, timeout=1) as response:
                if response.status == 200 and b'Se\xc3\xb1a' in response.read():
                    return
        except OSError:
            pass
        time.sleep(.5)
    raise SetupError('El servicio de Seña no aceptó la dirección privada. Inicia su servicio persistente y revisa los registros.')


# Construye la definición del servicio LaunchAgent de macOS.
def agent_definition():
    directory = DATA / 'server'
    return {'Label': LABEL, 'ProgramArguments': [sys.executable, str(ROOT / 'private_server.py'), 'run'],
            'WorkingDirectory': str(ROOT), 'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 10,
            'StandardOutPath': str(directory / 'service.log'), 'StandardErrorPath': str(directory / 'service-error.log'),
            'EnvironmentVariables': {'PYTHONUNBUFFERED': '1', 'TF_CPP_MIN_LOG_LEVEL': '2'}}


# Instala y arranca el supervisor local después de comprobar sus condiciones de funcionamiento.
def install_agent():
    if sys.platform != 'darwin':
        raise SetupError('El servicio automático incluido es para macOS.')
    path = Path.home() / 'Library' / 'LaunchAgents' / (LABEL + '.plist')
    definition = agent_definition()
    if path.exists() and plistlib.loads(path.read_bytes()).get('ProgramArguments') != definition['ProgramArguments']:
        raise SetupError('Existe otro servicio con este nombre. No se sobrescribirá.')
    loaded = subprocess.run(['launchctl', 'print', f'gui/{os.getuid()}/{LABEL}'], capture_output=True).returncode == 0
    if not loaded:
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', PORT)) == 0:
                raise SetupError('El puerto 8765 sigue ocupado. Detén la instancia manual de Seña antes de instalar el servicio.')
    path.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(definition)); path.chmod(0o600)
    result = subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(path)], capture_output=True)
    if result.returncode:
        # Loaded already is harmless only when our exact definition is active.
        check = subprocess.run(['launchctl', 'print', f'gui/{os.getuid()}/{LABEL}'], capture_output=True)
        if check.returncode:
            raise SetupError('macOS no pudo activar el servicio. Revisa permisos de acceso a Documentos.')
    try:
        wait_for_backend(current_config().get('origin') or TARGET)
    except SetupError:
        subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}/{LABEL}'], capture_output=True)
        raise SetupError('El servicio no inició. Desbloquea la Mac, revisa el permiso de Python para Documentos y vuelve a instalar el servicio.') from None
    print('Servicio de Seña instalado y respondiendo; se iniciará al entrar en esta cuenta de macOS.')


# Supervisa una única instancia hija y la reinicia al cambiar el origen del modo autenticado.
def run_backend():
    """Un solo servidor; recargar origen mata únicamente el hijo que iniciamos."""
    lock_path = CONFIG.parent / 'service.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    import fcntl
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SetupError('Ya existe un supervisor de Seña.') from None
        stopping = False
        # Marca la solicitud de parada para cerrar ordenadamente el proceso hijo.
        def stop(*_):
            nonlocal stopping
            stopping = True
        signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
        while not stopping:
            origin = current_config().get('origin')
            args = [sys.executable, str(ROOT / 'web_app.py'), '--host', '127.0.0.1', '--port', str(PORT)]
            if origin:
                args += ['--public-url', origin]
            child = subprocess.Popen(args, cwd=ROOT)
            try:
                while not stopping and child.poll() is None and current_config().get('origin') == origin:
                    time.sleep(1)
            finally:
                if child.poll() is None:
                    child.send_signal(signal.SIGINT)
                    try:
                        child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        child.terminate(); child.wait(timeout=5)
            if not stopping:
                time.sleep(1)


# Verifica TLS y que el despliegue heredado exija autenticación para acceder al estado.
def verify_private_https(origin):
    """Check TLS and the anonymous login gate from this machine."""
    import ssl
    from urllib.request import urlopen
    from urllib.error import HTTPError
    try:
        try:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            context = ssl.create_default_context()
        with urlopen(origin + '/', context=context, timeout=8) as response:
            if response.status != 200 or b'account-gate' not in response.read(200000):
                return False
        try:
            with urlopen(origin + '/api/state', context=context, timeout=8):
                return False
        except HTTPError as exc:
            return exc.code == 401
    except OSError:
        return False


# Muestra el diagnóstico del despliegue autenticado heredado y la conexión de Tailscale.
def status():
    result = {'local_url': TARGET, 'configured_url': current_config().get('origin'), 'admin_ready': configured_admin(),
              'private_access_verified': False}
    try:
        cli = cli_path()
        origin = discover_origin(read_json_output([cli, 'status', '--json']))
        configured = check_proxy(read_json_output([cli, 'serve', 'status', '--json']), origin)
        result.update(tailscale_connected=True, url=origin, proxy_configured=configured)
        if configured and result['configured_url'] == origin:
            result['private_access_verified'] = verify_private_https(origin)
        result['verification_scope'] = 'Desde esta Mac; falta probar desde otro equipo del laboratorio.' 
    except SetupError as exc:
        result['pending'] = str(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))


# Selecciona la acción de administración del servicio privado recibida por línea de comandos.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'install-service', 'enable', 'disable', 'run'])
    args = parser.parse_args()
    try:
        if args.action == 'status': status()
        elif args.action == 'install-service': install_agent()
        elif args.action == 'run': run_backend()
        else: configure(args.action == 'enable')
    except (SetupError, OSError, ValueError, sqlite3.Error) as exc:
        print('Seña: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
