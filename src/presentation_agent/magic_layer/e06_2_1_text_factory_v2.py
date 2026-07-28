"""Text factory marker module for E06.2.1 v2 compiler."""

from __future__ import annotations

from typing import Any


def text_object_preserves_baseline_xml(obj: dict[str, Any]) -> bool:
    return obj.get("object_type") in {"text", "source_footer"} and bool(obj.get("text_excerpt") is not None)
