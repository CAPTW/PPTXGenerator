"""SVG01 gate decision logic."""

from __future__ import annotations

from typing import Any


def build_svg01_gate_report(
    *,
    svg_library_discovered: bool,
    unresolved_required_count: int,
    smoke_test_created: bool,
    smoke_test_rendered: bool,
    package_proof_passed: bool,
    semantic_icon_raster_fallback_count: int,
    empty_circle_placeholder_count: int,
    procedural_native_without_source_count: int,
    e01hp_probe_passed: bool,
    e03hp_probe_passed: bool,
    protected_artifacts_unchanged: bool,
) -> dict[str, Any]:
    failures = []
    if not protected_artifacts_unchanged:
        failures.append("protected_artifacts_changed")
    if not svg_library_discovered:
        failures.append("no_svg_library_found")
    if unresolved_required_count:
        failures.append("unresolved_required_semantic_icons")
    if not smoke_test_created:
        failures.append("smoke_test_not_created")
    if not smoke_test_rendered:
        failures.append("smoke_test_not_rendered")
    if not package_proof_passed:
        failures.append("package_proof_failed")
    if semantic_icon_raster_fallback_count:
        failures.append("semantic_icon_raster_fallback")
    if empty_circle_placeholder_count:
        failures.append("empty_circle_placeholder")
    if procedural_native_without_source_count:
        failures.append("procedural_native_without_source_svg_asset_id")
    if not e01hp_probe_passed:
        failures.append("e01hp_rebinding_probe_failed")
    if not e03hp_probe_passed:
        failures.append("e03hp_rebinding_probe_failed")
    decision = _decision(failures)
    return {
        "schema_name": "svg01_gate_report",
        "status": "passed" if not failures else "failed",
        "decision": decision,
        "failures": failures,
        "svg_library_discovered": svg_library_discovered,
        "unresolved_required_count": unresolved_required_count,
        "smoke_test_created": smoke_test_created,
        "smoke_test_rendered": smoke_test_rendered,
        "package_proof_passed": package_proof_passed,
        "semantic_icon_raster_fallback_count": semantic_icon_raster_fallback_count,
        "empty_circle_placeholder_count": empty_circle_placeholder_count,
        "procedural_native_without_source_svg_asset_id_count": procedural_native_without_source_count,
        "e01hp_probe_passed": e01hp_probe_passed,
        "e03hp_probe_passed": e03hp_probe_passed,
        "protected_artifacts_unchanged": protected_artifacts_unchanged,
        "e03h_p2_unlocked": not failures,
        "e04h_unlocked": False,
        "e05_unlocked": False,
        "canva_parity_claimed": False,
    }


def _decision(failures: list[str]) -> str:
    if not failures:
        return "SVG01_PASS_READY_FOR_E03H_P2_SVG_REBINDING_PATCH"
    if "protected_artifacts_changed" in failures:
        return "SVG01_FAIL_PROTECTED_ARTIFACTS"
    if "no_svg_library_found" in failures:
        return "SVG01_FAIL_NO_SVG_LIBRARY_FOUND"
    if "semantic_icon_raster_fallback" in failures:
        return "SVG01_FAIL_SEMANTIC_ICON_RASTER_FALLBACK"
    if "unresolved_required_semantic_icons" in failures:
        return "SVG01_PATCH_SEMANTIC_RESOLVER"
    if "package_proof_failed" in failures:
        return "SVG01_PATCH_PACKAGE_PROVENANCE"
    return "SVG01_PATCH_NATIVE_PATH_CONVERSION"
