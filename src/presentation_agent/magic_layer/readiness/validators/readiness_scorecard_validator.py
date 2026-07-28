from __future__ import annotations

from typing import Any


def validate_readiness_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    label = scorecard.get("readiness_label") or scorecard.get("decision")
    failures = scorecard.get("failures", [])
    return {"schema": "readiness_scorecard_validator.v1", "pass": bool(label) and not failures, "label": label, "failures": failures, "product_pass": False}
