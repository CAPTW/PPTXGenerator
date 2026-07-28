"""Compile and render E06.3 contract variants."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e06_2_1_contract_compiler_v2 import compile_contract_pptx_v2
from src.presentation_agent.magic_layer.e06_2_contract_compiler import render_contract_deck
from src.presentation_agent.magic_layer.e06_3_contact_sheets import build_grid_contact_sheet


def compile_and_render_contract_variants(
    variants: dict[str, dict[str, Any]],
    baseline_pptx: Path,
    output_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    compile_rows: list[dict[str, Any]] = []
    render_rows: list[dict[str, Any]] = []
    for variant_id, contract in variants.items():
        letter = variant_id.split("_")[-1]
        candidate_dir = output_root / "candidates" / variant_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        contract_path = candidate_dir / f"layout_contract_variant_{letter}.json"
        deck_path = candidate_dir / f"harness_v3_e06_3_variant_{letter}_contract_improved_candidate.pptx"
        shutil.copy2(output_root / f"layout_contract_variant_{letter}.json", contract_path)
        compile_report = compile_contract_pptx_v2(contract, baseline_pptx, deck_path)
        render_report = render_contract_deck(deck_path, output_root, prefix=variant_id)
        paths = [Path(p) for p in render_report.get("rendered_paths", [])]
        contact = candidate_dir / "rendered_contact_sheet.png"
        build_grid_contact_sheet(contact, paths, f"E06.3 {variant_id} rendered deck")
        compile_rows.append(
            {
                "variant_id": variant_id,
                "status": compile_report.get("status"),
                "pptx_path": deck_path.as_posix(),
                "objects_compiled_from_contract": compile_report.get("objects_compiled_from_contract", 0),
            }
        )
        render_rows.append(
            {
                "variant_id": variant_id,
                "status": render_report.get("status"),
                "rendered_slide_count": render_report.get("rendered_slide_count", 0),
                "contact_sheet_path": contact.as_posix(),
            }
        )
    compile_report = {
        "schema_name": "candidate_compile_report",
        "status": "passed" if all(row["status"] == "passed" for row in compile_rows) else "failed",
        "variant_count": len(compile_rows),
        "variants": compile_rows,
    }
    render_report = {
        "schema_name": "candidate_render_report",
        "status": "passed" if all(row["status"] == "passed" and row["rendered_slide_count"] == 16 for row in render_rows) else "failed",
        "variant_count": len(render_rows),
        "variants": render_rows,
        "total_rendered_slides": sum(int(row["rendered_slide_count"]) for row in render_rows),
    }
    return compile_report, render_report
