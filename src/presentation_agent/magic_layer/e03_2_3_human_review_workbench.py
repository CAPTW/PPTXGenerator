"""Human review queue for unresolved complex icon SVG candidates."""

from __future__ import annotations

from typing import Any


def build_complex_icon_review_queue(candidate_manifest: dict[str, Any]) -> dict[str, Any]:
    rows = []
    template = []
    for idx, candidate in enumerate(candidate_manifest.get("review_required_candidates", []), start=1):
        if not str(candidate.get("priority", "")).startswith(("P0", "P1")):
            continue
        review_id = f"complex_icon_{idx:03d}_{candidate['icon_id']}"
        row = {
            "review_id": review_id,
            "icon_id": candidate["icon_id"],
            "role": candidate.get("likely_role"),
            "priority": candidate.get("priority"),
            "candidate_variant": candidate.get("variant"),
            "candidate_svg_path": candidate.get("svg_path"),
            "final_candidate_score": candidate.get("final_candidate_score"),
            "review_status": "pending_human_review",
            "recommended_decision": "approve_variant" if candidate.get("final_candidate_score", 0) >= 0.72 else "request_manual_svg",
        }
        rows.append(row)
        template.append({"review_id": review_id, "decision": "approve_variant | reject_not_icon | adjust_crop | request_manual_svg | accept_library_match", "approved_variant": candidate.get("variant"), "role": candidate.get("likely_role"), "notes": "", "adjusted_bbox_px": None})
    unresolved_p0 = sum(1 for row in rows if str(row.get("priority", "")).startswith("P0"))
    unresolved_p1 = sum(1 for row in rows if str(row.get("priority", "")).startswith("P1"))
    resolution = {
        "schema_name": "human_review_resolution_report",
        "status": "passed" if not rows else "pending",
        "unresolved_p0_count": unresolved_p0,
        "unresolved_p1_count": unresolved_p1,
        "resolved_count": 0,
        "rows": rows,
    }
    return {
        "schema_name": "complex_icon_review_queue",
        "status": resolution["status"],
        "human_review_required_count": len(rows),
        "icons": rows,
        "template": template,
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["review_id", "decision", "role"],
                "properties": {
                    "review_id": {"type": "string"},
                    "decision": {"enum": ["approve_variant", "reject_not_icon", "adjust_crop", "request_manual_svg", "accept_library_match"]},
                    "approved_variant": {"type": ["string", "null"]},
                    "role": {"type": "string"},
                    "notes": {"type": "string"},
                    "adjusted_bbox_px": {"type": ["array", "null"]},
                },
            },
        },
        "resolution_report": resolution,
    }
