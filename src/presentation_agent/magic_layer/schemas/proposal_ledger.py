from __future__ import annotations

from typing import Any

from .common import bbox_valid


def validate_proposal_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    proposals = [item for item in ledger.get("proposals", []) if isinstance(item, dict)]
    for proposal in proposals:
        if not proposal.get("proposal_id"):
            failures.append("Proposal requires proposal_id.")
        if not bbox_valid(proposal.get("bbox_norm", [0.1, 0.1, 0.1, 0.1])):
            failures.append(f"Proposal {proposal.get('proposal_id')} bbox_norm is invalid.")
        if proposal.get("content_bearing") and proposal.get("confidence", 1) < 0.5 and not proposal.get("accepted_as_layer_id") and not proposal.get("rejected_reason"):
            warnings.append(f"Low-confidence content-bearing proposal {proposal.get('proposal_id')} requires fusion or explicit rejection.")
    return {"schema_name": "proposal_ledger_validation", "pass": not failures, "proposal_count": len(proposals), "failures": failures, "warnings": warnings}
