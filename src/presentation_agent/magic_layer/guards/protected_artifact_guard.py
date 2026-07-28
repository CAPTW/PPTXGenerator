from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROTECTED_ARTIFACTS = [
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
]


def hash_protected_artifacts(root: Path) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": [_artifact_state(root, Path(path)) for path in PROTECTED_ARTIFACTS],
    }


def compare_protected_hashes(pre: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    before = {item["path"]: item for item in pre.get("artifacts", [])}
    comparisons = []
    for item in post.get("artifacts", []):
        old = before.get(item["path"], {})
        comparisons.append(
            {
                "path": item["path"],
                "unchanged": old.get("sha256") == item.get("sha256") and old.get("size_bytes") == item.get("size_bytes"),
                "pre_sha256": old.get("sha256"),
                "post_sha256": item.get("sha256"),
            }
        )
    return {"status": "passed" if all(row["unchanged"] for row in comparisons) else "failed", "comparisons": comparisons}


def assert_protected_unchanged(pre: dict[str, Any], post: dict[str, Any]) -> None:
    comparison = compare_protected_hashes(pre, post)
    if comparison["status"] != "passed":
        raise RuntimeError("Protected canonical artifacts changed.")


def _artifact_state(root: Path, rel_path: Path) -> dict[str, Any]:
    path = root / rel_path
    stat = path.stat() if path.exists() else None
    return {
        "path": rel_path.as_posix(),
        "exists": path.exists(),
        "size_bytes": stat.st_size if stat and path.is_file() else None,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() if stat else None,
        "sha256": _sha256(path),
    }


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
