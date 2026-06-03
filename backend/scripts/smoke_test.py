"""Smoke test: act as an MCP client and exercise the server end-to-end.

This does what Claude Desktop does — spawns the server over stdio, lists the
tools, and calls a few — so you can confirm everything works without any host.

Usage:  python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    # Launch the server exactly like a host would.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "insightforge_mcp.server"],
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Discovered tools:", [t.name for t in tools.tools])

            print("\n--- list_tables() ---")
            res = await session.call_tool("list_tables", {})
            print(res.content[0].text)

            print("\n--- run_query(top 3 products by revenue) ---")
            sql = (
                "SELECT p.name, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue "
                "FROM order_items oi JOIN products p ON p.id = oi.product_id "
                "GROUP BY p.name ORDER BY revenue DESC LIMIT 3"
            )
            res = await session.call_tool("run_query", {"sql": sql})
            print(res.content[0].text)

            print("\n--- run_query(blocked write attempt) ---")
            res = await session.call_tool("run_query", {"sql": "DELETE FROM orders"})
            print(res.content[0].text)

    print("\nSmoke test complete — server is working.")


if __name__ == "__main__":
    asyncio.run(main())
