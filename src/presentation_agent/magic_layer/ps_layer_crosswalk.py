"""Cross-ledger validation bridge for Photoshop-inspired Magic Layer+ records."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.ps_layer_protocol import normalize_bbox


def build_cross_ledger_reports(protocol: dict[str, Any], ledgers: dict[str, Any], bbox_mismatch_threshold: float = 0.20) -> dict[str, dict[str, Any]]:
    object_report = build_object_graph_crosswalk(protocol, ledgers.get("object_graph"), bbox_mismatch_threshold)
    manifest_report = build_layer_manifest_crosswalk(protocol, ledgers.get("layer_manifest"), object_report)
    slot_report = build_semantic_slot_crosswalk(protocol, ledgers.get("semantic_slot_graph"), object_report)
    native_report = build_native_reconstruction_crosswalk(protocol, ledgers.get("native_reconstruction_plan"), object_report)
    raster_report = build_raster_policy_crosswalk(protocol, ledgers.get("semantic_editability_ledger"), ledgers.get("semantic_raster_violation_report"), ledgers.get("layer_manifest"))
    return {
        "object_graph": object_report,
        "layer_manifest": manifest_report,
        "semantic_slot": slot_report,
        "native_reconstruction": native_report,
        "raster_policy": raster_report,
    }


def build_object_graph_crosswalk(protocol: dict[str, Any], object_graph: dict[str, Any] | None, bbox_mismatch_threshold: float = 0.20) -> dict[str, Any]:
    if not object_graph:
        return _skipped("ps_layer_to_object_graph_crosswalk", "object_graph_not_present")
    nodes = object_graph.get("nodes", [])
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    rows = []
    for layer in protocol.get("layers", []):
        if not _requires_cross_ledger_mapping(layer):
            continue
        match, basis = _match_record(layer, nodes)
        row = {"layer_id": layer.get("layer_id"), "semantic_role": layer.get("semantic_role"), "match_basis": basis}
        if match is None:
            errors.append({"code": "content_bearing_ps_layer_missing_object_graph_node", "layer_id": layer.get("layer_id")})
            row["status"] = "failed"
        else:
            row.update({"status": "matched", "object_id": match.get("object_id"), "object_semantic_role": match.get("semantic_role")})
            iou = bbox_iou(layer.get("bbox_norm"), match.get("bbox_norm"))
            row["bbox_iou"] = iou
            if iou < bbox_mismatch_threshold:
                warnings.append({"code": "bbox_mismatch_recorded", "layer_id": layer.get("layer_id"), "object_id": match.get("object_id"), "bbox_iou": iou})
            if _z_order_contradictory(layer.get("z_order"), match.get("z_order")):
                warnings.append({"code": "z_order_mismatch_recorded", "layer_id": layer.get("layer_id"), "object_id": match.get("object_id"), "ps_z_order": layer.get("z_order"), "ledger_z_order": match.get("z_order")})
        rows.append(row)
    return _crosswalk_report("ps_layer_to_object_graph_crosswalk", rows, errors, warnings)


def build_layer_manifest_crosswalk(protocol: dict[str, Any], layer_manifest: dict[str, Any] | None, object_report: dict[str, Any]) -> dict[str, Any]:
    if not layer_manifest:
        return _skipped("ps_layer_to_layer_manifest_crosswalk", "layer_manifest_not_present")
    manifest_layers = layer_manifest.get("layers", [])
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    rows = []
    object_ids = _matched_object_ids(object_report)
    for layer in protocol.get("layers", []):
        if not _requires_cross_ledger_mapping(layer):
            continue
        match = _match_manifest(layer, manifest_layers, object_ids.get(layer.get("layer_id")))
        row = {"layer_id": layer.get("layer_id"), "semantic_role": layer.get("semantic_role")}
        if match is None:
            errors.append({"code": "semantic_ps_layer_missing_layer_manifest_entry", "layer_id": layer.get("layer_id")})
            row["status"] = "failed"
        else:
            row.update({"status": "matched", "manifest_layer_id": match.get("layer_id"), "manifest_semantic_role": match.get("semantic_role")})
        rows.append(row)
    return _crosswalk_report("ps_layer_to_layer_manifest_crosswalk", rows, errors, warnings)


def build_semantic_slot_crosswalk(protocol: dict[str, Any], semantic_slot_graph: dict[str, Any] | None, object_report: dict[str, Any]) -> dict[str, Any]:
    if not semantic_slot_graph:
        return _skipped("ps_layer_to_semantic_slot_crosswalk", "semantic_slot_graph_not_present")
    slots = semantic_slot_graph.get("slots", [])
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    rows = []
    object_ids = _matched_object_ids(object_report)
    for layer in protocol.get("layers", []):
        if not _requires_cross_ledger_mapping(layer):
            continue
        match = _match_semantic_slot(layer, slots, object_ids.get(layer.get("layer_id")))
        row = {"layer_id": layer.get("layer_id"), "semantic_role": layer.get("semantic_role")}
        if match is None:
            errors.append({"code": "semantic_ps_layer_missing_semantic_slot", "layer_id": layer.get("layer_id")})
            row["status"] = "failed"
        else:
            row.update({"status": "matched", "slot_id": match.get("slot_id"), "slot_semantic_role": match.get("semantic_role"), "object_id": match.get("object_id")})
        rows.append(row)
    return _crosswalk_report("ps_layer_to_semantic_slot_crosswalk", rows, errors, warnings)


def build_native_reconstruction_crosswalk(protocol: dict[str, Any], native_plan: dict[str, Any] | None, object_report: dict[str, Any]) -> dict[str, Any]:
    if not native_plan:
        return _skipped("ps_layer_to_native_reconstruction_crosswalk", "native_reconstruction_plan_not_present")
    actions = native_plan.get("actions", [])
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    rows = []
    object_ids = _matched_object_ids(object_report)
    for layer in protocol.get("layers", []):
        if not _requires_cross_ledger_mapping(layer):
            continue
        object_id = object_ids.get(layer.get("layer_id"))
        match = next((action for action in actions if object_id and action.get("source_object_id") == object_id), None)
        if match is None:
            match = next(
                (action for action in actions if _canonical_role(action.get("semantic_role")) == _canonical_role(layer.get("semantic_role"))),
                None,
            )
        row = {"layer_id": layer.get("layer_id"), "semantic_role": layer.get("semantic_role")}
        if match is None:
            errors.append({"code": "semantic_ps_layer_missing_native_reconstruction_action", "layer_id": layer.get("layer_id")})
            row["status"] = "failed"
        else:
            row.update({"status": "matched", "source_object_id": match.get("source_object_id"), "target_ppt_object_type": match.get("target_ppt_object_type")})
            if _semantic_raster_allowed_for_semantic_layer(layer, match):
                errors.append({"code": "semantic_ps_layer_allows_raster_final_use", "layer_id": layer.get("layer_id"), "source_object_id": match.get("source_object_id")})
        rows.append(row)
    return _crosswalk_report("ps_layer_to_native_reconstruction_crosswalk", rows, errors, warnings)


def build_raster_policy_crosswalk(
    protocol: dict[str, Any],
    semantic_editability_ledger: dict[str, Any] | None,
    semantic_raster_violation_report: dict[str, Any] | None,
    layer_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    semantic_raster_count = int((semantic_editability_ledger or {}).get("semantic_raster_violation_count", 0)) + int(
        (semantic_raster_violation_report or {}).get("semantic_raster_violation_count", 0)
    )
    if semantic_raster_count != 0:
        errors.append({"code": "semantic_raster_violation_count_nonzero", "semantic_raster_violation_count": semantic_raster_count})
    unknown_count = 0
    for layer in (layer_manifest or {}).get("layers", []):
        if layer.get("content_bearing") and layer.get("unknown_disposition") not in {None, "resolved", "not_unknown"}:
            unknown_count += 1
    if unknown_count:
        errors.append({"code": "unknown_content_bearing_count_nonzero", "unknown_content_bearing_layer_count": unknown_count})
    for layer in protocol.get("layers", []):
        policy = layer.get("raster_policy") or {}
        if layer.get("content_bearing") is True and policy.get("final_use") == "bounded_nonsemantic_raster":
            errors.append({"code": "content_bearing_ps_layer_uses_bounded_raster", "layer_id": layer.get("layer_id")})
    return {
        "schema_name": "ps_layer_to_raster_policy_crosswalk",
        "status": "passed" if not errors else "failed",
        "semantic_raster_violation_count": semantic_raster_count,
        "unknown_content_bearing_layer_count": unknown_count,
        "failure_codes": sorted({error["code"] for error in errors}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "errors": errors,
        "warnings": warnings,
        "canva_parity_claimed": False,
    }


def classify_e01x_integration_readiness(statuses: dict[str, str]) -> dict[str, Any]:
    decision = "READY_FOR_E01X_INTEGRATION"
    if statuses.get("schema") == "failed":
        decision = "PATCH_PS_LAYER_SCHEMA"
    elif statuses.get("selection_schema") == "failed":
        decision = "PATCH_SELECTION_CONTEXT_SCHEMA"
    elif statuses.get("layers") == "failed":
        decision = "PATCH_MAPPING_RULES"
    elif statuses.get("masks") == "failed":
        decision = "PATCH_MASK_RULES"
    elif statuses.get("smart_objects") == "failed":
        decision = "PATCH_SMART_OBJECT_RULES"
    elif statuses.get("cross_ledgers") == "failed":
        decision = "PATCH_CROSS_LEDGER_VALIDATOR"
    elif statuses.get("cleanup") == "failed":
        decision = "FAIL_PROTOCOL_CONSISTENCY"
    return {
        "schema_name": "e01x_integration_readiness_report",
        "status": "passed" if decision == "READY_FOR_E01X_INTEGRATION" else "failed",
        "decision": decision,
        "ready": decision == "READY_FOR_E01X_INTEGRATION",
        "input_statuses": statuses,
        "canva_parity_claimed": False,
        "e02_started": False,
        "d08_started": False,
        "deck_generated": False,
        "pptx_compiled": False,
    }


def bbox_iou(left: Any, right: Any) -> float:
    try:
        a = normalize_bbox(left)
        b = normalize_bbox(right)
    except (KeyError, TypeError, ValueError):
        return 0.0
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    iw = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
    ih = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
    intersection = iw * ih
    union = a["w"] * a["h"] + b["w"] * b["h"] - intersection
    return round(intersection / union, 6) if union else 0.0


def _match_record(layer: dict[str, Any], records: list[dict[str, Any]], preferred_object_id: str | None = None) -> tuple[dict[str, Any] | None, str]:
    target = layer.get("pptx_target") or {}
    object_candidates = [preferred_object_id, target.get("object_id"), target.get("slot_id")]
    for object_id in [candidate for candidate in object_candidates if candidate]:
        match = next((record for record in records if record.get("object_id") == object_id or record.get("source_object_id") == object_id), None)
        if match:
            return match, "object_id"
    role = _canonical_role(layer.get("semantic_role"))
    match = next((record for record in records if _canonical_role(record.get("semantic_role")) == role), None)
    if match:
        return match, "semantic_role"
    return None, "none"


def _match_manifest(layer: dict[str, Any], records: list[dict[str, Any]], object_id: str | None) -> dict[str, Any] | None:
    if object_id:
        match = next((record for record in records if record.get("source_object_id") == object_id), None)
        if match is not None:
            return match
    match = next((record for record in records if record.get("layer_id") == layer.get("layer_id")), None)
    if match is not None:
        return match
    return next((record for record in records if _canonical_role(record.get("semantic_role")) == _canonical_role(layer.get("semantic_role"))), None)


def _match_semantic_slot(layer: dict[str, Any], slots: list[dict[str, Any]], object_id: str | None) -> dict[str, Any] | None:
    match = _match_record(layer, slots, object_id)[0]
    if match is not None:
        return match
    role = _canonical_role(layer.get("semantic_role"))
    slot_aliases = {
        "source_footer_strip": {"source_footer_text"},
        "footer_source_strip": {"source_footer_text"},
    }
    aliases = slot_aliases.get(role, set())
    return next((slot for slot in slots if _canonical_role(slot.get("semantic_role")) in aliases), None)


def _canonical_role(role: Any) -> str:
    value = str(role or "")
    aliases = {
        "title": "title_text",
        "subtitle": "subtitle_text",
        "body": "body_text",
        "footer": "source_footer_strip",
    }
    value = aliases.get(value, value)
    if value.endswith("_text_region"):
        value = value.removesuffix("_region")
    return value


def _requires_cross_ledger_mapping(layer: dict[str, Any]) -> bool:
    return layer.get("content_bearing") is True or layer.get("layer_kind") == "smart_object_like_image"


def _matched_object_ids(object_report: dict[str, Any]) -> dict[str, str]:
    return {row["layer_id"]: row["object_id"] for row in object_report.get("crosswalk", []) if row.get("status") == "matched" and row.get("object_id")}


def _semantic_raster_allowed_for_semantic_layer(layer: dict[str, Any], action: dict[str, Any]) -> bool:
    if layer.get("semantic_role") == "hero_visual_field" and layer.get("content_bearing") is not True:
        return False
    return layer.get("content_bearing") is True and action.get("semantic_raster_final_use_allowed") is True


def _z_order_contradictory(left: Any, right: Any) -> bool:
    try:
        return abs(int(left) - int(right)) > 20
    except (TypeError, ValueError):
        return False


def _crosswalk_report(schema_name: str, rows: list[dict[str, Any]], errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": schema_name,
        "status": "passed" if not errors else "failed",
        "mapped_count": sum(1 for row in rows if row.get("status") == "matched"),
        "unmapped_count": sum(1 for row in rows if row.get("status") == "failed"),
        "crosswalk": rows,
        "failure_codes": sorted({error["code"] for error in errors}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "errors": errors,
        "warnings": warnings,
        "canva_parity_claimed": False,
    }


def _skipped(schema_name: str, reason: str) -> dict[str, Any]:
    return {
        "schema_name": schema_name,
        "status": "skipped",
        "reason": reason,
        "crosswalk": [],
        "failure_codes": [],
        "warning_codes": [],
        "errors": [],
        "warnings": [],
        "canva_parity_claimed": False,
    }
