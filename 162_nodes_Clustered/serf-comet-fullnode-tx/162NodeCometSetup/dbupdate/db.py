"""
db.py
PostgreSQL connection pool shared by the Flask API and the scheduler,
so we never open more connections than the pool allows.
"""

import logging
import os
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "oden")
DB_USER = os.environ.get("DB_USER", "oden")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "changeme")

DB_POOL_MIN_CONN = int(os.environ.get("DB_POOL_MIN_CONN", "5"))
DB_POOL_MAX_CONN = int(os.environ.get("DB_POOL_MAX_CONN", "10"))

_connection_pool = None


def init_pool():
    """Initialize the global connection pool. Call once at startup."""
    global _connection_pool
    if _connection_pool is not None:
        return _connection_pool

    logger.info(
        "Initializing DB pool",
        extra={"db_host": DB_HOST, "db_name": DB_NAME, "pool_max": DB_POOL_MAX_CONN},
    )
    _connection_pool = psycopg2.pool.ThreadedConnectionPool(
        DB_POOL_MIN_CONN,
        DB_POOL_MAX_CONN,
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=10,
    )
    return _connection_pool


def close_pool():
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("DB pool closed")


@contextmanager
def get_connection():
    """Yield a pooled connection; always returns it to the pool."""
    if _connection_pool is None:
        raise RuntimeError("Connection pool not initialized. Call init_pool() first.")

    conn = _connection_pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _connection_pool.putconn(conn)


@contextmanager
def get_cursor(commit=False, dict_cursor=True):
    """Yield a cursor from a pooled connection, committing if requested."""
    with get_connection() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
