from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[5]


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: str | Path, title: str, lines: list[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join([f"# {title}", "", *lines]).rstrip() + "\n", encoding="utf-8")


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        return {}
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def sha256_file(path: str | Path) -> str | None:
    source = Path(path)
    if not source.is_file():
        return None
    digest = sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_profile(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    return {
        "path": str(source),
        "exists": source.is_file(),
        "size_bytes": source.stat().st_size if source.is_file() else None,
        "sha256": sha256_file(source),
        "mtime": source.stat().st_mtime if source.is_file() else None,
    }


def image_dimensions(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        return {"image_readable": False, "width_px": None, "height_px": None}
    try:
        from PIL import Image

        with Image.open(source) as image:
            return {"image_readable": True, "width_px": image.width, "height_px": image.height}
    except Exception as exc:  # pragma: no cover - depends on optional image deps
        return {"image_readable": False, "width_px": None, "height_px": None, "error": repr(exc)}


def protected_artifact_snapshot() -> dict[str, Any]:
    paths = [
        ROOT / "outputs/editable_template_spec.final.json",
        ROOT / "outputs/golden_template_masters.pptx",
        ROOT / "outputs/final_deck_large_premium.pptx",
    ]
    artifacts = [file_profile(path) for path in paths]
    return {
        "schema": "protected_artifact_snapshot.v1",
        "artifacts": artifacts,
        "status": "PASS" if all(item["exists"] for item in artifacts) else "FAIL_MISSING_PROTECTED_ARTIFACT",
    }


def markdown_bool(value: Any) -> str:
    return "`true`" if value is True else "`false`" if value is False else f"`{value}`"
