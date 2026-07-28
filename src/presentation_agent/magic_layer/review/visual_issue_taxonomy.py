from __future__ import annotations

from typing import Any


ISSUE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "semantic_raster_text": {
        "default_severity": "fatal",
        "blocks_product_pass": True,
        "recommended_patch_class": "PATCH_TEXT_REGION_LIFT",
        "required_evidence": ["bbox", "semantic role", "raster/native validation report"],
        "b03_relation": "semantic raster must fail native validation",
        "e01p_relation": "semantic raster precompile policy must reject this plan",
    },
    "residual_raster_text": {
        "default_severity": "high",
        "blocks_product_pass": True,
        "recommended_patch_class": "PATCH_RASTER_TEXT_SUPPRESSION",
        "required_evidence": ["text lift region", "suppression/replacement evidence"],
        "b03_relation": "residual visible raster text limits editability evidence",
        "e01p_relation": "suppression must be paired with editable replacement",
    },
    "text_overflow": {
        "default_severity": "warning",
        "blocks_product_pass": False,
        "recommended_patch_class": "PATCH_TEXT_OVERFLOW",
        "required_evidence": ["slot bbox", "text geometry or visual review"],
        "b03_relation": "B03 overflow evidence is heuristic unless a strict ledger exists",
        "e01p_relation": "slot contract must carry overflow policy",
    },
    "unknown_content_bearing": {
        "default_severity": "fatal",
        "blocks_product_pass": True,
        "recommended_patch_class": "PATCH_UNKNOWN_LAYER_CLASSIFICATION",
        "required_evidence": ["layer/object id", "bbox"],
        "b03_relation": "unknown content-bearing object cannot validate as native editable",
        "e01p_relation": "unknown layer policy treats this as fatal",
    },
    "full_slide_raster": {
        "default_severity": "fatal",
        "blocks_product_pass": True,
        "recommended_patch_class": "PATCH_RENDER_FIDELITY",
        "required_evidence": ["slide-sized raster bbox"],
        "b03_relation": "full-slide raster check must fail",
        "e01p_relation": "full-slide raster plan is forbidden before compile",
    },
    "screenshot_like": {
        "default_severity": "fatal",
        "blocks_product_pass": True,
        "recommended_patch_class": "PATCH_RENDER_FIDELITY",
        "required_evidence": ["dominant media object"],
        "b03_relation": "screenshot-like slide is not product pass",
        "e01p_relation": "screenshot targetability cannot pass",
    },
    "chart_raster_fallback": {
        "default_severity": "fatal",
        "blocks_product_pass": True,
        "recommended_patch_class": "PATCH_CHART_NATIVE_RECONSTRUCTION",
        "required_evidence": ["chart region bbox", "native/chart ledger"],
        "b03_relation": "chart must be native or editable shape chart",
        "e01p_relation": "chart target must be native/editable, not raster",
    },
    "table_raster_fallback": {
        "default_severity": "fatal",
        "blocks_product_pass": True,
        "recommended_patch_class": "PATCH_TABLE_NATIVE_RECONSTRUCTION",
        "required_evidence": ["table region bbox", "native/table ledger"],
        "b03_relation": "table must be native or editable shape grid",
        "e01p_relation": "table target must be native/editable, not raster",
    },
    "native_plate_flatness": {
        "default_severity": "warning",
        "blocks_product_pass": False,
        "recommended_patch_class": "PATCH_NATIVE_PLATE_STYLE",
        "required_evidence": ["plate bbox", "render/reference comparison"],
        "b03_relation": "native cover shape may pass editability with visual limitation",
        "e01p_relation": "suppression shape targetability must remain valid",
    },
    "visual_geometry_drift": {
        "default_severity": "warning",
        "blocks_product_pass": False,
        "recommended_patch_class": "PATCH_OBJECT_BBOX",
        "required_evidence": ["reference/render bbox comparison"],
        "b03_relation": "not an OOXML editability condition by itself",
        "e01p_relation": "object bbox should be patched at protocol level",
    },
    "color_drift": {
        "default_severity": "warning",
        "blocks_product_pass": False,
        "recommended_patch_class": "PATCH_RENDER_FIDELITY",
        "required_evidence": ["visual review"],
        "b03_relation": "visual review issue",
        "e01p_relation": "style tokens may require correction",
    },
    "low_contrast_text": {
        "default_severity": "warning",
        "blocks_product_pass": False,
        "recommended_patch_class": "PATCH_TEXT_OVERFLOW",
        "required_evidence": ["visual review"],
        "b03_relation": "may not be captured by OOXML native checks",
        "e01p_relation": "text style tokens may require correction",
    },
    "missing_slot": {
        "default_severity": "fatal",
        "blocks_product_pass": True,
        "recommended_patch_class": "PATCH_SLOT_SCHEMA",
        "required_evidence": ["slot graph"],
        "b03_relation": "missing required slot blocks product validation",
        "e01p_relation": "semantic slot graph must reject missing required slot",
    },
    "missing_bbox": {
        "default_severity": "warning",
        "blocks_product_pass": False,
        "recommended_patch_class": "PATCH_OBJECT_BBOX",
        "required_evidence": ["object/layer id"],
        "b03_relation": "limits localization",
        "e01p_relation": "protocol must carry bounded bboxes",
    },
    "z_order_mismatch": {
        "default_severity": "warning",
        "blocks_product_pass": False,
        "recommended_patch_class": "PATCH_Z_ORDER",
        "required_evidence": ["layer manifest"],
        "b03_relation": "may produce visual drift",
        "e01p_relation": "z-order policy must be deterministic",
    },
    "object_name_missing": {
        "default_severity": "info",
        "blocks_product_pass": False,
        "recommended_patch_class": "PATCH_OBJECT_BBOX",
        "required_evidence": ["OOXML object"],
        "b03_relation": "naming improves auditability",
        "e01p_relation": "stable ids improve traceability",
    },
    "low_confidence_mapping": {
        "default_severity": "warning",
        "blocks_product_pass": False,
        "recommended_patch_class": "PATCH_OBJECT_BBOX",
        "required_evidence": ["confidence score"],
        "b03_relation": "manual review required",
        "e01p_relation": "low-confidence content-bearing proposal cannot be ignored",
    },
}


def issue_definition(issue_type: str) -> dict[str, Any]:
    key = issue_type.lower()
    return ISSUE_DEFINITIONS.get(
        key,
        {
            "default_severity": "warning",
            "blocks_product_pass": False,
            "recommended_patch_class": "PATCH_RENDER_FIDELITY",
            "required_evidence": ["review evidence"],
            "b03_relation": "unknown review issue",
            "e01p_relation": "unknown protocol relation",
        },
    )


def recommended_patch_class(issue_type: str) -> str:
    return str(issue_definition(issue_type)["recommended_patch_class"])
