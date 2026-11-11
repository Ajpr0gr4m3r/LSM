"""Autorización local de operaciones administrativas; nunca guarda texto claro."""
import hashlib
import hmac
import json
import os
import time
from pathlib import Path


# Protege las operaciones administrativas con contraseña derivada y límite de intentos.
class AdminGuard:
    # Inicializa la ruta de credenciales y los contadores de bloqueo temporal.
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.failures = 0
        self.window_started = 0
        self.blocked_until = 0

    # Comprueba la contraseña contra PBKDF2; rechaza credenciales inválidas o intentos bloqueados.
    def verify(self, password):
        now = time.monotonic()
        if now < self.blocked_until:
            raise PermissionError('Demasiados intentos. Espera cinco minutos antes de volver a intentar.')
        if now - self.window_started > 300:
            self.failures = 0
            self.window_started = now
        valid_input = isinstance(password, str) and 0 < len(password) <= 256
        supplied = password.encode('utf-8') if valid_input else b''
        secret = os.environ.get('SENA_ADMIN_PASSWORD')
        if secret:
            self._check(valid_input and hmac.compare_digest(supplied, secret.encode('utf-8')), now)
            return
        try:
            config = json.loads(self.config_path.read_text(encoding='utf-8'))
            if config['algorithm'] != 'pbkdf2-sha256' or config['iterations'] != 600000:
                raise ValueError('Configuración administrativa incompatible.')
            salt = bytes.fromhex(config['salt'])
            expected = bytes.fromhex(config['digest'])
        except (OSError, ValueError, KeyError, TypeError):
            raise PermissionError('No está configurado el acceso de administrador en este servidor.') from None
        digest = hashlib.pbkdf2_hmac('sha256', supplied, salt, config['iterations'])
        self._check(valid_input and hmac.compare_digest(digest, expected), now)

    def _check(self, valid, now):
        if not valid:
            self.failures += 1
            if self.failures >= 5:
                self.blocked_until = now + 300
            raise PermissionError('Contraseña de administrador incorrecta.')
        self.failures = 0
        self.window_started = now
