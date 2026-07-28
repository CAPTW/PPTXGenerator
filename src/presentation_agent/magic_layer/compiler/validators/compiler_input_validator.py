from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.compiler.asset_policy import evaluate_asset_policy
from src.presentation_agent.magic_layer.compiler.compile_blocker import detect_compile_blockers
from src.presentation_agent.magic_layer.planning.validators.compiler_input_bundle_validator import validate_compiler_input_bundle


def validate_compiler_input(bundle: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    bundle_validation = validate_compiler_input_bundle(bundle)
    if not bundle_validation["pass"]:
        failures.extend(bundle_validation["failures"])
    for asset in bundle.get("asset_manifest", []):
        asset_result = evaluate_asset_policy(asset)
        if not asset_result["pass"]:
            failures.append(f"{asset.get('asset_id', 'asset')}: {asset_result['decision']}")
    blockers = detect_compile_blockers(
        {
            "objects": bundle.get("editable_candidate_spec", {}).get("objects", []),
            "expected_outputs": bundle.get("expected_outputs", []),
            "downstream_gates": bundle.get("downstream_gates", []),
        }
    )
    if not blockers["pass"]:
        failures.extend(item["blocker_type"] for item in blockers["blockers"])
    return {"schema": "compiler_input_validation.v1", "pass": not failures, "failures": failures, "bundle_validation": bundle_validation, "blockers": blockers}
