from __future__ import annotations

from src.presentation_agent.magic_layer.segmentation_stack.model_inventory import AdapterSpec


def adapter_spec() -> AdapterSpec:
    return AdapterSpec("florence_2", "Florence-2 auxiliary OCR/OD/regions", ["transformers"], ["microsoft/Florence-2-local"], "auxiliary")
