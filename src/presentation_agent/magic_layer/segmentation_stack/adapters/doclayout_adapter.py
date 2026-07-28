from __future__ import annotations

from src.presentation_agent.magic_layer.segmentation_stack.model_inventory import AdapterSpec


def adapter_spec() -> AdapterSpec:
    return AdapterSpec("doclayout_yolo", "DocLayout-YOLO / Docling / DiT DocLayNet", ["docling"], ["doclayout-yolo-or-doclaynet-local"], "layout")
