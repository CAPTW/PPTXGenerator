"""Report helpers for E04H-BP2."""

from __future__ import annotations

from typing import Any


def simple_markdown(payload: dict[str, Any], title: str) -> str:
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            continue
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def final_decision_markdown(payload: dict[str, Any]) -> str:
    return (
        "# E04H-BP2 Final Decision\n\n"
        f"- decision: `{payload.get('decision')}`\n"
        f"- status: `{payload.get('status')}`\n"
        f"- e05_unlocked: `{payload.get('e05_unlocked')}`\n"
        f"- reason: {payload.get('reason')}\n"
    )
