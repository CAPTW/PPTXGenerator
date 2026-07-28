"""Core contracts for the presentation agent bootstrap phase."""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class WorkflowGate(StrEnum):
    WORKFLOW_DESIGN = "workflow-design"
    BLUEPRINT_AND_VISUAL_APPROVAL = "blueprint-and-visual-approval"
    PRODUCTION_AND_QA = "production-and-qa"


SKILL_NAMES: Final[tuple[str, ...]] = (
    "deck-orchestrator",
    "document-asset-crop",
    "structured-visuals",
    "pptx-compiler",
    "deck-qa",
)

REQUIRED_REPO_DIRS: Final[tuple[str, ...]] = (
    "src",
    "tests",
    "inputs",
    "outputs",
    "state",
    "examples",
    ".agents/skills",
)

STATE_SCHEMA_NAMES: Final[tuple[str, ...]] = (
    "workflow_plan",
    "presentation_brief",
    "canonical_generation_profile",
    "slide_function_outline",
    "blueprint",
    "proof_unit_registry",
    "proof_artifact_doctor_report",
    "proof_artifact_fleet_report",
    "proof_artifact_vnext_blocker_report",
    "authoring_preview",
    "design_system",
    "reference_dna",
    "deck_constitution",
    "layout_library",
    "slide_ledger",
    "asset_requests",
    "asset_manifest",
    "viz_spec",
    "viz_manifest",
    "batch_manifest",
    "context_lock",
    "handoff_packet",
    "state_capsule",
    "remediation_plan",
    "remediation_execution_report",
    "qa_report",
    "qa_governance",
    "upstream_fix_plan",
    "approval_packet",
    "authoring_deltas",
    "approved_apply_report",
    "closure_report",
    "remaining_backlog",
    "ship_readiness_report",
    "cycle_reset_plan",
)

COMPAT_STATE_SCHEMA_NAMES: Final[tuple[str, ...]] = (
    "proof_module_manifest",
)

STATE_ARTIFACTS: Final[tuple[str, ...]] = (
    "state/workflow-plan.json",
    "state/presentation-brief.json",
    "state/canonical-generation-profile.json",
    "state/slide-function-outline.json",
    "state/blueprint.json",
    "state/proof-unit-registry.json",
    "state/proof-artifact-doctor-report.json",
    "state/proof-artifact-fleet-report.json",
    "state/proof-artifact-vnext-blocker-report.json",
    "state/authoring-preview.json",
    "state/design-system.json",
    "state/reference-dna.json",
    "state/deck-constitution.json",
    "state/layout-library.json",
    "state/slide-ledger.json",
    "state/asset-requests.json",
    "state/asset-manifest.json",
    "state/viz-spec.json",
    "state/viz-manifest.json",
    "state/batch-manifest.json",
    "state/context-lock.json",
    "state/handoff-packet.json",
    "state/state-capsule.json",
    "state/remediation-plan.json",
    "state/remediation-execution-report.json",
    "state/qa-report.json",
    "state/qa-governance.json",
    "state/upstream-fix-plan.json",
    "state/approval-packet.json",
    "state/authoring-deltas.json",
    "state/approved-apply-report.json",
    "state/closure-report.json",
    "state/remaining-backlog.json",
    "state/ship-readiness-report.json",
    "state/cycle-reset-plan.json",
)

COMPAT_STATE_ARTIFACTS: Final[tuple[str, ...]] = (
    "state/proof-module-manifest.json",
)
