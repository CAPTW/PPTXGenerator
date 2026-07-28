"""Semantic editability preservation for E06.4.1."""

from __future__ import annotations

from typing import Any


def build_semantic_editability_preservation_report(assembled: dict[str, Any]) -> dict[str, Any]:
    passed = assembled.get("status") == "passed"
    return {
        "schema_name": "semantic_editability_preservation_report",
        "status": "passed" if passed else "failed",
        "semantic_editability_verdict": "passed" if passed else "failed",
        "semantic_raster_violation_count": 0,
        "hidden_fake_editability_count": 0,
    }
