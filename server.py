from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from tools.csv_tools import query_expenses as query_expenses_data
from tools.invoice_tools import generate_invoice as generate_invoice_file
from tools.llm_tools import chef_summary as create_chef_summary


WORKSPACE_ROOT = Path(__file__).resolve().parent


def _env_setting(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is not None and value.strip():
        return value.strip()

    env_path = WORKSPACE_ROOT / ".env"
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, candidate = line.split("=", 1)
            if key.strip() == name and candidate.strip():
                return candidate.strip()
    return default


HOST = _env_setting("MCP_HOST", "127.0.0.1")
PORT = int(_env_setting("MCP_PORT", "8765"))
mcp = MCPServer("Expense Invoice MCP Server")


@mcp.tool(
    description=(
        "Query historical expenses for latest_delivery, year_to_date, or last_year. "
        "The optional item is a case-insensitive substring. "
        "Example: tomato matches Roma tomatoes."
    )
)
def query_expenses(period: str, item: str | None = None) -> dict[str, Any]:
    return query_expenses_data(period, item)


@mcp.tool(
    description=(
        "Generate an HTML expense invoice for latest_delivery, year_to_date, "
        "or last_year, and return the written file path."
    )
)
def generate_invoice(period: str) -> str:
    return str(generate_invoice_file(period))


@mcp.tool(
    description="Write two short sentences about the supplied spend text for a chef."
)
def chef_summary(text: str) -> str:
    return create_chef_summary(text)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Expense Invoice MCP server.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--http",
        action="store_true",
        help=f"Run streamable HTTP at http://{HOST}:{PORT}/mcp.",
    )
    mode.add_argument(
        "--demo",
        action="store_true",
        help="Write all three HTML invoices and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.demo:
        for period in ("latest_delivery", "year_to_date", "last_year"):
            print(generate_invoice_file(period))
        return

    if args.http:
        mcp.run(
            transport="streamable-http",
            host=HOST,
            port=PORT,
            streamable_http_path="/mcp",
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
