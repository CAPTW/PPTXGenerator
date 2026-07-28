from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .four_core_report import ROOT, file_profile, image_dimensions, read_json, sha256_file, write_json
from .four_core_scope_guard import ARCHETYPES


ACTIVE_REFERENCE_ROOT = ROOT / "design_runs/run_002/inputs/e02_rx/references"
FIXTURE_ROOT = ROOT / "design_runs/run_003/fixtures/e02_4core_pass"
HISTORICAL_ROOT = ROOT / "design_runs/run_002/outputs/magic_layer_engine_e02_rx_4core_template_reference_conversion_rerun_01"

REFERENCE_NAMES = {
    "cover_hero": "cover_hero.png",
    "standard_content": "standard_content.png",
    "data_dashboard": "data_dashboard.png",
    "table_heavy": "table_heavy.png",
}
REQUIRED_LEGACY = [
    "object_graph_v1.json",
    "layer_manifest_v5.json",
    "semantic_slot_graph.json",
    "template_contract.json",
    "slot_schema.json",
    "native_reconstruction_plan.json",
    "editable_reconstruction_spec.json",
]


def four_core_reference_contract() -> dict[str, Any]:
    return {
        "schema": "four_core_reference_input_contract.v1",
        "accepted_archetypes": ARCHETYPES,
        "allowed_reference_paths": {
            item: str(ACTIVE_REFERENCE_ROOT / REFERENCE_NAMES[item]) for item in ARCHETYPES
        },
        "allowed_fixture_fallback": str(FIXTURE_ROOT / "archetypes/{archetype}/input/reference_image.png"),
        "rules": {
            "reference_generation_allowed": False,
            "e03_references_allowed": False,
            "render_png_as_reference_allowed": False,
            "semantic_invention_allowed": False,
            "product_pass": False,
        },
        "hard_gates": {
            "data_dashboard": "chart region must be native_chart or editable_shape_chart; raster fallback fails",
            "table_heavy": "table region must be native_table or editable_shape_grid_table; raster fallback fails",
        },
    }


def select_four_core_references(
    *,
    active_reference_root: str | Path = ACTIVE_REFERENCE_ROOT,
    fixture_root: str | Path = FIXTURE_ROOT,
) -> dict[str, Any]:
    active = Path(active_reference_root)
    fixture = Path(fixture_root)
    rows: dict[str, dict[str, Any]] = {}
    for archetype in ARCHETYPES:
        active_path = active / REFERENCE_NAMES[archetype]
        fallback = fixture / "archetypes" / archetype / "input" / "reference_image.png"
        selected = active_path if active_path.is_file() else fallback
        profile = file_profile(selected)
        rows[archetype] = {
            "archetype": archetype,
            "selected_reference_path": str(selected),
            "exists": selected.is_file(),
            "sha256": profile["sha256"],
            "size_bytes": profile["size_bytes"],
            "dimensions": image_dimensions(selected),
            "active_input_or_fixture": "ACTIVE_INPUT" if selected == active_path and selected.is_file() else "FIXTURE_FALLBACK" if selected.is_file() else "MISSING",
            "provenance": "E02 active input reference" if selected == active_path and selected.is_file() else "E02 repaired fixture fallback" if selected.is_file() else "missing",
            "validation_status": "REFERENCE_SELECTED" if selected.is_file() else "BLOCKED_MISSING_REFERENCE",
            "product_pass": False,
        }
    return {
        "schema": "four_core_reference_selection_report.v1",
        "references": rows,
        "all_selected": all(item["exists"] for item in rows.values()),
        "product_pass": False,
    }


