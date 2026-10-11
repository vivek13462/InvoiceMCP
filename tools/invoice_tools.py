from __future__ import annotations

import html
import os
import shutil
from datetime import date
from pathlib import Path
from string import Template

from tools.csv_tools import query_expenses


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = WORKSPACE_ROOT / "templates" / "invoice.html"
OUTPUT_DIR = WORKSPACE_ROOT / "output"

PERIOD_FILES = {
    "latest_delivery": "invoice_latest_delivery.html",
    "year_to_date": "invoice_year_to_date.html",
    "last_year": "invoice_last_year.html",
}


def _invoice_metadata(period: str, data: dict[str, object]) -> tuple[str, str]:
    current_year = date.today().year
    if period == "latest_delivery":
        delivery_date = str(data["max_date"])
        return "INV-LATEST", f"Latest delivery ({delivery_date})"
    if period == "year_to_date":
        return f"INV-YTD-{current_year}", f"Year to date ({current_year})"
    if period == "last_year":
        previous_year = current_year - 1
        return f"INV-{previous_year}", f"Last year ({previous_year})"
    raise ValueError(
        "Invalid period. Expected latest_delivery, year_to_date, or last_year."
    )


def _copy_directory() -> Path | None:
    configured = os.environ.get("INVOICE_COPY_DIR")
    if configured is None:
        env_path = WORKSPACE_ROOT / ".env"
        if env_path.is_file():
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "INVOICE_COPY_DIR" and value.strip():
                    configured = value.strip()
                    break
    if not configured or not configured.strip():
        return None
    copy_dir = Path(configured.strip()).expanduser()
    if not copy_dir.is_absolute():
        copy_dir = WORKSPACE_ROOT / copy_dir
    return copy_dir.resolve()


def generate_invoice(period: str) -> Path:
    if period not in PERIOD_FILES:
        raise ValueError(
            "Invalid period. Expected latest_delivery, year_to_date, or last_year."
        )

    data = query_expenses(period)
    invoice_number, period_label = _invoice_metadata(period, data)
    rows = []
    for item in data["aggregated_items"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item['item']))}</td>"
            f"<td>{html.escape(str(item['vendor']))}</td>"
            f"<td class=\"number\">{item['total_qty']}</td>"
            f"<td class=\"number\">${item['average_unit_price']:,.2f}</td>"
            f"<td class=\"number\">${item['line_total']:,.2f}</td>"
            "</tr>"
        )
    if not rows:
        rows.append(
            '<tr><td colspan="5" class="empty">No expenses in this period.</td></tr>'
        )

    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    rendered = template.safe_substitute(
        invoice_number=html.escape(invoice_number),
        period_label=html.escape(period_label),
        start_date=html.escape(str(data["date_range"]["start"])),
        end_date=html.escape(str(data["date_range"]["end"])),
        line_items="\n".join(rows),
        grand_total=f"${data['grand_total']:,.2f}",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (OUTPUT_DIR / PERIOD_FILES[period]).resolve()
    output_path.write_text(rendered, encoding="utf-8")

    copy_dir = _copy_directory()
    if copy_dir is not None:
        copy_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_path, copy_dir / output_path.name)

    return output_path
