"""InsightForge MCP server.

Defines the tools the LLM discovers and calls to explore and analyse the
database. The model has *no* prior knowledge of the schema: it learns it at
runtime via ``list_tables`` / ``describe_table`` and then composes SQL for
``run_query``. Reporting tools turn results into CSV files and charts.

Run with:
    python -m insightforge_mcp.server      # stdio transport (Claude Desktop)
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import get_settings
from .database import close_pool, run_select
from .reporting import rows_to_chart, rows_to_csv
from .sql_guard import UnsafeQueryError, enforce_limit, validate_select

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("insightforge_mcp")

mcp = FastMCP("InsightForge")


# --------------------------------------------------------------------------- #
# Schema discovery tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def list_tables() -> list[dict[str, Any]]:
    """List the tables available in the database.

    Use this FIRST when you don't yet know the schema. Returns each table's
    name, schema, and an approximate row count so you can decide which tables
    to inspect with `describe_table`.
    """
    sql = """
        SELECT
            t.table_schema,
            t.table_name,
            COALESCE(c.reltuples::bigint, 0) AS approx_rows
        FROM information_schema.tables t
        LEFT JOIN pg_class c
               ON c.relname = t.table_name
        WHERE t.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name;
    """
    return run_select(sql)


@mcp.tool()
def describe_table(table_name: str) -> dict[str, Any]:
    """Describe a table's columns, types, and primary/foreign keys.

    Call this after `list_tables` to learn the exact column names and the
    relationships (foreign keys) you need to write correct JOINs.

    Args:
        table_name: The table to describe, e.g. "orders".
    """
    columns = run_select(
        """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position;
        """,
        (table_name,),
    )
    if not columns:
        return {"error": f"Table '{table_name}' not found in schema 'public'."}

    foreign_keys = run_select(
        """
        SELECT
            kcu.column_name,
            ccu.table_name  AS references_table,
            ccu.column_name AS references_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = %s;
        """,
        (table_name,),
    )
    return {"table": table_name, "columns": columns, "foreign_keys": foreign_keys}


# --------------------------------------------------------------------------- #
# Querying tool
# --------------------------------------------------------------------------- #
@mcp.tool()
def run_query(sql: str) -> dict[str, Any]:
    """Run a READ-ONLY SQL query and return the result rows.

    Only a single SELECT (or WITH ... SELECT) statement is allowed. Any
    attempt to modify data (INSERT/UPDATE/DELETE/DROP/...) is rejected. A row
    limit is applied automatically. Discover the schema with `list_tables` and
    `describe_table` before writing SQL.

    Args:
        sql: A single read-only SELECT statement.
    """
    try:
        safe_sql = validate_select(sql)
    except UnsafeQueryError as exc:
        return {"error": f"Query rejected: {exc}"}

    limited = enforce_limit(safe_sql, settings.max_query_rows)
    try:
        rows = run_select(limited)
    except Exception as exc:  # surface DB errors back to the model
        logger.warning("Query failed: %s", exc)
        return {"error": f"Database error: {exc}"}

    return {
        "row_count": len(rows),
        "truncated": len(rows) >= settings.max_query_rows,
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# Reporting tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def export_csv(sql: str, filename: str = "report") -> dict[str, Any]:
    """Run a read-only query and export the results to a CSV file.

    Args:
        sql: A single read-only SELECT statement.
        filename: Base name for the output file (timestamp is appended).
    """
    result = run_query(sql)
    if "error" in result:
        return result
    if not result["rows"]:
        return {"error": "Query returned no rows; nothing to export."}
    return rows_to_csv(result["rows"], filename)


@mcp.tool()
def generate_chart(
    sql: str,
    x: str,
    y: str,
    kind: str = "bar",
    title: str | None = None,
    filename: str = "chart",
) -> dict[str, Any]:
    """Run a read-only query and render a chart (bar/line/pie) as a PNG.

    Args:
        sql: A single read-only SELECT statement producing the plot data.
        x: Column to use for the category/x-axis (e.g. "product_name").
        y: Numeric column to plot (e.g. "revenue").
        kind: One of "bar", "line", or "pie".
        title: Optional chart title.
        filename: Base name for the output file (timestamp is appended).
    """
    result = run_query(sql)
    if "error" in result:
        return result
    if not result["rows"]:
        return {"error": "Query returned no rows; nothing to plot."}
    try:
        return rows_to_chart(
            result["rows"], x=x, y=y, kind=kind, title=title, filename=filename
        )
    except ValueError as exc:
        return {"error": str(exc)}


def main() -> None:
    """Console entry point — serve over stdio for Claude Desktop."""
    try:
        logger.info("Starting InsightForge MCP server (stdio)")
        mcp.run()
    finally:
        close_pool()


if __name__ == "__main__":
    main()
