"""E07 readiness after E06.2.1 style/content fidelity patch."""

from __future__ import annotations

from typing import Any


def build_e07_readiness_report(
    *,
    compile_report: dict[str, Any],
    text: dict[str, Any],
    style: dict[str, Any],
    media: dict[str, Any],
    render: dict[str, Any],
    product: dict[str, Any],
    mutation: dict[str, Any],
    source: dict[str, Any],
    citation: dict[str, Any],
    slot: dict[str, Any],
    icon: dict[str, Any],
    dense: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "contract_first_v2_compile_passed": compile_report.get("status") == "passed",
        "text_content_fidelity_passed": text.get("status") == "passed",
        "style_fidelity_passed": style.get("status") == "passed",
        "media_preservation_passed": media.get("status") == "passed",
        "render_product_preservation_passed": render.get("status") == "passed" and product.get("status") == "passed",
        "mutation_smoke_test_v2_passed": mutation.get("status") == "passed",
        "source_binding_preserved": source.get("status") == "passed",
        "citation_binding_preserved": citation.get("status") == "passed",
        "slot_binding_preserved": slot.get("status") == "passed",
        "icon_system_preserved": icon.get("status") == "passed",
        "dense_readability_preserved": dense.get("status") == "passed",
        "protected_artifacts_unchanged": protected_unchanged,
    }
    passed = all(checks.values())
    return {
        "schema_name": "e07_readiness_report",
        "status": "passed" if passed else "locked",
        "decision": "E07_READY_START_BASELINE_PROMOTION_REVIEW_WITH_STYLE_CONTENT_CONTRACT" if passed else "E07_LOCKED_PENDING_E06_2_1_PATCH",
        "e07_unlocked": passed,
        "checks": checks,
        "broad_canva_parity_claimed": False,
    }


def decision_from_e07(e07: dict[str, Any], reports: list[dict[str, Any]]) -> str:
    if e07.get("e07_unlocked"):
        return "E06_2_1_PASS_START_E07_BASELINE_PROMOTION_REVIEW_WITH_STYLE_CONTENT_CONTRACT"
    by_schema = {report.get("schema_name"): report for report in reports}
    if by_schema.get("style_preservation_report", {}).get("status") != "passed":
        return "E06_2_1_PATCH_STYLE_CONTRACT_REQUIRED"
    if by_schema.get("text_content_preservation_report", {}).get("status") != "passed":
        return "E06_2_1_PATCH_TEXT_CONTENT_PRESERVATION_REQUIRED"
    if by_schema.get("media_preservation_report", {}).get("status") != "passed":
        return "E06_2_1_PATCH_MEDIA_CROP_PRESERVATION_REQUIRED"
    if by_schema.get("contract_first_recompile_v2_render_diff_report", {}).get("status") != "passed":
        return "E06_2_1_PATCH_RENDER_FIDELITY_REQUIRED"
    if by_schema.get("mutation_smoke_test_v2_report", {}).get("status") != "passed":
        return "E06_2_1_PATCH_MUTATION_SMOKE_TEST_REQUIRED"
    return "E06_2_1_PATCH_RENDER_FIDELITY_REQUIRED"
