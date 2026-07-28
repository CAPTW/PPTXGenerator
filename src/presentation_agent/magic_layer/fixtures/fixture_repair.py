from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .fixture_manifest import sha256_file


def copy_selected_artifacts(selected: list[dict[str, Any]], target_root: str | Path) -> list[dict[str, Any]]:
    target = Path(target_root)
    copied = []
    for item in selected:
        source = Path(item["source_path"])
        destination = target / item["target_relative_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not source.is_file():
            copied.append({**item, "copied": False, "error": "source missing"})
            continue
        shutil.copy2(source, destination)
        copied.append(
            {
                **item,
                "target_path": str(destination),
                "copied": True,
                "source_sha256": sha256_file(source),
                "target_sha256": sha256_file(destination),
                "hash_match": sha256_file(source) == sha256_file(destination),
            }
        )
    return copied


def backup_fixture(source_root: str | Path, backup_root: str | Path) -> dict[str, Any]:
    source = Path(source_root)
    backup = Path(backup_root)
    backup.mkdir(parents=True, exist_ok=True)
    files = []
    if source.is_dir():
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            rel = path.relative_to(source)
            destination = backup / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            files.append({"source_path": str(path), "backup_path": str(destination), "sha256": sha256_file(path)})
    return {
        "schema": "e01b_fixture_backup_manifest.v1",
        "source_fixture_path": str(source),
        "backup_path": str(backup),
        "source_exists": source.is_dir(),
        "status": "BACKUP_CREATED" if files else "TARGET_FIXTURE_MISSING_BEFORE_C04" if not source.exists() else "TARGET_FIXTURE_EMPTY_BEFORE_C04",
        "files": files,
        "product_pass": False,
    }


def update_active_fixture(candidate_root: str | Path, active_root: str | Path) -> dict[str, Any]:
    candidate = Path(candidate_root)
    active = Path(active_root)
    active.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in sorted(item for item in candidate.rglob("*") if item.is_file()):
        rel = source.relative_to(candidate)
        destination = active / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        before_hash = sha256_file(destination)
        shutil.copy2(source, destination)
        copied.append(
            {
                "relative_path": rel.as_posix(),
                "source_path": str(source),
                "target_path": str(destination),
                "previous_sha256": before_hash,
                "new_sha256": sha256_file(destination),
                "replaced": before_hash is not None and before_hash != sha256_file(destination),
            }
        )
    return {
        "schema": "fixture_registry_update_report.v1",
        "active_fixture_path": str(active),
        "candidate_path": str(candidate),
        "updated": True,
        "copied_count": len(copied),
        "copied_files": copied,
        "product_pass": False,
    }

