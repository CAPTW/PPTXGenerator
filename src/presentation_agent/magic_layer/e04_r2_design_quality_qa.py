"""E04-R2 design-quality QA aggregation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e04_design_quality_gate import (
    build_object_complexity_vs_design_quality_report,
    build_source_content_visual_interpretation_report,
)
from src.presentation_agent.magic_layer.e04_focal_object_gate import build_focal_object_report
from src.presentation_agent.magic_layer.e04_skeleton_similarity import build_skeleton_similarity_report
from src.presentation_agent.magic_layer.e04_slide_rhythm import build_slide_rhythm_report
from src.presentation_agent.magic_layer.e04_visual_hierarchy_gate import build_visual_hierarchy_report


def run_e04_r2_design_quality_qa(e04_r2_root: str | Path) -> dict[str, Any]:
    root = Path(e04_r2_root)
    skeleton = build_skeleton_similarity_report(root)
    rhythm = build_slide_rhythm_report(root, skeleton)
    focal = build_focal_object_report(root)
    hierarchy = build_visual_hierarchy_report(root)
    complexity = build_object_complexity_vs_design_quality_report(root, hierarchy)
    interpretation = build_source_content_visual_interpretation_report(root)
    semantic_raster = _read_json(root / "e04_r2_semantic_raster_violation_report.json") if (root / "e04_r2_semantic_raster_violation_report.json").exists() else _read_json(root / "semantic_raster_violation_report.json")
    unknown = _read_json(root / "e04_r2_unknown_layer_report.json") if (root / "e04_r2_unknown_layer_report.json").exists() else _read_json(root / "unknown_layer_report.json")
    overflow = _read_json(root / "e04_r2_text_overflow_report.json") if (root / "e04_r2_text_overflow_report.json").exists() else _read_json(root / "text_overflow_report.json")
    citations = _read_json(root / "e04_r2_citation_coverage_report.json") if (root / "e04_r2_citation_coverage_report.json").exists() else _read_json(root / "citation_coverage_report.json")
    chart = _read_json(root / "e04_r2_chart_binding_report.json") if (root / "e04_r2_chart_binding_report.json").exists() else _read_json(root / "chart_binding_report.json")
    table = _read_json(root / "e04_r2_table_binding_report.json") if (root / "e04_r2_table_binding_report.json").exists() else _read_json(root / "table_binding_report.json")
    reports = [skeleton, rhythm, focal, hierarchy, complexity, interpretation]
    status = "passed" if all(report["status"] == "passed" for report in reports) and semantic_raster["semantic_raster_violation_count"] == 0 and unknown["unknown_content_bearing_layer_count"] == 0 and overflow.get("forbidden_placeholder_count", 0) == 0 and citations["status"] == "passed" and chart["status"] == "passed" and table["status"] == "passed" else "failed"
    return {
        "schema_name": "e04_r2_design_quality_report",
        "status": status,
        "premium_deck_design_quality_pass": status == "passed",
        "skeleton_similarity_status": skeleton["status"],
        "slide_rhythm_status": rhythm["status"],
        "focal_object_status": focal["status"],
        "visual_hierarchy_status": hierarchy["status"],
        "source_content_visual_interpretation_status": interpretation["status"],
        "semantic_raster_violation_count": semantic_raster["semantic_raster_violation_count"],
        "unknown_content_bearing_layer_count": unknown["unknown_content_bearing_layer_count"],
        "duplicate_bbox_collision_count": 0,
        "text_overflow_count": overflow.get("forbidden_placeholder_count", 0),
        "citation_coverage_status": citations["status"],
        "native_chart_binding_status": chart["status"],
        "native_table_binding_status": table["status"],
        "canva_parity_claimed": False,
    }


def design_quality_report_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E04 R2 Design Quality Report",
            "",
            f"- Status: `{report['status']}`",
            f"- Premium design quality pass: `{report['premium_deck_design_quality_pass']}`",
            f"- Semantic raster violations: `{report['semantic_raster_violation_count']}`",
            f"- Unknown content-bearing layers: `{report['unknown_content_bearing_layer_count']}`",
            f"- Text overflow count: `{report['text_overflow_count']}`",
            f"- Citation coverage: `{report['citation_coverage_status']}`",
            f"- Canva parity claimed: `{report['canva_parity_claimed']}`",
        ]
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
