"""Resolve semantic icon intents to existing SVG assets."""

from __future__ import annotations

from typing import Any


INTENT_SPECS: list[dict[str, Any]] = [
    {"intent": "checklist_plan_prepare", "required": True, "keywords": ["checklist_step_01_clipboard", "clipboard_check", "clipboard", "checklist"]},
    {"intent": "checklist_set_up_secure", "required": True, "keywords": ["checklist_step_02_valve", "valve", "secure", "lock", "shield"]},
    {"intent": "checklist_execute_monitor", "required": True, "keywords": ["checklist_step_03_gauge", "gauge", "monitor"]},
    {"intent": "checklist_verify_confirm", "required": True, "keywords": ["checklist_step_04_shield", "shield_check", "verify", "confirm", "shield"]},
    {"intent": "checklist_complete_record", "required": True, "keywords": ["checklist_step_05_document_pencil", "document_pencil", "record", "file", "document"]},
    {"intent": "safety_wear_ppe", "required": True, "keywords": ["bottom_hardhat_ppe", "hardhat", "ppe", "helmet", "warning_ppe"]},
    {"intent": "safety_zero_leak_zero_spill", "required": True, "keywords": ["bottom_lock_zero_leak", "zero_leak", "lock", "drop"]},
    {"intent": "safety_respect_chemical_barrier", "required": True, "keywords": ["bottom_chemical_barrier_shield", "chemical_barrier", "barrier", "shield"]},
    {"intent": "safety_communicate_confirm", "required": True, "keywords": ["bottom_communicate_chat", "communicate", "chat", "message"]},
    {"intent": "safety_teamwork", "required": True, "keywords": ["bottom_teamwork_users", "teamwork", "users", "team"]},
    {"intent": "process_intake", "required": True, "keywords": ["clipboard_check", "intake", "clipboard"]},
    {"intent": "process_triage", "required": True, "keywords": ["gauge", "triage", "priority"]},
    {"intent": "process_build", "required": True, "keywords": ["process_node", "build", "tool", "settings"]},
    {"intent": "process_review", "required": True, "keywords": ["shield_check", "review", "check"]},
    {"intent": "process_handoff", "required": True, "keywords": ["next_action", "handoff", "arrow_right", "arrow"]},
    {"intent": "dashboard_kpi_readiness", "required": True, "keywords": ["kpi", "readiness", "gauge", "chart_bar"]},
    {"intent": "dashboard_kpi_risk", "required": True, "keywords": ["risk_status", "risk", "alert_triangle", "alert"]},
    {"intent": "table_matrix_header_marker", "required": True, "keywords": ["table", "matrix", "header"]},
    {"intent": "toc_current_marker", "required": True, "keywords": ["route", "current", "bookmark", "navigation"]},
    {"intent": "roadmap_milestone", "required": True, "keywords": ["milestone_flag", "flag", "milestone"]},
    {"intent": "evidence_marker", "required": True, "keywords": ["evidence_trace", "evidence", "citation", "document"]},
    {"intent": "generic_check", "required": True, "keywords": ["check", "circle_check", "shield_check"]},
    {"intent": "generic_arrow", "required": True, "keywords": ["arrow_right", "arrow"]},
    {"intent": "generic_chevron", "required": True, "keywords": ["chevron_right", "chevron"]},
]


def build_semantic_icon_intent_catalog(limit_required: int | None = None) -> dict[str, Any]:
    specs = INTENT_SPECS[:limit_required] if limit_required is not None else INTENT_SPECS
    intents = {
        spec["intent"]: {
            "semantic_intent": spec["intent"],
            "required": spec["required"],
            "preferred_keywords": spec["keywords"],
            "forbidden_resolution": ["empty_circle", "procedural_placeholder", "raster_png"],
        }
        for spec in specs
    }
    return {
        "schema_name": "semantic_icon_intent_catalog",
        "status": "passed",
        "required_intent_count": sum(1 for spec in specs if spec["required"]),
        "intents": intents,
        "canva_parity_claimed": False,
    }


def resolve_semantic_icon_intents(catalog: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    assets = registry.get("assets", [])
    resolutions: dict[str, dict[str, Any]] = {}
    unresolved_required = 0
    for intent, spec in catalog.get("intents", {}).items():
        selected, candidates = _select_asset(spec, assets)
        if selected is None:
            if spec.get("required", False):
                unresolved_required += 1
            resolutions[intent] = {
                "selected_svg_asset_id": None,
                "selected_source_path": None,
                "confidence": 0.0,
                "match_reason": "unresolved",
                "rejected_candidates": candidates[:5],
                "fallback_allowed": False,
                "fallback_reason": "required semantic icon has no suitable SVG asset",
            }
            continue
        confidence = selected["_score"]
        resolutions[intent] = {
            "selected_svg_asset_id": selected["asset_id"],
            "selected_source_path": selected["source_path"],
            "selected_sha256": selected["sha256"],
            "confidence": min(1.0, confidence),
            "match_reason": selected["_reason"],
            "rejected_candidates": [row for row in candidates if row["asset_id"] != selected["asset_id"]][:5],
            "fallback_allowed": False,
            "fallback_reason": "source SVG resolved; raster/procedural fallback forbidden",
        }
    return {
        "schema_name": "semantic_to_svg_resolution_map",
        "status": "passed" if unresolved_required == 0 else "failed",
        "resolution_count": len(resolutions),
        "unresolved_required_count": unresolved_required,
        "resolutions": resolutions,
        "canva_parity_claimed": False,
    }


def _select_asset(spec: dict[str, Any], assets: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    candidates = []
    preferred = [keyword.lower() for keyword in spec.get("preferred_keywords", [])]
    for asset in assets:
        asset_id = asset.get("asset_id", "").lower()
        normalized_source = asset.get("source_path", "").replace("\\", "/").lower().replace("-", "_")
        haystack = " ".join(
            [
                asset.get("asset_id", ""),
                asset.get("source_path", ""),
                asset.get("filename", ""),
                " ".join(asset.get("semantic_tags", [])),
            ]
        ).lower().replace("-", "_")
        score = 0.0
        reason = "no keyword match"
        for index, keyword in enumerate(preferred):
            if keyword and keyword in haystack:
                score = max(score, 1.0 - min(index, 8) * 0.055)
                reason = f"matched keyword '{keyword}'"
                if keyword in asset_id or f"/{keyword}.svg" in normalized_source:
                    score += 0.2
        if score > 0:
            if "assets/icons/curated" in asset.get("source_path", "").replace("\\", "/"):
                score += 0.08
            if asset.get("native_path_conversion_supported"):
                score += 0.04
            candidates.append({**asset, "_score": min(score, 1.0), "_raw_score": score, "_reason": reason})
    candidates.sort(key=lambda row: (-row["_raw_score"], row["source_path"]))
    return (candidates[0] if candidates else None), [
        {
            "asset_id": row["asset_id"],
            "source_path": row["source_path"],
            "confidence": row["_score"],
            "match_reason": row["_reason"],
        }
        for row in candidates
    ]
