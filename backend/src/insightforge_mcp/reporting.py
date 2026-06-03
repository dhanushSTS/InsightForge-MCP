"""Reporting helpers: turn query results into CSV files and PNG charts.

Kept separate from the MCP tool definitions so the rendering logic can be
unit-tested without an MCP runtime. Matplotlib uses the headless ``Agg``
backend because the server has no display.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless rendering — must be set before pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .config import get_settings  # noqa: E402

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_-]+")


def _timestamped(name: str, suffix: str) -> Path:
    """Build a collision-resistant output path inside the export directory."""
    stem = _SAFE_NAME.sub("_", name).strip("_") or "report"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return get_settings().export_path / f"{stem}_{ts}.{suffix}"


def rows_to_csv(rows: list[dict[str, Any]], filename: str = "report") -> dict[str, Any]:
    """Write rows to a CSV file and return a summary dict."""
    df = pd.DataFrame(rows)
    out = _timestamped(filename, "csv")
    df.to_csv(out, index=False)
    return {"path": str(out), "rows": len(df), "columns": list(df.columns)}


def rows_to_chart(
    rows: list[dict[str, Any]],
    x: str,
    y: str,
    *,
    kind: str = "bar",
    title: str | None = None,
    filename: str = "chart",
) -> dict[str, Any]:
    """Render a simple chart (bar/line/pie) from rows and save it as PNG."""
    if not rows:
        raise ValueError("No data to plot.")

    df = pd.DataFrame(rows)
    for col in (x, y):
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found. Available: {list(df.columns)}")

    fig, ax = plt.subplots(figsize=(10, 6))
    if kind == "line":
        ax.plot(df[x].astype(str), df[y], marker="o")
    elif kind == "pie":
        ax.pie(df[y], labels=df[x].astype(str), autopct="%1.1f%%")
    else:  # default: bar
        ax.bar(df[x].astype(str), df[y])

    if kind != "pie":
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        plt.xticks(rotation=45, ha="right")
    ax.set_title(title or f"{y} by {x}")
    fig.tight_layout()

    out = _timestamped(filename, "png")
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return {"path": str(out), "kind": kind, "points": len(df)}
