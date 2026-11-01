import sqlite3
from contextlib import contextmanager
from flask import g
from config import Config

def get_connection():
    """Returns a database connection based on Config.DB_TYPE."""
    if Config.DB_TYPE == 'mysql':
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DATABASE,
                autocommit=False
            )
            return conn, 'mysql'
        except Exception as e:
            # Fallback to SQLite if MySQL fails
            print(f"[DB Warning] Could not connect to MySQL ({e}). Falling back to SQLite.")
            
    conn = sqlite3.connect(Config.SQLITE_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn, 'sqlite'

def get_db():
    """Get request-scoped database connection."""
    if 'db' not in g:
        conn, db_type = get_connection()
        g.db = conn
        g.db_type = db_type
    return g.db, g.db_type

def close_db(e=None):
    """Close request-scoped database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def _adapt_query(query, db_type):
    """
    Standardize queries so code can use '?' placeholders.
    If MySQL, replace '?' with '%s'.
    """
    if db_type == 'mysql':
        return query.replace('?', '%s')
    return query

def query_db(query, args=(), one=False):
    """Execute a SELECT query and return list of dict-like rows or single row."""
    conn, db_type = get_db()
    sql = _adapt_query(query, db_type)
    
    if db_type == 'mysql':
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, args)
        rv = cursor.fetchall()
        cursor.close()
        return (rv[0] if rv else None) if one else rv
    else:
        cursor = conn.cursor()
        cursor.execute(sql, args)
        rv = cursor.fetchall()
        cursor.close()
        if rv:
            rows = [dict(r) for r in rv]
            return rows[0] if one else rows
        return None if one else []

def execute_db(query, args=()):
    """Execute an INSERT, UPDATE, or DELETE query and commit."""
    conn, db_type = get_db()
    sql = _adapt_query(query, db_type)
    cursor = conn.cursor()
    cursor.execute(sql, args)
    conn.commit()
    last_id = cursor.lastrowid
    cursor.close()
    return last_id

@contextmanager
def get_db_transaction():
    """
    Context manager for strict DBMS transaction management (ACID).
    Ensures START TRANSACTION -> COMMIT or ROLLBACK on exception.
    """
    conn, db_type = get_db()
    try:
        if db_type == 'sqlite':
            cursor = conn.cursor()
            yield cursor, db_type
            conn.commit()
            cursor.close()
        else:
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            yield cursor, db_type
            conn.commit()
            cursor.close()
    except Exception as e:
        conn.rollback()
        raise e
