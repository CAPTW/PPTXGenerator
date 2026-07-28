"""Fail-closed Phase 6 fault-fixture and bounded-repair contracts."""

from .fixture import (
    FaultApplication,
    FaultFixtureError,
    apply_fault_fixture,
    evaluate_fault_detection,
    validate_fault_fixture,
    verify_bound_hash,
)
from .closure import (
    INVALIDATED_ARTIFACT_IDS,
    RepairClosureError,
    build_before_after_manifest,
    build_invalidation_manifest,
    build_phase6_acceptance,
    build_repair_history,
    build_repair_plan,
    build_unified_release_gate,
)

__all__ = [
    "FaultApplication",
    "FaultFixtureError",
    "apply_fault_fixture",
    "evaluate_fault_detection",
    "validate_fault_fixture",
    "verify_bound_hash",
    "INVALIDATED_ARTIFACT_IDS",
    "RepairClosureError",
    "build_before_after_manifest",
    "build_invalidation_manifest",
    "build_phase6_acceptance",
    "build_repair_history",
    "build_repair_plan",
    "build_unified_release_gate",
]
