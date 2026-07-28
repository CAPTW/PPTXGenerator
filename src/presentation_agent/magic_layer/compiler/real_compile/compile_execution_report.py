from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str | None:
    file_path = Path(path)
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_compile_execution_report(
    *,
    backend_selected: str,
    bundle_path: str | Path | None,
    input_bundle_hash: str | None,
    editable_spec_hash: str | None,
    output_path: str | Path,
    expected_object_count: int,
    warnings: list[str] | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    output = Path(output_path)
    blockers = blockers or []
    return {
        "schema": "controlled_minimal_compile_execution_report.v1",
        "backend_selected": backend_selected,
        "bundle_path": str(bundle_path) if bundle_path else None,
        "input_bundle_hash": input_bundle_hash,
        "editable_spec_hash": editable_spec_hash,
        "output_path": str(output),
        "output_exists": output.is_file(),
        "output_sha256": sha256_file(output),
        "output_size": output.stat().st_size if output.is_file() else None,
        "slide_count_expected": 1,
        "object_count_expected": expected_object_count,
        "unsupported_optional_count": 0,
        "unsupported_required_count": 0,
        "skipped_optional_instructions": [],
        "blockers": blockers,
        "warnings": warnings or [],
        "pptx_generated": output.is_file() and not blockers,
        "render_generated": False,
        "product_pass": False,
    }
