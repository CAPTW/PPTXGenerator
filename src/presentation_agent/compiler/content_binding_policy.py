"""Contract-aware content binding for editable template deck compilation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


DEFAULT_TEMPLATE_CONTRACTS_DIR = Path("outputs/template_contracts")

CARD_LIKE_SLOTS = {
    "cards",
    "caption_cards",
    "index_navigation",
    "progress_markers",
    "step_cards",
    "metric_panels",
}

PROCESS_LIKE_SLOTS = {
    "diagram",
    "process_visual",
    "hierarchy_pyramid",
    "timeline_steps",
    "method_steps",
    "gap_visual",
    "primary_chart",
}


def load_template_contracts(contracts_dir: str | Path = DEFAULT_TEMPLATE_CONTRACTS_DIR) -> dict[str, dict[str, Any]]:
    directory = Path(contracts_dir)
    if not directory.exists():
        return {}
    contracts: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.contract.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("archetype_id"):
            payload = dict(payload)
            payload["_contract_path"] = _display_path(path)
            contracts[str(payload["archetype_id"])] = payload
    return contracts


def apply_content_binding_policy(
    source_slide: dict[str, Any],
    layout: dict[str, Any],
    binding: dict[str, Any],
    contract: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a render-safe slide copy plus a machine-readable policy result."""

    shaped = copy.deepcopy(source_slide)
    archetype_id = str(layout.get("archetype_id") or binding.get("slide_type") or "")
    if not contract:
        return shaped, _empty_result(archetype_id)

    capacity = contract.get("content_capacity") if isinstance(contract.get("content_capacity"), dict) else {}
    overflow_policy = contract.get("overflow_policy") if isinstance(contract.get("overflow_policy"), dict) else {}
    warnings: list[dict[str, Any]] = []
    moved_details: list[str] = []

    title_result = _compress_field(
        shaped,
        "title",
        int(capacity.get("title_max_chars") or 0),
        "compress_title",
        warnings,
    )
    subtitle_result = _compress_field(
        shaped,
        "subtitle",
        int(capacity.get("subtitle_max_chars") or 0),
        "compress_subtitle",
        warnings,
    )

    blocks = [dict(block) for block in shaped.get("content_blocks") or [] if isinstance(block, dict)]
    shaped_blocks, block_result = _shape_blocks(
        blocks,
        capacity=capacity,
        layout=layout,
        overflow_policy=overflow_policy,
        warnings=warnings,
        moved_details=moved_details,
    )
    shaped["content_blocks"] = shaped_blocks
    shaped["strict_slot_content"] = True

    table_result = _shape_table(shaped, capacity, warnings, moved_details)
    chart_result = _shape_chart(shaped, capacity, warnings)
    source_anchor_preserved = _source_anchor_preserved(shaped, binding)
    if not source_anchor_preserved:
        warnings.append(
            _warning(
                "SOURCE_ANCHOR_NOT_VISIBLE",
                "No citation/source anchor is bound to a footer or citation strip.",
                {"slide_id": shaped.get("slide_id")},
            )
        )

    if moved_details:
        existing_notes = str(shaped.get("speaker_notes") or "").strip()
        detail_text = "\n".join(f"- {item}" for item in moved_details)
        shaped["speaker_notes"] = (existing_notes + "\n\nMoved detail:\n" + detail_text).strip()

    slot_status = {
        "title": title_result,
        "subtitle": subtitle_result,
        "body": block_result,
        "table": table_result,
        "chart": chart_result,
        "citations": {"status": "ok" if source_anchor_preserved else "warning"},
    }
    return shaped, {
        "contract_used": contract.get("_contract_path"),
        "archetype_id": archetype_id,
        "content_trimmed": bool(title_result["trimmed"] or subtitle_result["trimmed"] or block_result["content_trimmed"] or table_result.get("trimmed") or chart_result.get("trimmed")),
        "content_split": False,
        "content_moved_to_notes": bool(moved_details),
        "appendix_created": False,
        "overflow_warnings": warnings,
        "source_anchor_preserved": source_anchor_preserved,
        "slot_capacity_status": slot_status,
        "overflow_actions": _overflow_actions(title_result, subtitle_result, block_result, table_result, chart_result, moved_details),
    }


def _empty_result(archetype_id: str) -> dict[str, Any]:
    return {
        "contract_used": None,
        "archetype_id": archetype_id,
        "content_trimmed": False,
        "content_split": False,
        "content_moved_to_notes": False,
        "appendix_created": False,
        "overflow_warnings": [_warning("CONTRACT_NOT_FOUND", "No template usability contract was available.", {"archetype_id": archetype_id})],
        "source_anchor_preserved": False,
        "slot_capacity_status": {},
        "overflow_actions": [],
    }


