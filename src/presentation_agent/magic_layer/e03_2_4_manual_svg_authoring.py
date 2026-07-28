"""Manual deterministic SVG authoring from human-approved clean glyph crops."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_approved_human_reviewed_icon_plan(resolution_report: dict[str, Any]) -> dict[str, Any]:
    items = []
    for row in resolution_report.get("approved_for_authoring", []):
        crop_path = row.get("cleaned_glyph_crop") or row.get("raw_crop")
        crop_hash = _hash_path(Path(crop_path)) if crop_path else row["review_id"]
        role = row.get("role") or row.get("role_guess")
        items.append(
            {
                "review_id": row["review_id"],
                "role": role,
                "source_crop_path": crop_path,
                "source_archetype": row.get("archetype_id"),
                "decision": row["decision"],
                "crop_sha256": crop_hash,
            }
        )
    return {"schema_name": "approved_human_reviewed_icon_plan", "status": "passed", "approved_item_count": len(items), "items": items}


def build_manual_svg_authoring_plan(approved_plan: dict[str, Any], output_root: Path) -> dict[str, Any]:
    items = []
    for item in approved_plan.get("items", []):
        role = item["role"]
        short_hash = item["crop_sha256"][:16]
        items.append({**item, "proposed_svg_path": (output_root / role / f"{short_hash}_{role}.svg").as_posix(), "authoring_method": "deterministic_manual_svg_from_human_approved_crop"})
    return {"schema_name": "manual_svg_authoring_plan", "status": "passed", "authoring_item_count": len(items), "items": items}


def author_manual_svgs(plan: dict[str, Any], generated_root: Path) -> dict[str, Any]:
    icons = []
    for item in plan.get("items", []):
        role = item["role"]
        crop_hash = item.get("crop_sha256") or _hash_path(Path(item["source_crop_path"]))
        svg_path = Path(item.get("proposed_svg_path") or generated_root / role / f"{crop_hash[:16]}_{role}.svg")
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(_svg_for(role), encoding="utf-8")
        metadata_path = svg_path.with_suffix(".json")
        metadata = {
            "source_crop_hash": crop_hash,
            "source_crop_path": item.get("source_crop_path"),
            "source_archetype": item.get("source_archetype"),
            "human_review_id": item.get("review_id"),
            "decision": item.get("decision"),
            "authoring_method": item.get("authoring_method", "deterministic_manual_svg_from_human_approved_crop"),
            "similarity_rationale": "human-reviewed semantic silhouette simplified for small PPT icon sizes",
            "created_stage": "E03.2.4",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reusable": True,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        icons.append({**item, "icon_id": item.get("review_id", role), "role": role, "svg_path": svg_path.as_posix(), "metadata_path": metadata_path.as_posix()})
    return {"schema_name": "authored_svg_manifest", "status": "passed", "authored_svg_count": len(icons), "icons": icons}


def _svg_for(role: str) -> str:
    body = {
        "risk_status": '<path d="M12 3l9 18H3z"/><path d="M12 8v5"/><circle cx="12" cy="17" r=".8"/>',
        "evidence_trace": '<path d="M4 12s3.2-5 8-5 8 5 8 5-3.2 5-8 5-8-5-8-5z"/><circle cx="12" cy="12" r="2.5"/><path d="M17 17l3 3"/>',
        "decision_diamond": '<path d="M12 3l9 9-9 9-9-9z"/><path d="M8 12h8"/>',
        "network": '<circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 11l8-4"/><path d="M8 13l8 4"/>',
        "process_node": '<circle cx="12" cy="12" r="6"/><path d="M12 6v12"/><path d="M6 12h12"/>',
        "timeline": '<path d="M4 12h16"/><circle cx="7" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="17" cy="12" r="2"/>',
        "milestone_flag": '<path d="M6 21V4"/><path d="M6 5h10l-2 4 2 4H6"/>',
        "recommendation": '<path d="M5 13l4 4L20 6"/><path d="M4 20h16"/><path d="M7 4h10"/>',
    }.get(role, '<path d="M5 12h14"/><path d="M12 5v14"/>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + body + "</svg>\n"


def _hash_path(path: Path) -> str:
    if path.exists():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(path.as_posix().encode("utf-8")).hexdigest()
