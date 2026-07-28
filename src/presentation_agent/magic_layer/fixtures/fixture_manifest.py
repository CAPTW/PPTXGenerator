from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .e01b_fixture_contract import CORE_ALTERNATIVES, CORE_REQUIRED, OPTIONAL_PREFERRED


def sha256_file(path: str | Path) -> str | None:
    target = Path(path)
    if not target.is_file():
        return None
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_fixture(folder: str | Path) -> dict[str, Any]:
    root = Path(folder)
    files = []
    if root.exists():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            rel = path.relative_to(root).as_posix()
            files.append({"path": rel, "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "role": role_for(rel)})
    present = {item["path"] for item in files}
    missing_core = []
    for required in CORE_REQUIRED:
        alternatives = CORE_ALTERNATIVES.get(required, [])
        if required not in present and not any(alt in present for alt in alternatives):
            missing_core.append(required)
    missing_optional = [name for name in OPTIONAL_PREFERRED if name not in present]
    status = _status(root, files, missing_core)
    return {
        "schema": "current_e01b_fixture_inventory.v1",
        "fixture_path": str(root),
        "folder_exists": root.is_dir(),
        "file_count": len(files),
        "files": files,
        "missing_core_files": missing_core,
        "missing_optional_files": missing_optional,
        "current_fixture_status": status,
        "product_pass": False,
    }


def build_manifest(folder: str | Path, *, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    inventory = inventory_fixture(folder)
    return {
        "schema": "e01b_repaired_fixture_manifest.v1",
        "fixture_id": "e01b_single_reference_pass",
        "scope": "SINGLE_REFERENCE_MAGIC_LAYER_PLUS_REGRESSION",
        "fixture_path": str(Path(folder)),
        "files": inventory["files"],
        "missing_core_files": inventory["missing_core_files"],
        "missing_optional_files": inventory["missing_optional_files"],
        "provenance": provenance or {},
        "product_pass": False,
    }


def role_for(path: str) -> str:
    name = Path(path).name
    if name.endswith(".pptx"):
        return "editable_candidate_pptx"
    if name.endswith(".png") and "reference" in path:
        return "reference_image_historical_input"
    if name.endswith(".png"):
        return "historical_render_or_comparison"
    if "decision" in name:
        return "historical_decision"
    if "gate" in name:
        return "historical_gate_report"
    if "ledger" in name:
        return "historical_ledger"
    if "manifest" in name:
        return "fixture_manifest"
    return "supporting_evidence"


def _status(root: Path, files: list[dict[str, Any]], missing_core: list[str]) -> str:
    if not root.exists() or not files:
        return "EMPTY_OR_MISSING"
    if "editable_candidate_e01b.pptx" in missing_core:
        return "INCOMPLETE_MISSING_PPTX"
    if any("ledger" in item for item in missing_core):
        return "INCOMPLETE_MISSING_LEDGER"
    if missing_core:
        return "COMPLETE_WITH_LIMITATIONS"
    return "COMPLETE_CORE"

