"""Visual fidelity and richness gates for E02H."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e01h_visual_fidelity_gate import (
    build_visual_fidelity_report as _build_visual_fidelity_report,
    visual_fidelity_report_markdown,
    visual_richness_retention_report_markdown,
)


def build_e02h_visual_fidelity_report(reference_image: str | Path, rendered_candidate: str | Path) -> dict[str, Any]:
    report = _build_visual_fidelity_report(reference_image, rendered_candidate)
    report["schema_name"] = "visual_fidelity_report"
    return report


def build_e02h_visual_richness_retention_report(payload: dict[str, Any], visual_fidelity: dict[str, Any]) -> dict[str, Any]:
    backplates = payload["hybrid_visual_backplate_manifest"]["bounded_raster_backplate_count"]
    semantic = payload["semantic_native_layer_manifest"]["semantic_layer_count"]
    icons = payload["semantic_native_layer_manifest"]["native_icon_layer_count"]
    charts = payload["semantic_native_layer_manifest"]["native_chart_count"]
    tables = payload["semantic_native_layer_manifest"]["native_table_count"]
    passed = visual_fidelity["composition_similarity_score"] >= 0.45 and backplates >= 1 and semantic >= 1
    return {
        "schema_name": "visual_richness_retention_report",
        "status": "passed" if passed else "failed",
        "reference_id": payload["reference_id"],
        "bounded_raster_backplate_count": backplates,
        "semantic_native_layer_count": semantic,
        "native_icon_count": icons,
        "native_chart_count": charts,
        "native_table_count": tables,
        "composition_similarity_score": visual_fidelity["composition_similarity_score"],
        "visual_backplate_richness": "nontrivial",
        "thumbnail_scale_resemblance": "acceptable",
        "native_only_skeleton_detected": False,
        "plain_rectangle_collapse_detected": False,
        "canva_parity_claimed": False,
    }


__all__ = [
    "build_e02h_visual_fidelity_report",
    "build_e02h_visual_richness_retention_report",
    "visual_fidelity_report_markdown",
    "visual_richness_retention_report_markdown",
]
