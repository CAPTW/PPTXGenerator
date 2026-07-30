"""Thin, fail-closed Phase 4 to CAPTW/pngtopptx handoff."""

from .export import (
    HandoffError,
    HandoffResult,
    export_phase4_handoff,
    validate_handoff,
    validate_phase4_bundle,
)

__all__ = [
    "HandoffError",
    "HandoffResult",
    "export_phase4_handoff",
    "validate_handoff",
    "validate_phase4_bundle",
]
