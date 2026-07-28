"""Deterministic fallback policies for local-model-friendly deck compilation."""

from __future__ import annotations

from typing import Any


DEFAULT_CARD_COUNT = 3
MAX_CARD_COUNT = 6
MAX_TABLE_ROWS = 7
MAX_TABLE_COLUMNS = 5
DEFAULT_CHART_DATA = {
    "categories": ["A", "B", "C"],
    "series": [{"name": "Series", "values": [1, 2, 3]}],
}


def choose_title_body_slots(layout: dict[str, Any]) -> dict[str, str | None]:
    """Choose title/body slots from a layout without model judgment."""

    slots = layout.get("slots") or []
    title_slot = _first_slot_id(slots, slot_ids={"title", "section_title"}) or _first_slot_by_type(slots, "text")
    body_slot = (
        _first_slot_id(
            slots,
            slot_ids={
                "body",
                "cards",
                "roadmap_items",
                "matrix",
                "table",
                "metric_panels",
                "case_context",
                "case_evidence",
                "takeaway",
                "next_steps",
            },
        )
        or _first_slot_by_type(slots, "content")
        or _first_slot_by_type(slots, "table")
        or _first_slot_by_type(slots, "chart")
    )
    footer_slot = _first_slot_id(slots, slot_ids={"footer"})
    return {"title": title_slot, "body": body_slot, "footer": footer_slot}


def normalize_card_blocks(
    blocks: list[dict[str, Any]],
    *,
    slide_id: str,
    target_count: int = DEFAULT_CARD_COUNT,
    max_count: int = MAX_CARD_COUNT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    normalized = [dict(block) for block in blocks if isinstance(block, dict)]
    if not normalized:
        normalized = [
            {"block_id": f"auto-card-{index + 1}", "slot": "cards", "title": f"Card {index + 1}", "content": ""}
            for index in range(target_count)
        ]
        warnings.append(
            _warning(
                "CARD_COUNT_PADDED",
                slide_id,
                f"No card blocks were provided; padded to {target_count} deterministic placeholder cards.",
            )
        )
    if len(normalized) < target_count:
        start = len(normalized)
        normalized.extend(
            {"block_id": f"auto-card-{index + 1}", "slot": "cards", "title": f"Card {index + 1}", "content": ""}
            for index in range(start, target_count)
        )
        warnings.append(
            _warning(
                "CARD_COUNT_PADDED",
                slide_id,
                f"Card grid had {start} cards; padded to {target_count} for stable layout.",
            )
        )
    if len(normalized) > max_count:
        extra = len(normalized) - max_count
        normalized = normalized[:max_count]
        warnings.append(
            _warning(
                "CARD_COUNT_TRUNCATED",
                slide_id,
                f"Card grid exceeded {max_count} cards; {extra} cards were omitted for stable layout.",
            )
        )
    return normalized, warnings


def normalize_table_data(
    table_data: Any,
    *,
    slide_id: str,
    fallback_rows: list[list[str]] | None = None,
    max_rows: int = MAX_TABLE_ROWS,
    max_columns: int = MAX_TABLE_COLUMNS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    if isinstance(table_data, dict):
        headers = [str(item) for item in table_data.get("headers") or []]
        rows = [[str(cell) for cell in row] for row in table_data.get("rows") or [] if isinstance(row, list)]
    else:
        headers = []
        rows = []
    if not rows and fallback_rows:
        rows = [[str(cell) for cell in row] for row in fallback_rows]
        warnings.append(_warning("TABLE_DATA_FALLBACK_USED", slide_id, "Table data was missing; content blocks were converted to an editable table."))
    if not rows:
        rows = [["Item", "Detail"]]
        warnings.append(_warning("TABLE_DATA_FALLBACK_USED", slide_id, "Table data was missing; inserted one deterministic placeholder row."))
    if not headers:
        column_count = max(len(rows[0]) if rows else 2, 1)
        headers = [f"Col {index + 1}" for index in range(column_count)]
    if len(headers) > max_columns:
        headers = headers[:max_columns]
        rows = [row[:max_columns] for row in rows]
        warnings.append(_warning("TABLE_COLUMN_OVERFLOW_TRUNCATED", slide_id, f"Table exceeded {max_columns} columns; extra columns were omitted."))
    if len(rows) > max_rows:
        omitted = len(rows) - max_rows
        rows = rows[:max_rows]
        warnings.append(_warning("TABLE_ROW_OVERFLOW_TRUNCATED", slide_id, f"Table exceeded {max_rows} rows; {omitted} rows were omitted."))
    column_count = len(headers)
    rows = [row + [""] * max(0, column_count - len(row)) for row in rows]
    return {"headers": headers, "rows": rows}, warnings


def normalize_chart_data(chart_data: Any, *, slide_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    if not isinstance(chart_data, dict) or not chart_data.get("series"):
        warnings.append(_warning("CHART_DATA_FALLBACK_USED", slide_id, "Chart data was missing; inserted deterministic editable placeholder data."))
        return dict(DEFAULT_CHART_DATA), warnings
    categories = chart_data.get("categories") or DEFAULT_CHART_DATA["categories"]
    series = []
    for index, item in enumerate(chart_data.get("series") or []):
        if not isinstance(item, dict):
            continue
        values = item.get("values") or [0 for _ in categories]
        series.append({"name": str(item.get("name") or f"Series {index + 1}"), "values": list(values)})
    if not series:
        warnings.append(_warning("CHART_DATA_FALLBACK_USED", slide_id, "Chart series were invalid; inserted deterministic editable placeholder data."))
        return dict(DEFAULT_CHART_DATA), warnings
    return {"categories": list(categories), "series": series}, warnings


def _first_slot_id(slots: list[dict[str, Any]], *, slot_ids: set[str]) -> str | None:
    for slot in slots:
        slot_id = str(slot.get("slot_id") or "")
        if slot_id in slot_ids:
            return slot_id
    return None


def _first_slot_by_type(slots: list[dict[str, Any]], slot_type: str) -> str | None:
    for slot in slots:
        if slot.get("slot_type") == slot_type:
            return str(slot.get("slot_id") or "")
    return None


def _warning(code: str, slide_id: str, message: str) -> dict[str, Any]:
    return {"code": code, "slide_id": slide_id, "severity": "warning", "message": message}
