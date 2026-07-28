from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .real_reference_report import ROOT, file_profile, image_dimensions, read_json, sha256_file, write_json


FIXTURE_ID = "e01b_single_reference_pass"
FIXTURE_PATH = ROOT / "design_runs/run_003/fixtures/e01b_single_reference_pass"

REFERENCE = "input/reference_image.png"
HISTORICAL_PROOF = [
    "editable_candidate_e01b.pptx",
    "e01_gate_recheck_after_e01b.json",
    "canva_plus_gate_report_e01b.json",
    "pptx_semantic_editability_ledger_e01b.json",
    "semantic_raster_violation_report_e01b.json",
]
LEGACY_PROTOCOL_SET_A = {
    "object_graph": ["patched_object_graph_v1.json", "object_graph_v1.json"],
    "layer_manifest": ["patched_layer_manifest_v5.json", "layer_manifest_v5.json"],
    "semantic_slot_graph": ["patched_semantic_slot_graph.json", "semantic_slot_graph.json"],
    "native_reconstruction_plan": ["patched_native_reconstruction_plan.json", "native_reconstruction_plan.json"],
}


def real_reference_input_contract() -> dict[str, Any]:
    return {
        "schema": "real_reference_input_contract.v1",
        "fixture_id": FIXTURE_ID,
        "allowed_fixture_path": str(FIXTURE_PATH),
        "core_reference_required": [REFERENCE],
        "core_historical_proof_required": HISTORICAL_PROOF,
        "core_pipeline_input_required": {
            "set_a_preferred": LEGACY_PROTOCOL_SET_A,
            "set_b_acceptable_with_limitations": [
                "historical editable_candidate_spec / patched_editable_candidate_spec",
                "C04 B03 ledger data",
                "deterministic structural mapping only",
            ],
            "set_c_insufficient": ["PPTX + render + reports only"],
        },
        "rules": {
            "do_not_ocr_reference": True,
            "do_not_create_protocol_from_image_alone": True,
            "do_not_use_c02_p03_minimal_sample_as_substitute": True,
            "product_pass": False,
        },
    }


def inventory_fixture(fixture_path: str | Path = FIXTURE_PATH) -> dict[str, Any]:
    fixture = Path(fixture_path)
    expected = [REFERENCE, *HISTORICAL_PROOF, "rendered_candidate_e01b.png", "fixture_manifest.json"]
    for candidates in LEGACY_PROTOCOL_SET_A.values():
        expected.extend(candidates)
    files = []
    for rel in sorted(set(expected)):
        profile = file_profile(fixture / rel)
        profile["relative_path"] = rel
        profile["role"] = _role_for(rel)
        if rel.endswith(".png"):
            profile.update(image_dimensions(fixture / rel))
        files.append(profile)
    protocol_availability = {
        key: _first_existing(fixture, candidates)
        for key, candidates in LEGACY_PROTOCOL_SET_A.items()
    }
    reference = fixture / REFERENCE
    historical_pptx = fixture / "editable_candidate_e01b.pptx"
    historical_render = fixture / "rendered_candidate_e01b.png"
    return {
        "schema": "e01b_real_reference_fixture_inventory.v1",
        "fixture_id": FIXTURE_ID,
        "fixture_path": str(fixture),
        "fixture_exists": fixture.is_dir(),
        "selected_reference": str(reference),
        "reference_exists": reference.is_file(),
        "reference_sha256": sha256_file(reference),
        "reference_dimensions": image_dimensions(reference),
        "historical_pptx_hash": sha256_file(historical_pptx),
        "historical_render_hash": sha256_file(historical_render),
        "files": files,
        "protocol_artifact_availability": {
            key: str(path) if path else None for key, path in protocol_availability.items()
        },
        "planning_artifact_availability": {
            "editable_candidate_spec": str(_first_existing(fixture, ["patched_editable_candidate_spec.json", "editable_candidate_spec.json"]) or ""),
            "native_reconstruction_plan": str(protocol_availability["native_reconstruction_plan"] or ""),
        },
        "b03_validation_available": (fixture / "c04_b03_revalidation/e01b_repaired_b03_validation_report.json").is_file(),
        "product_pass": False,
    }


