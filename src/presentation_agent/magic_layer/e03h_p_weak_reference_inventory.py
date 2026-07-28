"""Weak-reference inventory for E03H-P."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e03h_p_reference_strength_score import score_reference_strength


def build_weak_reference_inventory(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    scores = {payload["reference_id"]: score_reference_strength(payload) for payload in payloads}
    weak = [reference_id for reference_id, score in scores.items() if score["status"] != "passed"]
    return {
        "schema_name": "weak_reference_inventory_report",
        "status": "passed" if not weak else "failed",
        "reference_count": len(payloads),
        "weak_reference_count": len(weak),
        "weak_reference_ids": weak,
        "scores": scores,
        "canva_parity_claimed": False,
    }


def weak_reference_inventory_markdown(report: dict[str, Any]) -> str:
    lines = ["# Weak Reference Inventory", "", f"- Status: `{report['status']}`", f"- Weak reference count: `{report['weak_reference_count']}`", "- Broad Canva parity claimed: `False`", ""]
    for reference_id in report["weak_reference_ids"]:
        lines.append(f"- {reference_id}")
    return "\n".join(lines)