def _compress_field(
    slide: dict[str, Any],
    field: str,
    limit: int,
    action: str,
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    text = str(slide.get(field) or "")
    if not limit or len(text) <= limit:
        return {"status": "ok", "chars": len(text), "limit": limit, "trimmed": False}
    slide[field] = _shorten(text, limit)
    warnings.append(
        _warning(
            f"{action.upper()}_APPLIED",
            f"{field.title()} text was shortened to fit the template contract.",
            {"before_chars": len(text), "after_chars": len(str(slide[field])), "limit": limit},
        )
    )
    return {"status": "adjusted", "chars": len(str(slide[field])), "limit": limit, "trimmed": True}


def _shape_blocks(
    blocks: list[dict[str, Any]],
    *,
    capacity: dict[str, Any],
    layout: dict[str, Any],
    overflow_policy: dict[str, Any],
    warnings: list[dict[str, Any]],
    moved_details: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    body_budget = int(capacity.get("body_bullet_count") or 0)
    body_line_limit = int(capacity.get("body_bullet_max_chars") or 0)
    card_budget = int(capacity.get("card_count") or 0)
    card_title_limit = int(capacity.get("card_title_max_chars") or 0)
    card_body_limit = int(capacity.get("card_body_max_chars") or 0)
    takeaway_limit = int(capacity.get("takeaway_max_chars") or 0)
    slot_ids = {str(slot.get("slot_id")) for slot in layout.get("slots") or [] if isinstance(slot, dict)}

    shaped: list[dict[str, Any]] = []
    used_body_lines = 0
    used_cards = 0
    trimmed_count = 0
    moved_count = 0
    for index, block in enumerate(blocks):
        slot_id = str(block.get("slot") or "")
        if slot_id and slot_id not in slot_ids:
            moved_details.append(_block_visible_text(block))
            moved_count += 1
            continue
        is_card = _is_card_slot(slot_id)
        is_process = slot_id in PROCESS_LIKE_SLOTS
        next_block = dict(block)
        visible = _block_visible_text(block)
        if is_card:
            if card_budget and used_cards >= card_budget:
                moved_details.append(visible)
                moved_count += 1
                continue
            compact = _card_title_from_block(block, card_title_limit, card_body_limit)
            next_block["title"] = compact["title"]
            next_block["content"] = compact["content"]
            trimmed_count += int(compact["trimmed"])
            used_cards += 1
            shaped.append(next_block)
            continue
        if is_process:
            label_limit = card_title_limit or body_line_limit or takeaway_limit
            next_block["title"] = _shorten(visible, label_limit) if label_limit else visible
            next_block["content"] = []
            trimmed_count += int(next_block["title"] != visible)
            used_body_lines += 1 if len(str(next_block["title"])) >= 8 else 0
            shaped.append(next_block)
            continue
        content_items = _content_items(block)
        allowed = max(0, body_budget - used_body_lines) if body_budget else len(content_items)
        if allowed <= 0 and body_budget:
            moved_details.append(visible)
            moved_count += 1
            continue
        kept = [_shorten(item, body_line_limit) for item in content_items[:allowed]]
        trimmed_count += sum(1 for before, after in zip(content_items[:allowed], kept) if before != after)
        if len(content_items) > len(kept):
            moved_details.extend(content_items[len(kept):])
            moved_count += len(content_items) - len(kept)
        next_block["content"] = kept
        if "title" in next_block and body_line_limit and len(str(next_block.get("title") or "")) > body_line_limit:
            next_block["title"] = _shorten(str(next_block["title"]), body_line_limit)
            trimmed_count += 1
        used_body_lines += sum(1 for item in kept if len(item.strip()) >= 8)
        shaped.append(next_block)

    if trimmed_count:
        warnings.append(
            _warning(
                "TRIM_OR_MERGE_BULLETS_APPLIED",
                "Visible content was shortened or compacted to fit slot capacity.",
                {"trimmed_items": trimmed_count, "overflow_policy": overflow_policy},
            )
        )
    if moved_count:
        warnings.append(
            _warning(
                "MOVE_DETAILS_TO_SPEAKER_NOTES_APPLIED",
                "Overflow content was moved to speaker notes rather than overloading slide slots.",
                {"moved_items": moved_count, "overflow_policy": overflow_policy},
            )
        )
    return shaped, {
        "status": "adjusted" if trimmed_count or moved_count else "ok",
        "body_bullet_count": used_body_lines,
        "body_bullet_limit": body_budget,
        "card_count": used_cards,
        "card_limit": card_budget,
        "content_trimmed": trimmed_count > 0,
        "moved_items": moved_count,
    }


def _shape_table(slide: dict[str, Any], capacity: dict[str, Any], warnings: list[dict[str, Any]], moved_details: list[str]) -> dict[str, Any]:
    data = slide.get("table_data")
    if not isinstance(data, dict):
        return {"status": "not_applicable", "trimmed": False}
    max_rows = int(capacity.get("table_max_rows") or 0)
    max_cols = int(capacity.get("table_max_columns") or 0)
    rows = [list(row) for row in data.get("rows") or [] if isinstance(row, list)]
    headers = list(data.get("headers") or [])
    original = {"rows": len(rows), "columns": len(headers)}
    if max_cols and len(headers) > max_cols:
        headers = headers[:max_cols]
        rows = [row[:max_cols] for row in rows]
    if max_rows and len(rows) > max_rows:
        moved_details.extend(" | ".join(str(cell) for cell in row) for row in rows[max_rows:])
        rows = rows[:max_rows]
    data["headers"] = headers
    data["rows"] = rows
    trimmed = original != {"rows": len(rows), "columns": len(headers)}
    if trimmed:
        warnings.append(_warning("CAP_TABLE_ROWS_APPLIED", "Table data was capped to contract row/column limits.", {"before": original, "after": {"rows": len(rows), "columns": len(headers)}}))
    return {"status": "adjusted" if trimmed else "ok", "rows": len(rows), "columns": len(headers), "limits": {"rows": max_rows, "columns": max_cols}, "trimmed": trimmed}


def _shape_chart(slide: dict[str, Any], capacity: dict[str, Any], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    data = slide.get("chart_data")
    if not isinstance(data, dict):
        return {"status": "not_applicable", "trimmed": False}
    limit = int(capacity.get("chart_label_max_chars") or 0)
    if not limit:
        return {"status": "ok", "label_limit": limit, "trimmed": False}
    trimmed = False
    categories = []
    for item in data.get("categories") or []:
        text = str(item)
        short = _shorten(text, limit)
        trimmed = trimmed or short != text
        categories.append(short)
    data["categories"] = categories
    for series in data.get("series") or []:
        if isinstance(series, dict) and isinstance(series.get("name"), str):
            short = _shorten(series["name"], limit)
            trimmed = trimmed or short != series["name"]
            series["name"] = short
    if trimmed:
        warnings.append(_warning("SHORTEN_CHART_LABELS_APPLIED", "Chart labels were shortened to contract limits.", {"label_limit": limit}))
    return {"status": "adjusted" if trimmed else "ok", "label_limit": limit, "trimmed": trimmed}


def _source_anchor_preserved(slide: dict[str, Any], binding: dict[str, Any]) -> bool:
    citations = slide.get("citations")
    if not isinstance(citations, list) or not citations:
        return True
    slot_bindings = binding.get("slot_bindings") if isinstance(binding.get("slot_bindings"), dict) else {}
    return any(str(value) == "citations" for value in slot_bindings.values())


def _overflow_actions(
    title_result: dict[str, Any],
    subtitle_result: dict[str, Any],
    block_result: dict[str, Any],
    table_result: dict[str, Any],
    chart_result: dict[str, Any],
    moved_details: list[str],
) -> list[str]:
    actions: list[str] = []
    if title_result.get("trimmed"):
        actions.append("compress_title")
    if subtitle_result.get("trimmed"):
        actions.append("compress_subtitle")
    if block_result.get("content_trimmed"):
        actions.append("trim_or_merge_bullets")
    if moved_details:
        actions.append("move_details_to_speaker_notes")
    if table_result.get("trimmed"):
        actions.append("cap_table_rows")
    if chart_result.get("trimmed"):
        actions.append("shorten_chart_labels")
    actions.append("preserve_source_anchors")
    return actions


def _is_card_slot(slot_id: str) -> bool:
    return slot_id in CARD_LIKE_SLOTS or "card" in slot_id


def _card_title_from_block(block: dict[str, Any], title_limit: int, body_limit: int) -> dict[str, Any]:
    title = str(block.get("title") or "")
    content_items = _content_items(block)
    if not title and content_items:
        first = content_items[0]
        if ":" in first:
            title, body = first.split(":", 1)
            content_items = [body.strip()] + content_items[1:]
        else:
            title = first
            content_items = content_items[1:]
    before_title = title
    title = _shorten(title, title_limit) if title_limit else title
    kept_body = [_shorten(content_items[0], body_limit)] if content_items and body_limit else content_items[:1]
    return {"title": title, "content": kept_body, "trimmed": title != before_title or len(content_items) > len(kept_body) or any(a != b for a, b in zip(content_items, kept_body))}


def _content_items(block: dict[str, Any]) -> list[str]:
    content = block.get("content")
    if isinstance(content, list):
        return [str(item).strip() for item in content if str(item).strip()]
    if isinstance(content, dict):
        return [f"{key}: {value}" for key, value in content.items()]
    if isinstance(content, str) and content.strip():
        return [content.strip()]
    return []


def _block_visible_text(block: dict[str, Any]) -> str:
    parts = [str(block.get("title") or "").strip()]
    parts.extend(_content_items(block))
    return " ".join(part for part in parts if part).strip()


def _shorten(text: str, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if not limit or len(value) <= limit:
        return value
    if limit <= 8:
        return value[:limit].rstrip()
    cut = value[: limit - 1].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "."


def _warning(code: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"code": code, "severity": "warning", "message": message, "details": details}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")
