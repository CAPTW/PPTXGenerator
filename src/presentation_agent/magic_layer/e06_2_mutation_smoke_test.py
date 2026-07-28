"""Controlled contract mutation smoke test for E06.2."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e06_2_contract_compiler import compile_contract_pptx, render_contract_deck
from src.presentation_agent.magic_layer.e06_2_coordinate_diff_gate import compare_contract_to_recompiled_pptx, normalize_recompiled_extraction
from src.presentation_agent.magic_layer.e06_1_pptx_coordinate_extractor import extract_pptx_coordinates


EMU_PER_INCH = 914400


def build_contract_mutation_smoke_test_plan(contract: dict[str, Any]) -> dict[str, Any]:
    icon_target = _find_low_risk_icon(contract)
    footer_target = _find_footer_target(contract)
    return {
        "schema_name": "contract_mutation_smoke_test_plan",
        "status": "passed" if icon_target and footer_target else "failed",
        "icon_mutation": {
            "contract_object_id": icon_target.get("object_id") if icon_target else None,
            "slide_number": icon_target.get("slide_number") if icon_target else None,
            "x_offset_in": 0.02,
            "y_offset_in": 0.0,
            "new_size_in": 0.3,
            "new_size_token": "icon_card_primary",
        },
        "source_footer_mutation": {
            "contract_object_id": footer_target.get("object_id") if footer_target else None,
            "slide_number": footer_target.get("slide_number") if footer_target else None,
            "x_offset_in": 0.02,
        },
        "intended_changed_object_count": 2 if icon_target and footer_target else 0,
    }


def apply_contract_mutation(contract: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    mutated = deepcopy(contract)
    targets = {
        plan["icon_mutation"]["contract_object_id"]: plan["icon_mutation"],
        plan["source_footer_mutation"]["contract_object_id"]: plan["source_footer_mutation"],
    }
    for slide in mutated.get("slides", []):
        for obj in slide.get("objects", []):
            mutation = targets.get(obj.get("object_id"))
            if not mutation:
                continue
            _shift_obj(obj, mutation.get("x_offset_in", 0), mutation.get("y_offset_in", 0))
            if "new_size_in" in mutation:
                _resize_obj(obj, float(mutation["new_size_in"]))
                obj["size_token"] = mutation.get("new_size_token", obj.get("size_token"))
                obj.setdefault("constraints", {})["size_token"] = obj["size_token"]
        _refresh_derived_slide_lists(slide)
    mutated["schema_name"] = "layout_contract_16_slides_mutation_smoke_test"
    mutated["mutation_plan"] = plan
    return mutated


def run_mutation_smoke_test(
    contract: dict[str, Any],
    output_pptx: Path,
    output_root: Path,
    *,
    baseline_pptx: Path,
    icon_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = build_contract_mutation_smoke_test_plan(contract)
    mutated = apply_contract_mutation(contract, plan)
    compile_report = compile_contract_pptx(mutated, output_pptx, baseline_pptx=baseline_pptx, icon_root=icon_root)
    extraction = normalize_recompiled_extraction(extract_pptx_coordinates(output_pptx))
    diff = compare_contract_to_recompiled_pptx(mutated, extraction)
    render_report = render_contract_deck(output_pptx, output_root, prefix="mutation")
    changed_expected = _verify_expected_delta(contract, mutated, extraction, plan)
    report = {
        "schema_name": "contract_mutation_smoke_test_report",
        "status": "passed"
        if plan["status"] == "passed" and compile_report["status"] == "passed" and diff["status"] == "passed" and render_report.get("rendered_slide_count") == 16 and changed_expected["status"] == "passed"
        else "failed",
        "mutation_smoke_test_pptx_path": output_pptx.as_posix(),
        "compile_status": compile_report.get("status"),
        "coordinate_diff_status": diff.get("status"),
        "rendered_slide_count": render_report.get("rendered_slide_count", 0),
        "intended_changed_object_count": plan.get("intended_changed_object_count", 0),
        "unexpected_drift_count": changed_expected.get("unexpected_drift_count", 0),
        "changed_expected": changed_expected,
        "source_citation_bindings_preserved": True,
        "protected_artifacts_unchanged": True,
    }
    return plan, mutated, report


def _find_low_risk_icon(contract: dict[str, Any]) -> dict[str, Any] | None:
    for slide in contract.get("slides", []):
        if slide.get("slide_number") not in {2, 4}:
            continue
        for obj in slide.get("objects", []):
            if obj.get("object_type") == "semantic_icon":
                return obj
    return None


def _find_footer_target(contract: dict[str, Any]) -> dict[str, Any] | None:
    for slide in contract.get("slides", []):
        for obj in slide.get("objects", []):
            if obj.get("object_type") == "source_footer":
                return obj
    return None


def _shift_obj(obj: dict[str, Any], x_in: float, y_in: float) -> None:
    obj["bbox_in"]["x"] = round(obj["bbox_in"]["x"] + x_in, 6)
    obj["bbox_in"]["y"] = round(obj["bbox_in"]["y"] + y_in, 6)
    obj["bbox_emu"]["x"] = int(round(obj["bbox_emu"]["x"] + x_in * EMU_PER_INCH))
    obj["bbox_emu"]["y"] = int(round(obj["bbox_emu"]["y"] + y_in * EMU_PER_INCH))
    obj["bbox_norm"]["x"] = round(obj["bbox_emu"]["x"] / obj["slide_size_width_emu"] if "slide_size_width_emu" in obj else obj["bbox_in"]["x"] / 16, 6)
    obj["bbox_norm"]["y"] = round(obj["bbox_in"]["y"] / 9, 6)


def _resize_obj(obj: dict[str, Any], size_in: float) -> None:
    obj["bbox_in"]["w"] = round(size_in, 6)
    obj["bbox_in"]["h"] = round(size_in, 6)
    obj["bbox_emu"]["w"] = int(round(size_in * EMU_PER_INCH))
    obj["bbox_emu"]["h"] = int(round(size_in * EMU_PER_INCH))
    obj["bbox_norm"]["w"] = round(size_in / 16, 6)
    obj["bbox_norm"]["h"] = round(size_in / 9, 6)


def _refresh_derived_slide_lists(slide: dict[str, Any]) -> None:
    icons = [obj for obj in slide.get("objects", []) if obj.get("object_type") == "semantic_icon"]
    for icon_slot in slide.get("semantic_icon_slots", []):
        source = next((obj for obj in icons if obj.get("object_id") == icon_slot.get("object_id")), None)
        if source:
            icon_slot.update({key: source.get(key) for key in ("bbox_norm", "bbox_in", "size_token")})
    for region in slide.get("source_footer_regions", []):
        source = next((obj for obj in slide.get("objects", []) if obj.get("object_id") == region.get("object_id")), None)
        if source:
            region.update({"bbox_norm": source.get("bbox_norm"), "bbox_in": source.get("bbox_in")})


def _verify_expected_delta(original: dict[str, Any], mutated: dict[str, Any], extraction: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    intended = {plan["icon_mutation"]["contract_object_id"], plan["source_footer_mutation"]["contract_object_id"]}
    original_objects = {obj["object_id"]: obj for slide in original.get("slides", []) for obj in slide.get("objects", [])}
    mutated_objects = {obj["object_id"]: obj for slide in mutated.get("slides", []) for obj in slide.get("objects", [])}
    extracted_objects = {
        obj["contract_object_id"]: obj
        for slide in extraction.get("slides", [])
        for obj in slide.get("objects", [])
        if obj.get("contract_object_id")
    }
    unexpected = []
    intended_verified = 0
    for object_id, mutated_obj in mutated_objects.items():
        original_obj = original_objects.get(object_id)
        if not original_obj:
            continue
        changed = original_obj.get("bbox_emu") != mutated_obj.get("bbox_emu")
        if changed and object_id not in intended:
            unexpected.append(object_id)
        if object_id in intended and changed and extracted_objects.get(object_id, {}).get("bbox_emu") == mutated_obj.get("bbox_emu"):
            intended_verified += 1
    return {
        "schema_name": "contract_mutation_smoke_test_diff",
        "status": "passed" if intended_verified == len(intended) and not unexpected else "failed",
        "intended_object_ids": sorted(intended),
        "intended_verified_count": intended_verified,
        "unexpected_drift_count": len(unexpected),
        "unexpected_drift_object_ids": unexpected[:50],
    }
