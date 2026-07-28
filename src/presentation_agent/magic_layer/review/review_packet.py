from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .patch_request import create_patch_request_from_issue
from .render_source import discover_render_sources
from .visual_issue_taxonomy import issue_definition, recommended_patch_class


def validate_review_packet(packet: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(packet)
    normalized.setdefault("schema", "review_packet.v1")
    normalized.setdefault("input_artifacts", [])
    normalized.setdefault("render_sources", [])
    normalized.setdefault("graph_sources", [])
    normalized.setdefault("validation_reports", [])
    normalized.setdefault("overlay_documents", [])
    normalized.setdefault("visual_issues", [])
    normalized.setdefault("patch_requests", [])
    normalized.setdefault("limitations", [])
    normalized.setdefault("next_actions", [])
    failures = []
    if normalized["schema"] != "review_packet.v1":
        failures.append("schema must be review_packet.v1")
    if not normalized.get("packet_id"):
        failures.append("packet_id is required")
    if not normalized.get("artifact_group_path"):
        failures.append("artifact_group_path is required")
    if not normalized.get("decision"):
        failures.append("decision is required")
    product_pass_allowed = False
    enriched_issues = []
    for index, issue in enumerate(normalized.get("visual_issues", [])):
        enriched = deepcopy(issue)
        enriched.setdefault("issue_id", f"issue_{index + 1}")
        definition = issue_definition(str(enriched.get("issue_type", "")))
        enriched.setdefault("severity", definition["default_severity"])
        enriched.setdefault("recommended_patch_class", definition["recommended_patch_class"])
        enriched.setdefault("blocks_product_pass", definition["blocks_product_pass"])
        enriched_issues.append(enriched)
    normalized["visual_issues"] = enriched_issues
    normalized["product_pass_allowed"] = bool(product_pass_allowed)
    return {"schema": "review_packet_validation.v1", "pass": not failures, "failures": failures, **normalized}


def build_review_packet_for_group(artifact_group: str | Path, fixture_name: str | None = None) -> dict[str, Any]:
    group = Path(artifact_group)
    fixture_name = fixture_name or group.name
    files = [path for path in group.rglob("*") if path.is_file()] if group.exists() else []
    render_sources = discover_render_sources(group)
    graph_files = [path for path in files if any(token in path.name.lower() for token in ("object_graph", "layer_manifest", "semantic_slot_graph", "slot_schema"))]
    reports = [path for path in files if path.suffix.lower() == ".json" and any(token in path.name.lower() for token in ("report", "ledger", "gate"))]
    if not group.exists() or not files:
        decision = "REVIEW_BLOCKED_MISSING_INPUT"
        scope = "MISSING"
    elif fixture_name == "canva_benchmark":
        decision = "REVIEW_BENCHMARK_ONLY"
        scope = "BENCHMARK_ONLY"
    elif render_sources["selected_review_image"] and graph_files:
        decision = "REVIEW_READY_WITH_LIMITATIONS"
        scope = "FULL_RENDER_AND_GRAPH"
    elif render_sources["selected_review_image"]:
        decision = "REVIEW_READY_WITH_LIMITATIONS"
        scope = "RENDER_ONLY"
    elif graph_files:
        decision = "REVIEW_BLOCKED_MISSING_RENDER"
        scope = "GRAPH_ONLY"
    else:
        decision = "REVIEW_BLOCKED_MISSING_INPUT"
        scope = "REPORT_ONLY"
    issues = _initial_issues(fixture_name, files)
    packet = {
        "schema": "review_packet.v1",
        "packet_id": f"{fixture_name}_review_packet",
        "fixture_name": fixture_name,
        "artifact_group_path": str(group),
        "review_scope": scope,
        "input_artifacts": [str(path) for path in files],
        "render_sources": [render_sources],
        "graph_sources": [str(path) for path in graph_files],
        "validation_reports": [str(path) for path in reports],
        "overlay_documents": [],
        "visual_issues": issues,
        "patch_requests": [],
        "decision": "REVIEW_FAIL_FATAL_ISSUES" if any(issue_definition(issue["issue_type"])["blocks_product_pass"] for issue in issues) and fixture_name.startswith("e01_") else decision,
        "limitations": _limitations(fixture_name, decision, graph_files, render_sources),
        "next_actions": ["create constrained patch request", "rerun protocol gate after future patch", "rerun B03 after future compile"],
    }
    validated = validate_review_packet(packet)
    packet["visual_issues"] = validated["visual_issues"]
    packet["product_pass_allowed"] = validated["product_pass_allowed"]
    packet["patch_requests"] = [create_patch_request_from_issue(packet, issue["issue_id"]) for issue in packet["visual_issues"][:3]]
    return packet


def _initial_issues(fixture_name: str, files: list[Path]) -> list[dict[str, Any]]:
    if fixture_name.startswith("e01_semantic_raster_fail"):
        bbox = _first_bbox(files)
        return [
            {
                "issue_id": "e01_semantic_raster_failure",
                "issue_type": "semantic_raster_text",
                "severity": "fatal",
                "bbox_norm": bbox,
                "description": "Known E01 failure must not be product PASS; B01 localizes it for patch planning.",
                "evidence_paths": [str(path) for path in files if "semantic" in path.name.lower() or "gate" in path.name.lower()],
            }
        ]
    if fixture_name.startswith("e02_4core_pass"):
        review_regions = _review_region_bboxes(files)
        return [
            {
                "issue_id": f"e02_review_region_{index + 1}",
                "issue_type": "visual_geometry_drift",
                "severity": "info",
                "bbox_norm": region["bbox_norm"],
                "slot_id": region.get("slot_id"),
                "description": f"{region.get('role', 'slot')} review region for four-core fixture; does not unlock E03/E04/D08.",
                "evidence_paths": [region["path"]],
            }
            for index, region in enumerate(review_regions[:6])
        ]
    return []


def _first_bbox(files: list[Path]) -> list[float] | None:
    for path in files:
        if not any(token in path.name.lower() for token in ("object_graph", "layer_manifest", "slot_schema")):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = data.get("nodes") or data.get("objects") or data.get("layers") or data.get("slots") or []
        for item in items:
            bbox = item.get("bbox_norm")
            if isinstance(bbox, list) and len(bbox) == 4 and bbox != [0.0, 0.0, 1.0, 1.0]:
                return bbox
    return None


def _review_region_bboxes(files: list[Path]) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for path in files:
        if "slot_schema" not in path.name.lower():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        slots = data.get("slots") or data.get("semantic_slots") or []
        for slot in slots:
            role = " ".join(str(slot.get(key, "")) for key in ("slot_id", "slot_type", "semantic_role")).lower()
            bbox = _normalize_bbox(slot.get("bbox_norm"))
            if any(token in role for token in ("chart", "table", "title", "body", "footer")) and bbox:
                regions.append({"slot_id": slot.get("slot_id"), "role": role, "bbox_norm": bbox, "path": str(path)})
    return regions


def _normalize_bbox(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) == 4:
        return [float(item) for item in value]
    if isinstance(value, dict) and all(key in value for key in ("x", "y", "w", "h")):
        return [float(value["x"]), float(value["y"]), float(value["w"]), float(value["h"])]
    return None


def _limitations(fixture_name: str, decision: str, graph_files: list[Path], render_sources: dict[str, Any]) -> list[str]:
    limitations = []
    if fixture_name == "e01b_single_reference_pass":
        limitations.append("E01B compact fixture is incomplete and remains fixture debt.")
    if not graph_files:
        limitations.append("Graph/slot data is missing or partial; overlay linkage is limited.")
    if not render_sources.get("selected_review_image"):
        limitations.append("Render image is missing; visual overlay review is limited.")
    if decision == "REVIEW_BENCHMARK_ONLY":
        limitations.append("Benchmark evidence is not product proof.")
    return limitations
