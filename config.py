import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'campus-commute-super-secret-key-2026')
    
    # Database mode: 'sqlite' or 'mysql'
    # Default to sqlite for instant zero-dependency demonstration, can be switched to mysql
    DB_TYPE = os.environ.get('DB_TYPE', 'sqlite').lower()
    
    # SQLite configuration
    SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'campuscommute.db')
    
    # MySQL configuration
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'campuscommute')
    
    # Pre-decided Admin Account Credentials
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@campuscommute.edu')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
