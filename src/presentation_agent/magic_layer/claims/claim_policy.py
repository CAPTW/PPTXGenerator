from __future__ import annotations

from typing import Any


CLAIM_TYPES = [
    "CLAIM_PRODUCT_SUCCESS",
    "CLAIM_ROUTE_PROOF",
    "CLAIM_VISUAL_FIDELITY",
    "CLAIM_SEMANTIC_EDITABILITY",
    "CLAIM_NATIVE_RECONSTRUCTION",
    "CLAIM_SOURCE_BINDING",
    "CLAIM_TEMPLATE_USABILITY",
    "CLAIM_CANVA_PARITY",
    "CLAIM_MAGIC_LAYER_PLUS",
    "CLAIM_TEMPLATE_PACK_READINESS",
    "CLAIM_SOURCE_BOUND_READINESS",
    "CLAIM_SCALEOUT_READINESS",
    "CLAIM_CANONICAL_PROMOTION",
]


def classify_claim_text(text: str) -> list[str]:
    lower = text.lower()
    claims: list[str] = []
    if "magic layer+" in lower or "magic layer plus" in lower:
        claims.append("CLAIM_MAGIC_LAYER_PLUS")
    if "template pack" in lower or "12" in lower or "16" in lower:
        claims.append("CLAIM_TEMPLATE_PACK_READINESS")
    if "source-bound" in lower or "source bound" in lower:
        claims.append("CLAIM_SOURCE_BOUND_READINESS")
    if "d08" in lower or "c11" in lower or "bulk" in lower or "scaleout" in lower:
        claims.append("CLAIM_SCALEOUT_READINESS")
    if "canonical promotion" in lower or "promotion" in lower:
        claims.append("CLAIM_CANONICAL_PROMOTION")
    if "report-only" in lower or "report only" in lower:
        claims.append("CLAIM_PRODUCT_SUCCESS")
    if "quarantined" in lower:
        claims.append("CLAIM_PRODUCT_SUCCESS")
    if "e03 passed" in lower or "e03 pass" in lower:
        claims.append("CLAIM_TEMPLATE_PACK_READINESS")
    if "e02" in lower and "four" in lower:
        claims.append("CLAIM_TEMPLATE_USABILITY")
    if not claims:
        claims.append("CLAIM_ROUTE_PROOF")
    return claims


def required_evidence_for_claim(claim_type: str) -> list[str]:
    if claim_type == "CLAIM_MAGIC_LAYER_PLUS":
        return [
            "reference_image",
            "object_graph",
            "layer_manifest",
            "semantic_slot_graph",
            "native_reconstruction_plan",
            "editable_pptx",
            "rendered_candidate",
            "ooxml_or_editability_ledger",
        ]
    if claim_type == "CLAIM_SCALEOUT_READINESS":
        return ["E03_PASS", "E04_SOURCE_BOUND_PASS", "PROTECTED_UNCHANGED", "REGISTRY_CLEAN", "VALIDATION_CLI_PASS"]
    if claim_type == "CLAIM_SOURCE_BOUND_READINESS":
        return ["E03_PASS", "E04_SOURCE_BOUND_PASS"]
    if claim_type == "CLAIM_TEMPLATE_PACK_READINESS":
        return ["E03_PASS", "VALIDATION_CLI_PASS"]
    if claim_type == "CLAIM_CANONICAL_PROMOTION":
        return ["NO_MANUAL_REVIEW_DEBT", "PROTECTED_UNCHANGED", "VALIDATION_CLI_PASS"]
    return []


def blocked_reason_for_claim(claim_type: str, evidence: dict[str, Any]) -> str | None:
    if evidence.get("quarantined"):
        return "Quarantined artifacts are not active product evidence."
    if evidence.get("manual_review"):
        return "Manual-review artifacts cannot support product claims."
    if claim_type in {"CLAIM_SCALEOUT_READINESS", "CLAIM_SOURCE_BOUND_READINESS", "CLAIM_TEMPLATE_PACK_READINESS", "CLAIM_CANONICAL_PROMOTION"}:
        return "Blocked by scaleout lock and current governance policy."
    return None
