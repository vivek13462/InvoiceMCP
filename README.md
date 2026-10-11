# Expense Invoice MCP Server

A standalone Python MCP server that queries historical expense CSV data and
generates HTML invoices. Use the machine Python already on `PATH`. No virtual
environment is needed.

## Install

```text
python -m pip install -r requirements.txt
```

## Expense data

The CSV must have these columns:

```text
date,item,vendor,qty,unit_price
```

Dates use `YYYY-MM-DD`; `qty` and `unit_price` are numbers. The server checks
`EXPENSES_CSV`, then `data/expenses.csv` in this workspace, then
`expenses.csv` in the parent folder. Point `EXPENSES_CSV` at the expenses file
if it is not in the parent folder.

## Run

Local STDIO:

```text
python server.py
```

Streamable HTTP:

```text
python server.py --http
```

The HTTP MCP endpoint is `http://127.0.0.1:8765/mcp`.

Generate all three demo invoices and exit:

```text
python server.py --demo
```

Agents connect with STDIO to `server.py` or with HTTP to
`http://127.0.0.1:8765/mcp`. The tool list is discovered at runtime.