def assess_readiness(inventory: dict[str, Any]) -> dict[str, Any]:
    fixture = Path(inventory.get("fixture_path", FIXTURE_PATH))
    missing_reference = not (fixture / REFERENCE).is_file()
    missing_historical = [rel for rel in HISTORICAL_PROOF if not (fixture / rel).is_file()]
    missing_protocol = [
        key for key, value in inventory.get("protocol_artifact_availability", {}).items() if not value
    ]
    semantic = read_json(fixture / "c04_b03_revalidation/e01b_repaired_pptx_semantic_editability_ledger.json")
    full = read_json(fixture / "c04_b03_revalidation/e01b_repaired_pptx_full_slide_raster_check.json")
    full_count = int(full.get("full_slide_raster_count", 0) or 0)
    semantic_count = int(semantic.get("semantic_raster_violation_count", 0) or 0)
    unknown_count = int(semantic.get("unknown_content_bearing_count", 0) or 0)
    blockers: list[str] = []
    warnings: list[str] = []
    if missing_reference:
        blockers.append("reference image is missing")
    if missing_historical:
        blockers.append("historical proof files are missing: " + ", ".join(missing_historical))
    if missing_protocol:
        blockers.append("protocol/planning files are missing: " + ", ".join(missing_protocol))
    if full_count or semantic_count or unknown_count:
        blockers.append("C04 B03 validation counts are not clean")
    warnings.append("legacy E01B protocol artifacts require structural normalization")
    warnings.append("minimal OOXML backend emits editable text objects only")
    if blockers:
        if missing_reference:
            decision = "BLOCKED_MISSING_REFERENCE_IMAGE"
        elif missing_historical:
            decision = "BLOCKED_MISSING_HISTORICAL_PROOF"
        elif missing_protocol:
            decision = "BLOCKED_MISSING_PROTOCOL_INPUTS"
        else:
            decision = "BLOCKED_INVALID_E01B_FIXTURE"
    else:
        decision = "REAL_REFERENCE_READY_WITH_LEGACY_LIMITATIONS"
    return {
        "schema": "e01b_real_reference_input_readiness_report.v1",
        "fixture_id": FIXTURE_ID,
        "readiness_decision": decision,
        "ready": decision in {"REAL_REFERENCE_READY_FOR_P04_PIPELINE", "REAL_REFERENCE_READY_WITH_LEGACY_LIMITATIONS"},
        "missing_reference": missing_reference,
        "missing_historical_proof": missing_historical,
        "missing_protocol_inputs": missing_protocol,
        "full_slide_raster_count": full_count,
        "semantic_raster_violation_count": semantic_count,
        "unknown_content_bearing_count": unknown_count,
        "blockers": blockers,
        "warnings": warnings,
        "compile_eligibility_needs_validation": True,
        "product_pass": False,
    }


