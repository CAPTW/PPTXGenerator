"""Deterministic evidence normalization for DeckCompiler."""

from .normalization import build_evidence_registry, validate_evidence_graph

__all__ = ["build_evidence_registry", "validate_evidence_graph"]
