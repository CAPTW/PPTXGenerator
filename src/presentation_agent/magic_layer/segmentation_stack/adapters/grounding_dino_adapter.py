from __future__ import annotations

from src.presentation_agent.magic_layer.segmentation_stack.model_inventory import AdapterSpec


def adapter_spec() -> AdapterSpec:
    return AdapterSpec("grounding_dino", "Grounding DINO", ["groundingdino"], ["grounding-dino-local"], "grounding")
