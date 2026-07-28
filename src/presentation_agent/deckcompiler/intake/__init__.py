"""Page-aware prompt and PDF intake for DeckCompiler Phase 3."""

from .config import Phase3Config, load_phase3_config
from .multi_source import IntakeArtifacts, build_intake_artifacts

__all__ = ["IntakeArtifacts", "Phase3Config", "build_intake_artifacts", "load_phase3_config"]
