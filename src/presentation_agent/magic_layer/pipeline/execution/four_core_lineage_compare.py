from __future__ import annotations

from pathlib import Path
from typing import Any

from .four_core_input import ARCHETYPES, ACTIVE_REFERENCE_ROOT, HISTORICAL_ROOT, REFERENCE_NAMES
from .four_core_report import read_json, sha256_file
from .four_core_scope_guard import PPTX_NAME, RENDER_NAME


P04_OUT = Path(__file__).resolve().parents[5] / "design_runs/run_003/outputs/p04_rx_controlled_real_reference_single_sample_pipeline_v2"


def compare_with_e02_historical(run_folder: str | Path) -> dict[str, Any]:
    run = Path(run_folder)
    rows: dict[str, dict[str, Any]] = {}
    statuses: list[str] = []
    for archetype in ARCHETYPES:
        folder = run / "archetypes" / archetype
        historical = HISTORICAL_ROOT / "archetypes" / archetype
        b03 = read_json(folder / "b03_validation_report.json")
        decision = read_json(folder / "archetype_decision.json")
        semantic = read_json(folder / "pptx_semantic_editability_ledger.json")
        full = read_json(folder / "pptx_full_slide_raster_check.json")
        policy = read_json(folder / "archetype_gate_report.json").get("chart_table_native_policy")
        status = "FOUR_CORE_PIPELINE_PASS_WITH_LIMITATIONS"
        if decision.get("decision") not in {"ARCHETYPE_P05_PASS", "ARCHETYPE_P05_PASS_WITH_LIMITATIONS"}:
            status = "FOUR_CORE_PIPELINE_PARTIAL"
        statuses.append(status)
        rows[archetype] = {
            "schema": "p05_archetype_compare_with_e02_historical.v1",
            "archetype": archetype,
            "status": status,
            "selected_reference_hash": sha256_file(ACTIVE_REFERENCE_ROOT / REFERENCE_NAMES[archetype]),
            "historical_pptx_hash": sha256_file(historical / "editable_reconstruction_candidate.pptx"),
            "historical_render_hash": sha256_file(historical / "rendered_reconstruction_candidate.png"),
            "p05_pptx_hash": sha256_file(folder / PPTX_NAME),
            "p05_render_hash": sha256_file(folder / RENDER_NAME),
            "historical_decision": read_json(historical / "archetype_decision.json").get("decision"),
            "p05_decision": decision.get("decision"),
            "p05_b03_status": b03.get("status"),
            "semantic_raster_violation_count": semantic.get("semantic_raster_violation_count"),
            "full_slide_raster_count": full.get("full_slide_raster_count"),
            "unknown_content_bearing_count": semantic.get("unknown_content_bearing_count"),
            "chart_table_status": policy,
            "visual_match_required": False,
            "product_pass": False,
        }
    overall = "FOUR_CORE_PIPELINE_PASS_WITH_LIMITATIONS" if all(status == "FOUR_CORE_PIPELINE_PASS_WITH_LIMITATIONS" for status in statuses) else "FOUR_CORE_PIPELINE_PARTIAL"
    return {
        "schema": "p05_compare_with_e02_historical_report.v1",
        "status": overall,
        "rows": rows,
        "product_pass": False,
        "limitations": ["P05 need not visually match historical E02 exactly", "historical E02 remains regression baseline"],
    }


def compare_with_p04_single_reference(run_folder: str | Path) -> dict[str, Any]:
    run = Path(run_folder)
    decisions = {
        archetype: read_json(run / "archetypes" / archetype / "archetype_decision.json").get("decision")
        for archetype in ARCHETYPES
    }
    return {
        "schema": "p05_compare_with_p04_single_reference_report.v1",
        "status": "FOUR_CORE_PIPELINE_PASS_WITH_LIMITATIONS" if all(value in {"ARCHETYPE_P05_PASS", "ARCHETYPE_P05_PASS_WITH_LIMITATIONS"} for value in decisions.values()) else "FOUR_CORE_PIPELINE_PARTIAL",
        "p04_scope": "single repaired E01B real-reference sample",
        "p05_scope": "four E02 core references",
        "p04_pptx_hash": sha256_file(P04_OUT / "p04_controlled_real_reference_candidate.pptx"),
        "p04_render_hash": sha256_file(P04_OUT / "p04_rendered_slide.png"),
        "p05_archetype_decisions": decisions,
        "new_complexity": ["data_dashboard chart policy", "table_heavy table policy"],
        "product_pass": False,
        "limitations": ["P05 is broader than P04 but still controlled regression only"],
    }
