from __future__ import annotations

from src.presentation_agent.magic_layer.segmentation_stack.model_inventory import AdapterSpec


def adapter_spec() -> AdapterSpec:
    return AdapterSpec("qwen_image_layered", "Qwen-Image-Layered", ["transformers"], ["qwen-image-layered-local"], "layers")
