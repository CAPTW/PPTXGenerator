"""Schemas and lightweight validators for E01X proposal/fusion artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROLE_ONTOLOGY = [
    "background_base",
    "hero_visual_field",
    "replaceable_image_frame",
    "decorative_texture",
    "title_text_region",
    "subtitle_text_region",
    "body_text_region",
    "source_footer_strip",
    "card_panel",
    "checklist_panel",
    "icon_region",
    "chart_region",
    "table_region",
    "matrix_region",
    "process_node",
    "timeline_phase",
    "connector",
    "technical_overlay",
    "accent_line",
    "shadow_or_glow",
    "unknown",
]

PPTX_TARGETS = [
    "ppt_text_box",
    "ppt_shape",
    "ppt_shape_group",
    "ppt_connector",
    "svg_vector",
    "native_chart",
    "editable_shape_chart",
    "native_table",
    "editable_shape_grid_table",
    "replaceable_image_frame",
    "bounded_decorative_raster",
    "reject_unknown",
]

ADAPTER_STATUSES = [
    "available",
    "unavailable_missing_package",
    "unavailable_missing_weights",
    "unavailable_disabled",
    "failed_runtime",
    "produced_proposals",
]

REQUIRED_PROPOSAL_FIELDS = {
    "proposal_id",
    "source_adapter",
    "source_type",
    "adapter_status",
    "bbox_px",
    "bbox_norm",
    "confidence",
    "role_candidates",
    "content_bearing_candidate",
    "semantic_candidate",
    "raster_allowed_candidate",
    "editability_target_candidate",
    "evidence",
    "warnings",
    "gate_eligible",
}

REQUIRED_FUSED_OBJECT_FIELDS = {
    "object_id",
    "bbox_px",
    "bbox_norm",
    "z_order",
    "semantic_role",
    "content_bearing",
    "editability_target",
    "proposal_sources",
}


def proposal_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Magic Layer E01X Proposal",
        "type": "object",
        "required": sorted(REQUIRED_PROPOSAL_FIELDS),
        "properties": {
            "proposal_id": {"type": "string", "minLength": 1},
            "source_adapter": {"type": "string", "minLength": 1},
            "source_type": {"enum": ["real_model", "heuristic_smoke_only", "manual_fixture", "ps_layer_protocol"]},
            "adapter_status": {"enum": ADAPTER_STATUSES},
            "bbox_px": _bbox_schema(integer=True),
            "bbox_norm": _bbox_schema(integer=False),
            "polygon_px": {"type": ["array", "null"]},
            "polygon_norm": {"type": ["array", "null"]},
            "mask_ref": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "role_candidates": {"type": "array"},
            "content_bearing_candidate": {"type": "boolean"},
            "semantic_candidate": {"type": "boolean"},
            "raster_allowed_candidate": {"type": "boolean"},
            "editability_target_candidate": {"enum": PPTX_TARGETS},
            "evidence": {"type": "array"},
            "warnings": {"type": "array"},
            "gate_eligible": {"type": "boolean"},
        },
        "additionalProperties": True,
    }


def fusion_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Magic Layer E01X Fused Object Graph v2",
        "type": "object",
        "required": ["schema_name", "schema_version", "objects", "relationships"],
        "properties": {
            "schema_name": {"const": "fused_object_graph_v2"},
            "schema_version": {"type": "string"},
            "objects": {"type": "array"},
            "relationships": {"type": "array"},
        },
        "additionalProperties": True,
    }


def native_reconstruction_readiness_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Magic Layer E01X Native Reconstruction Readiness",
        "type": "object",
        "required": ["schema_name", "objects", "summary"],
        "properties": {
            "schema_name": {"const": "native_reconstruction_readiness_plan"},
            "objects": {"type": "array"},
            "summary": {"type": "object"},
        },
        "additionalProperties": True,
    }


def semantic_role_ontology() -> dict[str, Any]:
    return {
        "schema_name": "semantic_role_ontology",
        "schema_version": "1.0",
        "roles": ROLE_ONTOLOGY,
        "unknown_policy": {
            "unknown_content_bearing_layer": "fatal",
            "unknown_semantic_layer": "fatal_or_explicit_reject",
            "decorative_unknown": "allowed_only_if_bounded_with_reason",
            "unknown_final_pptx_target": "fail_e01_readiness",
        },
        "canva_parity_claimed": False,
    }


def validate_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    _require_fields(proposal, REQUIRED_PROPOSAL_FIELDS, "proposal")
    _validate_bbox(proposal["bbox_px"], "bbox_px", normalized=False)
    _validate_bbox(proposal["bbox_norm"], "bbox_norm", normalized=True)
    if proposal["adapter_status"] not in ADAPTER_STATUSES:
        raise ValueError(f"adapter_status must be one of {ADAPTER_STATUSES}")
    if proposal["source_type"] == "heuristic_smoke_only" and proposal.get("gate_eligible") is not False:
        raise ValueError("heuristic_smoke_only proposals must set gate_eligible=false")
    if proposal["editability_target_candidate"] not in PPTX_TARGETS:
        raise ValueError("editability_target_candidate is not a supported PPTX target")
    if not isinstance(proposal.get("role_candidates"), list):
        raise ValueError("role_candidates must be a list")
    return proposal


def validate_fused_object(obj: dict[str, Any]) -> dict[str, Any]:
    _require_fields(obj, REQUIRED_FUSED_OBJECT_FIELDS, "fused object")
    _validate_bbox(obj["bbox_px"], "bbox_px", normalized=False)
    _validate_bbox(obj["bbox_norm"], "bbox_norm", normalized=True)
    if obj["semantic_role"] not in ROLE_ONTOLOGY:
        raise ValueError(f"semantic_role must be in ontology: {obj['semantic_role']}")
    if obj["editability_target"] not in PPTX_TARGETS:
        raise ValueError("editability_target is not a supported PPTX target")
    if not obj["proposal_sources"]:
        raise ValueError("proposal_sources must include evidence")
    return obj


def write_schema_artifacts(output_dir: Path, ps_layer_schema: dict[str, Any] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "proposal_schema.json": proposal_schema(),
        "fusion_schema.json": fusion_schema(),
        "semantic_role_ontology.json": semantic_role_ontology(),
        "native_reconstruction_readiness_schema.json": native_reconstruction_readiness_schema(),
    }
    if ps_layer_schema is not None:
        artifacts["ps_layer_protocol_schema.json"] = ps_layer_schema
    for name, payload in artifacts.items():
        (output_dir / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bbox_schema(*, integer: bool) -> dict[str, Any]:
    number_type: str | list[str] = "integer" if integer else "number"
    return {
        "type": "object",
        "required": ["x", "y", "w", "h"],
        "properties": {
            "x": {"type": number_type},
            "y": {"type": number_type},
            "w": {"type": number_type, "exclusiveMinimum": 0},
            "h": {"type": number_type, "exclusiveMinimum": 0},
        },
        "additionalProperties": False,
    }


def _require_fields(payload: dict[str, Any], fields: set[str], label: str) -> None:
    missing = sorted(field for field in fields if field not in payload)
    if missing:
        raise ValueError(f"{label} missing required field(s): {', '.join(missing)}")


def _validate_bbox(bbox: Any, field: str, *, normalized: bool) -> None:
    if not isinstance(bbox, dict):
        raise ValueError(f"{field} must be an object with x/y/w/h")
    for key in ("x", "y", "w", "h"):
        if key not in bbox:
            raise ValueError(f"{field} missing {key}")
        if not isinstance(bbox[key], (int, float)):
            raise ValueError(f"{field}.{key} must be numeric")
    if bbox["w"] <= 0 or bbox["h"] <= 0:
        raise ValueError(f"{field} width/height must be positive")
    if normalized:
        if bbox["x"] < 0 or bbox["y"] < 0 or bbox["x"] + bbox["w"] > 1.000001 or bbox["y"] + bbox["h"] > 1.000001:
            raise ValueError(f"{field} must stay inside normalized slide bounds")
