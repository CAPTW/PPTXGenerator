"""Resolve local model pack paths without downloading weights."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
from pathlib import Path
from typing import Any


PATH_FIELDS = ["model_dir", "checkpoint_path", "config_path", "processor_path", "tokenizer_path"]
R5_PATH_FIELDS = ["binary_path", "model_path", "model_dir", "processor_dir", "checkpoint_path", "config_path", "processor_path", "tokenizer_path"]
MAX_HASH_BYTES = 64 * 1024 * 1024


def resolve_model_pack(manifest: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for group, group_entries in manifest.get("adapter_groups", {}).items():
        for entry in group_entries:
            entries.append(resolve_model_entry(entry, repo_root=repo_root, group=group))
    return {
        "schema_name": "resolved_model_pack_manifest",
        "schema_version": "1.0",
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "enabled_entry_count": sum(1 for item in entries if item.get("enabled")),
            "can_run_count": sum(1 for item in entries if item.get("can_run")),
            "missing_path_count": sum(len([b for b in item.get("blockers", []) if b.startswith("missing_path:")]) for item in entries),
        },
        "canva_parity_claimed": False,
    }


def resolve_model_entry(entry: dict[str, Any], *, repo_root: Path, group: str | None = None) -> dict[str, Any]:
    package_evidence = [_package_evidence(name) for name in entry.get("package_names", [])]
    path_evidence = {field: _resolve_path(entry.get(field), repo_root=repo_root) for field in PATH_FIELDS if entry.get(field)}
    binary_evidence = _binary_evidence(entry["adapter_id"]) if entry.get("adapter_id") == "tesseract" else None
    blockers: list[str] = []
    if entry.get("enabled") and any(not item["available"] for item in package_evidence):
        blockers.extend(f"missing_package:{item['name']}" for item in package_evidence if not item["available"])
    for field, evidence in path_evidence.items():
        if not evidence["exists"]:
            blockers.append(f"missing_path:{field}")
    if entry.get("adapter_id") == "tesseract" and not (binary_evidence or {}).get("available"):
        blockers.append("missing_binary:tesseract")
    enabled = bool(entry.get("enabled"))
    can_run = enabled and not blockers and (bool(path_evidence) or entry.get("adapter_id") == "tesseract" or not _requires_weight_path(entry))
    return {
        "adapter_id": entry.get("adapter_id"),
        "group": group or entry.get("group") or "unknown",
        "enabled": enabled,
        "device": entry.get("device", "auto"),
        "precision": entry.get("precision", "auto"),
        "local_files_only": entry.get("local_files_only", True),
        "allow_download": bool(entry.get("allow_download", False)),
        "package_evidence": package_evidence,
        "binary_evidence": binary_evidence,
        "paths": path_evidence,
        "model_id": entry.get("model_id"),
        "expected_outputs": entry.get("expected_outputs", []),
        "blockers": blockers,
        "can_run": can_run,
        "canva_parity_claimed": False,
    }


def package_inventory(package_names: list[str]) -> dict[str, Any]:
    rows = [_package_evidence(name) for name in sorted(set(package_names))]
    return {
        "schema_name": "package_inventory",
        "packages": rows,
        "summary": {
            "package_count": len(rows),
            "available_count": sum(1 for row in rows if row["available"]),
            "missing_count": sum(1 for row in rows if not row["available"]),
        },
        "canva_parity_claimed": False,
    }


def resolve_r5_model_pack(manifest: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    entries = []
    for group, group_entries in manifest.get("adapters", {}).items():
        for entry in group_entries:
            entries.append(resolve_r5_adapter_entry(entry, group=group, repo_root=repo_root))
    return {
        "schema_name": "r5_resolved_model_pack_manifest",
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "enabled_entry_count": sum(1 for entry in entries if entry["enabled"]),
            "can_run_count": sum(1 for entry in entries if entry["can_run"]),
            "missing_path_count": sum(len(entry["missing_paths"]) for entry in entries),
            "missing_package_count": sum(len(entry["missing_packages"]) for entry in entries),
            "missing_binary_count": sum(1 for entry in entries if entry.get("binary_required") and not entry.get("binary_available")),
        },
        "canva_parity_claimed": False,
    }


def resolve_r5_adapter_entry(entry: dict[str, Any], *, group: str, repo_root: Path) -> dict[str, Any]:
    package_evidence = [_package_evidence(name) for name in entry.get("package_names", [])]
    paths = {
        field: _resolve_path(entry.get(field), repo_root=repo_root)
        for field in R5_PATH_FIELDS
        if entry.get(field)
    }
    missing_paths = [
        field
        for field, evidence in paths.items()
        if field != "binary_path" and evidence.get("raw") and not evidence.get("exists")
    ]
    binary_required = entry.get("adapter_id") == "system_tesseract"
    binary_evidence = _resolve_binary(entry.get("binary_path"), "tesseract", repo_root=repo_root) if binary_required else None
    missing_packages = [item["name"] for item in package_evidence if not item["available"]]
    blockers = []
    if missing_packages:
        blockers.extend(f"missing_package:{name}" for name in missing_packages)
    if missing_paths:
        blockers.extend(f"missing_path:{field}" for field in missing_paths)
    if binary_required and not (binary_evidence or {}).get("available"):
        blockers.append("missing_binary:tesseract")
    enabled = bool(entry.get("enabled"))
    can_run = enabled and not blockers
    return {
        "adapter_id": entry.get("adapter_id"),
        "group": group,
        "enabled": enabled,
        "device": entry.get("device", "auto"),
        "language": entry.get("language", "eng"),
        "min_confidence": entry.get("min_confidence", 0.25),
        "class_role_map": entry.get("class_role_map", {}),
        "package_evidence": package_evidence,
        "missing_packages": missing_packages,
        "paths": paths,
        "missing_paths": missing_paths,
        "binary_required": binary_required,
        "binary_evidence": binary_evidence,
        "binary_available": bool((binary_evidence or {}).get("available")),
        "blockers": blockers,
        "can_run": can_run,
        "raw_entry": entry,
        "canva_parity_claimed": False,
    }


def _package_evidence(name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(name)
    return {
        "name": name,
        "available": spec is not None,
        "origin": spec.origin if spec and spec.origin else None,
    }


def _binary_evidence(binary: str) -> dict[str, Any]:
    path = shutil.which(binary)
    return {"binary": binary, "available": path is not None, "path": path}


def _resolve_binary(value: str | None, fallback: str, *, repo_root: Path) -> dict[str, Any]:
    raw = value or fallback
    if raw and raw != fallback:
        resolved = _resolve_path(raw, repo_root=repo_root)
        if resolved["exists"]:
            return {"binary": fallback, "available": True, "path": resolved["resolved"], "source": "manifest_binary_path"}
    path = shutil.which(fallback)
    common = [
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ]
    if not path:
        path = next((str(item) for item in common if item.is_file()), None)
    return {"binary": fallback, "available": path is not None, "path": path, "source": "PATH_or_common_windows_path"}


def _resolve_path(value: str | None, *, repo_root: Path) -> dict[str, Any]:
    if not value:
        return {"raw": value, "resolved": None, "exists": False, "sha256": None, "size_bytes": None}
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    path = Path(expanded)
    if not path.is_absolute():
        path = repo_root / path
    resolved = path.resolve()
    exists = resolved.exists()
    is_file = resolved.is_file()
    size = resolved.stat().st_size if exists and is_file else None
    return {
        "raw": value,
        "resolved": str(resolved),
        "exists": exists,
        "is_file": is_file,
        "is_dir": resolved.is_dir() if exists else False,
        "size_bytes": size,
        "sha256": _sha256_file(resolved) if exists and is_file and (size or 0) <= MAX_HASH_BYTES else None,
        "hash_skipped_reason": "file_too_large" if exists and is_file and (size or 0) > MAX_HASH_BYTES else None,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _requires_weight_path(entry: dict[str, Any]) -> bool:
    return bool(entry.get("model_id")) or entry.get("adapter_id") not in {"tesseract"}
