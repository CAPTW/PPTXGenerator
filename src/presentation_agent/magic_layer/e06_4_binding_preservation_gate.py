"""E06.4 binding preservation gate."""

from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.e06_2_binding_preservation_gate import build_binding_preservation_reports


def build_e06_4_binding_preservation_reports(
    source: dict[str, Any],
    citation: dict[str, Any],
    slot: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    reports = build_binding_preservation_reports(source, citation, slot, contract)
    for report in reports:
        report["stage"] = "E06.4"
        report["human_tuned_candidate_preservation"] = True
    return reports
