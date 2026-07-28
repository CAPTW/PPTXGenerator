"""Design-pipeline adapters for generator-facing artifacts."""

from .build_editable_template_spec import build_editable_template_spec
from .generate_template_image_prompts import generate_template_image_prompts
from .generate_template_images import generate_template_images_from_manifest
from .template_archetypes import selectRequiredArchetypes

__all__ = [
    "build_editable_template_spec",
    "generate_template_image_prompts",
    "generate_template_images_from_manifest",
    "selectRequiredArchetypes",
]
