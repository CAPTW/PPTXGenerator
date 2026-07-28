from __future__ import annotations

from typing import Any


def validate_planner_inputs(inputs: dict[str, Any], sample_mode: bool = False) -> dict[str, Any]:
    failures: list[str] = []
    for field in ("template_contract", "slot_schema"):
        if not inputs.get(field):
            failures.append(f"{field} is required")
    if not sample_mode:
        for field in ("object_graph", "layer_manifest", "semantic_slot_graph"):
            if not inputs.get(field):
                failures.append(f"{field} is required unless sample_mode is true")
    evidence_paths = [str(path).lower() for path in inputs.get("evidence_paths", [])]
    if any("manual_review" in path or "manual-review" in path for path in evidence_paths):
        failures.append("manual-review artifacts cannot support planner inputs")
    if any("quarantine" in path or "__quarantine" in path for path in evidence_paths):
        failures.append("quarantined artifacts cannot support planner inputs")
    return {"schema": "planner_input_validation.v1", "pass": not failures, "failures": failures, "sample_mode": sample_mode}
