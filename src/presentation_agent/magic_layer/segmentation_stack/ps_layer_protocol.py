"""Photoshop-inspired layer protocol artifacts for E01X."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .semantic_roles import PREFIX_BY_ROLE, is_semantic_role, role_prefix


RASTER_TARGETS = {"replaceable_image_frame", "bounded_decorative_raster"}
SEMANTIC_RASTER_FORBIDDEN = {
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
}


def ps_layer_protocol_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "E01X PS Layer Protocol",
        "type": "object",
        "required": ["schema_name", "layers", "groups", "masks"],
        "properties": {
            "schema_name": {"const": "ps_layer_protocol_v2"},
            "layers": {"type": "array"},
            "groups": {"type": "array"},
            "masks": {"type": "array"},
        },
        "additionalProperties": True,
    }


def selection_patch_context_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "E01X Selection Patch Context",
        "type": "object",
        "required": ["object_id", "selected_region", "patch_intent"],
        "properties": {
            "object_id": {"type": "string"},
            "selected_region": {"type": "object"},
            "patch_intent": {"type": "string"},
        },
        "additionalProperties": True,
    }


def build_ps_layer_as_built(objects: list[dict[str, Any]]) -> dict[str, Any]:
    layers = []
    for obj in objects:
        role = obj.get("semantic_role", "unknown")
        prefix = role_prefix(role)
        layer_name = obj.get("object_id") or f"{prefix}_{role}"
        layers.append(
            {
                "object_id": obj.get("object_id"),
                "layer_name": layer_name,
                "semantic_role": role,
                "content_bearing": bool(obj.get("content_bearing")),
                "bbox_px": obj.get("bbox_px"),
                "bbox_norm": obj.get("bbox_norm"),
                "z_order": obj.get("z_order"),
                "pptx_target": obj.get("editability_target"),
                "editability_required": role in SEMANTIC_RASTER_FORBIDDEN,
                "opacity": 1.0,
                "blend_mode": "normal",
                "raster_policy": {
                    "final_use": obj.get("editability_target"),
                    "bounded": True,
                    "semantic_raster_allowed": role not in SEMANTIC_RASTER_FORBIDDEN,
                },
                "unknown_disposition": "reject_unknown" if role == "unknown" else "not_unknown",
                "proposal_sources": obj.get("proposal_sources", []),
            }
        )
    cleanup = validate_layer_cleanup_naming(layers)
    return {
        "schema_name": "ps_layer_protocol_v2",
        "schema_version": "2.0",
        "groups": [],
        "layers": layers,
        "masks": [],
        "smart_objects": [layer for layer in layers if layer.get("pptx_target") == "replaceable_image_frame"],
        "layer_cleanup_gate": cleanup,
        "canva_parity_claimed": False,
    }


def build_protocol_artifacts(output_dir: Path, objects: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    as_built = build_ps_layer_as_built(objects or [])
    intent = {
        "schema_name": "ps_layer_intent_template",
        "schema_version": "2.0",
        "description": "Template for model/fusion-selected PS-style object intent before PPTX reconstruction.",
        "required_prefixes": required_semantic_prefixes(),
        "layers": [],
        "groups": [],
        "masks": [],
        "canva_parity_claimed": False,
    }
    artifacts = {
        "ps_layer_protocol_definition.md": ps_layer_protocol_definition_markdown(),
        "ps_layer_intent_template.json": intent,
        "ps_layer_as_built.json": as_built,
        "ps_to_pptx_mapping_rules.json": ps_to_pptx_mapping_rules(),
        "mask_to_pptx_rendering_rules.json": mask_to_pptx_rendering_rules(),
        "smart_object_to_image_frame_rules.json": smart_object_to_image_frame_rules(),
        "selection_patch_context_schema.json": selection_patch_context_schema(),
        "layer_cleanup_naming_rules.json": layer_cleanup_naming_rules(),
    }
    for name, payload in artifacts.items():
        path = output_dir / name
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifacts


def validate_layer_cleanup_naming(layers: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for layer in layers:
        object_id = str(layer.get("object_id") or "")
        name = str(layer.get("layer_name") or "")
        role = str(layer.get("semantic_role") or "unknown")
        content_bearing = bool(layer.get("content_bearing"))
        expected_prefix = role_prefix(role)
        target = str(layer.get("pptx_target") or "")
        final_use = str((layer.get("raster_policy") or {}).get("final_use") or target)

        if object_id:
            if object_id in seen_ids:
                errors.append({"code": "duplicate_object_id", "object_id": object_id})
            seen_ids.add(object_id)
        if content_bearing and expected_prefix != "UNKNOWN" and not name.startswith(f"{expected_prefix}_"):
            errors.append(
                {
                    "code": "content_bearing_layer_without_semantic_prefix",
                    "object_id": object_id,
                    "layer_name": name,
                    "expected_prefix": expected_prefix,
                }
            )
        if role == "unknown" and content_bearing:
            errors.append({"code": "unknown_content_bearing_layer", "object_id": object_id})
        if role == "unknown" and is_semantic_role(role):
            errors.append({"code": "unknown_semantic_layer", "object_id": object_id})
        if role in SEMANTIC_RASTER_FORBIDDEN and (target in RASTER_TARGETS or final_use in RASTER_TARGETS):
            errors.append({"code": "semantic_raster_layer", "object_id": object_id, "semantic_role": role, "pptx_target": target})
        if role in {"decorative_texture", "accent_line", "shadow_or_glow"} and not (layer.get("raster_policy") or {}).get("bounded", True):
            errors.append({"code": "unbounded_decorative_raster", "object_id": object_id})
        if role == "unknown" and not content_bearing:
            warnings.append({"code": "decorative_unknown_requires_bounded_reason", "object_id": object_id})
    return {
        "schema_name": "layer_cleanup_naming_gate",
        "schema_version": "1.0",
        "status": "passed" if not errors else "failed",
        "failure_codes": sorted({error["code"] for error in errors}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "errors": errors,
        "warnings": warnings,
        "canva_parity_claimed": False,
    }


def required_semantic_prefixes() -> dict[str, str]:
    return dict(sorted(PREFIX_BY_ROLE.items()))


def ps_to_pptx_mapping_rules() -> dict[str, Any]:
    return {
        "schema_name": "ps_to_pptx_mapping_rules",
        "mappings": {
            "Photoshop layer": "PPTX object/group/z-order layer",
            "Photoshop target layer": "object_id patch target",
            "Photoshop selection": "selected_region / bbox / mask seed",
            "Photoshop layer mask": "polygon_mask_ledger / clipping path",
            "Photoshop smart object": "replaceable PPT image frame",
            "Photoshop layer cleanup": "deterministic layer/object naming gate",
        },
        "canva_parity_claimed": False,
    }


def mask_to_pptx_rendering_rules() -> dict[str, Any]:
    return {
        "schema_name": "mask_to_pptx_rendering_rules",
        "rules": [
            "semantic masks must promote to native PPT primitives or SVG vectors",
            "bounded nonsemantic decorative masks may become bounded decorative raster",
            "mask overlap with protected text zones must be reported",
        ],
        "canva_parity_claimed": False,
    }


def smart_object_to_image_frame_rules() -> dict[str, Any]:
    return {
        "schema_name": "smart_object_to_image_frame_rules",
        "rules": [
            "smart_object_like image fields map to replaceable_image_frame",
            "smart objects must not contain semantic text, chart, table, icon, card, footer, or source content",
            "full-slide smart objects are rejected",
        ],
        "canva_parity_claimed": False,
    }


def layer_cleanup_naming_rules() -> dict[str, Any]:
    return {
        "schema_name": "layer_cleanup_naming_rules",
        "required_prefixes": {
            "T_": "text",
            "S_": "shape/card/panel",
            "I_": "SVG/vector icon",
            "C_": "chart",
            "TB_": "table",
            "F_": "footer/source/citation",
            "IMG_": "replaceable image/hero/photo field",
            "D_": "decorative nonsemantic visual field",
            "G_": "group/container",
            "MASK_": "clipping/mask geometry",
            "UNKNOWN_": "explicit fail/reject evidence only",
        },
        "failure_rules": [
            "content-bearing layer without semantic prefix fails",
            "semantic raster layer fails",
            "unknown semantic layer fails",
            "duplicate object ids fail",
        ],
        "canva_parity_claimed": False,
    }


def ps_layer_protocol_definition_markdown() -> str:
    return "\n".join(
        [
            "# PS-Layer Protocol Definition",
            "",
            "This protocol maps Photoshop-style layer discipline to editable PPTX reconstruction.",
            "",
            "- Photoshop layer -> PPTX object/group/z-order layer",
            "- Photoshop target layer -> object_id patch target",
            "- Photoshop selection -> selected_region / bbox / mask seed",
            "- Photoshop layer mask -> polygon_mask_ledger / clipping path",
            "- Photoshop smart object -> replaceable PPT image frame",
            "- Photoshop layer cleanup -> deterministic layer/object naming gate",
            "",
            "Semantic raster policy forbids rasterized title, body text, labels, KPI cards, checklist content, tables, charts, semantic icons, footer/source/citation, and recurring layout chrome.",
            "",
            "Canva parity claimed: `False`",
        ]
    ) + "\n"
