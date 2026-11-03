"""Cuentas persistentes del equipo. SQLite, cookies opacas y CSRF por sesión."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager, closing
from pathlib import Path

ITERATIONS = 600000
COOKIE = 'sena_session'


# Calcula el hash SHA-256 de un token para no almacenarlo en claro en SQLite.
def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


# Gestiona las cuentas del modo de equipo heredado; el modo local actual no exige iniciar sesión.
class Accounts:
    # Conserva la ruta de la base SQLite sin abrir una conexión permanente.
    def __init__(self, path):
        self.path = Path(path)

    # Abre una transacción, crea las tablas si faltan y cierra la conexión al terminar.
    @contextmanager
    # Abre una transacción, crea las tablas si faltan y cierra la conexión al terminar.
    def db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=20)) as db, db:
            self.path.chmod(0o600)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    salt TEXT NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), csrf TEXT NOT NULL,
                    expires REAL NOT NULL, touched REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS invites (
                    token TEXT PRIMARY KEY, expires REAL NOT NULL, created_by TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                    key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL);
            ''')
            yield db

    # Indica si ya se registró alguna cuenta en este servidor.
    def configured(self):
        with self.db() as db:
            return bool(db.execute('SELECT 1 FROM users LIMIT 1').fetchone())

    # Devuelve únicamente los campos de usuario que pueden enviarse al navegador.
    @staticmethod
    # Devuelve únicamente los campos de usuario que pueden enviarse al navegador.
    def public(row):
        return {k: row[k] for k in ('id', 'username', 'name', 'role', 'active')}

    # Valida caducidad y actividad de la sesión y devuelve usuario y token CSRF.
    def session(self, token):
        if not token or len(token) > 128:
            return None
        now = time.time()
        with self.db() as db:
            row = db.execute('SELECT * FROM sessions WHERE token=? AND expires>? AND touched>?',
                             (digest(token), now, now-3600)).fetchone()
            if row is None:
                return None
            user = None
            if row['user_id']:
                user = db.execute('SELECT * FROM users WHERE id=? AND active=1', (row['user_id'],)).fetchone()
                if not user:
                    return None
                user = self.public(user)
            db.execute('UPDATE sessions SET touched=? WHERE token=?', (now, digest(token)))
            return {'user': user, 'csrf': row['csrf']}

    # Emite tokens aleatorios de sesión y CSRF; sustituye la sesión anterior si corresponde.
    def issue(self, user_id=None, previous=None):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE expires<? OR touched<?', (now, now-3600))
            if previous:
                db.execute('DELETE FROM sessions WHERE token=?', (digest(previous),))
            if db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] >= 5000:
                raise ValueError('Demasiadas sesiones. Inténtalo más tarde.')
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',
                       (digest(token), user_id, csrf, now+(43200 if user_id else 900), now))
        return token, csrf

    # Elimina la sesión identificada por el hash del token recibido.
    def logout(self, token):
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (digest(token),))

    # Comprueba formato y longitud de usuario, nombre y contraseña antes del registro.
    @staticmethod
    # Comprueba formato y longitud de usuario, nombre y contraseña antes del registro.
    def validate(username, name, password):
        if not isinstance(username, str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{3,40}', username):
            raise ValueError('Usuario: usa de 3 a 40 letras, números, puntos o guiones.')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError('Escribe un nombre de hasta 80 caracteres.')
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise ValueError('La contraseña debe tener entre 12 y 256 caracteres.')
        return username.lower(), name.strip()

    # Registra una cuenta con contraseña derivada y consume una invitación de un solo uso.
    def register(self, username, name, password, invite=None, bootstrap=False):
        username, name = self.validate(username, name, password)
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
        identifier = uuid.uuid4().hex
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if bootstrap:
                if db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                    raise PermissionError('Ya existe un administrador. Inicia sesión.')
            else:
                if not isinstance(invite, str) or len(invite) > 128 or not db.execute(
                        'SELECT 1 FROM invites WHERE token=? AND expires>?', (digest(invite), time.time())).fetchone():
                    raise PermissionError('La invitación no existe, venció o ya se utilizó.')
            try:
                db.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?,?)',
                           (identifier, username, name, salt, hashed, 'admin' if bootstrap else 'member', 1, time.time()))
            except sqlite3.IntegrityError:
                raise ValueError('Ese nombre de usuario ya está ocupado.') from None
            if not bootstrap:
                db.execute('DELETE FROM invites WHERE token=?', (digest(invite),))
        return identifier

    # Cuenta intentos por identidad y bloquea temporalmente el acceso cuando supera el límite.
    def throttle(self, identity, limit=10):
        key, now = digest(identity), time.time()
        with self.db() as db:
            db.execute('DELETE FROM attempts WHERE expires<?', (now,))
            row = db.execute('SELECT count FROM attempts WHERE key=?', (key,)).fetchone()
            if row and row['count'] >= limit:
                raise PermissionError('Demasiados intentos. Espera diez minutos.')
            db.execute('INSERT INTO attempts VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1', (key, now+600))

    # Borra el contador de intentos de una identidad después de autenticarla.
    def clear_throttle(self, identity):
        with self.db() as db:
            db.execute('DELETE FROM attempts WHERE key=?', (digest(identity),))

    # Verifica usuario y contraseña con PBKDF2 y comparación de tiempo constante.
    def login(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str) or len(username)>40 or len(password)>256:
            raise PermissionError('Usuario o contraseña incorrectos.')
        with self.db() as db:
            row = db.execute('SELECT * FROM users WHERE username=?', (username.lower(),)).fetchone()
        # El mismo coste para usuarios inexistentes.
        salt = bytes.fromhex(row['salt']) if row else bytes(16)
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS).hex()
        if not row or not row['active'] or not hmac.compare_digest(actual, row['password']):
            raise PermissionError('Usuario o contraseña incorrectos.')
        return self.public(row)

    # Crea una invitación aleatoria con caducidad para añadir un colaborador.
    def invite(self, admin_id):
        token = secrets.token_urlsafe(24)
        with self.db() as db:
            db.execute('DELETE FROM invites WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO invites VALUES (?,?,?)', (digest(token), time.time()+604800, admin_id))
        return token

    # Lista los datos públicos de las cuentas en orden de creación.
    def users(self):
        with self.db() as db:
            return [self.public(row) for row in db.execute('SELECT * FROM users ORDER BY created')]

    # Reactiva una cuenta colaboradora sin modificar administradores.
    def enable(self, identifier):
        with self.db() as db:
            row = db.execute('SELECT role FROM users WHERE id=?', (identifier,)).fetchone()
            if not row or row['role'] == 'admin':
                raise ValueError('Selecciona una cuenta colaboradora.')
            db.execute('UPDATE users SET active=1 WHERE id=?', (identifier,))

    # Desactiva un colaborador y revoca sus sesiones; impide desactivar al propio actor.
    def disable(self, identifier, actor):
        if identifier == actor:
            raise ValueError('No puedes desactivar tu propia cuenta.')
        with self.db() as db:
            row = db.execute('SELECT role FROM users WHERE id=?', (identifier,)).fetchone()
            if not row or row['role'] == 'admin':
                raise ValueError('Selecciona una cuenta colaboradora.')
            db.execute('UPDATE users SET active=0 WHERE id=?', (identifier,))
            db.execute('DELETE FROM sessions WHERE user_id=?', (identifier,))
