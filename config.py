import os
import secrets

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_secret_key():
    """
    Use the SECRET_KEY environment variable if set. Otherwise generate a random key
    once and keep it in a git-ignored file, so sessions stay valid across restarts
    without shipping a guessable default key.
    """
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key
    key_file = os.path.join(_BASE_DIR, '.secret_key')
    try:
        with open(key_file, 'r') as f:
            key = f.read().strip()
            if key:
                return key
    except OSError:
        pass
    key = secrets.token_hex(32)
    try:
        with open(key_file, 'w') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
    except OSError:
        pass  # read-only folder: fall back to a per-process key
    return key


class Config:
    SECRET_KEY = _load_secret_key()

    # Session cookie hardening (set SESSION_COOKIE_SECURE=1 when serving over HTTPS)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE') == '1'

    # Database mode: 'sqlite' or 'mysql'
    # Default to sqlite (the fully supported mode) for zero-dependency demonstration
    DB_TYPE = os.environ.get('DB_TYPE', 'sqlite').lower()

    # SQLite configuration
    SQLITE_DB_PATH = os.path.join(_BASE_DIR, 'database', 'campusconnect.db')

    # MySQL configuration
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'campusconnect')

    # Pre-decided Admin Account (seeded in the database; shown on the login page for the demo)
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@campusconnect.edu')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
