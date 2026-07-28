from __future__ import annotations

from pathlib import Path
from typing import Any

from .e03_reference_contract import CORE_ARCHETYPES, EXPANSION_ARCHETYPES
from .e03_reference_registry import load_and_normalize_reference_registry


EXPECTED_ARCHETYPES = [*CORE_ARCHETYPES, *EXPANSION_ARCHETYPES]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def inventory_run_references(run_folder: str | Path) -> dict[str, Any]:
    run = Path(run_folder)
    registry_path = run / "inputs/e03_rx/reference_registry.json"
    references_dir = run / "inputs/e03_rx/references"
    registry_report = load_and_normalize_reference_registry(registry_path)
    entries = {entry["archetype_id"]: entry for entry in registry_report.get("registry", {}).get("references", [])}
    rows = []
    for archetype in EXPECTED_ARCHETYPES:
        entry = entries.get(archetype, {})
        expected = Path(entry.get("expected_path") or run / f"inputs/e03_rx/references/{archetype}.png")
        if not expected.is_absolute():
            expected = run.parents[1] / expected if expected.parts and expected.parts[0] == "design_runs" else run / expected
        exists = expected.is_file()
        rows.append({
            "archetype_id": archetype,
            "group": "core" if archetype in CORE_ARCHETYPES else "expansion",
            "expected_path": str(expected),
            "exists": exists,
            "file_size": expected.stat().st_size if exists else None,
            "extension": expected.suffix.lower() if exists else ".png",
            "registry_status": entry.get("status"),
            "presence_status": "PRESENT" if exists else "MISSING",
        })
    known = {Path(row["expected_path"]).resolve() for row in rows}
    files = [path for path in references_dir.rglob("*") if path.is_file()] if references_dir.is_dir() else []
    unexpected = [path for path in files if path.resolve() not in known]
    image_like = [path for path in files if path.suffix.lower() in IMAGE_SUFFIXES]
    forbidden = [path for path in files if path.suffix.lower() == ".pptx" or "render" in path.name.lower() or "contact" in path.name.lower()]
    return {
        "schema": "e03_reference_inventory_report.v1",
        "run_folder": str(run),
        "registry_path": str(registry_path),
        "references_dir": str(references_dir),
        "expected_count": len(EXPECTED_ARCHETYPES),
        "present_count": sum(1 for row in rows if row["exists"]),
        "missing_count": sum(1 for row in rows if not row["exists"]),
        "references": rows,
        "image_like_files": [{"path": str(path)} for path in image_like],
        "unexpected_files": [{"path": str(path), "suffix": path.suffix.lower()} for path in unexpected],
        "forbidden_files": [{"path": str(path)} for path in forbidden],
        "product_pass": False,
    }
