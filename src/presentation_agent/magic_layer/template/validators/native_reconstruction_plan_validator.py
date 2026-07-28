from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.template.native_reconstruction_plan_v1 import validate_native_reconstruction_plan


def validate_native_reconstruction_plan_file(path: str | Path, slot_schema_path: str | Path | None = None) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    slots = json.loads(Path(slot_schema_path).read_text(encoding="utf-8")) if slot_schema_path else None
    return validate_native_reconstruction_plan(data, slots)
