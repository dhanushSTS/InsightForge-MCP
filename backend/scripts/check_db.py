"""One-off helper: check Postgres connectivity and whether `insightforge` exists.

Usage:  python scripts/check_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg

from insightforge_mcp.config import get_settings


def main() -> None:
    settings = get_settings()
    # Connect to the maintenance DB to enumerate databases.
    base = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    try:
        with psycopg.connect(base, connect_timeout=4) as conn:
            rows = conn.execute(
                "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
            ).fetchall()
        dbs = [r[0] for r in rows]
        print("CONNECT_OK")
        print("Databases:", dbs)
        print("insightforge exists:", "insightforge" in dbs)
    except Exception as exc:  # noqa: BLE001
        print("CONNECT_FAIL:", str(exc).splitlines()[0][:200])


if __name__ == "__main__":
    main()