def build_p04_inputs(out_dir: str | Path, fixture_path: str | Path = FIXTURE_PATH) -> dict[str, Any]:
    out = Path(out_dir)
    fixture = Path(fixture_path)
    target = out / "p04_inputs"
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    copy_plan = {
        "reference_image.png": fixture / REFERENCE,
        "source_fixture_manifest.json": fixture / "fixture_manifest.json",
        "object_graph.json": _first_existing(fixture, LEGACY_PROTOCOL_SET_A["object_graph"]),
        "layer_manifest.json": _first_existing(fixture, LEGACY_PROTOCOL_SET_A["layer_manifest"]),
        "semantic_slot_graph.json": _first_existing(fixture, LEGACY_PROTOCOL_SET_A["semantic_slot_graph"]),
    }
    for name, source in copy_plan.items():
        if source and source.is_file():
            destination = target / name
            if not destination.exists():
                shutil.copy2(source, destination)
            copied.append({"source_path": str(source), "target_path": str(destination), "sha256": sha256_file(destination), "copied": True})
        else:
            copied.append({"source_path": str(source) if source else None, "target_path": str(target / name), "sha256": None, "copied": False})

    legacy_plan_path = _first_existing(fixture, LEGACY_PROTOCOL_SET_A["native_reconstruction_plan"])
    legacy_plan = read_json(legacy_plan_path) if legacy_plan_path else {}
    bundle, contract, slot_schema, native_plan, editable_spec, normalization = normalize_legacy_plan_to_bundle(legacy_plan)
    write_json(target / "template_contract.json", contract)
    write_json(target / "slot_schema.json", slot_schema)
    write_json(target / "native_reconstruction_plan.json", native_plan)
    write_json(target / "editable_candidate_spec.json", editable_spec)
    write_json(target / "compiler_input_bundle.json", bundle)
    (target / "README.md").write_text(
        "# P04 inputs\n\nRepaired E01B single-reference fixture inputs copied or structurally normalized for one controlled P04 run. These files are not product evidence.\n",
        encoding="utf-8",
    )
    for generated in ["template_contract.json", "slot_schema.json", "native_reconstruction_plan.json", "editable_candidate_spec.json", "compiler_input_bundle.json"]:
        copied.append({"source_path": str(legacy_plan_path), "target_path": str(target / generated), "sha256": sha256_file(target / generated), "copied": False, "generated_from_legacy_fixture": True})
    return {
        "schema": "p04_input_bundle_build.v1",
        "input_folder": str(target),
        "copied_or_normalized": copied,
        "normalization": normalization,
        "compiler_input_bundle_path": str(target / "compiler_input_bundle.json"),
        "editable_text_object_count": len(editable_spec["objects"]),
        "product_pass": False,
    }


