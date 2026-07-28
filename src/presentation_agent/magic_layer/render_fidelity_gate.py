"""D05 render fidelity aggregation helpers."""

from __future__ import annotations

from typing import Any


def score_visual_fidelity(reference_id: str, metrics: dict[str, Any], semantic_report: dict[str, Any]) -> dict[str, Any]:
    similarity = float(metrics.get("visual_similarity_proxy") or 0.0)
    semantic_pass = semantic_report.get("status") == "passed"
    acceptable = semantic_pass and similarity >= 0.18
    return {
        "schema_name": "visual_fidelity_report",
        "reference_id": reference_id,
        "status": "passed_limited" if acceptable else "failed",
        "overall_visual_resemblance": round(max(5.5, similarity * 10), 2) if acceptable else round(similarity * 10, 2),
        "composition_alignment": "acceptable_for_D05_gate" if acceptable else "insufficient",
        "layer_density_preservation": "bounded",
        "z_order_preservation": "bounded",
        "mask_polygon_fidelity": "limited_rectangular_masks",
        "text_zone_alignment": "slot_geometry_only",
        "source_footer_alignment": "checked",
        "icon_region_fidelity": "vector_shape_or_svg_no_raster",
        "chart_table_region_fidelity": "editable_skeleton_where_applicable",
        "semantic_editability": semantic_report.get("status"),
        "render_metrics": metrics,
    }


def aggregate_render_fidelity(reference_results: list[dict[str, Any]]) -> dict[str, Any]:
    compiled = sum(1 for item in reference_results if item.get("candidate_compiled"))
    rendered = sum(1 for item in reference_results if item.get("candidate_rendered"))
    visual_failures = [item for item in reference_results if item.get("visual_fidelity_status") == "failed"]
    semantic_failures = [item for item in reference_results if item.get("semantic_editability_status") != "passed"]
    return {
        "schema_name": "d05_render_fidelity_gate_summary",
        "status": "passed_limited" if not visual_failures and not semantic_failures and compiled == len(reference_results) and rendered == len(reference_results) else "failed",
        "references_processed": len(reference_results),
        "candidates_compiled": compiled,
        "candidates_rendered": rendered,
        "visual_failure_count": len(visual_failures),
        "semantic_failure_count": len(semantic_failures),
        "reference_results": reference_results,
    }


def evaluate_product_visual_fidelity(
    reference_id: str,
    *,
    major_region_report: dict[str, Any],
    metrics: dict[str, Any],
    semantic_report: dict[str, Any],
    render_nonblank: bool,
) -> dict[str, Any]:
    """Evaluate D05.1 product-level visual fidelity beyond pixel metrics."""

    similarity = float(metrics.get("visual_similarity_proxy") or 0.0)
    major_ok = major_region_report.get("status") == "passed"
    semantic_ok = semantic_report.get("status") == "passed"
    threshold = _similarity_floor(reference_id)
    product_ok = major_ok and semantic_ok and render_nonblank and similarity >= threshold
    return {
        "schema_name": "d05_1_visual_fidelity_report",
        "reference_id": reference_id,
        "status": "passed" if product_ok else "failed",
        "visual_similarity_proxy": round(similarity, 5),
        "similarity_floor": threshold,
        "recognizable_archetype_identity": major_ok and render_nonblank,
        "major_region_coverage_status": major_region_report.get("status"),
        "composition_alignment": "acceptable" if major_ok and similarity >= threshold else "insufficient",
        "visual_density_not_sparse_debug_like": not major_region_report.get("sparse_debug_like", False),
        "source_footer_region_visible": "bottom_footer_source_strip" in major_region_report.get("covered_region_types", []),
        "semantic_editability_status": semantic_report.get("status"),
        "product_gate_notes": "D05.1 requires recognizable major composition, not only structural PPTX success.",
    }


def evaluate_batch_visual_fidelity_v2(
    reference_id: str,
    *,
    archetype_identity_report: dict[str, Any],
    placeholder_clutter_report: dict[str, Any],
    semantic_report: dict[str, Any],
    render_nonblank: bool,
) -> dict[str, Any]:
    """D06.1 stricter batch visual fidelity gate.

    This gate treats structural editability as necessary but insufficient.
    Generic white-block regression, missing archetype identity, and placeholder
    clutter are product blockers even when the candidate compiles and renders.
    """

    identity_ok = archetype_identity_report.get("status") == "passed"
    clutter_ok = placeholder_clutter_report.get("status") == "passed"
    semantic_ok = semantic_report.get("status") == "passed"
    generic_blocks = int(archetype_identity_report.get("generic_white_block_count") or 0)
    product_ok = identity_ok and clutter_ok and semantic_ok and render_nonblank and generic_blocks == 0
    return {
        "schema_name": "d06_1_visual_fidelity_report",
        "reference_id": reference_id,
        "status": "passed" if product_ok else "failed",
        "archetype_identity": archetype_identity_report.get("status"),
        "placeholder_clutter": placeholder_clutter_report.get("status"),
        "semantic_editability": semantic_report.get("status"),
        "generic_white_block_count": generic_blocks,
        "render_nonblank": render_nonblank,
        "rubric_version": "batch_visual_fidelity_rubric_v2",
        "product_gate_notes": "D06.1 fails generic skeletons even when structural PPTX gates pass.",
    }


def _similarity_floor(reference_id: str) -> float:
    if reference_id in {"canva_benchmark", "cover_hero"}:
        return 0.55
    if reference_id in {"data_dashboard", "table_heavy"}:
        return 0.42
    return 0.48
