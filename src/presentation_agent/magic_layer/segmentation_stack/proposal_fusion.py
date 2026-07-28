"""Fuse adapter proposals into E01X fused_object_graph_v2 evidence objects."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .native_readiness import build_native_reconstruction_readiness_plan, target_for_role
from .schemas import validate_fused_object, validate_proposal
from .semantic_roles import is_semantic_role, role_prefix, vote_role
from .z_order import assign_z_order, build_z_order_graph


def fuse_proposals(
    *,
    proposals: list[dict[str, Any]],
    protected_text_zones: list[dict[str, Any]],
    ps_layers: list[dict[str, Any]],
    canva_benchmark: dict[str, Any] | None = None,
) -> dict[str, Any]:
    valid = []
    rejected = []
    for proposal in proposals:
        try:
            validate_proposal(proposal)
        except ValueError as exc:
            rejected.append({"proposal_id": proposal.get("proposal_id"), "reason": str(exc)})
            continue
        if proposal.get("gate_eligible") is True:
            valid.append(proposal)

    groups = _group_proposals(valid)
    objects = []
    votes = []
    relationships = []
    for index, grouped in enumerate(groups):
        vote = vote_role(grouped)
        role = vote["winning_role"]
        prefix = role_prefix(role)
        obj = {
            "object_id": f"{prefix}_{role}_{index + 1:03d}",
            "bbox_px": _average_bbox([item["bbox_px"] for item in grouped]),
            "bbox_norm": _average_bbox([item["bbox_norm"] for item in grouped]),
            "z_order": assign_z_order(role, index),
            "semantic_role": role,
            "content_bearing": any(item.get("content_bearing_candidate") for item in grouped),
            "editability_target": _target(grouped, role),
            "proposal_sources": [
                {
                    "proposal_id": item["proposal_id"],
                    "source_adapter": item["source_adapter"],
                    "source_type": item["source_type"],
                    "confidence": item["confidence"],
                    "evidence": item.get("evidence", []),
                }
                for item in grouped
            ],
            "warnings": _fusion_warnings(grouped, protected_text_zones, role),
        }
        validate_fused_object(obj)
        objects.append(obj)
        votes.append({"object_id": obj["object_id"], **vote})

    relationships.extend(_relationships(objects, protected_text_zones))
    z_graph = build_z_order_graph(objects)
    native_plan = build_native_reconstruction_readiness_plan(objects)
    semantic_slots = _semantic_slot_graph(objects)
    visual_graph = _visual_layer_graph(objects)
    object_graph = {
        "schema_name": "fused_object_graph_v2",
        "schema_version": "2.0",
        "objects": objects,
        "relationships": relationships,
        "protected_text_zone_count": len(protected_text_zones),
        "ps_layer_input_count": len(ps_layers),
        "canva_benchmark_facts": canva_benchmark or {},
        "rejected_proposals": rejected,
        "unknown_content_bearing_layer_count": sum(1 for obj in objects if obj["semantic_role"] == "unknown" and obj["content_bearing"]),
        "semantic_raster_violation_count": native_plan["summary"]["semantic_raster_violation_count"],
        "full_slide_raster_detected": False,
        "screenshot_slide_detected": False,
        "canva_parity_claimed": False,
    }
    report = {
        "schema_name": "proposal_fusion_report",
        "schema_version": "1.0",
        "status": "passed" if objects else "blocked_no_gate_eligible_proposals",
        "input_proposal_count": len(proposals),
        "gate_eligible_proposal_count": len(valid),
        "fused_object_count": len(objects),
        "rejected_proposal_count": len(rejected),
        "fusion_principles": [
            "model proposals are evidence",
            "fusion decides object graph",
            "native reconstruction plan decides PPTX primitive",
            "gate decides pass/fail",
        ],
        "canva_parity_claimed": False,
    }
    return {
        "fused_object_graph_v2": object_graph,
        "semantic_role_votes": {"schema_name": "semantic_role_votes", "votes": votes, "canva_parity_claimed": False},
        "semantic_slot_graph": semantic_slots,
        "visual_layer_graph": visual_graph,
        "z_order_graph": z_graph,
        "native_reconstruction_readiness_plan": native_plan,
        "proposal_fusion_report": report,
    }


def proposal_fusion_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Proposal Fusion Report",
            "",
            f"- Status: `{report['status']}`",
            f"- Input proposals: `{report['input_proposal_count']}`",
            f"- Gate-eligible proposals: `{report['gate_eligible_proposal_count']}`",
            f"- Fused objects: `{report['fused_object_count']}`",
            f"- Rejected proposals: `{report['rejected_proposal_count']}`",
            "",
            "Fusion treats model outputs as evidence only; it does not allow a model to decide the final PPTX object graph.",
            "",
            "Canva parity claimed: `False`",
        ]
    ) + "\n"


def _group_proposals(proposals: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    buckets: dict[tuple[str, tuple[int, int, int, int]], list[dict[str, Any]]] = defaultdict(list)
    for proposal in proposals:
        role = proposal.get("role_candidates", [{}])[0].get("role", "unknown")
        bbox = proposal["bbox_norm"]
        key = (role, (round(bbox["x"], 2), round(bbox["y"], 2), round(bbox["w"], 2), round(bbox["h"], 2)))
        buckets[key].append(proposal)
    return list(buckets.values())


def _target(proposals: list[dict[str, Any]], role: str) -> str:
    targets = [proposal.get("editability_target_candidate") for proposal in proposals if proposal.get("editability_target_candidate")]
    preferred = target_for_role(role)
    if preferred in targets or preferred != "reject_unknown":
        return preferred
    return targets[0] if targets else "reject_unknown"


def _average_bbox(boxes: list[dict[str, Any]]) -> dict[str, float]:
    keys = ("x", "y", "w", "h")
    return {key: round(sum(float(box[key]) for box in boxes) / len(boxes), 6) for key in keys}


def _fusion_warnings(proposals: list[dict[str, Any]], protected_text_zones: list[dict[str, Any]], role: str) -> list[str]:
    warnings: list[str] = []
    if len({proposal["source_adapter"] for proposal in proposals}) == 1:
        warnings.append("single_adapter_evidence")
    if role not in {"title_text_region", "subtitle_text_region", "body_text_region", "source_footer_strip"}:
        for proposal in proposals:
            if any(_bbox_overlap_ratio(proposal["bbox_norm"], zone["bbox_norm"]) > 0.05 for zone in protected_text_zones):
                warnings.append("overlaps_protected_text_zone")
                break
    return warnings


def _relationships(objects: list[dict[str, Any]], protected_text_zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    for obj in objects:
        for zone in protected_text_zones:
            if _bbox_overlap_ratio(obj["bbox_norm"], zone["bbox_norm"]) > 0:
                relationships.append({"type": "protects_zone", "source": zone.get("zone_id"), "target": obj["object_id"]})
    for left in objects:
        for right in objects:
            if left["object_id"] == right["object_id"]:
                continue
            overlap = _bbox_overlap_ratio(left["bbox_norm"], right["bbox_norm"])
            if overlap > 0:
                relationships.append({"type": "overlaps", "source": left["object_id"], "target": right["object_id"], "overlap_ratio": overlap})
    return relationships


def _semantic_slot_graph(objects: list[dict[str, Any]]) -> dict[str, Any]:
    slots = [
        {
            "slot_id": obj["object_id"],
            "object_id": obj["object_id"],
            "semantic_role": obj["semantic_role"],
            "bbox_norm": obj["bbox_norm"],
            "editability_target": obj["editability_target"],
            "editable_required": is_semantic_role(obj["semantic_role"]) or obj["content_bearing"],
        }
        for obj in objects
        if is_semantic_role(obj["semantic_role"]) or obj["content_bearing"]
    ]
    return {"schema_name": "semantic_slot_graph", "schema_version": "1.0", "slot_count": len(slots), "slots": slots, "canva_parity_claimed": False}


def _visual_layer_graph(objects: list[dict[str, Any]]) -> dict[str, Any]:
    layers = [obj for obj in objects if not is_semantic_role(obj["semantic_role"])]
    return {"schema_name": "visual_layer_graph", "schema_version": "1.0", "visual_layer_count": len(layers), "layers": layers, "canva_parity_claimed": False}


def _bbox_overlap_ratio(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax2 = float(a["x"]) + float(a["w"])
    ay2 = float(a["y"]) + float(a["h"])
    bx2 = float(b["x"]) + float(b["w"])
    by2 = float(b["y"]) + float(b["h"])
    ix = max(0.0, min(ax2, bx2) - max(float(a["x"]), float(b["x"])))
    iy = max(0.0, min(ay2, by2) - max(float(a["y"]), float(b["y"])))
    inter = ix * iy
    area = float(a["w"]) * float(a["h"])
    return round(inter / area, 6) if area > 0 else 0.0