def inventory_four_core_fixtures(
    *,
    fixture_root: str | Path = FIXTURE_ROOT,
    historical_root: str | Path = HISTORICAL_ROOT,
) -> dict[str, Any]:
    fixture = Path(fixture_root)
    historical = Path(historical_root)
    rows: dict[str, dict[str, Any]] = {}
    for archetype in ARCHETYPES:
        fixture_dir = fixture / "archetypes" / archetype
        historical_dir = historical / "archetypes" / archetype
        files = {}
        for rel in REQUIRED_LEGACY:
            source = historical_dir / rel
            files[rel] = file_profile(source)
        files["fixture_editable_master_candidate.pptx"] = file_profile(fixture_dir / "editable_master_candidate.pptx")
        files["historical_editable_reconstruction_candidate.pptx"] = file_profile(historical_dir / "editable_reconstruction_candidate.pptx")
        files["historical_rendered_reconstruction_candidate.png"] = file_profile(historical_dir / "rendered_reconstruction_candidate.png")
        files["chart_table_native_reconstruction_plan.json"] = file_profile(historical_dir / "chart_table_native_reconstruction_plan.json")
        files["pptx_semantic_editability_ledger_reconstruction.json"] = file_profile(historical_dir / "pptx_semantic_editability_ledger_reconstruction.json")
        rows[archetype] = {
            "archetype": archetype,
            "fixture_dir": str(fixture_dir),
            "historical_dir": str(historical_dir),
            "fixture_exists": fixture_dir.is_dir(),
            "historical_exists": historical_dir.is_dir(),
            "files": files,
            "missing_required": [rel for rel in REQUIRED_LEGACY if not (historical_dir / rel).is_file()],
            "product_pass": False,
        }
    return {
        "schema": "four_core_fixture_inventory.v1",
        "fixture_root": str(fixture),
        "historical_root": str(historical),
        "archetypes": rows,
        "product_pass": False,
    }


