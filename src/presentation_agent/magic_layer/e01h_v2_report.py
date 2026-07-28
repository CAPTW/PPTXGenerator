"""Report helpers for E01H-V2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def write_md(path: str | Path, content: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content.rstrip() + "\n", encoding="utf-8")


def simple_markdown(payload: dict[str, Any], title: str) -> str:
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            continue
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def final_decision_markdown(payload: dict[str, Any]) -> str:
    return (
        "# E01H-V2 Final Decision\n\n"
        f"- decision: `{payload.get('decision')}`\n"
        f"- status: `{payload.get('status')}`\n"
        f"- e02h_v2_unlocked: `{payload.get('e02h_v2_unlocked')}`\n"
        f"- e05_unlocked: `{payload.get('e05_unlocked')}`\n"
        f"- reason: {payload.get('reason')}\n"
    )
