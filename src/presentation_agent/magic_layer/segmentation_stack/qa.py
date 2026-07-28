"""QA report builders for E01X segmentation stack outputs."""

from __future__ import annotations

from typing import Any


def build_qa_reports(
    *,
    fused_graph: dict[str, Any],
    native_plan: dict[str, Any],
    protected_text_zones: list[dict[str, Any]],
    real_model_proposal_count: int,
    heuristic_proposal_count: int,
) -> dict[str, Any]:
    objects = fused_graph.get("objects", [])
    text_overlap_violations = _text_overlap_violations(objects, protected_text_zones)
    unknown_layers = [obj for obj in objects if obj.get("semantic_role") == "unknown" and obj.get("content_bearing")]
    semantic_raster = [
        row for row in native_plan.get("objects", []) if row.get("semantic_raster_violation")
    ]
    qa_summary = {
        "schema_name": "qa_summary",
        "object_recall_by_role": "not_available_no_ground_truth",
        "bbox_mAP_by_role": "not_available_no_ground_truth",
        "mask_iou_by_role": "not_available_no_masks_or_ground_truth",
        "boundary_f_score": "not_available_no_masks",
        "text_region_recall": "not_available_without_real_ocr_ground_truth",
        "text_region_overlap_violation_count": len(text_overlap_violations),
        "z_order_pairwise_quality": "not_available_without_ground_truth_pairs",
        "native_promotion_readiness_rate": native_plan.get("summary", {}).get("native_promotion_readiness_rate", 0),
        "unknown_content_bearing_layer_count": len(unknown_layers),
        "semantic_raster_violation_count": len(semantic_raster),
        "full_slide_raster_detected": bool(fused_graph.get("full_slide_raster_detected", False)),
        "screenshot_slide_detected": bool(fused_graph.get("screenshot_slide_detected", False)),
        "human_correction_effort_estimate": "high" if not objects else "medium",
        "render_similarity_after_reconstruction": "not_available_no_candidate_render",
        "proposal_stack_real_model_count": real_model_proposal_count,
        "proposal_stack_heuristic_only": heuristic_proposal_count > 0 and real_model_proposal_count == 0,
        "canva_parity_claimed": False,
    }
    return {
        "mask_quality_report.json": {
            "schema_name": "mask_quality_report",
            "status": "not_available",
            "mask_iou_by_role": "not_available_no_masks",
            "boundary_f_score": "not_available_no_masks",
            "canva_parity_claimed": False,
        },
        "text_lock_violation_report.json": {
            "schema_name": "text_lock_violation_report",
            "status": "passed" if not text_overlap_violations else "failed",
            "text_region_overlap_violation_count": len(text_overlap_violations),
            "violations": text_overlap_violations,
            "canva_parity_claimed": False,
        },
        "semantic_raster_violation_report.json": {
            "schema_name": "semantic_raster_violation_report",
            "status": "passed" if not semantic_raster else "failed",
            "semantic_raster_violation_count": len(semantic_raster),
            "violations": semantic_raster,
            "canva_parity_claimed": False,
        },
        "unknown_content_layer_report.json": {
            "schema_name": "unknown_content_layer_report",
            "status": "passed" if not unknown_layers else "failed",
            "unknown_content_bearing_layer_count": len(unknown_layers),
            "unknown_layers": unknown_layers,
            "canva_parity_claimed": False,
        },
        "z_order_quality_report.json": {
            "schema_name": "z_order_quality_report",
            "status": "not_available_without_ground_truth_pairs",
            "z_order_pairwise_quality": "not_available_without_ground_truth_pairs",
            "canva_parity_claimed": False,
        },
        "native_promotion_readiness_report.json": {
            "schema_name": "native_promotion_readiness_report",
            "status": "passed" if native_plan.get("summary", {}).get("native_promotion_readiness_rate", 0) == 1.0 and objects else "blocked",
            "summary": native_plan.get("summary", {}),
            "canva_parity_claimed": False,
        },
        "object_overlay_manifest.json": {
            "schema_name": "object_overlay_manifest",
            "object_count": len(objects),
            "objects": [{"object_id": obj["object_id"], "bbox_px": obj["bbox_px"], "semantic_role": obj["semantic_role"]} for obj in objects],
            "canva_parity_claimed": False,
        },
        "qa_summary": qa_summary,
    }


def qa_summary_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# QA Summary",
            "",
            f"- Text lock overlap violations: `{summary['text_region_overlap_violation_count']}`",
            f"- Unknown content-bearing layers: `{summary['unknown_content_bearing_layer_count']}`",
            f"- Semantic raster violations: `{summary['semantic_raster_violation_count']}`",
            f"- Full-slide raster detected: `{summary['full_slide_raster_detected']}`",
            f"- Screenshot slide detected: `{summary['screenshot_slide_detected']}`",
            f"- Real model proposals: `{summary['proposal_stack_real_model_count']}`",
            f"- Heuristic-only proposal stack: `{summary['proposal_stack_heuristic_only']}`",
            f"- Native promotion readiness rate: `{summary['native_promotion_readiness_rate']}`",
            "- Canva parity claimed: `False`",
        ]
    ) + "\n"


def _text_overlap_violations(objects: list[dict[str, Any]], zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    violations = []
    for obj in objects:
        if obj.get("semantic_role") in {"title_text_region", "subtitle_text_region", "body_text_region", "source_footer_strip"}:
            continue
        for zone in zones:
            overlap = _bbox_overlap_ratio(obj["bbox_norm"], zone["bbox_norm"])
            if overlap > 0.05:
                violations.append({"object_id": obj["object_id"], "zone_id": zone.get("zone_id"), "overlap_ratio": overlap})
    return violations


def _bbox_overlap_ratio(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax2 = float(a["x"]) + float(a["w"])
    ay2 = float(a["y"]) + float(a["h"])
    bx2 = float(b["x"]) + float(b["w"])
    by2 = float(b["y"]) + float(b["h"])
    ix = max(0.0, min(ax2, bx2) - max(float(a["x"]), float(b["x"])))
    iy = max(0.0, min(ay2, by2) - max(float(a["y"]), float(b["y"])))
    area = float(a["w"]) * float(a["h"])
    return round((ix * iy) / area, 6) if area > 0 else 0.0
