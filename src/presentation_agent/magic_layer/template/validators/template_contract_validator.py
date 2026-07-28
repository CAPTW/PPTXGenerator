from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.template.template_contract_v1 import validate_template_contract


def validate_template_contract_file(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_template_contract(data)
