"""Creative-template front-end contracts for deterministic editable decks."""

from .pipeline import (
    build_creative_template_architecture,
    build_presentation_architecture,
    build_slide_semantic_sidecars,
    run_creative_frontend,
    run_creative_frontend_from_files,
)
from .template_spec_adapter import adapt_image_template_spec, adapt_image_template_spec_from_files
from .qa import build_creative_frontend_qa_report, build_creative_frontend_qa_report_from_files

__all__ = [
    "adapt_image_template_spec",
    "adapt_image_template_spec_from_files",
    "build_creative_template_architecture",
    "build_presentation_architecture",
    "build_slide_semantic_sidecars",
    "build_creative_frontend_qa_report",
    "build_creative_frontend_qa_report_from_files",
    "run_creative_frontend",
    "run_creative_frontend_from_files",
]
