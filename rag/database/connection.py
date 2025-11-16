"""PostgreSQL connection helpers with connection pooling and error handling."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from rag.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()
_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """
    Get or create a singleton psycopg connection pool.
    
    The pool maintains connections to PostgreSQL and reuses them
    for better performance. Connection pool size is configurable
    via environment variables.
    
    Returns:
        ConnectionPool: Configured connection pool instance
        
    Raises:
        psycopg.OperationalError: If unable to connect to database
    """
    global _pool
    if _pool is None:
        try:
            logger.info(
                f"Initializing database connection pool: "
                f"{_settings.postgres_host}:{_settings.postgres_port}/{_settings.postgres_db}"
            )
            _pool = ConnectionPool(
                conninfo=_settings.database_url,
                min_size=1,
                max_size=10,
                kwargs={
                    "connect_timeout": 10,
                    "options": "-c statement_timeout=30000"  # 30 second statement timeout
                },
                open=True,
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    return _pool


@contextmanager
def get_sync_connection() -> Iterator[psycopg.Connection]:
    """
    Provide a managed synchronous database connection with pgvector support.
    
    This context manager automatically:
    - Gets a connection from the pool
    - Registers pgvector types
    - Returns the connection to the pool when done
    - Handles errors and ensures cleanup
    
    Usage:
        ```python
        with get_sync_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sections LIMIT 10")
                results = cur.fetchall()
        ```
    
    Yields:
        psycopg.Connection: Active database connection with pgvector registered
        
    Raises:
        psycopg.OperationalError: If connection fails
        psycopg.DatabaseError: For other database errors
    """
    pool = get_pool()
    connection = None
    
    try:
        connection = pool.getconn()
        register_vector(connection)
        yield connection
        
    except psycopg.OperationalError as e:
        logger.error(f"Database operational error: {e}")
        raise
        
    except psycopg.DatabaseError as e:
        logger.error(f"Database error: {e}")
        if connection:
            connection.rollback()
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error in database connection: {e}")
        if connection:
            connection.rollback()
        raise
        
    finally:
        if connection:
            pool.putconn(connection)


def test_connection() -> bool:
    """
    Test database connectivity.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        with get_sync_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                return result is not None and result[0] == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def close_pool() -> None:
    """
    Close the connection pool and clean up resources.
    
    Should be called during application shutdown.
    """
    global _pool
    if _pool:
        logger.info("Closing database connection pool")
        _pool.close()
        _pool = None
        logger.info("Database connection pool closed")
