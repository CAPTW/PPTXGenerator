from __future__ import annotations

from src.presentation_agent.magic_layer.segmentation_stack.model_inventory import AdapterSpec


def adapter_spec() -> AdapterSpec:
    return AdapterSpec("table_transformer", "Table Transformer", ["transformers"], ["microsoft/table-transformer-structure-recognition"], "chart_table")
