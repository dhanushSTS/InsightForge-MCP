"""Tests for the read-only SQL guard — the security-critical layer.

Run with:  pytest   (from the backend/ directory)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from insightforge_mcp.sql_guard import (  # noqa: E402
    UnsafeQueryError,
    enforce_limit,
    validate_select,
)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM products",
        "select id, name from products where price > 10",
        "WITH t AS (SELECT 1 AS n) SELECT n FROM t",
        "SELECT * FROM orders ORDER BY created_at DESC",  # 'create' substring is OK
    ],
)
def test_allows_read_only(sql: str) -> None:
    assert validate_select(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE products",
        "DELETE FROM orders",
        "UPDATE products SET price = 0",
        "INSERT INTO products (name) VALUES ('x')",
        "SELECT 1; DROP TABLE products",          # stacked statements
        "SELECT * FROM products; DELETE FROM x",
        "TRUNCATE customers",
        "SELECT * FROM t /* sneaky */; DROP TABLE t",
        "",
    ],
)
def test_rejects_writes(sql: str) -> None:
    with pytest.raises(UnsafeQueryError):
        validate_select(sql)


def test_comment_smuggling_is_stripped() -> None:
    # A DELETE hidden behind a line comment must not slip through.
    with pytest.raises(UnsafeQueryError):
        validate_select("SELECT 1 -- harmless\nDELETE FROM orders")


def test_enforce_limit_appends_when_missing() -> None:
    out = enforce_limit("SELECT * FROM products", 100)
    assert "LIMIT 100" in out


def test_enforce_limit_respects_existing() -> None:
    out = enforce_limit("SELECT * FROM products LIMIT 5", 100)
    assert out.lower().count("limit") == 1
