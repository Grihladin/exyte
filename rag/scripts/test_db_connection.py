"""Simple script to verify the PostgreSQL connection."""

from __future__ import annotations

import sys

from psycopg import sql

from rag.database.connection import get_sync_connection


def main() -> int:
    try:
        with get_sync_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("SELECT version()"))
                version = cur.fetchone()
        print("Successfully connected to PostgreSQL.")
        if version:
            print(f"Server version: {version[0]}")
        return 0
    except Exception as exc:  # pragma: no cover - debug helper
        print(f"Connection failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
