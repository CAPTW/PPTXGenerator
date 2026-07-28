"""Stage-based tool access rules for the stage-gated harness."""

from __future__ import annotations

from dataclasses import dataclass

from .stages import PipelineStage, coerce_stage


def _normalize_tool_name(tool_name: str) -> str:
    return tool_name.strip().lower().replace("-", "_").replace(" ", "_")


@dataclass(frozen=True)
class StageToolPolicy:
    allowed: frozenset[str]
    forbidden: frozenset[str]


STAGE_TOOL_ACL: dict[PipelineStage, StageToolPolicy] = {
    PipelineStage.INGEST: StageToolPolicy(
        allowed=frozenset({"file_listing", "file_reading", "metadata_extraction", "asset_classification", "ocr", "brief_intake", "fingerprinting"}),
        forbidden=frozenset({"slide_creation", "template_creation", "rendering", "slide_generation", "external_export"}),
    ),
    PipelineStage.DESIGN_REFERENCE_CHECK: StageToolPolicy(
        allowed=frozenset({"image_inspection", "pdf_inspection", "color_extraction", "typography_extraction", "layout_analysis", "asset_comparison", "workflow_planning", "reference_scan"}),
        forbidden=frozenset({"slide_generation", "content_outlining", "rendering", "external_export"}),
    ),
    PipelineStage.MASTER_TEMPLATE: StageToolPolicy(
        allowed=frozenset({"template_schema_creation", "theme_token_definition", "preview_manifest_generation", "template_bundle_write"}),
        forbidden=frozenset({"section_slide_generation", "full_deck_expansion", "rendering", "external_export"}),
    ),
    PipelineStage.CONTENT_PLAN: StageToolPolicy(
        allowed=frozenset({"content_summarization", "section_decomposition", "slide_plan_generation", "slot_mapping", "blueprint_planning", "continuity_planning"}),
        forbidden=frozenset({"design_token_changes", "template_changes", "rendering", "external_export"}),
    ),
    PipelineStage.GENERATE: StageToolPolicy(
        allowed=frozenset({"slide_spec_generation", "slide_content_generation", "section_parallel_generation", "asset_request_derivation", "document_crop_rendering", "crop_review", "structured_visual_rendering"}),
        forbidden=frozenset({"new_design_reference_selection", "template_drift", "generic_fallback_design", "external_export"}),
    ),
    PipelineStage.QA: StageToolPolicy(
        allowed=frozenset({"style_linting", "overflow_detection", "consistency_check", "evidence_check", "repair_suggestion", "preflight_render", "deck_q_audit", "continuity_orchestration"}),
        forbidden=frozenset({"template_redefinition", "final_rendering", "external_export"}),
    ),
    PipelineStage.RENDER_LOCAL_PPTX: StageToolPolicy(
        allowed=frozenset({"local_pptx_assembly", "asset_embedding", "final_validation", "render_validation", "checksum_generation"}),
        forbidden=frozenset({"wording_changes", "design_token_changes", "external_export"}),
    ),
}


def tool_allowed(stage: PipelineStage | str, tool_name: str) -> bool:
    normalized_stage = coerce_stage(stage)
    normalized_tool = _normalize_tool_name(tool_name)
    policy = STAGE_TOOL_ACL[normalized_stage]
    if normalized_tool in policy.forbidden:
        return False
    return normalized_tool in policy.allowed


def assert_tool_allowed(stage: PipelineStage | str, tool_name: str) -> None:
    normalized_stage = coerce_stage(stage)
    normalized_tool = _normalize_tool_name(tool_name)
    policy = STAGE_TOOL_ACL[normalized_stage]
    if normalized_tool in policy.forbidden:
        raise PermissionError(f"tool {normalized_tool!r} is forbidden during {normalized_stage.value}")
    if normalized_tool not in policy.allowed:
        allowed = ", ".join(sorted(policy.allowed))
        raise PermissionError(f"tool {normalized_tool!r} is not allowed during {normalized_stage.value}; allowed tools: {allowed}")
