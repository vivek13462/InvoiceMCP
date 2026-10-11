from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
VALID_PERIODS = {"latest_delivery", "year_to_date", "last_year"}
REQUIRED_COLUMNS = {"date", "item", "vendor", "qty", "unit_price"}


def _env_file_value(name: str) -> str | None:
    env_path = WORKSPACE_ROOT / ".env"
    if not env_path.is_file():
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name and value.strip():
            return value.strip()
    return None


def find_expenses_csv() -> Path:
    configured = os.environ.get("EXPENSES_CSV") or _env_file_value("EXPENSES_CSV")
    candidates: list[Path] = []
    if configured and configured.strip():
        configured_path = Path(configured.strip()).expanduser()
        if not configured_path.is_absolute():
            configured_path = WORKSPACE_ROOT / configured_path
        candidates.append(configured_path)
    candidates.extend(
        [
            WORKSPACE_ROOT / "data" / "expenses.csv",
            WORKSPACE_ROOT.parent / "expenses.csv",
        ]
    )

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            print(f"Using expenses CSV: {resolved}", file=sys.stderr)
            return resolved

    tried = "\n".join(f"- {candidate.resolve()}" for candidate in candidates)
    raise FileNotFoundError(f"Expenses CSV was not found. Paths tried:\n{tried}")


def _load_rows(csv_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - fieldnames)
        if missing:
            raise ValueError(
                f"Expenses CSV is missing required columns: {', '.join(missing)}"
            )

        for line_number, raw in enumerate(reader, start=2):
            try:
                row_date = date.fromisoformat(raw["date"].strip())
            except (AttributeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid date on CSV line {line_number}; expected YYYY-MM-DD."
                ) from exc
            try:
                qty = Decimal(raw["qty"].strip())
                unit_price = Decimal(raw["unit_price"].strip())
            except (AttributeError, InvalidOperation) as exc:
                raise ValueError(
                    f"Invalid qty or unit_price on CSV line {line_number}."
                ) from exc

            item = raw["item"].strip()
            vendor = raw["vendor"].strip()
            if not item or not vendor:
                raise ValueError(
                    f"Item and vendor must not be blank on CSV line {line_number}."
                )
            rows.append(
                {
                    "date": row_date,
                    "item": item,
                    "vendor": vendor,
                    "qty": qty,
                    "unit_price": unit_price,
                }
            )

    if not rows:
        raise ValueError(f"Expenses CSV contains no data rows: {csv_path}")
    return rows


def _period_range(period: str, rows: list[dict[str, Any]]) -> tuple[date, date]:
    if period not in VALID_PERIODS:
        choices = ", ".join(sorted(VALID_PERIODS))
        raise ValueError(f"Invalid period '{period}'. Expected one of: {choices}.")

    today = date.today()
    if period == "latest_delivery":
        latest = max(row["date"] for row in rows)
        return latest, latest
    if period == "year_to_date":
        return date(today.year, 1, 1), today
    previous_year = today.year - 1
    return date(previous_year, 1, 1), date(previous_year, 12, 31)


def _number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def query_expenses(period: str, item: str | None = None) -> dict[str, Any]:
    csv_path = find_expenses_csv()
    rows = _load_rows(csv_path)
    start_date, end_date = _period_range(period, rows)
    item_filter = item.strip() if item and item.strip() else None

    matched_rows = [
        row
        for row in rows
        if start_date <= row["date"] <= end_date
        and (
            item_filter is None
            or item_filter.casefold() in row["item"].casefold()
        )
    ]

    grouped: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(
        lambda: {"total_qty": Decimal("0"), "line_total": Decimal("0")}
    )
    for row in matched_rows:
        group = grouped[(row["item"], row["vendor"])]
        group["total_qty"] += row["qty"]
        group["line_total"] += row["qty"] * row["unit_price"]

    aggregated_items: list[dict[str, Any]] = []
    grand_total = Decimal("0")
    for (item_name, vendor), values in sorted(
        grouped.items(), key=lambda entry: (entry[0][0].casefold(), entry[0][1].casefold())
    ):
        total_qty = values["total_qty"]
        line_total = values["line_total"]
        average_unit_price = (
            line_total / total_qty if total_qty != 0 else Decimal("0")
        )
        aggregated_items.append(
            {
                "item": item_name,
                "vendor": vendor,
                "total_qty": _number(total_qty),
                "average_unit_price": float(round(average_unit_price, 2)),
                "line_total": float(round(line_total, 2)),
            }
        )
        grand_total += line_total

    matched_dates = [row["date"] for row in matched_rows]
    return {
        "csv_path": str(csv_path),
        "row_count": len(rows),
        "min_date": min(row["date"] for row in rows).isoformat(),
        "max_date": max(row["date"] for row in rows).isoformat(),
        "period": period,
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "matched_row_count": len(matched_rows),
        "matched_min_date": min(matched_dates).isoformat() if matched_dates else None,
        "matched_max_date": max(matched_dates).isoformat() if matched_dates else None,
        "item_filter": item_filter,
        "aggregated_items": aggregated_items,
        "grand_total": float(round(grand_total, 2)),
    }
