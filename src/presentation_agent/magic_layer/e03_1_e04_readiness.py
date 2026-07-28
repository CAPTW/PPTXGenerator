"""Revised E04 readiness after E03.1."""

from __future__ import annotations

from typing import Any

from .e03_e04_readiness import build_e04_readiness_report


def build_e04_revised_readiness_report(archetype_gates: dict[str, dict[str, Any]], rhythm_report: dict[str, Any], *, pack_rendered: bool, protected_unchanged: bool) -> dict[str, Any]:
    report = build_e04_readiness_report(archetype_gates, rhythm_report, pack_rendered=pack_rendered, protected_unchanged=protected_unchanged)
    report["schema_name"] = "e04_revised_readiness_report"
    report["e03_1_reference_fidelity_patch_passed"] = report["e04_unlocked"]
    return report
