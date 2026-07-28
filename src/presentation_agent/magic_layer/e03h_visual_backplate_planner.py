"""E03H visual backplate policy wrapper."""

from __future__ import annotations

from src.presentation_agent.magic_layer.e02h_visual_backplate_planner import build_e02h_visual_backplate_policy


def build_e03h_visual_backplate_policy(object_graph):
    return build_e02h_visual_backplate_policy(object_graph)
