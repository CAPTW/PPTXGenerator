"""Manual deterministic SVG authoring for E03.4 icon foundation gaps."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_manual_svg_authoring_backlog(taxonomy: dict[str, Any], gap_matrix: dict[str, Any]) -> dict[str, Any]:
    taxonomy_by_role = taxonomy.get("roles_by_role", {})
    items: list[dict[str, Any]] = []
    for row in gap_matrix.get("roles", []):
        if row.get("status") == "accepted_v6":
            continue
        role = taxonomy_by_role.get(row["role_id"], {})
        items.append(
            {
                "role_id": row["role_id"],
                "priority": row["priority"],
                "visual_description": role.get("visual_description", row["role_id"]),
                "reference_context": role.get("usage_contexts", []),
                "preferred_geometry": _preferred_geometry(row["role_id"]),
                "simple_svg_construction_plan": f"Author a role-specific {row['role_id']} pictogram with currentColor primitives.",
                "examples_from_local_library": [row.get("candidate_source")] if row.get("candidate_source") else [],
                "output_path": f"assets/icons/generated/magic_layer/e03_4_v7/{row['role_id']}/{row['role_id']}.svg",
                "priority_reason": row.get("reason"),
            }
        )
    return {
        "schema_name": "manual_svg_authoring_backlog",
        "status": "passed",
        "backlog_count": len(items),
        "backlog_items": items,
    }


def author_svg_backlog_v7(backlog: dict[str, Any], generated_root: Path) -> dict[str, Any]:
    authored: list[dict[str, Any]] = []
    for item in backlog.get("backlog_items", []):
        role_id = item["role_id"]
        svg_path = generated_root / role_id / f"{role_id}.svg"
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_text = svg_for_role(role_id)
        svg_path.write_text(svg_text, encoding="utf-8")
        metadata = {
            "role_id": role_id,
            "authored_stage": "E03.4",
            "source": "manual_svg_authoring",
            "rationale": item.get("simple_svg_construction_plan"),
            "usage_contexts": item.get("reference_context", []),
            "quality_status": "pending_quality_gate",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "render_hash": hashlib.sha256(svg_text.encode("utf-8")).hexdigest(),
        }
        metadata_path = svg_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        authored.append({**item, "svg_path": svg_path.as_posix(), "metadata_path": metadata_path.as_posix(), "sha256": metadata["render_hash"]})
    return {
        "schema_name": "authored_svg_manifest_v7",
        "status": "passed",
        "authored_svg_count": len(authored),
        "authored_svgs": authored,
    }


def svg_for_role(role_id: str) -> str:
    body = ROLE_SVG_BODIES.get(role_id, f'<path d="M12 3l7 5v8l-7 5-7-5V8z"/><path d="M{4 + len(role_id) % 4} 17h{12 + len(role_id) % 3}"/>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>\n"
    )


def _preferred_geometry(role_id: str) -> str:
    if "chart" in role_id:
        return "axis and data marks"
    if role_id in {"table", "comparison_matrix"}:
        return "grid lines"
    if role_id in {"shield", "shield_check", "warning", "risk_status", "lock"}:
        return "risk/control silhouette"
    if role_id in {"timeline", "milestone_flag", "process_node", "route"}:
        return "node and connector system"
    return "monoline pictogram"


ROLE_SVG_BODIES = {
    "source": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v8c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M7 18h10"/>',
    "citation": '<path d="M8 7H6a3 3 0 0 0 0 6h2"/><path d="M16 7h2a3 3 0 0 1 0 6h-2"/><path d="M9 10h6"/><path d="M7 18h10"/>',
    "document": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5"/><path d="M9 12h6M9 16h5"/>',
    "file_check": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5"/><path d="M9 15l2 2 4-5"/>',
    "checklist": '<path d="M5 7l2 2 3-4"/><path d="M13 7h6"/><path d="M5 14l2 2 3-4"/><path d="M13 14h6"/><path d="M13 20h6"/>',
    "clipboard_check": '<path d="M9 4h6l1 3H8z"/><path d="M6 6h12v15H6z"/><path d="M9 15l2 2 4-5"/>',
    "database": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
    "table": '<rect x="4" y="5" width="16" height="14" rx="1"/><path d="M4 10h16M4 14h16M10 5v14M15 5v14"/>',
    "chart_bar": '<path d="M4 20h16"/><rect x="6" y="12" width="3" height="6"/><rect x="11" y="8" width="3" height="10"/><rect x="16" y="5" width="3" height="13"/>',
    "chart_line": '<path d="M4 19h16"/><path d="M5 15l4-4 4 2 5-7"/><circle cx="9" cy="11" r="1"/><circle cx="13" cy="13" r="1"/><circle cx="18" cy="6" r="1"/>',
    "pie_chart": '<path d="M12 3v9h9"/><path d="M19.1 16.5A8 8 0 1 1 10 4.2"/><path d="M13 4.1A8 8 0 0 1 20.9 11"/>',
    "dashboard": '<rect x="4" y="5" width="7" height="6" rx="1"/><rect x="13" y="5" width="7" height="4" rx="1"/><rect x="4" y="13" width="7" height="6" rx="1"/><path d="M14 18a4 4 0 0 1 5-5"/><path d="M17 16l2-3"/>',
    "kpi": '<rect x="4" y="5" width="16" height="14" rx="2"/><path d="M8 15l3-3 2 2 4-5"/><path d="M8 18h8"/>',
    "shield": '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/>',
    "shield_check": '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/><path d="M9 12l2 2 4-5"/>',
    "warning": '<path d="M12 3l9 18H3z"/><path d="M12 8v5"/><circle cx="12" cy="17" r=".8"/>',
    "risk_status": '<path d="M12 3l3.2 5.4 5.8 1.2-4 4.4.7 6-5.7-2.6L6.3 20l.7-6-4-4.4 5.8-1.2z"/><path d="M12 8.5v5"/><circle cx="12" cy="16.5" r=".7"/>',
    "lock": '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><path d="M12 14v2"/>',
    "approval": '<circle cx="12" cy="12" r="8"/><path d="M8 12l3 3 5-6"/>',
    "decision_diamond": '<path d="M12 3l9 9-9 9-9-9z"/><path d="M8 12h8"/>',
    "process_node": '<circle cx="7" cy="12" r="3"/><circle cx="17" cy="12" r="3"/><path d="M10 12h4"/><path d="M16 10l2 2-2 2"/>',
    "timeline": '<path d="M4 12h16"/><circle cx="7" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="17" cy="12" r="2"/><path d="M7 8v-2M17 16v2"/>',
    "milestone_flag": '<path d="M6 21V4"/><path d="M6 5h10l-2 4 2 4H6"/><circle cx="6" cy="18" r="1"/>',
    "flag": '<path d="M6 21V4"/><path d="M6 5h10l-2 4 2 4H6"/>',
    "target": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    "route": '<circle cx="5" cy="18" r="2"/><circle cx="19" cy="6" r="2"/><path d="M7 18c5 0 4-12 10-12"/><path d="M10 12h4"/>',
    "network": '<circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 11l8-4M8 13l8 4"/>',
    "calendar": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/><path d="M8 14h2M12 14h2M16 14h2M8 17h2M12 17h2"/>',
    "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.4-4 4.3-6 8-6s6.6 2 8 6"/>',
    "users": '<circle cx="9" cy="8" r="3"/><circle cx="16" cy="9" r="2.5"/><path d="M3 21c1-3.7 3.2-5.5 6-5.5s5 1.8 6 5.5"/><path d="M14 16c2.6.3 4.6 2 5.5 5"/>',
    "team": '<circle cx="12" cy="7" r="3"/><circle cx="6" cy="10" r="2.5"/><circle cx="18" cy="10" r="2.5"/><path d="M4 21c1.1-3 3.8-5 8-5s6.9 2 8 5"/>',
    "owner": '<circle cx="10" cy="8" r="4"/><path d="M3 21c1.3-4 3.8-6 7-6"/><path d="M16 13l4 2v3c0 2-1.5 3.2-4 4-2.5-.8-4-2-4-4v-3z"/>',
    "note": '<path d="M5 4h14v11l-5 5H5z"/><path d="M14 20v-5h5"/><path d="M8 8h8M8 12h6"/>',
    "insight": '<path d="M8 10a4 4 0 1 1 8 0c0 1.5-.8 2.5-1.8 3.5-.7.8-1.2 1.4-1.2 2.5h-2c0-1.1-.5-1.7-1.2-2.5C8.8 12.5 8 11.5 8 10z"/><path d="M9 18h6M10 21h4M12 2v2M5.5 5.5l1.4 1.4M18.5 5.5l-1.4 1.4"/>',
    "recommendation": '<path d="M5 13l4 4L20 6"/><path d="M4 20h16"/><path d="M7 4h10"/>',
    "next_action": '<path d="M4 12h13"/><path d="M13 7l5 5-5 5"/><path d="M5 19h6"/>',
    "evidence_trace": '<path d="M4 12s3.2-5 8-5 8 5 8 5-3.2 5-8 5-8-5-8-5z"/><circle cx="12" cy="12" r="2.5"/><path d="M17 17l3 3"/>',
    "scale": '<path d="M12 4v16M6 7h12"/><path d="M7 7l-4 7h8zM17 7l-4 7h8z"/>',
    "book": '<path d="M5 5.5c2.5-1 4.5-.5 7 1v13c-2.5-1.5-4.5-2-7-1z"/><path d="M19 5.5c-2.5-1-4.5-.5-7 1v13c2.5-1.5 4.5-2 7-1z"/>',
    "folder": '<path d="M3 7h7l2 2h9v10H3z"/><path d="M3 7v-2h7l2 2"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 12l9 5 9-5"/><path d="M3 16l9 5 9-5"/>',
    "building": '<path d="M5 21V5l9-2v18"/><path d="M14 9h5v12"/><path d="M8 8h2M8 12h2M8 16h2M16 13h1M16 17h1"/>',
    "bank": '<path d="M3 9l9-5 9 5z"/><path d="M5 10v8M9 10v8M15 10v8M19 10v8"/><path d="M4 20h16"/>',
    "factory": '<path d="M4 21V10l5 3v-3l5 3V8h6v13z"/><path d="M7 17h2M12 17h2M17 17h2"/>',
    "api": '<path d="M7 8l-4 4 4 4"/><path d="M17 8l4 4-4 4"/><path d="M10 19l4-14"/>',
    "automation": '<path d="M12 4v3"/><path d="M12 17v3"/><path d="M4 12h3"/><path d="M17 12h3"/><circle cx="12" cy="12" r="5"/><path d="M10 12l2 2 3-4"/>',
    "brain": '<path d="M9 4c-2 0-4 1.5-4 4 0 1 .4 1.8 1 2.4A4 4 0 0 0 7 18c1.2 0 2-.4 3-1"/><path d="M15 4c2 0 4 1.5 4 4 0 1-.4 1.8-1 2.4A4 4 0 0 1 17 18c-1.2 0-2-.4-3-1"/><path d="M12 5v14"/>',
    "chip": '<rect x="7" y="7" width="10" height="10" rx="2"/><path d="M4 9h3M4 15h3M17 9h3M17 15h3M9 4v3M15 4v3M9 17v3M15 17v3"/>',
    "model": '<path d="M12 3l8 4v10l-8 4-8-4V7z"/><path d="M12 3v18M4 7l8 4 8-4"/><path d="M8 15l4 2 4-2"/>',
    "cloud": '<path d="M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 11.5 3.5 3.5 0 0 0 7 18z"/>',
    "server": '<rect x="5" y="4" width="14" height="7" rx="1"/><rect x="5" y="13" width="14" height="7" rx="1"/><path d="M8 8h.1M8 17h.1M12 8h4M12 17h4"/>',
    "filter": '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
    "search": '<circle cx="10" cy="10" r="6"/><path d="M15 15l5 5"/>',
    "refresh": '<path d="M20 7v5h-5"/><path d="M4 17v-5h5"/><path d="M18 12a6 6 0 0 0-10-5"/><path d="M6 12a6 6 0 0 0 10 5"/>',
    "loop": '<path d="M17 7h2a4 4 0 0 1 0 8h-3"/><path d="M7 17H5a4 4 0 0 1 0-8h3"/><path d="M14 5l3 2-3 2M10 19l-3-2 3-2"/>',
    "package": '<path d="M4 8l8-4 8 4v9l-8 4-8-4z"/><path d="M4 8l8 4 8-4"/><path d="M12 12v9"/>',
    "launch": '<path d="M5 19c2-5 6-10 14-14-4 8-9 12-14 14z"/><path d="M13 7l4 4"/><path d="M5 19l4-1-3-3z"/>',
    "gavel": '<path d="M14 4l6 6-3 3-6-6z"/><path d="M11 7l-4 4"/><path d="M4 20h10"/><path d="M6 18l4-4"/>',
    "trophy": '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 6H4c0 3 1.5 5 4 5"/><path d="M16 6h4c0 3-1.5 5-4 5"/><path d="M12 13v5M8 21h8"/>',
    "star": '<path d="M12 3l2.7 5.5 6 .9-4.3 4.2 1 6-5.4-2.9-5.4 2.9 1-6-4.3-4.2 6-.9z"/>',
    "anchor": '<path d="M12 3v14"/><circle cx="12" cy="5" r="2"/><path d="M5 12h14"/><path d="M6 14c0 4 3 7 6 7s6-3 6-7"/><path d="M4 17l2-3 3 2M20 17l-2-3-3 2"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c3 3 3 15 0 18"/><path d="M12 3c-3 3-3 15 0 18"/>',
    "handshake": '<path d="M7 12l3-3 3 3 2-2 4 4-5 5-4-4-2 2-4-4 3-3z"/><path d="M10 15l2-2M13 18l2-2"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.8 2.8 0 1 1 4.2 2.4c-1 .6-1.7 1.2-1.7 2.6"/><circle cx="12" cy="17" r=".7"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 10v7"/><circle cx="12" cy="7" r=".7"/>',
}
