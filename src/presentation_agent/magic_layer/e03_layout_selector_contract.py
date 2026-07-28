"""E03 layout selector and local-model slot filling contracts."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e03_archetype_registry import CORE_12_ARCHETYPE_IDS


def build_layout_selector_contract() -> dict[str, Any]:
    return {
        "schema_name": "e03_layout_selector_contract",
        "archetypes": {archetype_id: _selector_entry(archetype_id) for archetype_id in CORE_12_ARCHETYPE_IDS},
        "canva_parity_claimed": False,
    }


def validate_layout_selector_contract(contract: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(set(CORE_12_ARCHETYPE_IDS) - set(contract.get("archetypes", {})))
    failures = []
    for archetype_id, entry in contract.get("archetypes", {}).items():
        for field in ("when_to_use", "required_slide_blueprint_fields", "compatible_content_density", "incompatible_content_cases", "fallback_archetype", "slot_binding_rules", "overflow_policy", "required_source_refs", "chart_table_data_requirements"):
            if field not in entry:
                failures.append(f"{archetype_id}_missing_{field}")
    return {"schema_name": "e03_layout_selector_contract_validation", "status": "passed" if not missing and not failures else "failed", "missing": missing, "failures": failures, "canva_parity_claimed": False}


def build_local_model_slot_filling_contract() -> dict[str, Any]:
    return {
        "schema_name": "e03_local_model_slot_filling_contract",
        "purpose": "Lower-performing local models choose and fill slots without changing design.",
        "rules": {
            "may_select_archetype": True,
            "may_fill_text_slots": True,
            "may_bind_table_chart_data": True,
            "may_choose_image_asset_from_manifest": True,
            "may_alter_design_tokens": False,
            "may_invent_layout_geometry": False,
            "may_rasterize_semantic_objects": False,
            "may_modify_ps_layer_protocol": False,
            "must_preserve_source_refs": True,
        },
        "canva_parity_claimed": False,
    }


def _selector_entry(archetype_id: str) -> dict[str, Any]:
    chart_table = {}
    if archetype_id == "data_dashboard":
        chart_table["primary_chart"] = "required"
    if archetype_id in {"table_heavy", "comparison_matrix"}:
        chart_table["table_region" if archetype_id == "table_heavy" else "comparison_matrix"] = "required"
    return {
        "when_to_use": f"Use {archetype_id} when the slide blueprint matches its narrative role.",
        "required_slide_blueprint_fields": ["title", "slots", "source_refs"],
        "compatible_content_density": "light_to_medium" if archetype_id not in {"table_heavy", "comparison_matrix"} else "medium_to_dense",
        "incompatible_content_cases": ["full_slide_screenshot", "semantic_raster_required"],
        "fallback_archetype": "standard_content" if archetype_id != "standard_content" else "card_grid",
        "slot_binding_rules": {"preserve_geometry": True, "bind_by_semantic_role": True},
        "overflow_policy": "request_smaller_copy_or_select_denser_archetype",
        "required_source_refs": ["source_refs"],
        "chart_table_data_requirements": chart_table,
    }
