"""Semantic icon inventory for the E01H-P fidelity patch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CHECKLIST_ICON_GLYPHS = [
    ("checklist_icon_1", "PLAN & PREPARE", "clipboard"),
    ("checklist_icon_2", "SET UP & SECURE", "valve"),
    ("checklist_icon_3", "EXECUTE & MONITOR", "gauge"),
    ("checklist_icon_4", "VERIFY & CONFIRM", "shield"),
    ("checklist_icon_5", "COMPLETE & RECORD", "document"),
]
FOOTER_ICON_GLYPHS = [
    ("footer_icon_1", "WEAR PPE", "ppe"),
    ("footer_icon_2", "ZERO LEAK ZERO SPILL", "no_leak"),
    ("footer_icon_3", "SAFETY BARRIER", "barrier_shield"),
    ("footer_icon_4", "COMMUNICATE CONFIRM", "speech"),
    ("footer_icon_5", "TEAMWORK", "team"),
]


def build_semantic_icon_inventory_report(e01h_root: str | Path) -> dict[str, Any]:
    root = Path(e01h_root)
    object_graph = _read_json(root / "object_graph_v2.json")
    node_index = {node.get("object_id"): node for node in object_graph.get("nodes", [])}
    required_icons: list[dict[str, Any]] = []

    for object_id, label, glyph in CHECKLIST_ICON_GLYPHS:
        required_icons.append(_icon_row(object_id, label, glyph, "checklist_step_icon", node_index.get(object_id)))
    for index in range(1, 6):
        object_id = f"checklist_chevron_{index}"
        required_icons.append(_icon_row(object_id, f"CHECKLIST ROW {index} CHEVRON", "chevron", "chevron_marker", node_index.get(object_id)))
    for object_id, label, glyph in FOOTER_ICON_GLYPHS:
        required_icons.append(_icon_row(object_id, label, glyph, "safety_bar_icon", node_index.get(object_id)))

    missing = [row for row in required_icons if not row["source_region_present"]]
    empty_placeholder_count = sum(1 for row in required_icons if row["baseline_render_issue"] == "empty_or_generic_circle")
    return {
        "schema_name": "semantic_icon_inventory_report",
        "status": "needs_patch" if empty_placeholder_count or missing else "passed",
        "input_root": root.as_posix(),
        "required_semantic_icon_count": len(required_icons),
        "checklist_step_icon_count": sum(1 for row in required_icons if row["icon_class"] == "checklist_step_icon"),
        "chevron_marker_count": sum(1 for row in required_icons if row["icon_class"] == "chevron_marker"),
        "safety_bar_icon_count": sum(1 for row in required_icons if row["icon_class"] == "safety_bar_icon"),
        "unknown_icon_count": 0,
        "empty_circle_placeholder_count": empty_placeholder_count,
        "missing_source_region_count": len(missing),
        "required_icons": required_icons,
        "rules": [
            "Visible checklist step icons are semantic icons.",
            "Bottom safety-bar icons are semantic icons.",
            "Checklist chevrons are semantic navigation markers.",
            "Empty circles do not satisfy meaningful semantic icon reconstruction.",
        ],
        "canva_parity_claimed": False,
    }


def semantic_icon_inventory_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Semantic Icon Inventory Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Required semantic icons: `{report['required_semantic_icon_count']}`",
        f"- Checklist step icons: `{report['checklist_step_icon_count']}`",
        f"- Checklist chevrons: `{report['chevron_marker_count']}`",
        f"- Safety-bar icons: `{report['safety_bar_icon_count']}`",
        f"- Baseline empty/generic placeholders: `{report['empty_circle_placeholder_count']}`",
        "- Broad Canva parity claimed: `False`",
        "",
        "## Required Icons",
    ]
    for row in report["required_icons"]:
        lines.append(f"- `{row['object_id']}`: {row['icon_class']} -> `{row['required_glyph_kind']}`")
    return "\n".join(lines)


def _icon_row(object_id: str, label: str, glyph: str, icon_class: str, node: dict[str, Any] | None) -> dict[str, Any]:
    bbox = node.get("bbox_norm") if node else None
    return {
        "object_id": object_id,
        "label": label,
        "icon_class": icon_class,
        "classification": "semantic_icon" if icon_class != "chevron_marker" else "navigation_marker",
        "required_glyph_kind": glyph,
        "source_region_present": node is not None,
        "bbox_norm": bbox,
        "content_bearing": True,
        "required_target": "native_vector",
        "raster_allowed": False,
        "not_applicable_allowed": False,
        "baseline_render_issue": "empty_or_generic_circle",
        "patch_requirement": "replace empty/generic circle with meaningful vector glyph",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
