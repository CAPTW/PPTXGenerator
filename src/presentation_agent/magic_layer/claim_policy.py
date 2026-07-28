"""E00-RX artifact claim verification helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence


REQUIRED_MAGIC_LAYER_PLUS_ARTIFACTS = {
    "reference_image": ("reference_image.png",),
    "reference_analysis_report": ("reference_analysis_report.json", "reference_analysis_report.md"),
    "object_graph": ("object_graph_v1.json",),
    "layer_manifest": ("layer_manifest_v5.json",),
    "semantic_slot_graph": ("semantic_slot_graph.json",),
    "visual_layer_graph": ("visual_layer_graph.json",),
    "object_bbox_ledger": ("object_bbox_ledger.json",),
    "polygon_mask_ledger": ("polygon_mask_ledger.json",),
    "z_order_ledger": ("z_order_ledger.json",),
    "text_region_ledger": ("text_region_ledger.json",),
    "image_field_ledger": ("image_field_ledger.json",),
    "icon_region_ledger": ("icon_region_ledger.json",),
    "chart_table_region_ledger": ("chart_table_region_ledger.json",),
    "native_reconstruction_plan": ("native_reconstruction_plan.json",),
    "editable_candidate_spec": ("editable_candidate_spec.json",),
    "editable_candidate_pptx": ("editable_candidate.pptx",),
    "rendered_candidate": ("rendered_candidate.png",),
    "reference_vs_render": ("reference_vs_render.png",),
    "visual_similarity_metrics": ("visual_similarity_metrics.json",),
    "semantic_editability_ledger": ("semantic_editability_ledger.json",),
    "semantic_raster_violation_report": ("semantic_raster_violation_report.json",),
    "unknown_layer_report": ("unknown_layer_report.json",),
    "canva_plus_gate_report": ("canva_plus_gate_report.json",),
}


def classify_claim(claim_text_or_dict: str | Mapping[str, Any]) -> str:
    text = _claim_text(claim_text_or_dict)
    if "magic layer+" in text or "magic_layer_plus" in text:
        return "CLAIM_MAGIC_LAYER_PLUS"
    if "canva" in text and "parity" in text:
        return "CLAIM_CANVA_PARITY"
    if "scaleout" in text or "large deck" in text or "d08" in text:
        return "CLAIM_SCALEOUT_READINESS"
    if "source-bound" in text or "source_bound" in text or "source binding" in text:
        return "CLAIM_SOURCE_BINDING"
    if "editable" in text or "editability" in text:
        return "CLAIM_EDITABILITY"
    if "visual" in text or "fidelity" in text or "render" in text:
        return "CLAIM_VISUAL_FIDELITY"
    return "CLAIM_ROUTE_PROOF"


def verify_magic_layer_plus_claim(evidence_paths: Mapping[str, Any] | Sequence[str | Path]) -> dict[str, Any]:
    evidence = _normalize_evidence(evidence_paths)
    missing = _missing_required(evidence)
    failures: list[str] = []

    if missing:
        failures.append("missing_required_artifacts")
    if _truthy(evidence, "full_slide_raster") or _truthy(evidence, "full_slide_reference_background"):
        failures.append("full_slide_raster")
    if _truthy(evidence, "screenshot_slide"):
        failures.append("screenshot_slide")
    if _int_value(evidence, "semantic_raster_violations", "semantic_raster_violation_count") > 0:
        failures.append("semantic_raster")
    if _int_value(evidence, "unknown_content_bearing_layers", "unknown_content_bearing_layer_count") > 0:
        failures.append("unknown_content_bearing_layer")
    if evidence.get("semantic_text_editable") is False:
        failures.append("semantic_text_not_editable")
    if evidence.get("protected_artifacts_unchanged") is False:
        failures.append("protected_artifacts_changed")

    status = "VERIFIED" if not missing and not failures else _blocked_status(missing, failures)
    return {
        "claim_type": "CLAIM_MAGIC_LAYER_PLUS",
        "status": status,
        "missing_required_artifacts": missing,
        "failures": failures,
        "can_claim_magic_layer_plus": status == "VERIFIED",
    }


def verify_canva_parity_claim(evidence_paths: Mapping[str, Any] | Sequence[str | Path]) -> dict[str, Any]:
    result = verify_magic_layer_plus_claim(evidence_paths)
    result["claim_type"] = "CLAIM_CANVA_PARITY"
    result["can_claim_canva_parity"] = result["status"] == "VERIFIED"
    return result


def reject_report_only_claim(claim: str | Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_type": classify_claim(claim),
        "status": "REPORT_ONLY",
        "can_claim_product_success": False,
        "reason": "A report cannot prove itself without referenced object graph, PPTX, render, and editability ledgers.",
    }


def _claim_text(claim_text_or_dict: str | Mapping[str, Any]) -> str:
    if isinstance(claim_text_or_dict, Mapping):
        return " ".join(str(v) for v in claim_text_or_dict.values()).lower()
    return str(claim_text_or_dict).lower()


def _normalize_evidence(evidence_paths: Mapping[str, Any] | Sequence[str | Path]) -> dict[str, Any]:
    if isinstance(evidence_paths, Mapping):
        normalized = {str(k): v for k, v in evidence_paths.items()}
        artifacts = normalized.get("artifacts")
        if isinstance(artifacts, Sequence) and not isinstance(artifacts, (str, bytes)):
            for item in artifacts:
                _add_path_marker(normalized, item)
        return normalized
    normalized: dict[str, Any] = {}
    for item in evidence_paths:
        _add_path_marker(normalized, item)
    return normalized


def _add_path_marker(evidence: dict[str, Any], item: str | Path) -> None:
    name = Path(str(item).replace("\\", "/")).name
    lower_name = name.lower()
    for key, accepted_names in REQUIRED_MAGIC_LAYER_PLUS_ARTIFACTS.items():
        if lower_name in accepted_names:
            evidence[key] = str(item)


def _missing_required(evidence: Mapping[str, Any]) -> list[str]:
    return [key for key in REQUIRED_MAGIC_LAYER_PLUS_ARTIFACTS if not evidence.get(key)]


def _truthy(evidence: Mapping[str, Any], *keys: str) -> bool:
    return any(evidence.get(key) is True for key in keys)


def _int_value(evidence: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        if key in evidence:
            try:
                return int(evidence[key])
            except (TypeError, ValueError):
                return 1
    return 0


def _blocked_status(missing: list[str], failures: list[str]) -> str:
    if "semantic_raster" in failures:
        return "CONTRADICTED"
    if "full_slide_raster" in failures or "screenshot_slide" in failures:
        return "CONTRADICTED"
    if "unknown_content_bearing_layer" in failures:
        return "CONTRADICTED"
    if missing:
        if any("ledger" in item or "report" in item for item in missing):
            return "BLOCKED_BY_MISSING_LEDGER"
        return "INSUFFICIENT_EVIDENCE"
    return "OVERCLAIMED"
