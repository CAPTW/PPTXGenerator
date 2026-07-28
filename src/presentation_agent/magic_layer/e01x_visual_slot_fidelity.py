"""Visual slot cardinality and motif gate for E01X-P."""

from __future__ import annotations

from typing import Any


REQUIRED_VISIBLE_COUNTS = {
    "title_text_region": 1,
    "subtitle_text_region": 1,
    "card_panel": 3,
    "card_text": 3,
    "hero_visual_field": 1,
    "source_footer_strip": 1,
    "semantic_icon": 1,
}


def build_slot_count_preservation_report(nodes: list[dict[str, Any]], duplicate_report: dict[str, Any]) -> dict[str, Any]:
    declared = dict(duplicate_report.get("declared_counts") or {})
    visible = dict(duplicate_report.get("visible_counts") or {})
    for node in nodes:
        slot = _slot_kind(node)
        declared.setdefault(slot, 0)
        visible.setdefault(slot, 0)
    failures = []
    rows = []
    for slot, required in REQUIRED_VISIBLE_COUNTS.items():
        actual = int(visible.get(slot, 0))
        declared_count = int(declared.get(slot, 0))
        status = "passed" if actual >= required else "failed"
        if status == "failed":
            failures.append(f"{slot}_visible_count_lt_required")
        rows.append({"slot_kind": slot, "required_visible_count": required, "declared_count": declared_count, "visible_count": actual, "status": status})
    return {
        "schema_name": "slot_count_preservation_report",
        "status": "passed" if not failures else "failed",
        "required_visible_counts": REQUIRED_VISIBLE_COUNTS,
        "declared_counts": declared,
        "visible_counts": visible,
        "rows": rows,
        "failures": failures,
        "canva_parity_claimed": False,
    }


def build_rendered_visibility_report(duplicate_report: dict[str, Any]) -> dict[str, Any]:
    hidden = [row for row in duplicate_report.get("visibility", []) if row.get("render_visibility") != "visible"]
    return {
        "schema_name": "rendered_visibility_report",
        "status": "passed" if not hidden else "failed",
        "hidden_or_overlapped_count": len(hidden),
        "visibility": duplicate_report.get("visibility", []),
        "hidden_or_overlapped": hidden,
        "canva_parity_claimed": False,
    }


def build_visual_motif_preservation_report(nodes: list[dict[str, Any]], duplicate_report: dict[str, Any]) -> dict[str, Any]:
    by_role: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        by_role.setdefault(_slot_kind(node), []).append(node)
    visible = duplicate_report.get("visible_counts", {})
    required = {
        "hero_contour_visual_field": int(visible.get("hero_visual_field", len(by_role.get("hero_visual_field", [])))) >= 1,
        "footer_strip_with_gold_rule": int(visible.get("source_footer_strip", len(by_role.get("source_footer_strip", [])))) >= 1,
        "three_card_content_cluster": int(visible.get("card_panel", 0)) >= 3,
        "title_subtitle_hierarchy": int(visible.get("title_text_region", 0)) >= 1 and int(visible.get("subtitle_text_region", 0)) >= 1,
    }
    supporting = {
        "card_gold_underlines": any(node.get("semantic_role") == "card_underline" for node in nodes),
        "cyan_circle_icon_with_triangle": any(node.get("semantic_role") == "semantic_icon" and node.get("vector_motif") == "cyan_circle_with_inner_triangle" for node in nodes),
        "lower_technical_connector_dot_line": any(node.get("semantic_role") == "technical_overlay" for node in nodes),
        "top_right_subtle_grid_texture": any(node.get("semantic_role") == "decorative_texture" for node in nodes),
    }
    failures = [name for name, passed in required.items() if not passed]
    warnings = [name for name, passed in supporting.items() if not passed]
    return {
        "schema_name": "visual_motif_preservation_report",
        "status": "passed" if not failures else "failed",
        "required_motifs": required,
        "important_supporting_motifs": supporting,
        "failures": failures,
        "warnings": warnings,
        "canva_parity_claimed": False,
    }


def evaluate_visual_slot_fidelity_gate(
    *,
    duplicate_report: dict[str, Any],
    slot_count_report: dict[str, Any],
    motif_report: dict[str, Any],
    semantic_raster_violation_count: int,
    unknown_content_bearing_layer_count: int,
    e01p_v_postcompile_status: str,
) -> dict[str, Any]:
    failures: list[str] = []
    if duplicate_report.get("collision_count", 0):
        failures.append("duplicate_semantic_bbox_collision")
    failures.extend(slot_count_report.get("failures", []))
    failures.extend(f"required_motif_missing:{item}" for item in motif_report.get("failures", []))
    if semantic_raster_violation_count:
        failures.append("semantic_raster_violation")
    if unknown_content_bearing_layer_count:
        failures.append("unknown_content_bearing_layer")
    if e01p_v_postcompile_status != "passed":
        failures.append("e01p_v_postcompile_failed")
    if not failures:
        decision = "E01X_P_PASS_READY_FOR_E02_4CORE"
    elif any(item in failures for item in ("semantic_raster_violation", "unknown_content_bearing_layer")):
        decision = "E01X_P_FAIL_SEMANTIC_EDITABILITY"
    elif "e01p_v_postcompile_failed" in failures:
        decision = "E01X_P_PATCH_COMPILER_LAYOUT_MAPPING"
    elif "duplicate_semantic_bbox_collision" in failures:
        decision = "E01X_P_FAIL_VISUAL_SLOT_FIDELITY"
    else:
        decision = "E01X_P_PATCH_RENDER_FIDELITY"
    return {
        "schema_name": "visual_slot_fidelity_report",
        "status": "passed" if not failures else "failed",
        "decision": decision,
        "failures": failures,
        "warnings": motif_report.get("warnings", []),
        "duplicate_collision_count": duplicate_report.get("collision_count", 0),
        "visible_counts": slot_count_report.get("visible_counts", {}),
        "semantic_raster_violation_count": semantic_raster_violation_count,
        "unknown_content_bearing_layer_count": unknown_content_bearing_layer_count,
        "canva_parity_claimed": False,
    }


def _slot_kind(node: dict[str, Any]) -> str:
    object_id = str(node.get("object_id") or "")
    role = str(node.get("semantic_role") or "")
    if object_id.startswith("card_text") or role == "body_text_region":
        return "card_text"
    if object_id.startswith("card_panel") or role == "card_panel":
        return "card_panel"
    return role or object_id
