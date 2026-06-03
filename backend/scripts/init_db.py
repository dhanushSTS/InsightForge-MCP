"""Create the database schema.

Runs ``schema.sql`` against the configured ``DATABASE_URL``. Idempotent: the
SQL drops and recreates the tables, so you can re-run it freely.

Usage:
    python scripts/init_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the package importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg  # noqa: E402

from insightforge_mcp.config import get_settings  # noqa: E402

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def main() -> None:
    settings = get_settings()
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    print(f"Applying schema to {settings.database_url.split('@')[-1]} ...")
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(schema_sql)
    print("Schema created: customers, products, orders, order_items, payments.")


if __name__ == "__main__":
    main()
