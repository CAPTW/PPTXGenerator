from __future__ import annotations

from typing import Any


def validate_registry_update(report: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "reference_registry_update_validator.v1", "pass": report.get("fake_hashes_inserted") is False, "product_pass": False}
