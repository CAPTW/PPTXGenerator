from __future__ import annotations

from src.presentation_agent.magic_layer.segmentation_stack.model_inventory import AdapterSpec


def adapter_spec() -> AdapterSpec:
    return AdapterSpec("birefnet_rmbg", "BiRefNet / RMBG", ["transformers"], ["birefnet-or-rmbg-local"], "matting")
