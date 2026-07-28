from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_stage_execution_report(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "controlled_replay_stage_execution_report.v1",
        "decision": run.get("decision"),
        "stage_count": len(run.get("stage_results", [])),
        "stage_results": run.get("stage_results", []),
        "pptx_generated": bool(run.get("compile_report", {}).get("pptx_generated")),
        "render_generated": bool(run.get("render", {}).get("render_generated")),
        "product_pass": False,
    }


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: str | Path, title: str, lines: list[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join([f"# {title}", "", *lines]).rstrip() + "\n", encoding="utf-8")
