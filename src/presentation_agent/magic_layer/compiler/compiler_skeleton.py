from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.compiler.dry_run_compiler import dry_run_compile_bundle, dry_run_compile_spec


def run_compiler_skeleton_dry_run(
    *,
    bundle_path: str | Path | None = None,
    editable_spec_path: str | Path | None = None,
    backend_name: str = "dry_run_only",
) -> dict[str, Any]:
    if bundle_path:
        path = Path(bundle_path)
        bundle = json.loads(path.read_text(encoding="utf-8"))
        return dry_run_compile_bundle(bundle, backend_name=backend_name, input_bundle_path=str(path))
    if editable_spec_path:
        path = Path(editable_spec_path)
        spec = json.loads(path.read_text(encoding="utf-8"))
        return dry_run_compile_spec(spec, backend_name=backend_name)
    return {
        "schema": "dry_run_compile_report.v1",
        "decision": "DRY_RUN_INSUFFICIENT_EVIDENCE",
        "product_pass": False,
        "pptx_generated": False,
        "render_generated": False,
        "blocker_count": 1,
        "downstream_gates": ["B03_native_validation_gate"],
        "limitations": ["bundle_path or editable_spec_path required"],
    }
