from __future__ import annotations

from pathlib import Path
from typing import Any


FIXTURE_CLASSES = {
    "r01_failure_analysis_context": "GOVERNANCE_EVIDENCE",
    "e01_semantic_raster_fail": "DIAGNOSTIC_PROOF_FAIL_CASE",
    "e01b_single_reference_pass": "REGRESSION_FIXTURE_SINGLE_REFERENCE_PASS",
    "e02_4core_pass": "REGRESSION_FIXTURE_4CORE_TEMPLATE_PASS",
    "canva_benchmark": "BENCHMARK_EVIDENCE",
}


def register_fixture(name: str, path: str | Path, evidence_class: str) -> dict[str, Any]:
    return {
        "name": name,
        "path": str(path).replace("\\", "/"),
        "evidence_class": evidence_class,
        "claims_supported": _fixture_claims(name),
        "claims_blocked": ["CLAIM_TEMPLATE_PACK_READINESS", "CLAIM_SOURCE_BOUND_READINESS", "CLAIM_SCALEOUT_READINESS", "CLAIM_CANONICAL_PROMOTION"],
    }


def build_evidence_index(fixtures_root: Path, repo_state: dict[str, Any]) -> dict[str, Any]:
    fixtures = []
    for name, evidence_class in FIXTURE_CLASSES.items():
        path = fixtures_root / name
        fixtures.append(register_fixture(name, path, evidence_class) | {"exists": path.exists(), "file_count": sum(1 for p in path.rglob("*") if p.is_file()) if path.exists() else 0})
    return {
        "schema": "evidence_index.v1",
        "fixtures_root": str(fixtures_root).replace("\\", "/"),
        "fixtures": fixtures,
        "quarantine_excluded": True,
        "manual_review_not_product_evidence": True,
    }


def fixture_supports_claim(fixture: dict[str, Any], claim_type: str) -> bool:
    name = fixture.get("name", "")
    return claim_type in _fixture_claims(name)


def _fixture_claims(name: str) -> list[str]:
    if name == "e01_semantic_raster_fail":
        return ["CLAIM_SEMANTIC_EDITABILITY"]
    if name == "e01b_single_reference_pass":
        return ["CLAIM_MAGIC_LAYER_PLUS", "CLAIM_SEMANTIC_EDITABILITY", "CLAIM_NATIVE_RECONSTRUCTION"]
    if name == "e02_4core_pass":
        return ["CLAIM_TEMPLATE_USABILITY", "CLAIM_SEMANTIC_EDITABILITY", "CLAIM_NATIVE_RECONSTRUCTION"]
    if name == "canva_benchmark":
        return ["CLAIM_CANVA_PARITY"]
    if name == "r01_failure_analysis_context":
        return ["CLAIM_ROUTE_PROOF"]
    return []