def assess_four_core_readiness(
    selection: dict[str, Any],
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inventory = inventory or inventory_four_core_fixtures()
    rows: dict[str, dict[str, Any]] = {}
    for archetype in ARCHETYPES:
        reference = selection.get("references", {}).get(archetype, {})
        inv = inventory.get("archetypes", {}).get(archetype, {})
        missing_required = list(inv.get("missing_required", []))
        blockers: list[str] = []
        if not reference.get("exists"):
            blockers.append("missing E02 reference image")
            status = "BLOCKED_MISSING_REFERENCE"
        elif missing_required:
            blockers.append("missing protocol/planning artifacts: " + ", ".join(missing_required))
            status = "BLOCKED_MISSING_PROTOCOL_INPUT"
        else:
            policy = evaluate_chart_table_policy(archetype, _legacy_objects(archetype))
            if not policy["pass"]:
                blockers.extend(policy["blockers"])
                status = "BLOCKED_UNSAFE_SEMANTIC_MAPPING"
            else:
                status = "READY_WITH_LEGACY_LIMITATIONS"
        rows[archetype] = {
            "schema": "archetype_input_readiness_report.v1",
            "archetype": archetype,
            "reference_ready": bool(reference.get("exists")),
            "protocol_ready": not missing_required,
            "readiness_status": status,
            "ready": status in {"FOUR_CORE_ARCHETYPE_READY_FOR_P05", "READY_WITH_LEGACY_LIMITATIONS"},
            "blockers": blockers,
            "warnings": ["legacy E02 protocol artifacts require structural normalization"] if not blockers else [],
            "product_pass": False,
        }
    return {
        "schema": "four_core_input_readiness_report.v1",
        "archetypes": rows,
        "overall_ready": all(item["ready"] for item in rows.values()),
        "product_pass": False,
    }


def build_archetype_inputs(
    archetype: str,
    archetype_out: str | Path,
    selection: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    out = Path(archetype_out)
    target = out / "input"
    target.mkdir(parents=True, exist_ok=True)
    historical_dir = Path(inventory["archetypes"][archetype]["historical_dir"])
    fixture_dir = Path(inventory["archetypes"][archetype]["fixture_dir"])
    reference = Path(selection["references"][archetype]["selected_reference_path"])

    copied: list[dict[str, Any]] = []
    copy_plan = {
        "reference_image.png": reference,
        "object_graph.json": historical_dir / "object_graph_v1.json",
        "layer_manifest.json": historical_dir / "layer_manifest_v5.json",
        "semantic_slot_graph.json": historical_dir / "semantic_slot_graph.json",
    }
    for name, source in copy_plan.items():
        destination = target / name
        if source.is_file():
            shutil.copy2(source, destination)
            copied.append({"source_path": str(source), "target_path": str(destination), "sha256": sha256_file(destination), "copied": True})
        else:
            copied.append({"source_path": str(source), "target_path": str(destination), "sha256": None, "copied": False})

    legacy_spec = read_json(historical_dir / "editable_reconstruction_spec.json")
    legacy_slots = read_json(historical_dir / "slot_schema.json")
    chart_table_plan = read_json(historical_dir / "chart_table_native_reconstruction_plan.json")
    bundle, contract, slot_schema, native_plan, editable_spec, normalization = normalize_legacy_archetype_to_bundle(
        archetype=archetype,
        legacy_spec=legacy_spec,
        legacy_slot_schema=legacy_slots,
        chart_table_plan=chart_table_plan,
    )
    write_json(target / "template_contract.json", contract)
    write_json(target / "slot_schema.json", slot_schema)
    write_json(target / "native_reconstruction_plan.json", native_plan)
    write_json(target / "editable_candidate_spec.json", editable_spec)
    write_json(target / "compiler_input_bundle.json", bundle)
    source_manifest = {
        "schema": "p05_source_fixture_manifest.v1",
        "archetype": archetype,
        "historical_dir": str(historical_dir),
        "fixture_dir": str(fixture_dir),
        "reference_source": str(reference),
        "copied_or_normalized": copied,
        "generated_from_legacy_fixture": True,
        "semantic_invention": False,
        "product_pass": False,
    }
    write_json(target / "source_fixture_manifest.json", source_manifest)
    (target / "README.md").write_text(
        f"# P05 {archetype} inputs\n\nE02 historical fixture evidence copied or structurally normalized for controlled four-core regression. These files are not product evidence.\n",
        encoding="utf-8",
    )
    return {
        "schema": "four_core_protocol_mapping_report.v1",
        "archetype": archetype,
        "input_folder": str(target),
        "mapping_status": "PASS_WITH_LEGACY_LIMITATIONS",
        "copied_or_normalized": copied,
        "normalization": normalization,
        "semantic_invention": False,
        "chart_table_policy": evaluate_chart_table_policy(archetype, editable_spec["objects"]),
        "product_pass": False,
    }


def normalize_legacy_archetype_to_bundle(
    *,
    archetype: str,
    legacy_spec: dict[str, Any],
    legacy_slot_schema: dict[str, Any],
    chart_table_plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, obj in enumerate(legacy_spec.get("objects", []) if isinstance(legacy_spec.get("objects"), list) else []):
        normalized = _normalize_object(archetype, obj, index, chart_table_plan)
        if normalized:
            objects.append(normalized)
        else:
            skipped.append({"object_id": obj.get("object_id"), "reason": "unsupported or invalid geometry"})
    objects.sort(key=lambda item: item.get("z_order", 0))
    slots = _normalize_slots(archetype, legacy_slot_schema.get("slots", []), objects)
    contract = _template_contract(archetype, slots)
    native_plan = {
        "schema": "native_reconstruction_plan.v1",
        "plan_id": f"p05_{archetype}_native_plan",
        "template_id": f"p05_{archetype}_template",
        "archetype_id": archetype,
        "reconstruction_objects": [_reconstruction_from_object(obj) for obj in objects if obj.get("slot_id") in {slot["slot_id"] for slot in slots}],
        "legacy_source_schema": legacy_spec.get("schema"),
        "generated_from_legacy_fixture": True,
        "semantic_invention": False,
        "product_pass": False,
    }
    editable_spec = {
        "schema": "editable_candidate_spec.v1",
        "spec_id": f"p05_{archetype}_editable_candidate_spec",
        "template_id": f"p05_{archetype}_template",
        "archetype_id": archetype,
        "pptx_setup": {"slide_size": "LAYOUT_WIDE", "ratio": "16:9", "slides": 1},
        "objects": objects,
        "slots": slots,
        "validation_requirements": ["B03_native_validation_gate", "B01_render_review"],
        "semantic_raster_final_use_count": 0,
        "provenance": {"source": "verified_e02_historical_fixture", "semantic_invention": False, "generated_from_legacy_fixture": True},
        "product_pass": False,
    }
    bundle = {
        "schema": "compiler_input_bundle.v1",
        "bundle_id": f"p05_{archetype}_compiler_input_bundle",
        "editable_candidate_spec": editable_spec,
        "asset_manifest": [],
        "expected_outputs": ["controlled_candidate.pptx", "b03_validation_report.json", "rendered_slide.png"],
        "downstream_gates": ["B03_native_validation_gate", "B01_render_review"],
        "forbidden_outputs": ["full_slide_raster", "screenshot_slide", "semantic_raster_fallback", "source_bound_deck", "canonical_artifact_overwrite"],
        "created_pptx": False,
        "limitations": ["legacy E02 artifact normalization", "minimal OOXML backend visual fidelity is limited"],
        "product_pass": False,
    }
    return bundle, contract, {"schema": "slot_schema.v1", "schema_id": f"p05_{archetype}_slot_schema", "template_id": f"p05_{archetype}_template", "archetype_id": archetype, "slots": slots, "product_pass": False}, native_plan, editable_spec, {"skipped_objects": skipped, "object_count": len(objects)}


def evaluate_chart_table_policy(archetype: str, objects: list[dict[str, Any]]) -> dict[str, Any]:
    types = {str(obj.get("pptx_object_type")) for obj in objects}
    roles = " ".join(str(obj.get("semantic_role", "")).lower() for obj in objects)
    blockers: list[str] = []
    if archetype == "data_dashboard":
        if any(t in types for t in {"raster_image", "bounded_raster"}) and "chart" in roles:
            return {"schema": "p05_chart_table_policy.v1", "status": "FAIL_RASTER_CHART_FALLBACK", "pass": False, "blockers": ["dashboard chart raster fallback is forbidden"], "product_pass": False}
        if "editable_shape_chart" in types or "native_chart" in types:
            return {"schema": "p05_chart_table_policy.v1", "status": "PASS_EDITABLE_SHAPE_CHART", "pass": True, "blockers": [], "product_pass": False}
        blockers.append("dashboard chart is missing native/editable-shape representation")
    elif archetype == "table_heavy":
        if any(t in types for t in {"raster_image", "bounded_raster"}) and "table" in roles:
            return {"schema": "p05_chart_table_policy.v1", "status": "FAIL_RASTER_TABLE_FALLBACK", "pass": False, "blockers": ["table raster fallback is forbidden"], "product_pass": False}
        if "editable_shape_grid_table" in types or "native_table" in types:
            return {"schema": "p05_chart_table_policy.v1", "status": "PASS_EDITABLE_SHAPE_GRID_TABLE", "pass": True, "blockers": [], "product_pass": False}
        blockers.append("table is missing native/editable-grid representation")
    return {"schema": "p05_chart_table_policy.v1", "status": "PASS_NOT_APPLICABLE" if not blockers else "FAIL_MISSING_NATIVE_COMPONENT", "pass": not blockers, "blockers": blockers, "product_pass": False}


def _normalize_object(archetype: str, obj: dict[str, Any], index: int, chart_table_plan: dict[str, Any]) -> dict[str, Any] | None:
    bbox = _legacy_bbox_to_xywh(obj.get("geometry", {}).get("bbox_norm"))
    if bbox is None:
        return None
    source_type = str(obj.get("pptx_object_type") or "")
    text = obj.get("text_content")
    object_id = str(obj.get("object_id") or f"OBJ_{index}")
    slot_id = obj.get("slot_id") or _derived_slot_id(archetype, obj)
    object_type = _normalized_type(archetype, source_type, object_id, text)
    if object_type is None:
        return None
    role = str(obj.get("semantic_role") or _role_from_object(archetype, object_id, object_type))
    instruction = {
        "instruction_id": f"instr_{object_id.lower()}",
        "object_id": object_id,
        "layer_id": obj.get("source_layer_id"),
        "slot_id": slot_id,
        "pptx_object_type": object_type,
        "semantic_role": role,
        "editable_required": object_type != "shape",
        "raster_allowed": False,
        "geometry": {"bbox_norm": bbox, "geometry_source": "e02_legacy_bbox_xyxy_normalized_to_xywh"},
        "style": obj.get("style", {}),
        "object_name": str(slot_id or object_id),
        "validation_checks": ["semantic_editability_ledger", "no_full_slide_raster", "no_semantic_raster"],
        "review_hook_ids": ["text_overflow_review"],
        "patch_hook_ids": ["PATCH_TEXT_OVERFLOW"],
        "z_order": int(obj.get("z_order", index) or index),
        "targetability": {"selectable": True, "style_editable": True, "independently_editable": True, "text_editable": object_type == "text_box"},
        "provenance": {"source": "verified_e02_historical_fixture", "semantic_invention": False, "source_pptx_object_type": source_type},
    }
    if object_type == "text_box":
        content = str(text) if text is not None else str(obj.get("placeholder_text") or object_id)
        instruction["text"] = {"content": content}
        instruction["overflow_policy_id"] = f"ov_{str(slot_id or object_id).lower()}"
    elif object_type == "editable_shape_chart":
        instruction["data"] = _chart_data(chart_table_plan)
        instruction["targetability"]["shape_editable"] = True
        instruction["targetability"]["text_editable"] = True
    elif object_type == "editable_shape_grid_table":
        instruction["table_schema"] = _table_schema(chart_table_plan)
        instruction["targetability"]["shape_editable"] = True
        instruction["targetability"]["text_editable"] = True
    return instruction


def _normalize_slots(archetype: str, legacy_slots: list[dict[str, Any]], objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    object_by_slot = {obj.get("slot_id"): obj for obj in objects if obj.get("slot_id")}
    slots: list[dict[str, Any]] = []
    for raw in legacy_slots if isinstance(legacy_slots, list) else []:
        slot_id = raw.get("slot_id")
        if slot_id not in object_by_slot:
            continue
        bbox = _legacy_bbox_to_xywh(raw.get("bbox_norm"))
        if bbox is None:
            continue
        slot_type = str(raw.get("slot_type") or "text")
        native_target = _native_target_for_slot(slot_type)
        slots.append(
            {
                "slot_id": slot_id,
                "slot_name": raw.get("slot_id"),
                "slot_type": slot_type,
                "semantic_role": raw.get("semantic_role", slot_type),
                "bbox_norm": bbox,
                "required": bool(raw.get("required", True)),
                "editable": bool(raw.get("editable", True)),
                "native_target": native_target,
                "pptx_object_name": raw.get("pptx_object_name") or slot_id,
                "object_ids": [object_by_slot[slot_id]["object_id"]],
                "layer_ids": [],
                "overflow_policy_id": f"ov_{str(slot_id).lower()}",
                "validation_rule_ids": ["editable_text" if slot_type == "text" else "native_or_editable_component"],
                "review_hook_ids": ["text_overflow_review"],
                "patch_hook_ids": ["PATCH_TEXT_OVERFLOW"],
            }
        )
    if archetype == "table_heavy":
        for slot_id, object_id in (("SLOT_TABLE_HEADER_01", "T_TABLE_CELL_01_01"), ("SLOT_TABLE_BODY_01", "T_TABLE_CELL_02_01")):
            obj = next((item for item in objects if item["object_id"] == object_id), None)
            if obj and slot_id not in {slot["slot_id"] for slot in slots}:
                slots.append(
                    {
                        "slot_id": slot_id,
                        "slot_name": slot_id,
                        "slot_type": "text",
                        "semantic_role": "table_cell_text",
                        "bbox_norm": obj["geometry"]["bbox_norm"],
                        "required": True,
                        "editable": True,
                        "native_target": "ppt_text_box",
                        "pptx_object_name": slot_id,
                        "object_ids": [obj["object_id"]],
                        "layer_ids": [],
                        "overflow_policy_id": f"ov_{slot_id.lower()}",
                        "validation_rule_ids": ["editable_text"],
                        "review_hook_ids": ["text_overflow_review"],
                        "patch_hook_ids": ["PATCH_TEXT_OVERFLOW"],
                    }
                )
                obj["slot_id"] = slot_id
                obj["object_name"] = slot_id
    return slots


def _template_contract(archetype: str, slots: list[dict[str, Any]]) -> dict[str, Any]:
    slot_ids = [slot["slot_id"] for slot in slots]
    taxonomy_required = {
        "cover_hero": ["SLOT_TITLE"],
        "standard_content": ["SLOT_TITLE", "SLOT_BODY"],
        "data_dashboard": ["SLOT_KPI_VALUE_01", "SLOT_KPI_LABEL_01", "SLOT_CHART_MAIN"],
        "table_heavy": ["SLOT_TABLE_MAIN", "SLOT_TABLE_HEADER_01", "SLOT_TABLE_BODY_01"],
    }[archetype]
    editable = sorted({slot["slot_id"] for slot in slots if slot["slot_type"] in {"text", "footer_source"}} | {sid for sid in taxonomy_required if sid not in slot_ids and sid != "SLOT_TABLE_MAIN" and sid != "SLOT_CHART_MAIN"})
    native = sorted({slot["slot_id"] for slot in slots if slot["slot_type"] in {"chart", "table"}} | {sid for sid in taxonomy_required if sid in {"SLOT_TABLE_MAIN", "SLOT_CHART_MAIN"}})
    return {
        "schema": "template_contract.v1",
        "contract_id": f"p05_{archetype}_template_contract",
        "template_id": f"p05_{archetype}_template",
        "archetype_id": archetype,
        "template_name": f"P05 {archetype} controlled regression template",
        "intended_use": "controlled four-core Pipeline v2 regression",
        "canvas": {"ratio": "16:9", "slide_width_in": 13.333, "slide_height_in": 7.5},
        "design_tokens": {},
        "fixed_style_elements": [],
        "editable_content_slots": editable,
        "replaceable_visual_slots": [],
        "native_component_slots": native,
        "structural_shapes": [],
        "protected_zones": [],
        "optional_slots": [],
        "forbidden_slots": ["full_slide_raster", "screenshot_slide", "semantic_raster_fallback"],
        "slot_binding_rules": [{"slot_id": slot_id, "binding": "e02_legacy_exact_or_structural_mapping"} for slot_id in sorted(set(editable + native))],
        "overflow_policy": {"required_for_text_slots": True, "policy": "heuristic_review_required"},
        "raster_policy": {"full_slide_raster_allowed": False, "semantic_raster_allowed": False},
        "native_component_policy": {"chart_table_raster_fallback_allowed": False, "editable_shape_chart_table_allowed": True},
        "review_hooks": ["B01_review_packet", "text_overflow_review"],
        "patch_hooks": ["PATCH_TEXT_OVERFLOW", "PATCH_CHART_NATIVE_RECONSTRUCTION", "PATCH_TABLE_NATIVE_RECONSTRUCTION"],
        "source_binding_preparation": {"source_bound_deck_generated": False, "source_binding_preparedness": False},
        "compile_eligibility": {"eligible": True, "canonical_promotion_allowed": False, "product_pass": False},
        "product_pass": False,
    }


def _reconstruction_from_object(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "reconstruction_id": f"recon_{obj['object_id'].lower()}",
        "object_id": obj["object_id"],
        "slot_id": obj.get("slot_id"),
        "semantic_role": obj.get("semantic_role"),
        "pptx_object_type": obj.get("pptx_object_type"),
        "geometry": obj.get("geometry"),
        "text": obj.get("text"),
        "data": obj.get("data"),
        "table_schema": obj.get("table_schema"),
        "semantic_raster_allowed": False,
        "validation_checks": ["semantic_raster_forbidden", "bbox_within_slide", "native_or_editable_component"],
        "product_pass": False,
    }


def _legacy_objects(archetype: str) -> list[dict[str, Any]]:
    spec = read_json(HISTORICAL_ROOT / "archetypes" / archetype / "editable_reconstruction_spec.json")
    plan = read_json(HISTORICAL_ROOT / "archetypes" / archetype / "chart_table_native_reconstruction_plan.json")
    return [item for index, item in enumerate((_normalize_object(archetype, obj, index, plan) for index, obj in enumerate(spec.get("objects", [])))) if item]


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


def _normalized_type(archetype: str, source_type: str, object_id: str, text: Any) -> str | None:
    if source_type == "text_box":
        return "text_box"
    if source_type in {"autoshape", "shape", "freeform_shape"}:
        return "shape"
    if source_type in {"editable_shape_chart", "native_chart"}:
        return "editable_shape_chart"
    if source_type in {"editable_shape_grid_table", "native_table"}:
        if archetype == "table_heavy" and text:
            return "text_box"
        if archetype == "table_heavy" and ("TABLE_MAIN" in object_id or object_id.startswith("TB_TABLE")):
            return "editable_shape_grid_table"
        return "shape"
    return None


def _derived_slot_id(archetype: str, obj: dict[str, Any]) -> str | None:
    object_id = str(obj.get("object_id") or "")
    text = obj.get("text_content")
    if archetype == "data_dashboard" and "CHART" in object_id:
        return "SLOT_CHART_MAIN"
    if archetype == "table_heavy" and ("TABLE_MAIN" in object_id or object_id.startswith("TB_TABLE")):
        return "SLOT_TABLE_MAIN"
    if text:
        return object_id
    return None


def _role_from_object(archetype: str, object_id: str, object_type: str) -> str:
    lowered = object_id.lower()
    if "chart" in lowered or object_type == "editable_shape_chart":
        return "chart_region"
    if "table" in lowered or object_type == "editable_shape_grid_table":
        return "table_region"
    if "kpi" in lowered:
        return "kpi_text"
    if "title" in lowered:
        return "title_text"
    if object_type == "shape":
        return "structural_shape"
    return f"{archetype}_text"


def _native_target_for_slot(slot_type: str) -> str:
    if slot_type == "chart":
        return "editable_shape_chart"
    if slot_type == "table":
        return "editable_shape_grid_table"
    return "ppt_text_box"


def _chart_data(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "chart_type": plan.get("chart_type", "editable_shape_chart"),
        "values": plan.get("values", []),
        "labels": plan.get("labels", []),
        "source": "E02 historical native component plan",
        "semantic_invention": False,
    }


def _table_schema(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": plan.get("rows"),
        "columns": plan.get("columns"),
        "cells": plan.get("cells", []),
        "target": "editable_shape_grid_table",
        "source": "E02 historical native component plan",
        "semantic_invention": False,
    }
