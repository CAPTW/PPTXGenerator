from __future__ import annotations

from src.presentation_agent.magic_layer.segmentation_stack.model_inventory import AdapterSpec


def adapter_spec() -> AdapterSpec:
    return AdapterSpec("paddleocr_vl", "PaddleOCR-VL / PaddleOCR-VL-1.5", ["paddleocr"], ["PaddlePaddle/PaddleOCR-VL"], "text_first_lock")
