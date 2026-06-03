# CLAUDE.md — guidance for working in InsightForge MCP

InsightForge is an **MCP server over PostgreSQL** that lets an LLM act as an
autonomous data analyst: it discovers the schema at runtime and writes its own
read-only SQL. This file tells Claude Code how the repo is organised and the
conventions to follow.

## Architecture (request flow)

```
Host (Claude Desktop) → MCP stdio → server.py tools → sql_guard → database.py → PostgreSQL
```

- `backend/src/insightforge_mcp/server.py` — FastMCP server; every `@mcp.tool()`
  is something the LLM can discover and call. Keep tool **docstrings**
  accurate and action-oriented — the model relies on them to choose tools.
- `sql_guard.py` — the read-only gate. **All** user/LLM SQL must pass through
  `validate_select()` before touching the DB.
- `database.py` — psycopg3 pool; reads run inside a `READ ONLY` transaction
  with a statement timeout.
- `reporting.py` — CSV + matplotlib (Agg backend) rendering.
- `config.py` — typed settings from the **root `.env`** (not `backend/.env`).
- `scripts/` — `schema.sql`, `init_db.py`, `seed_data.py`.

## Conventions

- Python **3.11+**, standard library `from __future__ import annotations`,
  type hints everywhere, 100-char lines.
- Tools return **plain JSON-serialisable dicts/lists**. On error, return
  `{"error": "..."}` rather than raising — the model reads the message and
  recovers.
- Secrets live in the root `.env` only; never hard-code credentials. `.env` is
  git-ignored; `.env.example` is the committed template.
- Generated artifacts go to `backend/exports/` (git-ignored except `.gitkeep`).

## Safety — non-negotiable

This server must stay **read-only**. When adding or changing query paths:
1. Route SQL through `sql_guard.validate_select()`.
2. Keep the `READ ONLY` transaction + `statement_timeout` in `database.py`.
3. Never add a tool that writes, drops, or alters data.
If you genuinely need a write feature, raise it explicitly with the user first.

## Common commands

```bash
cd backend
pip install -r requirements.txt
python scripts/init_db.py        # (re)create schema
python scripts/seed_data.py      # load sample data
pytest                           # run tests (sql_guard is the critical suite)
python -m insightforge_mcp.server   # run the server over stdio
```

## When adding a new tool

1. Define it in `server.py` with a clear docstring and typed args.
2. Reuse `run_query()` / `run_select()` rather than opening raw connections.
3. If it returns tabular data, consider whether CSV/chart export applies.
4. Add/extend tests, especially if it touches `sql_guard`.
