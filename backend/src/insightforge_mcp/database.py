"""PostgreSQL access layer.

Wraps a psycopg3 connection pool and exposes small helpers used by the MCP
tools. Every read path runs inside a **read-only** transaction with a
statement timeout, so even if the SQL guard is bypassed the database itself
refuses to mutate data.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Lazily create and return the shared connection pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        logger.info("Opening PostgreSQL connection pool")
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


@contextmanager
def read_connection() -> Iterator[psycopg.Connection]:
    """Yield a connection pinned to a read-only transaction with a timeout.

    The `SET` statements make the *database* the final authority on safety:
    no INSERT/UPDATE/DELETE/DDL can commit, and runaway queries are aborted.
    """
    settings = get_settings()
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            # Postgres SET does not accept bound parameters; inject a validated
            # integer literal (int() cast makes this injection-safe). SET LOCAL
            # scopes the timeout to this transaction so it can't leak to the
            # next pooled user of the connection.
            cur.execute(f"SET LOCAL statement_timeout = {int(settings.query_timeout_ms)}")
        try:
            yield conn
        finally:
            # Never persist anything from a read path.
            conn.rollback()


def run_select(sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    """Execute a SELECT and return rows as a list of dicts (row cap applied)."""
    settings = get_settings()
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchmany(settings.max_query_rows)
    return [dict(r) for r in rows]


def close_pool() -> None:
    """Close the pool on shutdown (best-effort)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
