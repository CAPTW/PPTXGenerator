from __future__ import annotations

from typing import Any


READY = {"DRY_RUN_READY", "DRY_RUN_READY_WITH_WARNINGS"}


def build_dry_run_report(
    *,
    report_id: str,
    input_bundle_path: str | None,
    backend_capability: dict[str, Any],
    primitive_plan: dict[str, Any],
    decision: str,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    blockers = primitive_plan.get("blockers", [])
    warnings = primitive_plan.get("warnings", [])
    unsupported = primitive_plan.get("unsupported_items", [])
    primitives = primitive_plan.get("primitives", [])
    return {
        "schema": "dry_run_compile_report.v1",
        "report_id": report_id,
        "input_bundle_path": input_bundle_path,
        "input_spec_path": None,
        "backend_capability": backend_capability,
        "primitive_plan": primitive_plan,
        "primitive_plan_path": None,
        "decision": decision,
        "object_instruction_count": primitive_plan.get("object_instruction_count", len(primitives)),
        "primitive_count": len(primitives),
        "supported_count": len(primitives) - len(unsupported),
        "warning_count": len(warnings),
        "blocker_count": len(blockers),
        "unsupported_required_count": sum(1 for item in unsupported if item.get("required")),
        "unsupported_optional_count": sum(1 for item in unsupported if not item.get("required")),
        "semantic_raster_blocker_count": primitive_plan.get("semantic_raster_blocker_count", 0),
        "full_slide_raster_blocker_count": primitive_plan.get("full_slide_raster_blocker_count", 0),
        "unknown_content_bearing_blocker_count": primitive_plan.get("unknown_content_bearing_blocker_count", 0),
        "protected_output_blocker_count": primitive_plan.get("protected_output_blocker_count", 0),
        "expected_outputs": primitive_plan.get("expected_outputs", []),
        "forbidden_outputs": primitive_plan.get("forbidden_outputs", []),
        "downstream_gates": primitive_plan.get("downstream_gates", []),
        "limitations": limitations or [],
        "product_pass": False,
        "pptx_generated": False,
        "render_generated": False,
    }
