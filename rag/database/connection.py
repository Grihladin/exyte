"""PostgreSQL connection helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from rag.config import get_settings

_settings = get_settings()
_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Return a singleton psycopg connection pool."""

    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_settings.database_url,
            min_size=1,
            max_size=5,
            kwargs={"connect_timeout": 5},
        )
    return _pool


@contextmanager
def get_sync_connection() -> Iterator[psycopg.Connection]:
    """Provide a managed synchronous database connection."""

    pool = get_pool()
    with pool.connection() as conn:
        register_vector(conn)
        yield conn
