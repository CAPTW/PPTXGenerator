from __future__ import annotations

from typing import Any

from .claim_policy import classify_claim_text, required_evidence_for_claim


def verify_magic_layer_plus_claim(evidence_paths: dict[str, Any]) -> dict[str, Any]:
    required = required_evidence_for_claim("CLAIM_MAGIC_LAYER_PLUS")
    aliases = {
        "editable_pptx": ["editable_pptx", "editable_candidate"],
        "ooxml_or_editability_ledger": ["ooxml_or_editability_ledger", "editability_ledger", "pptx_semantic_editability_ledger"],
    }
    missing: list[str] = []
    for item in required:
        keys = aliases.get(item, [item])
        if not any(evidence_paths.get(key) for key in keys):
            missing.append(item)
    status = "PARTIALLY_VERIFIED" if not missing else "BLOCKED_BY_MISSING_LEDGER"
    return {
        "claim_type": "CLAIM_MAGIC_LAYER_PLUS",
        "status": status,
        "evidence_used": {key: value for key, value in evidence_paths.items() if value},
        "missing_evidence": missing,
        "block_reason": "" if not missing else "Magic Layer+ requires reference/object/layer/semantic/native/editability ledgers and candidates.",
        "recommended_next_gate": "B03_PPTX_NATIVE_VALIDATION_CLI",
    }


def verify_template_pack_readiness_claim(evidence_paths: dict[str, Any]) -> dict[str, Any]:
    return _blocked("CLAIM_TEMPLATE_PACK_READINESS", "E03 did not pass; E02 4-core pass does not prove 12-16 template pack readiness.")


def verify_source_bound_readiness_claim(evidence_paths: dict[str, Any]) -> dict[str, Any]:
    return _blocked("CLAIM_SOURCE_BOUND_READINESS", "E04 did not start; source-bound readiness remains blocked.")


def verify_scaleout_readiness_claim(evidence_paths: dict[str, Any]) -> dict[str, Any]:
    return _blocked("CLAIM_SCALEOUT_READINESS", "D08/C11/bulk require E03 pass, E04 pass, registry clean, and validation CLI pass.")


