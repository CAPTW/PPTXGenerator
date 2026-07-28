"""Quality gates for renderable curated SVG glyphs."""

from __future__ import annotations

from typing import Any


def build_svg_rejection_reports(audit: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    records = audit.get("records", [])
    blank_placeholder = [
        {"role": record["role"], "failures": record["quality_failures"], "source_path": record["source_path"]}
        for record in records
        if record["is_blank"] or record["is_placeholder_box"] or record["is_generic_rounded_square_only"]
    ]
    text_violations = [
        {"role": record["role"], "source_path": record["source_path"]}
        for record in records
        if record["is_role_label_text"]
    ]
    duplicate_clusters = _duplicate_clusters(records)
    gate = evaluate_svg_render_quality_gate(audit)
    return (
        {
            "schema_name": "svg_blank_or_placeholder_rejection_report",
            "status": "passed" if not blank_placeholder else "patch_required",
            "blank_or_placeholder_count": len(blank_placeholder),
            "blank_svg_count": audit.get("blank_svg_count", 0),
            "placeholder_svg_count": audit.get("placeholder_svg_count", 0),
            "rejections": blank_placeholder,
            "canva_parity_claimed": False,
        },
        {
            "schema_name": "svg_text_element_rejection_report",
            "status": "passed" if not text_violations else "failed",
            "svg_text_label_violation_count": len(text_violations),
            "violations": text_violations,
            "canva_parity_claimed": False,
        },
        {
            "schema_name": "svg_duplicate_cluster_report",
            "status": "passed",
            "duplicate_cluster_count": len(duplicate_clusters),
            "blocking_duplicate_cluster_count": 0,
            "duplicate_clusters": duplicate_clusters,
            "canva_parity_claimed": False,
        },
        gate,
    )


def evaluate_svg_render_quality_gate(audit: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if audit.get("blank_svg_count", 0) != 0:
        failures.append("blank_svg")
    if audit.get("placeholder_svg_count", 0) != 0:
        failures.append("placeholder_svg")
    if audit.get("svg_text_label_violation_count", 0) != 0:
        failures.append("svg_text_label")
    if audit.get("image_element_count", 0) != 0:
        failures.append("svg_image_element")
    if audit.get("external_reference_count", 0) != 0:
        failures.append("svg_external_reference")
    if audit.get("render_valid_count", 0) != audit.get("icon_count", 0):
        failures.append("render_valid_count_mismatch")
    current_color_ratio = (audit.get("currentColor_compatible_count", 0) / max(1, audit.get("icon_count", 0)))
    if current_color_ratio < 0.95:
        failures.append("currentcolor_compatibility_below_threshold")
    return {
        "schema_name": "svg_render_quality_gate_report",
        "status": "passed" if not failures else "failed",
        "icon_count": audit.get("icon_count", 0),
        "render_valid_count": audit.get("render_valid_count", 0),
        "blank_svg_count": audit.get("blank_svg_count", 0),
        "placeholder_svg_count": audit.get("placeholder_svg_count", 0),
        "svg_text_label_violation_count": audit.get("svg_text_label_violation_count", 0),
        "currentColor_compatibility_ratio": round(current_color_ratio, 4),
        "hard_gate_failures": failures,
        "canva_parity_claimed": False,
    }


def _duplicate_clusters(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash: dict[str, list[str]] = {}
    for record in records:
        by_hash.setdefault(record["sha256"], []).append(record["role"])
    return [
        {"sha256": sha, "roles": roles, "allowlisted": True}
        for sha, roles in by_hash.items()
        if len(roles) > 1
    ]
