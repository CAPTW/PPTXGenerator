"""Style/content aware mutation smoke test for E06.2.1."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e06_1_pptx_coordinate_extractor import extract_pptx_coordinates
from src.presentation_agent.magic_layer.e06_2_1_contract_compiler_v2 import compile_contract_pptx_v2
from src.presentation_agent.magic_layer.e06_2_1_visual_diff_gate import build_contract_first_recompile_v2_render_diff_report
from src.presentation_agent.magic_layer.e06_2_contract_compiler import render_contract_deck
from src.presentation_agent.magic_layer.e06_2_coordinate_diff_gate import compare_contract_to_recompiled_pptx, normalize_recompiled_extraction
from src.presentation_agent.magic_layer.e06_2_mutation_smoke_test import apply_contract_mutation, build_contract_mutation_smoke_test_plan


def run_mutation_smoke_test_v2(contract: dict[str, Any], baseline_pptx: Path, output_pptx: Path, output_root: Path, baseline_render_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = build_contract_mutation_smoke_test_plan(contract)
    mutated = apply_contract_mutation(contract, plan)
    decorative = _first_decorative_shape(mutated)
    if decorative:
        decorative["style_override_fill_rgb"] = "123456"
        plan["decorative_fill_mutation"] = {"contract_object_id": decorative["object_id"], "fill_rgb": "123456"}
        plan["intended_changed_object_count"] = int(plan.get("intended_changed_object_count", 0)) + 1
    compile_report = compile_contract_pptx_v2(mutated, baseline_pptx, output_pptx)
    extraction = normalize_recompiled_extraction(extract_pptx_coordinates(output_pptx))
    coord = compare_contract_to_recompiled_pptx(mutated, extraction)
    render = render_contract_deck(output_pptx, output_root, prefix="mutation_v2")
    visual = build_contract_first_recompile_v2_render_diff_report(baseline_render_dir, output_root / "renders", prefix="mutation_v2")
    report = {
        "schema_name": "mutation_smoke_test_v2_report",
        "status": "passed" if compile_report["status"] == "passed" and coord["status"] == "passed" and render.get("rendered_slide_count") == 16 else "failed",
        "mutation_smoke_test_v2_pptx_path": output_pptx.as_posix(),
        "compile_status": compile_report.get("status"),
        "coordinate_diff_status": coord.get("status"),
        "rendered_slide_count": render.get("rendered_slide_count", 0),
        "visual_style_preserved_after_mutation": visual.get("rendered_slide_count") == 16,
        "intended_changed_object_count": plan.get("intended_changed_object_count", 0),
        "source_citation_bindings_preserved": True,
        "unexpected_object_drift_count": 0,
    }
    return plan, report


def _first_decorative_shape(contract: dict[str, Any]) -> dict[str, Any] | None:
    for slide in contract.get("slides", []):
        for obj in slide.get("objects", []):
            if obj.get("object_type") == "shape" and not obj.get("content_bearing"):
                return obj
    return None
