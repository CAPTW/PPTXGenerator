"""Quarantine reports for contaminated and placeholder icon candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .e03_4_icon_role_taxonomy import P0_ROLE_IDS


def build_generic_placeholder_rejection_report(audit: dict[str, Any]) -> dict[str, Any]:
    placeholders = [
        {
            "role_id": row["role_id"],
            "priority": row.get("priority"),
            "svg_path": row.get("svg_path"),
            "reason": "generic_placeholder_shape",
            "status": "quarantined_do_not_use_for_semantic_icon",
        }
        for row in audit.get("role_audits", [])
        if row.get("placeholder_like")
    ]
    return {
        "schema_name": "generic_placeholder_rejection_report",
        "status": "passed",
        "generic_placeholder_icon_count": len(placeholders),
        "generic_placeholder_p0_count": sum(
            row.get("priority") == "P0_REQUIRED_SEMANTIC" or row.get("role_id") in P0_ROLE_IDS for row in placeholders
        ),
        "quarantined_svg_paths": [row["svg_path"] for row in placeholders if row.get("svg_path")],
        "placeholders": placeholders,
    }


def build_contaminated_crop_rejection_report(previous_icon_stage_root: Path | None = None) -> dict[str, Any]:
    rejected: list[dict[str, Any]] = []
    if previous_icon_stage_root:
        for name in ("rejected_crop_resolution_report.json", "icon_false_positive_report.json", "revised_false_positive_report.json"):
            path = previous_icon_stage_root / name
            if path.exists():
                try:
                    import json

                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                rows = payload.get("rejected_crops") or payload.get("auto_rejected") or payload.get("items") or []
                for row in rows:
                    rejected.append(
                        {
                            "source_stage_report": path.as_posix(),
                            "role_id": row.get("role") or row.get("role_id") or row.get("role_guess"),
                            "crop_path": row.get("raw_crop") or row.get("cleaned_glyph_crop") or row.get("crop_path"),
                            "reason": row.get("reason") or row.get("decision") or "previous_stage_rejected_crop",
                            "status": "rejected_contaminated_crop_not_used",
                        }
                    )
                if rejected:
                    break
    return {
        "schema_name": "contaminated_crop_rejection_report",
        "status": "passed",
        "rejected_contaminated_crop_count": len(rejected),
        "semantic_icon_crop_reused_count": 0,
        "rejected_crops": rejected,
    }
