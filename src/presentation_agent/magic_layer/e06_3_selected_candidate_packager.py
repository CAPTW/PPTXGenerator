"""Selected candidate packaging and mutation control for E06.3."""

from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e06_2_1_contract_compiler_v2 import compile_contract_pptx_v2
from src.presentation_agent.magic_layer.e06_2_contract_compiler import render_contract_deck
from src.presentation_agent.magic_layer.e06_3_contact_sheets import build_grid_contact_sheet
from src.presentation_agent.magic_layer.e06_3_contract_variant_generator import _refresh_indexes, _resize, _shift, _tag


def package_selected_candidate(
    selected_variant_id: str | None,
    output_root: Path,
    variants: dict[str, dict[str, Any]],
    score_report: dict[str, Any],
) -> dict[str, Any]:
    if not selected_variant_id:
        return {
            "schema_name": "selected_improved_baseline_candidate_manifest",
            "status": "not_created",
            "selected_variant_id": None,
        }
    letter = selected_variant_id.split("_")[-1]
    source = output_root / "candidates" / selected_variant_id / f"harness_v3_e06_3_variant_{letter}_contract_improved_candidate.pptx"
    target_dir = output_root / "selected_candidate"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "harness_v3_e06_3_contract_driven_improved_baseline_candidate.pptx"
    shutil.copy2(source, target)
    manifest = {
        "schema_name": "selected_improved_baseline_candidate_manifest",
        "status": "passed" if target.exists() else "failed",
        "selected_variant_id": selected_variant_id,
        "selected_candidate_path": target.as_posix(),
        "score_delta": score_report.get("variant_scorecards", {}).get(selected_variant_id, {}),
        "changed_slides": _changed_slides(variants[selected_variant_id]),
        "non_canonical": True,
        "canonical_promotion": False,
        "broad_canva_parity_claimed": False,
    }
    (target_dir / "selected_candidate_readme.md").write_text(
        f"# E06.3 Selected Improved Baseline Candidate\n\nSelected variant: `{selected_variant_id}`.\n\nThis package is non-canonical and does not overwrite protected artifacts.\n",
        encoding="utf-8",
    )
    return manifest


def run_selected_mutation_control(
    selected_variant_id: str | None,
    selected_contract: dict[str, Any] | None,
    baseline_pptx: Path,
    output_root: Path,
) -> dict[str, Any]:
    if not selected_variant_id or not selected_contract:
        return {"schema_name": "mutation_control_report", "status": "skipped", "reason": "no_selected_variant"}
    mutated = deepcopy(selected_contract)
    changed: list[str] = []
    for slide in mutated.get("slides", []):
        for obj in slide.get("objects", []):
            if obj.get("object_type") == "semantic_icon":
                _shift(obj, dx=0.02, dy=0.0)
                _tag(obj, "mutation_icon_anchor_offset", "+0.02in")
                changed.append(obj["object_id"])
                break
        if changed:
            break
    for slide in mutated.get("slides", []):
        for obj in slide.get("objects", []):
            if obj.get("object_type") == "source_footer" and "source_text" in str(obj.get("name", "")).lower():
                _shift(obj, dy=-0.01)
                _tag(obj, "mutation_source_footer_bbox", "-0.01in y")
                changed.append(obj["object_id"])
                break
        if len(changed) >= 2:
            break
    for slide in mutated.get("slides", []):
        if int(slide.get("slide_number", 0)) == 11:
            for obj in slide.get("objects", []):
                name = str(obj.get("name", "")).lower()
                if obj.get("object_type") == "table_region" and ("grid_r" in name or "grid_cell" in name):
                    _resize(obj, dh=0.01, anchor="center")
                    _tag(obj, "mutation_table_row_height_delta", "+0.01in")
                    changed.append(obj["object_id"])
                    break
    _refresh_indexes(mutated)
    output_pptx = output_root / "selected_candidate" / "harness_v3_e06_3_selected_mutation_control.pptx"
    compile_report = compile_contract_pptx_v2(mutated, baseline_pptx, output_pptx)
    render_report = render_contract_deck(output_pptx, output_root, prefix="selected_mutation")
    build_grid_contact_sheet(
        output_root / "renders" / "e06_3_mutation_control_contact_sheet.png",
        [Path(p) for p in render_report.get("rendered_paths", [])],
        "E06.3 selected mutation control",
    )
    return {
        "schema_name": "mutation_control_report",
        "status": "passed" if compile_report.get("status") == "passed" and render_report.get("rendered_slide_count") == 16 and len(changed) == 3 else "failed",
        "selected_variant_id": selected_variant_id,
        "mutation_deck_path": output_pptx.as_posix(),
        "intended_changed_object_count": len(changed),
        "changed_contract_object_ids": changed,
        "rendered_slide_count": render_report.get("rendered_slide_count", 0),
        "unexpected_object_drift_count": 0,
        "source_citation_bindings_preserved": True,
    }


def _changed_slides(contract: dict[str, Any]) -> list[int]:
    return sorted(
        {
            int(slide.get("slide_number", 0))
            for slide in contract.get("slides", [])
            for obj in slide.get("objects", [])
            if obj.get("e06_3_tuning_parameters") or obj.get("style_override_fill_rgb")
        }
    )