def normalize_legacy_plan_to_bundle(legacy_plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    text_objects: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    legacy_objects = legacy_plan.get("objects", [])
    for obj in legacy_objects if isinstance(legacy_objects, list) else []:
        if not isinstance(obj, dict) or obj.get("pptx_object_type") != "text_box":
            continue
        text = obj.get("text_content")
        bbox = _legacy_bbox_to_xywh(obj.get("geometry", {}).get("bbox_norm"))
        if not text or bbox is None:
            skipped.append({"object_id": obj.get("object_id"), "reason": "missing text or invalid bbox"})
            continue
        slot_id = "SLOT_TITLE" if obj.get("object_id") == "OBJ_CHECK_TITLE" else str(obj.get("object_id"))
        role = "title" if slot_id == "SLOT_TITLE" else str(obj.get("semantic_role") or "body")
        text_objects.append(
            {
                "instruction_id": f"instr_{slot_id.lower()}",
                "object_id": str(obj.get("object_id")),
                "object_name": slot_id,
                "slot_id": slot_id,
                "pptx_object_type": "text_box",
                "semantic_role": role,
                "editable_required": True,
                "raster_allowed": False,
                "geometry": {"bbox_norm": bbox, "geometry_source": "legacy_e01b_bbox_xyxy_normalized_to_xywh"},
                "style": {"font_color": obj.get("style", {}).get("font_color", "white_or_cyan")},
                "text": {"content": str(text)},
                "targetability": {"selectable": True, "text_editable": True, "style_editable": True, "independently_editable": True},
                "validation_checks": ["editable_text", "overflow_policy_attached"],
                "review_hook_ids": ["text_overflow_review"],
                "patch_hook_ids": ["PATCH_TEXT_OVERFLOW"],
                "overflow_policy_id": f"ov_{slot_id.lower()}",
                "z_order": int(obj.get("z_order", 0) or 0),
                "provenance": {"source": "repaired_e01b_legacy_native_plan", "semantic_invention": False},
            }
        )
    text_objects.sort(key=lambda item: item["z_order"])
    slots = [_slot_from_object(obj, required=True) for obj in text_objects]
    contract = _template_contract([slot["slot_id"] for slot in slots])
    slot_schema = {
        "schema": "slot_schema.v1",
        "schema_id": "p04_e01b_real_reference_slot_schema",
        "template_id": "p04_e01b_single_reference_template",
        "archetype_id": "cover_hero",
        "slots": slots,
        "product_pass": False,
    }
    native_plan = {
        "schema": "native_reconstruction_plan.v1",
        "plan_id": "p04_e01b_real_reference_native_plan",
        "template_id": "p04_e01b_single_reference_template",
        "archetype_id": "cover_hero",
        "reconstruction_objects": [_reconstruction_from_object(obj) for obj in text_objects],
        "legacy_source_schema": legacy_plan.get("schema_name"),
        "generated_from_legacy_fixture": True,
        "semantic_invention": False,
        "product_pass": False,
    }
    editable_spec = {
        "schema": "editable_candidate_spec.v1",
        "spec_id": "p04_e01b_real_reference_editable_candidate_spec",
        "template_id": "p04_e01b_single_reference_template",
        "archetype_id": "cover_hero",
        "canvas": {"ratio": "16:9", "slide_width_in": 13.333, "slide_height_in": 7.5},
        "pptx_setup": {"ratio": "16:9", "slide_width_in": 13.333, "slide_height_in": 7.5},
        "objects": text_objects,
        "slots": slots,
        "groups": [],
        "media_assets": [],
        "style_tokens": {},
        "theme_tokens": {},
        "source_protocol_refs": {"object_graph": True, "layer_manifest": True, "semantic_slot_graph": True},
        "validation_requirements": ["E01P_protocol_gate", "T01_contract_gate", "B03_native_validation_gate"],
        "limitations": ["legacy geometry normalized structurally", "minimal backend compiles text boxes only"],
        "product_pass": False,
        "provenance": {"source": "C04_repaired_E01B_fixture", "product_evidence": False, "semantic_invention": False},
    }
    bundle = {
        "schema": "compiler_input_bundle.v1",
        "bundle_id": "p04_e01b_real_reference_compiler_input_bundle",
        "template_id": "p04_e01b_single_reference_template",
        "archetype_id": "cover_hero",
        "editable_candidate_spec_id": editable_spec["spec_id"],
        "editable_candidate_spec": editable_spec,
        "asset_manifest": [],
        "expected_outputs": [
            "p04_controlled_real_reference_candidate.pptx",
            "p04_b03_validation_report.json",
            "p04_rendered_slide.png",
        ],
        "forbidden_outputs": [
            "full_slide_raster",
            "screenshot_slide",
            "semantic_raster_fallback",
            "source_bound_deck",
            "template_pack",
            "canonical_artifact_overwrite",
        ],
        "downstream_gates": ["B03_native_validation_gate", "B01_render_review_optional"],
        "created_pptx": False,
        "sample_only": True,
        "product_evidence": False,
        "product_pass": False,
        "limitations": ["real reference single-sample only", "legacy protocol normalization", "text-only minimal backend"],
        "validation_contract": {"protected_artifact_guard_required": True, "no_canonical_promotion": True},
    }
    normalization = {
        "schema": "p04_legacy_normalization.v1",
        "legacy_object_count": len(legacy_objects) if isinstance(legacy_objects, list) else 0,
        "compiled_text_object_count": len(text_objects),
        "skipped_text_objects": skipped,
        "semantic_invention": False,
        "limitations": ["non-text visual fields are not compiled by the minimal OOXML backend"],
    }
    return bundle, contract, slot_schema, native_plan, editable_spec, normalization


def _template_contract(slot_ids: list[str]) -> dict[str, Any]:
    editable_slots = ["SLOT_TITLE", *[slot for slot in slot_ids if slot != "SLOT_TITLE"]]
    return {
        "schema": "template_contract.v1",
        "contract_id": "p04_e01b_real_reference_template_contract",
        "template_id": "p04_e01b_single_reference_template",
        "archetype_id": "cover_hero",
        "template_name": "P04 E01B Single Reference Controlled Template",
        "intended_use": "controlled real-reference single-sample regression",
        "canvas": {"ratio": "16:9", "slide_width_in": 13.333, "slide_height_in": 7.5},
        "design_tokens": {},
        "fixed_style_elements": [],
        "editable_content_slots": editable_slots,
        "replaceable_visual_slots": [],
        "native_component_slots": [],
        "structural_shapes": [],
        "protected_zones": [],
        "optional_slots": [],
        "forbidden_slots": ["full_slide_raster", "screenshot_slide", "semantic_raster_fallback"],
        "slot_binding_rules": [{"slot_id": slot, "binding": "legacy_e01b_text_object"} for slot in editable_slots],
        "overflow_policy": {"required_for_text_slots": True, "policy": "heuristic_review_required"},
        "raster_policy": {"full_slide_raster_allowed": False, "semantic_raster_allowed": False},
        "native_component_policy": {"minimal_backend_text_only": True},
        "review_hooks": ["B01_review_packet", "text_overflow_review"],
        "patch_hooks": ["PATCH_TEXT_OVERFLOW"],
        "source_binding_preparation": {"source_bound_deck_generated": False, "source_binding_preparedness": False},
        "compile_eligibility": {"eligible": True, "canonical_promotion_allowed": False, "product_pass": False},
        "product_pass": False,
    }


def _slot_from_object(obj: dict[str, Any], *, required: bool) -> dict[str, Any]:
    return {
        "slot_id": obj["slot_id"],
        "slot_name": obj["object_name"],
        "slot_type": "text",
        "semantic_role": obj["semantic_role"],
        "bbox_norm": obj["geometry"]["bbox_norm"],
        "required": required,
        "editable": True,
        "native_target": "ppt_text_box",
        "pptx_object_name": obj["object_name"],
        "object_ids": [obj["object_id"]],
        "layer_ids": [],
        "overflow_policy_id": obj["overflow_policy_id"],
        "validation_rule_ids": ["editable_text"],
        "review_hook_ids": ["text_overflow_review"],
        "patch_hook_ids": ["PATCH_TEXT_OVERFLOW"],
    }


def _reconstruction_from_object(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "reconstruction_id": f"recon_{obj['slot_id'].lower()}",
        "object_id": obj["object_id"],
        "slot_id": obj["slot_id"],
        "semantic_role": obj["semantic_role"],
        "pptx_object_type": "text_box",
        "geometry": obj["geometry"],
        "text": obj["text"],
        "semantic_raster_allowed": False,
        "validation_checks": ["editable_text", "semantic_raster_forbidden", "bbox_within_slide"],
        "product_pass": False,
    }


def _legacy_bbox_to_xywh(value: Any) -> list[float] | None:
    if not (isinstance(value, list) and len(value) == 4):
        return None
    try:
        x1, y1, x2, y2 = [float(item) for item in value]
    except (TypeError, ValueError):
        return None
    width = x2 - x1
    height = y2 - y1
    if x1 < 0 or y1 < 0 or x2 > 1 or y2 > 1 or width <= 0 or height <= 0:
        return None
    return [round(x1, 6), round(y1, 6), round(width, 6), round(height, 6)]


def _first_existing(root: Path, candidates: list[str]) -> Path | None:
    for rel in candidates:
        path = root / rel
        if path.is_file():
            return path
    return None


def _role_for(rel: str) -> str:
    if rel == REFERENCE:
        return "reference_image"
    if rel.endswith(".pptx"):
        return "historical_pptx"
    if "object_graph" in rel:
        return "object_graph"
    if "layer_manifest" in rel:
        return "layer_manifest"
    if "semantic_slot" in rel:
        return "semantic_slot_graph"
    if "native_reconstruction" in rel:
        return "native_reconstruction_plan"
    if rel.endswith(".png"):
        return "historical_render_or_reference"
    return "historical_proof"
