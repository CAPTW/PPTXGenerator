"""E03H semantic native planning wrapper."""

from __future__ import annotations

from src.presentation_agent.magic_layer.e02h_semantic_native_planner import build_e02h_semantic_native_plan


def build_e03h_semantic_native_plan(object_graph, reference_id):
    return build_e02h_semantic_native_plan(object_graph, reference_id)
