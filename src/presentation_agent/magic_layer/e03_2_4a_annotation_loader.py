"""Load or scaffold E03.2.4A human review annotations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_DECISIONS = {
    "accept_existing_library_match",
    "author_manual_svg_from_crop",
    "adjust_crop_then_author_svg",
    "reject_not_icon",
    "mark_decorative_optional",
    "defer_not_required_for_e03_3",
}


def load_or_create_annotations(annotations_path: Path, template_path: Path) -> dict[str, Any]:
    created = False
    if annotations_path.exists():
        annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
    else:
        template = json.loads(template_path.read_text(encoding="utf-8")) if template_path.exists() else []
        annotations = [_scaffold_annotation(row) for row in template]
        annotations_path.parent.mkdir(parents=True, exist_ok=True)
        annotations_path.write_text(json.dumps(annotations, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        created = True

    concrete = [row for row in annotations if is_concrete_decision(row.get("decision"))]
    invalid = [row for row in annotations if row.get("decision") not in {None, ""} and not is_concrete_decision(row.get("decision"))]
    return {
        "schema_name": "human_review_annotation_load_report",
        "status": "passed" if concrete else "blocked_missing_concrete_annotations",
        "annotations_path": annotations_path.as_posix(),
        "created_from_template": created,
        "annotation_count": len(annotations),
        "concrete_annotation_count": len(concrete),
        "invalid_decision_count": len(invalid),
        "annotations": annotations,
    }


def is_concrete_decision(value: Any) -> bool:
    return isinstance(value, str) and value in ALLOWED_DECISIONS


def apply_role_decision_overrides(annotations: list[dict[str, Any]], role_decisions: dict[str, str]) -> dict[str, Any]:
    updated: list[dict[str, Any]] = []
    invalid_roles: list[str] = []
    for row in annotations:
        role = str(row.get("role") or row.get("role_guess") or "").strip()
        decision = row.get("decision")
        if not is_concrete_decision(decision) and role in role_decisions:
            decision = role_decisions[role]
        if not is_concrete_decision(decision):
            invalid_roles.append(role)
        updated.append({**row, "role": role, "decision": decision if is_concrete_decision(decision) else row.get("decision")})
    concrete = [row for row in updated if is_concrete_decision(row.get("decision"))]
    return {
        "schema_name": "human_review_annotation_override_report",
        "status": "passed" if not invalid_roles else "blocked",
        "annotation_count": len(updated),
        "concrete_annotation_count": len(concrete),
        "invalid_or_missing_role_count": len(invalid_roles),
        "invalid_or_missing_roles": invalid_roles,
        "annotations": updated,
    }


def _scaffold_annotation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": row.get("review_id"),
        "decision": row.get("decision") if is_concrete_decision(row.get("decision")) else None,
        "role": row.get("role") or row.get("role_guess"),
        "approved_variant": row.get("approved_variant"),
        "notes": row.get("notes") or "No concrete human review decision supplied.",
        "adjusted_bbox_px": row.get("adjusted_bbox_px"),
    }
