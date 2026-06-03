"""Read-only SQL guardrails.

Defence in depth: this module is the *first* line of defence (the database
read-only transaction in ``database.py`` is the second). The LLM is free to
generate SQL, but we only ever let well-formed, single-statement SELECT/CTE
queries reach the database.
"""

from __future__ import annotations

import re

# Statements we never allow, even inside a CTE or subquery.
_FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "truncate", "alter", "create",
    "grant", "revoke", "merge", "call", "do", "copy", "vacuum", "reindex",
    "comment", "security", "lock",
)

# Read-only entry points a query may legitimately start with.
_ALLOWED_PREFIXES = ("select", "with")


class UnsafeQueryError(ValueError):
    """Raised when a query violates the read-only policy."""


def _strip_comments(sql: str) -> str:
    """Remove `-- line` and `/* block */` comments to stop keyword smuggling."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def validate_select(sql: str) -> str:
    """Validate and normalise a read-only query.

    Returns the cleaned SQL on success; raises :class:`UnsafeQueryError`
    otherwise.
    """
    if not sql or not sql.strip():
        raise UnsafeQueryError("Empty query.")

    cleaned = _strip_comments(sql).strip().rstrip(";").strip()

    # Reject multiple statements (a `;` left after stripping the trailing one).
    if ";" in cleaned:
        raise UnsafeQueryError("Multiple SQL statements are not allowed.")

    lowered = cleaned.lower()

    if not lowered.startswith(_ALLOWED_PREFIXES):
        raise UnsafeQueryError(
            "Only read-only SELECT (or WITH ... SELECT) queries are permitted."
        )

    # Word-boundary search so columns like `created_at` don't trip `create`.
    for kw in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", lowered):
            raise UnsafeQueryError(f"Forbidden keyword detected: '{kw.upper()}'.")

    return cleaned


def enforce_limit(sql: str, max_rows: int) -> str:
    """Append a LIMIT clause if the query doesn't already constrain rows."""
    if re.search(r"\blimit\b", sql.lower()):
        return sql
    return f"{sql}\nLIMIT {max_rows}"
