from __future__ import annotations

from src.presentation_agent.magic_layer.segmentation_stack.model_inventory import AdapterSpec


def adapter_spec() -> AdapterSpec:
    return AdapterSpec("sam2", "SAM2.1 / SAM-HQ", ["sam2"], ["sam2-local"], "masks")
