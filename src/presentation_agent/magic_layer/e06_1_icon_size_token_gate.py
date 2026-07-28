"""Icon size token validation for the E06.1 layout contract."""

from __future__ import annotations

from typing import Any


def validate_icon_size_tokens(contract: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    token_defs = policy.get("tokens", {})
    failures: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for slide in contract.get("slides", []):
        for icon in slide.get("semantic_icon_slots", []):
            token = icon.get("size_token")
            token_def = token_defs.get(token)
            bbox = icon.get("bbox_in", {})
            if not token_def:
                failures.append({"object_id": icon.get("object_id"), "failure": "missing_size_token", "size_token": token})
                continue
            w = float(bbox.get("w", 0))
            h = float(bbox.get("h", 0))
            passed = token_def["min_w_in"] - 0.005 <= w <= token_def["max_w_in"] + 0.005 and token_def["min_h_in"] - 0.005 <= h <= token_def["max_h_in"] + 0.005
            row = {
                "slide_id": slide.get("slide_id"),
                "object_id": icon.get("object_id"),
                "semantic_role": icon.get("semantic_role"),
                "slot_type": icon.get("slot_type"),
                "size_token": token,
                "w_in": w,
                "h_in": h,
                "status": "passed" if passed else "failed",
            }
            rows.append(row)
            if not passed:
                failures.append({**row, "failure": "icon_size_outside_token_range", "token_def": token_def})
    return {
        "schema_name": "icon_size_token_validation_report",
        "status": "passed" if not failures else "failed",
        "semantic_icon_count": len(rows),
        "icon_size_token_failure_count": len(failures),
        "distinct_size_token_count": len({row["size_token"] for row in rows}),
        "rows": rows,
        "failures": failures,
    }
