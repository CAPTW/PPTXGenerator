from __future__ import annotations

import re
from typing import Any


SLOT_ID_RE = re.compile(r"^SLOT_[A-Z0-9]+(?:_[A-Z0-9]+)*$")
RANDOM_LOOKING_RE = re.compile(r"(slot_[a-f0-9]{8,}|uuid|random|tmp)", re.IGNORECASE)


def validate_slot_name(slot: dict[str, Any]) -> dict[str, Any]:
    failures = []
    warnings = []
    slot_id = str(slot.get("slot_id", ""))
    required = bool(slot.get("required"))
    if required and not SLOT_ID_RE.match(slot_id):
        failures.append(f"{slot_id}: required slot_id must use stable SLOT_ uppercase snake case")
    elif slot_id and not SLOT_ID_RE.match(slot_id):
        warnings.append(f"{slot_id}: optional slot_id does not follow recommended SLOT_ uppercase snake case")
    if RANDOM_LOOKING_RE.search(slot_id):
        (failures if required else warnings).append(f"{slot_id}: random-looking slot id is not stable")
    if required and not slot.get("pptx_object_name"):
        failures.append(f"{slot_id}: required slot missing pptx_object_name")
    return {"pass": not failures, "failures": failures, "warnings": warnings}
