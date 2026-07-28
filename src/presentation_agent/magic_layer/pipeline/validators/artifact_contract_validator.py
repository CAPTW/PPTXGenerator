from __future__ import annotations

from pathlib import Path
from typing import Any

from ..hash_lineage import sha256_file


def validate_artifact_contract(contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    for artifact in contract.get("artifacts", []):
        path = Path(artifact.get("path", ""))
        if artifact.get("required") and not path.is_file():
            failures.append(f"missing required artifact {artifact.get('artifact_id')}")
        expected = artifact.get("expected_hash")
        if expected and sha256_file(path) != expected:
            failures.append(f"hash mismatch {artifact.get('artifact_id')}")
        if "golden_template_masters" in str(path) or artifact.get("product_pass_allowed"):
            failures.append(f"invalid canonical/product contract {artifact.get('artifact_id')}")
    return {"schema": "artifact_contract_validation.v1", "pass": not failures, "failures": failures, "product_pass": False}
