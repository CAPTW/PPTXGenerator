from __future__ import annotations

from pathlib import Path

from .compile_scope_guard import validate_compile_scope


def ensure_output_path_allowed(output_path: str | Path, out_dir: str | Path) -> dict:
    return validate_compile_scope({}, out_dir, output_path)
