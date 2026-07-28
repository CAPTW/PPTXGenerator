"""Optional adapter spec modules for E01X.

These modules intentionally avoid heavy imports at module import time.
"""

from __future__ import annotations

__all__ = [
    "paddleocr_vl_adapter",
    "doclayout_adapter",
    "grounding_dino_adapter",
    "sam2_adapter",
    "qwen_image_layered_adapter",
    "layerd_adapter",
    "birefnet_adapter",
    "table_transformer_adapter",
    "deplot_adapter",
    "florence_adapter",
    "system_tesseract_adapter",
    "paddleocr_adapter",
    "easyocr_adapter",
    "generic_ultralytics_layout_adapter",
    "generic_transformers_object_detection_adapter",
    "generic_transformers_segmentation_adapter",
    "generic_sam_adapter",
    "docling_layout_adapter",
]
