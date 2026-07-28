"""Local Magic Layer decomposition workbench.

The workbench produces analysis artifacts for reference-image decomposition.
It does not create source-bound decks or final editable PPTX files.
"""

from .image_asset import ImageMetadata, read_image_metadata
from .layer_schema_v4 import (
    ALLOWED_EDITABILITY_TARGETS,
    ALLOWED_LAYER_TYPES,
    LayerValidationError,
    bbox_norm,
    make_layer,
    validate_layer,
    validate_manifest,
)
from .workbench import MagicLayerWorkbench

__all__ = [
    "ALLOWED_EDITABILITY_TARGETS",
    "ALLOWED_LAYER_TYPES",
    "ImageMetadata",
    "LayerValidationError",
    "MagicLayerWorkbench",
    "bbox_norm",
    "make_layer",
    "read_image_metadata",
    "validate_layer",
    "validate_manifest",
]
