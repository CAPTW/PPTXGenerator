"""Local environment doctor for E01X-R5 minimal model packs."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Any


COMMON_MODEL_DIRS = [
    "models/",
    "local_models/",
    ".models/",
    "design_runs/model_cache/",
]

COMMON_TESSERACT_WINDOWS_PATHS = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
]


def python_package_probe(packages: list[str]) -> dict[str, Any]:
    rows = []
    for package in sorted(set(packages)):
        spec = importlib.util.find_spec(package)
        rows.append({"name": package, "available": spec is not None, "origin": spec.origin if spec and spec.origin else None})
    return {"schema_name": "python_package_probe", "packages": rows, "canva_parity_claimed": False}


def probe_system_binaries(extra_paths: list[Path] | None = None) -> dict[str, Any]:
    common = COMMON_TESSERACT_WINDOWS_PATHS + list(extra_paths or [])
    path = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if not path:
        path = next((str(item) for item in common if item.is_file()), None)
    return {
        "schema_name": "system_binary_probe",
        "binaries": {
            "tesseract": {
                "available": path is not None,
                "path": path,
            }
        },
        "common_windows_paths_checked": [str(item) for item in common],
        "canva_parity_claimed": False,
    }


def probe_model_paths(repo_root: Path) -> dict[str, Any]:
    dirs = COMMON_MODEL_DIRS[:]
    if os.environ.get("ML_MODEL_CACHE_DIR"):
        dirs.append(os.environ["ML_MODEL_CACHE_DIR"])
    if os.environ.get("USERPROFILE"):
        dirs.append(str(Path(os.environ["USERPROFILE"]) / ".cache/huggingface/hub"))
    rows = []
    for raw in dirs:
        path = Path(os.path.expandvars(raw))
        if not path.is_absolute():
            path = repo_root / path
        rows.append({"raw": raw, "resolved": str(path.resolve()), "exists": path.exists(), "is_dir": path.is_dir() if path.exists() else False})
    return {"schema_name": "model_path_probe", "paths": rows, "canva_parity_claimed": False}


def local_environment_doctor(
    *,
    repo_root: Path,
    manifest_present: bool,
    package_names: list[str],
    resolved_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    packages = python_package_probe(package_names)
    binaries = probe_system_binaries()
    model_paths = probe_model_paths(repo_root)
    text_run = sum(1 for entry in resolved_entries if entry.get("group") == "text_first_lock" and entry.get("can_run"))
    non_text_run = sum(1 for entry in resolved_entries if entry.get("group") != "text_first_lock" and entry.get("can_run"))
    decision = evaluate_doctor_decision(
        manifest_present=manifest_present,
        enabled_adapter_count=sum(1 for entry in resolved_entries if entry.get("enabled")),
        runnable_text_adapter_count=text_run,
        runnable_non_text_adapter_count=non_text_run,
        missing_path_count=sum(len(entry.get("missing_paths", [])) for entry in resolved_entries),
    )
    return {
        "schema_name": "local_environment_doctor",
        "python": {"executable": sys.executable, "version": sys.version},
        "package_probe": packages,
        "system_binary_probe": binaries,
        "model_path_probe": model_paths,
        "decision": decision,
        "canva_parity_claimed": False,
    }


def evaluate_doctor_decision(
    *,
    manifest_present: bool,
    enabled_adapter_count: int,
    runnable_text_adapter_count: int,
    runnable_non_text_adapter_count: int,
    missing_path_count: int,
) -> dict[str, Any]:
    if not manifest_present or enabled_adapter_count == 0:
        decision = "E01X_R5_BLOCKED_CREATE_LOCAL_MODEL_PACK_MANIFEST"
        reasons = ["local_model_pack_manifest_missing_or_no_enabled_adapters"]
    elif missing_path_count > 0:
        decision = "E01X_R5_BLOCKED_MODEL_PATHS_MISSING"
        reasons = ["configured_model_paths_missing"]
    elif runnable_text_adapter_count == 0:
        decision = "E01X_R5_BLOCKED_TEXT_ADAPTER_MISSING"
        reasons = ["text_first_lock_adapter_missing"]
    elif runnable_non_text_adapter_count == 0:
        decision = "E01X_R5_BLOCKED_NON_TEXT_ADAPTER_MISSING"
        reasons = ["non_text_adapter_missing"]
    else:
        decision = "E01X_R5_READY_FOR_E01X_REENTRY"
        reasons = []
    return {
        "schema_name": "r5_doctor_decision",
        "decision": decision,
        "block_reasons": reasons,
        "e01x_may_be_rerun": decision == "E01X_R5_READY_FOR_E01X_REENTRY",
        "e01_may_start": False,
        "canva_parity_claimed": False,
    }


def adapter_feasibility_matrix(resolved_entries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        {
            "adapter_id": entry.get("adapter_id"),
            "group": entry.get("group"),
            "enabled": entry.get("enabled"),
            "can_run": entry.get("can_run"),
            "missing_packages": entry.get("missing_packages", []),
            "missing_paths": entry.get("missing_paths", []),
            "blockers": entry.get("blockers", []),
        }
        for entry in resolved_entries
    ]
    return {"schema_name": "adapter_feasibility_matrix", "rows": rows, "canva_parity_claimed": False}


def feasibility_matrix_markdown(matrix: dict[str, Any]) -> str:
    lines = ["# Adapter Feasibility Matrix", "", "| Adapter | Group | Enabled | Can run | Blockers |", "|---|---|---|---|---|"]
    for row in matrix.get("rows", []):
        lines.append(f"| `{row['adapter_id']}` | `{row['group']}` | `{row['enabled']}` | `{row['can_run']}` | `{', '.join(row['blockers']) or '-'}` |")
    lines.append("")
    lines.append("Canva parity claimed: `False`")
    return "\n".join(lines) + "\n"
