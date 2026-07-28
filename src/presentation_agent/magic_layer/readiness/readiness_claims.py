from __future__ import annotations

from typing import Any


def verify_readiness_claims(*, bridge_ready: bool, four_core_ready: bool) -> dict[str, Any]:
    claims = [
        ("Pipeline v2 four-core controlled regression is ready with limitations.", "VERIFIED" if four_core_ready else "PARTIALLY_VERIFIED"),
        ("Recovery validation bridge can be planned.", "VERIFIED" if bridge_ready else "PARTIALLY_VERIFIED"),
        ("P07 proves product PASS.", "OVERCLAIMED"),
        ("P07 proves arbitrary Magic Layer+ robustness.", "OVERCLAIMED"),
        ("P07 is E03.", "CONTRADICTED"),
        ("P07 unlocks E04.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("P07 unlocks D08.", "BLOCKED_BY_SCALEOUT_LOCK"),
        ("P07 allows canonical promotion.", "BLOCKED_BY_POLICY"),
        ("P06/P05 outputs can be promoted to golden_template_masters.pptx.", "BLOCKED_BY_POLICY"),
        ("E03 can be directly rerun now without RV00/reference readiness.", "CONTRADICTED"),
    ]
    return {"schema": "readiness_claim_verification_report.v1", "claims": [{"claim": claim, "status": status} for claim, status in claims], "product_pass": False}
