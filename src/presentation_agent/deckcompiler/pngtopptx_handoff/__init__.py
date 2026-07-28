"""Thin, fail-closed Phase 4 to CAPTW/pngtopptx handoff."""

from .export import HandoffError, HandoffResult, export_phase4_handoff, validate_handoff

__all__ = [
    "HandoffError",
    "HandoffResult",
    "export_phase4_handoff",
    "validate_handoff",
]
