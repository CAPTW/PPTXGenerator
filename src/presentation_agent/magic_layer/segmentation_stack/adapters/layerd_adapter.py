from __future__ import annotations

from src.presentation_agent.magic_layer.segmentation_stack.model_inventory import AdapterSpec


def adapter_spec() -> AdapterSpec:
    return AdapterSpec("layerd_birefnet", "LayerD / cyberagent layerd-birefnet", ["transformers"], ["cyberagent/layerd-birefnet"], "layers")
