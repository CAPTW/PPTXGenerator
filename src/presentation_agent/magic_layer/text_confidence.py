"""Confidence policies and D01 calibration helpers for D02."""

from __future__ import annotations

from typing import Any


def low_confidence_report(candidates: list[dict[str, Any]], slot_map: dict[str, Any]) -> dict[str, Any]:
    mapping_by_candidate: dict[str, dict[str, Any]] = {}
    for mapping in slot_map.get("mappings") or []:
        for candidate_id in mapping.get("source_candidate_ids") or []:
            mapping_by_candidate[candidate_id] = mapping
    findings = []
    for candidate in candidates:
        mapping = mapping_by_candidate.get(candidate["candidate_id"], {})
        if candidate.get("low_confidence") or mapping.get("disposition") == "mapped_low_confidence_review":
            severity = "blocking" if candidate.get("content_bearing") and mapping.get("slot_type") == "unknown_text" else "review"
            findings.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "slot_type": mapping.get("slot_type", "unknown_text"),
                    "confidence": candidate.get("confidence"),
                    "severity": severity,
                    "reason": candidate.get("disposition"),
                }
            )
    return {
        "schema_name": "low_confidence_text_report",
        "status": "blocking" if any(item["severity"] == "blocking" for item in findings) else "passed_with_reviews" if findings else "passed",
        "low_confidence_count": len(findings),
        "findings": findings,
    }


def unresolved_text_report(candidates: list[dict[str, Any]], slot_map: dict[str, Any]) -> dict[str, Any]:
    unresolved = []
    mapping_by_candidate: dict[str, dict[str, Any]] = {}
    for mapping in slot_map.get("mappings") or []:
        for candidate_id in mapping.get("source_candidate_ids") or []:
            mapping_by_candidate[candidate_id] = mapping
    for candidate in candidates:
        mapping = mapping_by_candidate.get(candidate["candidate_id"])
        if mapping is None or "blocking" in str(mapping.get("disposition")):
            unresolved.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "candidate_type": candidate.get("candidate_type"),
                    "content_bearing": candidate.get("content_bearing"),
                    "reason": "missing_slot_mapping" if mapping is None else mapping.get("disposition"),
                    "disposition": "blocking" if candidate.get("content_bearing") else "bounded_non_content",
                }
            )
    return {
        "schema_name": "unresolved_text_region_report",
        "status": "blocking" if any(item["disposition"] == "blocking" for item in unresolved) else "passed",
        "unresolved_text_region_count": len(unresolved),
        "content_bearing_unresolved_count": sum(1 for item in unresolved if item["disposition"] == "blocking"),
        "unresolved_regions": unresolved,
    }


def calibrate_d01_quality(reference_quality_reports: list[dict[str, Any]], mask_manifests: list[dict[str, Any]]) -> dict[str, Any]:
    total = max(1, len(reference_quality_reports))
    zero_text = sum(1 for report in reference_quality_reports if _score(report, "text_region_detection_coverage") == 0)
    zero_chart = sum(1 for report in reference_quality_reports if _score(report, "chart_table_region_detection_coverage") == 0)
    mask_total = 0
    rectangular = 0
    polygon = 0
    for manifest in mask_manifests:
        for item in manifest.get("masks") or []:
            mask_total += 1
            if item.get("mask_source") == "polygon":
                polygon += 1
            else:
                rectangular += 1
    rectangular_ratio = rectangular / mask_total if mask_total else 0.0
    classifications = [
        "D01_WORKBENCH_SCAFFOLD_PASS",
        "D01_LIMITED_AUTOMATION",
        "D01_NOT_MAGIC_LAYER_PARITY",
        "D01_READY_FOR_D02_TEXT_LIFT",
    ]
    caps = []
    if zero_text:
        caps.append("text_region_detection_coverage_zero_for_some_references")
    if zero_chart:
        caps.append("chart_table_region_detection_coverage_zero_for_some_references")
    if rectangular_ratio > 0.75:
        caps.append("mask_quality_rectangular_only_or_limited")
    caps.append("reference_preview_resemblance_requires_debug_visual_review")
    return {
        "schema_name": "d01_score_calibration_report",
        "status": "calibrated_limited_automation",
        "required_classification": classifications,
        "reference_count": total,
        "zero_text_region_detection_coverage_count": zero_text,
        "zero_chart_table_region_detection_coverage_count": zero_chart,
        "mask_source_summary": {
            "mask_count": mask_total,
            "bbox_rectangular_count": rectangular,
            "polygon_count": polygon,
            "bbox_rectangular_ratio": round(rectangular_ratio, 4),
            "classification": "rectangular_only_or_limited" if rectangular_ratio > 0.75 else "mixed_mask_sources",
        },
        "score_caps_applied": caps,
        "overclaim_prevention": "D01 remains D02-ready but is not classified as full Magic Layer decomposition or semantic component decomposition.",
        "canva_parity_claimed": False,
    }


def _score(report: dict[str, Any], key: str) -> float:
    value = (report.get("scores") or {}).get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0
