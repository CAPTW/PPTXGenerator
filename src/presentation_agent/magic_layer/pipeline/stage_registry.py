from __future__ import annotations

from typing import Any


STAGE_ORDER = [
    "A01_REGISTRY_CLAIM_GUARD",
    "E01P_PROTOCOL_GATE",
    "T01_TEMPLATE_CONTRACT_GATE",
    "T02_NATIVE_RECONSTRUCTION_PLANNER",
    "C01_COMPILER_DRY_RUN",
    "C02B_CONTROLLED_COMPATIBLE_COMPILE",
    "B03_PPTX_NATIVE_VALIDATION",
    "C03A_RETRY_CONTROLLED_RENDER",
    "B01_REVIEW_PACKET",
    "CLAIM_BOUNDARY_CHECK",
]


def build_stage_registry() -> dict[str, Any]:
    stages = [
        _stage("A01_REGISTRY_CLAIM_GUARD", "GOVERNANCE", "src.presentation_agent.magic_layer.registry.artifact_registry", "python scripts/pptxlocal.py registry summary", [], ["repo_state"], ["IMPORT_EXISTING", "DRY_RUN_ONLY"]),
        _stage("E01P_PROTOCOL_GATE", "PRECOMPILE_PROTOCOL", "src.presentation_agent.magic_layer.protocol.protocol_gate", "python scripts/pptxlocal.py protocol validate-group", ["A01_REGISTRY_CLAIM_GUARD"], ["protocol_validation_report"], ["IMPORT_EXISTING", "DRY_RUN_ONLY"]),
        _stage("T01_TEMPLATE_CONTRACT_GATE", "TEMPLATE_CONTRACT", "src.presentation_agent.magic_layer.template.template_contract_v1", "python scripts/pptxlocal.py template validate-group", ["E01P_PROTOCOL_GATE"], ["template_contract_report"], ["IMPORT_EXISTING", "DRY_RUN_ONLY"]),
        _stage("T02_NATIVE_RECONSTRUCTION_PLANNER", "PLANNING", "src.presentation_agent.magic_layer.planning.native_reconstruction_planner", "python scripts/pptxlocal.py planner validate-group", ["T01_TEMPLATE_CONTRACT_GATE"], ["editable_candidate_spec", "compiler_input_bundle"], ["IMPORT_EXISTING", "DRY_RUN_ONLY"]),
        _stage("C01_COMPILER_DRY_RUN", "DRY_RUN_COMPILER", "src.presentation_agent.magic_layer.compiler.compiler_skeleton", "python scripts/pptxlocal.py compiler dry-run", ["T02_NATIVE_RECONSTRUCTION_PLANNER"], ["dry_run_report", "primitive_plan"], ["IMPORT_EXISTING", "DRY_RUN_ONLY"]),
        _stage("C02B_CONTROLLED_COMPATIBLE_COMPILE", "COMPILE", "src.presentation_agent.magic_layer.compiler.real_compile.minimal_compile", "python scripts/pptxlocal.py compiler controlled-compatibility-test", ["C01_COMPILER_DRY_RUN"], ["controlled_minimal_editable_candidate_c02b.pptx"], ["IMPORT_EXISTING"]),
        _stage("B03_PPTX_NATIVE_VALIDATION", "POST_COMPILE_VALIDATION", "src.presentation_agent.magic_layer.gates.pptx_native_validation_gate", "python scripts/pptxlocal.py pptx validate-native", ["C02B_CONTROLLED_COMPATIBLE_COMPILE"], ["patched_pptx_b03_validation_report"], ["IMPORT_EXISTING", "DRY_RUN_ONLY"]),
        _stage("C03A_RETRY_CONTROLLED_RENDER", "RENDER", "src.presentation_agent.magic_layer.render.controlled_render_workflow", "python scripts/pptxlocal.py render controlled-retry", ["B03_PPTX_NATIVE_VALIDATION"], ["controlled_minimal_c02b_rendered_slide.png"], ["IMPORT_EXISTING"]),
        _stage("B01_REVIEW_PACKET", "VISUAL_REVIEW", "src.presentation_agent.magic_layer.review.review_workbench", "python scripts/pptxlocal.py review build-packet", ["C03A_RETRY_CONTROLLED_RENDER"], ["controlled_retry_b01_review_packet"], ["IMPORT_EXISTING", "DRY_RUN_ONLY"]),
        _stage("CLAIM_BOUNDARY_CHECK", "CLAIM_BOUNDARY", "src.presentation_agent.magic_layer.pipeline.pipeline_boundary", "python scripts/pptxlocal.py pipeline gate-rollup", ["B01_REVIEW_PACKET"], ["claim_verification", "scaleout_lock"], ["IMPORT_EXISTING", "DRY_RUN_ONLY"]),
    ]
    return {"schema": "pipeline_stage_registry.v1", "stages": stages, "stage_count": len(stages), "product_pass": False}


def stage_ids(registry: dict[str, Any] | None = None) -> set[str]:
    reg = registry or build_stage_registry()
    return {stage["stage_id"] for stage in reg["stages"]}


def _stage(stage_id: str, stage_type: str, module: str, cli: str, inputs: list[str], outputs: list[str], modes: list[str]) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "stage_type": stage_type,
        "implementation_module": module,
        "cli_command": cli,
        "required_inputs": inputs,
        "expected_outputs": outputs,
        "forbidden_outputs": ["new_pptx", "new_render", "reference_image", "source_bound_deck", "canonical_artifact"],
        "gate_conditions": ["product_pass_false", "scaleout_lock_closed"],
        "allowed_modes": modes,
        "product_pass_claim_allowed": False,
        "unlocks_next_stage": stage_id not in {"CLAIM_BOUNDARY_CHECK"},
        "cannot_unlock": ["E03", "E04", "D08", "C11", "bulk", "canonical_promotion"],
        "evidence_paths": [],
        "limitations": ["controlled_minimal_scope_only"],
    }