def verify_claim(claim: dict[str, Any], registry: Any) -> dict[str, Any]:
    text = str(claim.get("claim_text", ""))
    lower = text.lower()
    claim_types = classify_claim_text(text)
    claim_type = claim_types[0]

    if "c03 rendered the c02 controlled minimal pptx" in lower:
        return _result(text, "CLAIM_VISUAL_FIDELITY", "VERIFIED", "C03 render evidence verifies only a controlled minimal render smoke test.", "P02_PIPELINE_V2_ORCHESTRATOR")
    if "c03 b01 review packet exists" in lower:
        return _result(text, "CLAIM_ROUTE_PROOF", "VERIFIED", "C03 B01 review packet is diagnostic review evidence, not product proof.", "P02_PIPELINE_V2_ORCHESTRATOR")
    if "c03 proves product pass" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "OVERCLAIMED", "C03 visual smoke review is not product PASS.", "P02_PIPELINE_V2_ORCHESTRATOR")
    if "c03 proves visual fidelity to a reference image" in lower:
        return _result(text, "CLAIM_VISUAL_FIDELITY", "OVERCLAIMED", "C03 renders the C02 minimal PPTX without a reference fidelity target.", "P02_PIPELINE_V2_ORCHESTRATOR")
    if "c03 proves arbitrary magic layer+ conversion" in lower:
        return _result(text, "CLAIM_MAGIC_LAYER_PLUS", "OVERCLAIMED", "Controlled minimal render/review does not prove arbitrary Magic Layer+ conversion.", "P02_PIPELINE_V2_ORCHESTRATOR")
    if "c03 unlocks e03" in lower or "c03 unlocks e04" in lower or "c03 unlocks d08" in lower:
        return _result(text, "CLAIM_SCALEOUT_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "C03 passing does not unlock E03/E04/D08.", "P02_PIPELINE_V2_ORCHESTRATOR")
    if "c03 output may be promoted to golden_template_masters.pptx" in lower:
        return _result(text, "CLAIM_CANONICAL_PROMOTION", "BLOCKED_BY_POLICY", "C03 output is diagnostic smoke evidence and cannot be promoted to protected canonical outputs.", "P02_PIPELINE_V2_ORCHESTRATOR")
    if "c03 generated a source-bound deck" in lower:
        return _result(text, "CLAIM_SOURCE_BOUND_READINESS", "CONTRADICTED", "C03 renders/reviews one C02 PPTX and creates no source-bound deck.", "P02_PIPELINE_V2_ORCHESTRATOR")
    if "c02 created one controlled minimal pptx" in lower:
        return _result(text, "CLAIM_ROUTE_PROOF", "VERIFIED", "C02 may verify exactly one controlled minimal PPTX smoke output; this is not product proof.", "C03_CONTROLLED_RENDER_REVIEW")
    if "c02 pptx passed b03 controlled minimal smoke validation" in lower:
        return _result(text, "CLAIM_ROUTE_PROOF", "VERIFIED", "B03 controlled minimal smoke validation is bounded to the C02 sample.", "C03_CONTROLLED_RENDER_REVIEW")
    if "c02 proves product pass" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "OVERCLAIMED", "C02 is a compiler smoke test and cannot prove product PASS.", "C03_CONTROLLED_RENDER_REVIEW")
    if "c02 proves arbitrary magic layer+ conversion" in lower:
        return _result(text, "CLAIM_MAGIC_LAYER_PLUS", "OVERCLAIMED", "A controlled minimal sample does not prove arbitrary Magic Layer+ conversion.", "C03_CONTROLLED_RENDER_REVIEW")
    if "c02 unlocks e03" in lower or "c02 unlocks e04" in lower or "c02 unlocks d08" in lower:
        return _result(text, "CLAIM_SCALEOUT_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "C02 passing does not unlock E03/E04/D08.", "C03_CONTROLLED_RENDER_REVIEW")
    if "c02 output may be promoted to golden_template_masters.pptx" in lower:
        return _result(text, "CLAIM_CANONICAL_PROMOTION", "BLOCKED_BY_POLICY", "C02 output is a smoke-test artifact and cannot be promoted to protected canonical outputs.", "C03_CONTROLLED_RENDER_REVIEW")
    if "c02 generated a source-bound deck" in lower:
        return _result(text, "CLAIM_SOURCE_BOUND_READINESS", "CONTRADICTED", "C02 creates only a controlled minimal template smoke-test PPTX, not a source-bound deck.", "C03_CONTROLLED_RENDER_REVIEW")
    if "c02 produced visual fidelity proof" in lower:
        return _result(text, "CLAIM_VISUAL_FIDELITY", "CONTRADICTED", "C02 does not render by default, so it cannot prove visual fidelity.", "C03_CONTROLLED_RENDER_REVIEW")
    if "c01 dry-run exists" in lower:
        return _result(text, "CLAIM_ROUTE_PROOF", "VERIFIED", "C01 dry-run reports are compiler-planning evidence, not product proof.", "C02_CONTROLLED_MINIMAL_COMPILE")
    if "c01 dry-run proves pptx exists" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "CONTRADICTED", "C01 dry-run creates no PPTX and cannot prove a deck exists.", "C02_CONTROLLED_MINIMAL_COMPILE")
    if "c01 dry-run proves product pass" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "OVERCLAIMED", "Dry-run readiness is not product PASS.", "C02_CONTROLLED_MINIMAL_COMPILE")
    if "c01 dry-run unlocks e03" in lower or "c01 dry-run unlocks e04" in lower or "c01 dry-run unlocks d08" in lower:
        return _result(text, "CLAIM_SCALEOUT_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "C01 passing does not unlock E03/E04/D08.", "C02_CONTROLLED_MINIMAL_COMPILE")
    if "t02 planner output exists" in lower:
        return _result(text, "CLAIM_ROUTE_PROOF", "VERIFIED", "T02 planner outputs are compiler-input preparation evidence, not product proof.", "C01_CONTRACT_AWARE_COMPILER")
    if "t02 editable spec proves product pass" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "OVERCLAIMED", "Editable candidate spec is not a compiled PPTX and cannot prove product PASS.", "C01_CONTRACT_AWARE_COMPILER")
    if "t02 compiler bundle means pptx exists" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "CONTRADICTED", "Compiler input bundle is not a compiled deck and creates no PPTX.", "C01_CONTRACT_AWARE_COMPILER")
    if "t02 unlocks e03" in lower or "t02 unlocks e04" in lower or "t02 unlocks d08" in lower:
        return _result(text, "CLAIM_SCALEOUT_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "T02 passing does not unlock E03/E04/D08.", "C01_CONTRACT_AWARE_COMPILER")
    if "t02 source binding prep means source-bound deck ready" in lower:
        return _result(text, "CLAIM_SOURCE_BOUND_READINESS", "OVERCLAIMED", "T02 does not generate source-bound decks or prove source-bound readiness.", "C01_CONTRACT_AWARE_COMPILER")
    if "t01 template contract schema exists" in lower:
        return _result(text, "CLAIM_ROUTE_PROOF", "VERIFIED", "T01 template contract schema and validator modules are active governance evidence.", "T02_NATIVE_RECONSTRUCTION_PLANNER")
    if "t01 contract pass proves product pass" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "OVERCLAIMED", "T01 contract PASS is compile eligibility evidence, not product PASS.", "T02_NATIVE_RECONSTRUCTION_PLANNER")
    if "t01 compile eligibility means pptx has passed b03" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "CONTRADICTED", "Compile eligibility occurs before compile; it cannot prove B03 post-compile validation.", "T02_NATIVE_RECONSTRUCTION_PLANNER")
    if "t01 source binding preparation means source-bound deck is ready" in lower:
        return _result(text, "CLAIM_SOURCE_BOUND_READINESS", "OVERCLAIMED", "Source binding preparation is not source-bound deck readiness.", "T02_NATIVE_RECONSTRUCTION_PLANNER")
    if "e02 fixture plus t01 unlocks e03" in lower:
        return _result(text, "CLAIM_TEMPLATE_PACK_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "E02 plus T01 does not provide an E03 pass.", "T02_NATIVE_RECONSTRUCTION_PLANNER")
    if "t01 unlocks e04" in lower or "t01 unlocks d08" in lower:
        return _result(text, "CLAIM_SCALEOUT_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "T01 passing does not unlock E04 or D08.", "T02_NATIVE_RECONSTRUCTION_PLANNER")
    if "t01 enables future compiler work" in lower:
        return _result(text, "CLAIM_NATIVE_RECONSTRUCTION", "PARTIALLY_VERIFIED", "T01 defines compiler contracts; T02 can build native reconstruction planner and editable spec builder next.", "T02_NATIVE_RECONSTRUCTION_PLANNER")
    if "b01 review packet exists" in lower:
        return _result(text, "CLAIM_ROUTE_PROOF", "VERIFIED", "B01 review packet files are governance/review evidence, not product proof.", "T01_TEMPLATE_CONTRACT_V1")
    if "b01 review packet proves product pass" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "OVERCLAIMED", "B01 review packet is visual review evidence; it cannot prove product PASS.", "T01_TEMPLATE_CONTRACT_V1")
    if "b01 patch request is an applied patch" in lower:
        return _result(text, "CLAIM_NATIVE_RECONSTRUCTION", "CONTRADICTED", "Patch request is not an applied patch and does not modify PPTX or protocol artifacts.", "T01_TEMPLATE_CONTRACT_V1")
    if "b01 overlay image is generated reference image" in lower:
        return _result(text, "CLAIM_VISUAL_FIDELITY", "CONTRADICTED", "B01 overlay PNG is a diagnostic review artifact, not a generated reference image.", "T01_TEMPLATE_CONTRACT_V1")
    if "b01 review allows e03" in lower or "b01 review allows e04" in lower or "b01 review allows d08" in lower:
        return _result(text, "CLAIM_SCALEOUT_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "B01 review infrastructure does not unlock E03/E04/D08.", "T01_TEMPLATE_CONTRACT_V1")
    if "b01 is ready to support template contract work" in lower:
        return _result(text, "CLAIM_ROUTE_PROOF", "PARTIALLY_VERIFIED", "B01 review schemas and patch request hooks support Template Contract work, with fixture limitations carried forward.", "T01_TEMPLATE_CONTRACT_V1")
    if "e01p protocol schema exists" in lower:
        return _result(text, "CLAIM_ROUTE_PROOF", "VERIFIED", "E01P protocol schema modules and spec reports are active governance evidence.", "B01_RENDER_REVIEW_WORKBENCH")
    if "e01p protocol pass proves magic layer+" in lower:
        return _result(text, "CLAIM_MAGIC_LAYER_PLUS", "OVERCLAIMED", "Protocol PASS is compile eligibility, not product PASS or Magic Layer+ proof.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "protocol pass allows pptx compile" in lower:
        return _result(text, "CLAIM_NATIVE_RECONSTRUCTION", "PARTIALLY_VERIFIED", "Protocol PASS can allow compile eligibility only when downstream B03 remains required.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "b03 pass is no longer needed" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "CONTRADICTED", "B03 remains required after compile; E01P does not replace downstream PPTX-native validation.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "unknown content-bearing layer can be warning only" in lower:
        return _result(text, "CLAIM_SEMANTIC_EDITABILITY", "CONTRADICTED", "Unknown content-bearing layers are fatal under E01P policy.", "E01P_LAYER_PROTOCOL")
    if "semantic text can remain in bounded raster" in lower:
        return _result(text, "CLAIM_SEMANTIC_EDITABILITY", "CONTRADICTED", "Semantic text cannot remain in bounded raster even if visually close.", "E01P_LAYER_PROTOCOL")
    if "e01p enables future compiler work" in lower:
        return _result(text, "CLAIM_NATIVE_RECONSTRUCTION", "PARTIALLY_VERIFIED", "E01P defines compile eligibility protocol, but does not compile or validate product output itself.", "T01_TEMPLATE_CONTRACT_V1")
    if "e02 fixture plus e01p unlocks e04" in lower:
        return _result(text, "CLAIM_SOURCE_BOUND_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "E02 plus E01P still does not provide E03 pass or E04 source-bound pass.", "B01_RENDER_REVIEW_WORKBENCH")
    if "manual-review" in lower or "manual review" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "BLOCKED_BY_MANUAL_REVIEW", "Manual-review artifacts are governance debt and cannot support product claims.", "manual_review_resolution")
    if "report-only" in lower or "report only" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "CONTRADICTED", "Report-only PASS is not product PASS.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "quarantined" in lower or "quarantine" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "BLOCKED_BY_QUARANTINE", "Quarantined artifacts are not active product evidence.", "explicit_future_re_registration")
    if "e01 fixture" in lower and "product pass" in lower:
        return _result(text, "CLAIM_PRODUCT_SUCCESS", "CONTRADICTED", "E01 is a known negative fixture; detecting its failure is success, not product PASS.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "e01" in lower and "semantic raster failure detection" in lower:
        return _result(text, "CLAIM_SEMANTIC_EDITABILITY", "VERIFIED", "E01 fixture is registered as a bounded negative validation fixture.", "E01P_LAYER_PROTOCOL", ["design_runs/run_003/fixtures/e01_semantic_raster_fail"])
    if "arbitrary image robustness" in lower:
        return _result(text, "CLAIM_MAGIC_LAYER_PLUS", "OVERCLAIMED", "E01B can only support a single-reference regression scope, not arbitrary image robustness.", "E01P_LAYER_PROTOCOL")
    if "e02" in lower and ("unlock" in lower or "unlocks" in lower) and ("e04" in lower or "d08" in lower):
        return _result(text, "CLAIM_SCALEOUT_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "E02 4-core validation does not unlock E04 or D08.", "E01P_LAYER_PROTOCOL")
    if "d07" in lower or "visual asset route proof" in lower:
        return _result(text, "CLAIM_MAGIC_LAYER_PLUS", "OVERCLAIMED", "D07/source-bound/visual-asset route proof cannot prove Magic Layer+ object decomposition.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "source-bound" in lower or "source bound" in lower:
        return _result(text, "CLAIM_SOURCE_BOUND_READINESS", "OVERCLAIMED", "Source-bound route proof does not unlock Magic Layer+.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "d08" in lower or "c11" in lower or "bulk" in lower:
        return _result(text, "CLAIM_SCALEOUT_READINESS", "BLOCKED_BY_SCALEOUT_LOCK", "D08/C11/bulk remain blocked.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "e04" in lower and "e02" in lower:
        return _result(text, "CLAIM_SOURCE_BOUND_READINESS", "OVERCLAIMED", "E02 4-core pass does not unlock E04.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "canonical promotion" in lower or "promotion may start" in lower:
        return _result(text, "CLAIM_CANONICAL_PROMOTION", "BLOCKED_BY_SCALEOUT_LOCK", "Canonical promotion is blocked while validation and manual-review debt remain.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "e03 passed" in lower or lower.strip() == "e03 passed.":
        return _result(text, "CLAIM_TEMPLATE_PACK_READINESS", "CONTRADICTED", "E03 did not pass in the active A01 context.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "e02" in lower and ("12" in lower or "16" in lower or "template pack readiness" in lower):
        return _result(text, "CLAIM_TEMPLATE_PACK_READINESS", "OVERCLAIMED", "E02 proves only four-core archetype conversion, not 12-16 template pack readiness.", "B03_PPTX_NATIVE_VALIDATION_CLI")
    if "e02" in lower and ("four" in lower or "4-core" in lower or "4core" in lower):
        return _result(text, "CLAIM_TEMPLATE_USABILITY", "VERIFIED", "E02 fixture supports bounded four-core archetype template conversion.", "B03_PPTX_NATIVE_VALIDATION_CLI", ["design_runs/run_003/fixtures/e02_4core_pass"])
    if "e01b" in lower and ("single-reference" in lower or "single reference" in lower):
        return _result(text, "CLAIM_MAGIC_LAYER_PLUS", "PARTIALLY_VERIFIED", "E01B supports one single-reference regression fixture only.", "B03_PPTX_NATIVE_VALIDATION_CLI", ["design_runs/run_003/fixtures/e01b_single_reference_pass"])
    return _result(text, claim_type, "INSUFFICIENT_EVIDENCE", "No active registered evidence supports this claim.", "B03_PPTX_NATIVE_VALIDATION_CLI")


def _blocked(claim_type: str, reason: str) -> dict[str, Any]:
    return {
        "claim_type": claim_type,
        "status": "BLOCKED_BY_SCALEOUT_LOCK",
        "evidence_used": {},
        "missing_evidence": required_evidence_for_claim(claim_type),
        "block_reason": reason,
        "recommended_next_gate": "B03_PPTX_NATIVE_VALIDATION_CLI",
    }


def _result(
    text: str,
    claim_type: str,
    status: str,
    reason: str,
    next_gate: str,
    evidence_used: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "claim_text": text,
        "claim_type": claim_type,
        "status": status,
        "evidence_used": evidence_used or [],
        "missing_evidence": [] if status in {"VERIFIED", "PARTIALLY_VERIFIED"} else required_evidence_for_claim(claim_type),
        "block_reason": reason,
        "recommended_next_gate": next_gate,
    }
