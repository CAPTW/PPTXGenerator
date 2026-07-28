from __future__ import annotations

from pathlib import Path
from typing import Any


def classify_reference_source(path: str | Path, run_folder: str | Path, registry_entry: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(path)
    run = Path(run_folder)
    lower = str(path).lower().replace("\\", "/")
    name = path.name.lower()
    if "contact" in name or "contact_sheet" in lower:
        decision = "SOURCE_BLOCKED_CONTACT_SHEET"
    elif "render" in name or "/renders/" in lower or "rendered" in name:
        decision = "SOURCE_BLOCKED_RENDER_OUTPUT"
    elif "generated_flood" in lower or "flood" in name:
        decision = "SOURCE_BLOCKED_GENERATED_FLOOD"
    elif "quarantine" in lower:
        decision = "SOURCE_BLOCKED_QUARANTINE"
    elif "/outputs/" in lower:
        decision = "SOURCE_BLOCKED_OUTPUT_ARTIFACT"
    elif _is_relative_to(path, run / "inputs/e03_rx/references") or "inputs/e03_rx/references" in lower:
        decision = "SOURCE_ALLOWED_ACTIVE_INPUT"
    elif registry_entry and registry_entry.get("provenance"):
        decision = "SOURCE_ALLOWED_WITH_MANUAL_PROVENANCE"
    else:
        decision = "SOURCE_BLOCKED_UNKNOWN"
    return {"schema": "e03_reference_source_policy_report.v1", "path": str(path), "decision": decision, "forbidden_source": decision.startswith("SOURCE_BLOCKED"), "product_pass": False}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False
