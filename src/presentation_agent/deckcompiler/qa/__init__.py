"""Independent Phase 6 quality gates and current-output evidence contracts."""

from .composite import (
    CompositeQAError,
    CompositeQAResult,
    bind_external_visual_reconciliation,
    composite_acceptance_status,
    run_composite_qa,
    validate_composite_qa,
)
from .evidence_capsule import (
    EVIDENCE_PREREQUISITE_DAG,
    EvidenceCapsuleError,
    bind_current_output_evidence,
    build_evidence_capsule,
    materialize_per_slide_crop_evidence,
    reconcile_external_visual_qa,
    require_baseline_reachability,
    seal_reconstruction_scores,
)
from .external_visual_qa import (
    ExternalVisualQAError,
    build_external_visual_qa_reconciliation,
    parse_external_visual_qa,
    validate_resolution_record,
    verify_bound_report_hash,
)

__all__ = [
    "CompositeQAError",
    "CompositeQAResult",
    "EVIDENCE_PREREQUISITE_DAG",
    "EvidenceCapsuleError",
    "ExternalVisualQAError",
    "bind_external_visual_reconciliation",
    "bind_current_output_evidence",
    "build_evidence_capsule",
    "build_external_visual_qa_reconciliation",
    "composite_acceptance_status",
    "materialize_per_slide_crop_evidence",
    "parse_external_visual_qa",
    "reconcile_external_visual_qa",
    "require_baseline_reachability",
    "run_composite_qa",
    "seal_reconstruction_scores",
    "validate_resolution_record",
    "validate_composite_qa",
    "verify_bound_report_hash",
]
