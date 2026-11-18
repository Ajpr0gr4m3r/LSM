"""Prepara el entorno de esta copia de Seña y abre la aplicación local."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
ENV = ROOT / '.venv'
ENV_PYTHON = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
PYTHON_CHECK = '''
import struct
import sys
if sys.version_info[:2] != (3, 11) or struct.calcsize('P') != 8:
    raise SystemExit(1)
'''
DEPENDENCY_CHECK = '''
from importlib.metadata import version
from importlib.util import find_spec
if (version('tensorflow') != '2.15.1' or version('keras') != '2.15.0'
        or version('mediapipe') != '0.10.14'
        or any(find_spec(module) is None for module in
               ('numpy', 'cv2', 'sklearn', 'matplotlib', 'seaborn'))):
    raise SystemExit(1)
'''


def passes(command, check):
    try:
        return subprocess.run([*command, '-c', check], cwd=ROOT, timeout=15,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_python():
    candidates = [[sys.executable]]
    if os.name == 'nt' and shutil.which('py'):
        candidates.append(['py', '-3.11'])
    if shutil.which('python3.11'):
        candidates.append(['python3.11'])
    for command in candidates:
        if passes(command, PYTHON_CHECK):
            return command
    raise RuntimeError('Instala Python 3.11 de 64 bits y vuelve a ejecutar iniciar.py.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instalar', action='store_true',
                        help='Vuelve a resolver las dependencias de requirements.txt.')
    args, web_args = parser.parse_known_args()
    try:
        if not ENV.exists():
            print('Creando el entorno de Seña para esta computadora…', flush=True)
            subprocess.run([*find_python(), '-m', 'venv', str(ENV)], cwd=ROOT, check=True)
        if not passes([str(ENV_PYTHON)], PYTHON_CHECK):
            raise RuntimeError('El entorno .venv no funciona con Python 3.11 de 64 bits. '
                               'Renombra .venv a .venv.bak y vuelve a ejecutar iniciar.py.')
        if args.instalar or not passes([str(ENV_PYTHON)], DEPENDENCY_CHECK):
            print('Instalando las dependencias de Seña…', flush=True)
            subprocess.run([str(ENV_PYTHON), '-m', 'pip', 'install', '-r', 'requirements.txt'],
                           cwd=ROOT, check=True)
        return subprocess.call([str(ENV_PYTHON), '-u', 'web_app.py', *web_args], cwd=ROOT)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Seña no pudo iniciar. {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
