from __future__ import annotations

from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.compiler.aggregate import assemble_pptx_review_pack

from .aggregate_scope_guard import ARCHETYPES, PACK_NAME


def aggregate_backend_selection_report() -> dict[str, Any]:
    return {
        "schema": "p06_aggregate_backend_selection_report.v1",
        "candidates": [
            {
                "backend": "powerpoint_com_insert_from_file",
                "safe": True,
                "preserves_editable_objects": True,
                "flattens_to_images": False,
                "writes_only_p06_output": True,
            },
            {
                "backend": "deterministic_ooxml_slide_package_merge",
                "safe": False,
                "reason": "not implemented for relationship merge in this repo",
            },
            {
                "backend": "raster_contact_sheet_pack",
                "safe": False,
                "reason": "would flatten slides to images",
            },
        ],
        "selected_backend": "powerpoint_com_insert_from_file",
        "reason": "local PowerPoint InsertFromFile can preserve editable slide objects without using render PNGs as content",
        "modifies_source_pptx": False,
        "product_pass": False,
    }


def aggregate_assembly_plan(p05_run: str | Path, out_dir: str | Path) -> dict[str, Any]:
    p05 = Path(p05_run)
    out = Path(out_dir)
    return {
        "schema": "p06_aggregate_assembly_plan.v1",
        "source_stage": "P05",
        "slide_order": ARCHETYPES,
        "source_pptx_paths": [str(p05 / "archetypes" / item / "controlled_candidate.pptx") for item in ARCHETYPES],
        "output_path": str(out / PACK_NAME),
        "uses_render_png_as_slide_content": False,
        "canonical_output": False,
        "product_pass": False,
    }


def assemble_aggregate_pack(p05_run: str | Path, out_dir: str | Path) -> dict[str, Any]:
    plan = aggregate_assembly_plan(p05_run, out_dir)
    return assemble_pptx_review_pack([Path(path) for path in plan["source_pptx_paths"]], Path(out_dir) / PACK_NAME)
