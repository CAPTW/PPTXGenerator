"""Semantic icon inventory for E03H-P2 SVG provenance rebinding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e03h_reference_registry import CORE_REFERENCE_IDS


REFERENCE_ICON_INTENTS: dict[str, list[str]] = {
    "maritime_checklist_hero": [
        "checklist_plan_prepare",
        "checklist_set_up_secure",
        "checklist_execute_monitor",
        "checklist_verify_confirm",
        "checklist_complete_record",
        "safety_wear_ppe",
        "safety_zero_leak_zero_spill",
        "safety_respect_chemical_barrier",
        "safety_communicate_confirm",
        "safety_teamwork",
    ],
    "process_workflow_infographic": ["process_intake", "process_triage", "process_build", "process_review", "process_handoff", "generic_arrow"],
    "data_dashboard_hybrid": ["dashboard_kpi_readiness", "dashboard_kpi_risk", "generic_check"],
    "table_matrix_hybrid": ["table_matrix_header_marker", "generic_check"],
    "cover_hero_photo_editorial": ["generic_arrow", "evidence_marker"],
    "standard_content_card_cluster": ["evidence_marker", "generic_check"],
    "evidence_stack_visual": ["evidence_marker", "generic_check"],
    "comparison_matrix_hybrid": ["table_matrix_header_marker", "generic_check"],
    "methodology_framework_layered": ["process_intake", "process_build", "process_review"],
    "timeline_roadmap_hybrid": ["roadmap_milestone", "generic_arrow"],
    "visual_toc_navigation": ["toc_current_marker", "generic_chevron"],
    "photo_caption_grid_hybrid": ["evidence_marker", "generic_check"],
}


def build_e03h_p2_semantic_icon_rebinding_inventory(e03h_p_root: str | Path) -> dict[str, Any]:
    root = Path(e03h_p_root)
    references: dict[str, list[dict[str, Any]]] = {}
    required_count = 0
    patch_required = 0
    for reference_id in CORE_REFERENCE_IDS:
        ref_dir = root / "references" / reference_id
        current_has_provenance = _candidate_has_svg_provenance(ref_dir / "editable_candidate.pptx")
        icon_report = _read_json(ref_dir / "semantic_icon_inventory_report.json")
        rows = []
        for index, intent in enumerate(REFERENCE_ICON_INTENTS.get(reference_id, ["generic_check"]), start=1):
            role = _role_for_intent(intent)
            is_patch_required = not current_has_provenance
            rows.append(
                {
                    "reference_id": reference_id,
                    "slide_object_id": f"{reference_id}::sem_icon::{index:02d}",
                    "semantic_role": role,
                    "semantic_intent": intent,
                    "classification": "required_semantic_icon",
                    "current_rendering_mode": "native_or_procedural_vector",
                    "current_has_source_svg_provenance": current_has_provenance,
                    "current_source_svg_asset_id": None,
                    "current_is_empty_circle": False,
                    "current_is_procedural_without_svg_source": not current_has_provenance,
                    "current_is_raster": False,
                    "patch_required": is_patch_required,
                    "source_report_status": icon_report.get("status", "unknown"),
                }
            )
            required_count += 1
            patch_required += 1 if is_patch_required else 0
        references[reference_id] = rows
    return {
        "schema_name": "semantic_icon_rebinding_inventory",
        "status": "passed" if len(references) == 12 and required_count > 0 else "failed",
        "core_reference_count": len(references),
        "required_semantic_icon_count": required_count,
        "optional_semantic_icon_count": 0,
        "patch_required_count": patch_required,
        "references": references,
        "canva_parity_claimed": False,
    }


def _candidate_has_svg_provenance(pptx_path: Path) -> bool:
    if not pptx_path.exists():
        return False
    try:
        from src.presentation_agent.magic_layer.svg_packaging_inspector import inspect_svg_pptx_package

        inventory = inspect_svg_pptx_package(pptx_path)
        return inventory.get("semantic_icon_with_source_svg_provenance_count", 0) > 0
    except Exception:
        return False


def _role_for_intent(intent: str) -> str:
    if intent.startswith("checklist"):
        return "checklist_step_icon"
    if intent.startswith("safety"):
        return "safety_bar_icon"
    if intent.startswith("process"):
        return "connector_or_process_marker"
    if intent.startswith("dashboard"):
        return "chart_marker"
    if "table" in intent:
        return "table_marker"
    if "toc" in intent:
        return "toc_marker"
    if "roadmap" in intent:
        return "roadmap_marker"
    if "evidence" in intent:
        return "evidence_marker"
    return "semantic_icon"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
