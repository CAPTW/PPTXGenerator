from __future__ import annotations

from typing import Any

from ..schemas.common import is_full_slide_bbox


def validate_unknown_layers(psd_like_layer_model: dict[str, Any], object_graph: dict[str, Any] | None = None) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    unknown_content = 0
    unknown_decorative = 0
    manual_review = 0

    for item in list(psd_like_layer_model.get("layers", []) or []) + list((object_graph or {}).get("objects", []) or []):
        kind = str(item.get("kind") or item.get("object_kind") or "")
        role = str(item.get("semantic_role") or "")
        is_unknown = kind == "unknown" or role == "unknown"
        if not is_unknown:
            continue
        item_id = item.get("id") or item.get("object_id") or item.get("layer_id") or "<unknown>"
        if is_full_slide_bbox(item.get("bbox_norm")):
            failures.append(f"Unknown full-slide layer/object {item_id} is fatal.")
        elif item.get("content_bearing"):
            unknown_content += 1
            failures.append(f"Unknown content-bearing layer/object {item_id} is fatal.")
        else:
            unknown_decorative += 1
            manual_review += 1
            warnings.append(f"Unknown decorative bounded layer/object {item_id} requires warning/manual review.")
    return {
        "schema_name": "unknown_layer_policy_validation",
        "unknown_content_bearing_count": unknown_content,
        "unknown_decorative_count": unknown_decorative,
        "fatal_unknown_count": len(failures),
        "manual_review_required_count": manual_review,
        "pass": not failures,
        "failures": failures,
        "warnings": warnings,
    }
