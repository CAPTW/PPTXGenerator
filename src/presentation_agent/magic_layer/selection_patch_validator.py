"""Selection-patch scope validation for Photoshop-inspired Magic Layer+ records."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.ps_layer_protocol import bbox_inside_slide


DANGEROUS_OPERATION_TOKENS = {
    "full_slide_raster": "patch_allows_full_slide_raster",
    "rasterize_text": "patch_allows_rasterize_text",
    "rasterize_semantic_text": "patch_allows_rasterize_text",
    "rasterize_icon": "patch_allows_rasterize_icon",
    "rasterize_semantic_icon": "patch_allows_rasterize_icon",
    "rasterize_card": "patch_allows_rasterize_card",
    "rasterize_chart": "patch_allows_rasterize_chart",
    "rasterize_table": "patch_allows_rasterize_table",
    "rasterize_footer": "patch_allows_rasterize_footer",
    "create_full_slide_raster_background": "patch_allows_full_slide_raster",
    "insert_reference_image_as_background": "patch_allows_full_slide_raster",
    "merge_semantic_layers_into_bitmap": "patch_allows_rasterize_semantic_layer",
}


def validate_selection_patch_contexts(protocol: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    layers = {layer.get("layer_id"): layer for layer in protocol.get("layers", [])}
    group_to_layers: dict[str, list[dict[str, Any]]] = {}
    for layer in protocol.get("layers", []):
        group_id = layer.get("group_id")
        if group_id:
            group_to_layers.setdefault(group_id, []).append(layer)

    contexts = protocol.get("selection_patch_contexts", [])
    for context in contexts:
        context_id = context.get("patch_context_id", "<missing>")
        if not bbox_inside_slide(context.get("selected_bbox_norm")):
            errors.append(_issue("selected_bbox_norm_outside_slide_bounds", context_id))
        selected_layer_ids = set(context.get("selected_layer_ids") or [])
        selected_group_ids = set(context.get("selected_group_ids") or [])
        if not selected_layer_ids and not selected_group_ids:
            errors.append(_issue("selection_patch_missing_selected_layers_or_groups", context_id))
        if not context.get("allowed_operations"):
            errors.append(_issue("selection_patch_missing_allowed_operations", context_id))
        if not context.get("forbidden_operations"):
            errors.append(_issue("selection_patch_missing_forbidden_operations", context_id))
        _validate_dangerous_allowed_operations(context, errors)
        _validate_modified_scope(context, layers, selected_layer_ids, selected_group_ids, group_to_layers, errors)
        _validate_expected_improvement(context, errors)
    return {
        "schema_name": "selection_patch_scope_validation_report",
        "status": "passed" if not errors else "failed",
        "context_count": len(contexts),
        "failure_codes": sorted({error["code"] for error in errors}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "errors": errors,
        "warnings": warnings,
        "canva_parity_claimed": False,
    }


def _validate_dangerous_allowed_operations(context: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    context_id = context.get("patch_context_id", "<missing>")
    for operation in context.get("allowed_operations") or []:
        op = str(operation)
        for token, code in DANGEROUS_OPERATION_TOKENS.items():
            if token in op:
                errors.append(_issue(code, context_id, operation=op))


def _validate_modified_scope(
    context: dict[str, Any],
    layers: dict[str, dict[str, Any]],
    selected_layer_ids: set[str],
    selected_group_ids: set[str],
    group_to_layers: dict[str, list[dict[str, Any]]],
    errors: list[dict[str, Any]],
) -> None:
    selected_from_groups = {layer.get("layer_id") for group_id in selected_group_ids for layer in group_to_layers.get(group_id, [])}
    allowed = selected_layer_ids | selected_from_groups
    modified = set(context.get("modified_layer_ids") or selected_layer_ids)
    for layer_id in modified:
        if layer_id in allowed:
            continue
        layer = layers.get(layer_id, {})
        if layer.get("content_bearing") is True or layer.get("semantic_role"):
            errors.append(_issue("patch_modifies_unselected_semantic_layer", context.get("patch_context_id", "<missing>"), modified_layer_id=layer_id))
        else:
            errors.append(_issue("patch_modifies_unselected_layer", context.get("patch_context_id", "<missing>"), modified_layer_id=layer_id))


def _validate_expected_improvement(context: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    improvement = context.get("expected_qa_improvement") or {}
    required = ("target_gate", "metric", "expected_delta", "verification_artifact")
    if any(not str(improvement.get(field, "")).strip() for field in required):
        errors.append(_issue("expected_qa_improvement_vague", context.get("patch_context_id", "<missing>")))


def _issue(code: str, context_id: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "patch_context_id": context_id, **extra}
