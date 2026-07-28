"""Visual rhythm gate across the 16 E03.3 archetypes."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_visual_rhythm_report(archetype_statuses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    families = Counter(row.get("family", "unknown") for row in archetype_statuses.values())
    repeated_family_blockers = [family for family, count in families.items() if family == "cards" and count > 3]
    failed = [key for key, row in archetype_statuses.items() if row.get("status") != "passed"]
    blockers = repeated_family_blockers + failed
    return {
        "schema_name": "e03_3_visual_rhythm_summary",
        "status": "passed" if not blockers else "failed",
        "visual_rhythm_verdict": "passed" if not blockers else "patch_required",
        "critical_rhythm_blocker_count": len(blockers),
        "blockers": blockers,
        "family_counts": dict(families),
        "archetype_distinction_status": "passed" if not blockers else "failed",
        "broad_canva_parity_claimed": False,
    }
