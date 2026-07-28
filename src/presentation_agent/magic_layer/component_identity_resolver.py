"""Component identity resolution for D03 layer manifests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def resolve_component_identity(
    manifest: dict[str, Any],
    icon_mappings: list[dict[str, Any]],
    primitive_mappings: list[dict[str, Any]],
) -> dict[str, Any]:
    reference_id = manifest.get("reference_id") or "reference"
    icon_by_layer = {item["layer_id"]: item for item in icon_mappings}
    primitive_by_layer = {}
    for mapping in primitive_mappings:
        for layer_id in mapping.get("source_layer_ids") or []:
            primitive_by_layer[layer_id] = mapping
    resolutions = []
    for layer in manifest.get("layers") or []:
        icon = icon_by_layer.get(layer["layer_id"])
        primitive = primitive_by_layer.get(layer["layer_id"])
        status, explanation = _status(layer, icon, primitive)
        resolutions.append(
            {
                "layer_id": layer["layer_id"],
                "reference_id": reference_id,
                "preserved_component_identity_candidate": deepcopy(layer.get("component_identity_candidate")),
                "resolved_component_identity": _identity(layer, icon, primitive),
                "component_identity_status": status,
                "explanation": explanation,
            }
        )
    return {
        "schema_name": "component_identity_resolution",
        "reference_id": reference_id,
        "resolutions": resolutions,
        "unresolved_blocking_count": sum(1 for item in resolutions if item["component_identity_status"] == "unresolved_blocking"),
    }


def validate_component_identity_resolution(resolution: dict[str, Any]) -> list[str]:
    errors = []
    for item in resolution.get("resolutions") or []:
        if "component_identity_status" not in item:
            errors.append(f"{item.get('layer_id')}:component_identity_status_required")
    return errors


def build_updated_icon_primitive_manifest(
    manifest: dict[str, Any],
    icon_mappings: list[dict[str, Any]],
    primitive_mappings: list[dict[str, Any]],
    component_resolution: dict[str, Any],
    d02_text_risk: dict[str, Any],
) -> dict[str, Any]:
    updated = deepcopy(manifest)
    icon_by_layer = {item["layer_id"]: item for item in icon_mappings}
    primitive_by_layer = {}
    for mapping in primitive_mappings:
        for layer_id in mapping.get("source_layer_ids") or []:
            primitive_by_layer[layer_id] = mapping
    resolution_by_layer = {item["layer_id"]: item for item in component_resolution.get("resolutions") or []}
    for layer in updated.get("layers") or []:
        layer_id = layer["layer_id"]
        icon = icon_by_layer.get(layer_id)
        primitive = primitive_by_layer.get(layer_id)
        resolution = resolution_by_layer.get(layer_id, {})
        if icon:
            layer["resolved_icon_role"] = icon.get("selected_role")
            layer["svg_mapping_candidate"] = icon.get("selected_svg_candidate_path")
            layer["d03_icon_disposition"] = icon.get("final_disposition")
        if primitive:
            layer["primitive_family"] = primitive.get("primitive_family")
            layer["target_ppt_object_type"] = primitive.get("target_ppt_object_type")
            layer["D04_handoff_required"] = primitive.get("handoff_stage") == "D04"
        layer["component_identity_status"] = resolution.get("component_identity_status", "unresolved_nonblocking")
        layer["D05_render_fidelity_notes"] = "Render comparison required before productized conversion."
        layer["d02_text_risk_carryforward"] = d02_text_risk
        layer["d03_unresolved_disposition"] = resolution.get("component_identity_status")
    updated["schema_name"] = "layer_manifest_v4_icon_primitive_mapped"
    updated["d03_icon_primitive_mapping"] = {
        "icon_mapping_count": len(icon_mappings),
        "primitive_mapping_count": len(primitive_mappings),
        "component_identity_resolution_count": len(component_resolution.get("resolutions") or []),
        "ocr_backend_status": d02_text_risk.get("ocr_backend_status"),
        "text_risk_status": d02_text_risk.get("text_risk_status"),
    }
    return updated


def _status(layer: dict[str, Any], icon: dict[str, Any] | None, primitive: dict[str, Any] | None) -> tuple[str, str]:
    layer_type = layer.get("layer_type")
    if icon:
        if icon.get("final_disposition") == "svg_mapped":
            return "resolved", "Icon-like layer mapped to local SVG role; OCR text was not used as strong evidence."
        if icon.get("final_disposition") == "chart_table_marker_handoff_D04":
            return "handoff_D04", "Icon-like layer is likely part of a chart/table component and is reserved for D04."
        if icon.get("final_disposition", "").startswith("unresolved"):
            return "unresolved_blocking", icon.get("unresolved_reason") or "Icon-like layer unresolved."
        return "provisional", "Icon-like layer treated as nonsemantic primitive or decorative mark."
    if primitive and primitive.get("handoff_stage") == "D04":
        return "handoff_D04", "Primitive is chart/table-like and needs native component promotion."
    if layer_type == "unknown" and layer.get("content_bearing"):
        return "unresolved_blocking", "Content-bearing unknown layer must not silently pass."
    if layer_type == "unknown":
        return "unresolved_nonblocking", "Decorative unknown remains explicitly bounded for later render review."
    return "resolved" if primitive else "provisional", "Primitive family resolved from D01/D02 layer context."


def _identity(layer: dict[str, Any], icon: dict[str, Any] | None, primitive: dict[str, Any] | None) -> str:
    if icon and icon.get("final_disposition") == "svg_mapped":
        return f"svg_icon:{icon.get('selected_role')}"
    if primitive:
        return str(primitive.get("primitive_family"))
    candidate = layer.get("component_identity_candidate") or {}
    return str(candidate.get("primary") or layer.get("layer_type") or "unknown")

