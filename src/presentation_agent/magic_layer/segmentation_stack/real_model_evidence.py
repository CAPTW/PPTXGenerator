"""Real model proposal evidence validation for E01X-R4."""

from __future__ import annotations

from typing import Any


def summarize_real_model_evidence(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = []
    rejected = []
    heuristic = []
    for proposal in proposals:
        if proposal.get("source_type") == "heuristic_smoke_only":
            heuristic.append(proposal)
            rejected.append({"proposal_id": proposal.get("proposal_id"), "reason": "heuristic_smoke_only"})
            continue
        reasons = _real_evidence_rejection_reasons(proposal)
        if reasons:
            rejected.append({"proposal_id": proposal.get("proposal_id"), "reason": ",".join(reasons)})
        else:
            accepted.append(proposal)
    adapters = {proposal.get("source_adapter") for proposal in accepted}
    text_adapters = {
        proposal.get("source_adapter")
        for proposal in accepted
        if any(candidate.get("role", "").endswith("text_region") or "text" in candidate.get("role", "") for candidate in proposal.get("role_candidates", []))
    }
    non_text_adapters = adapters - text_adapters
    return {
        "schema_name": "real_model_evidence_report",
        "real_adapter_count": len(adapters),
        "real_text_adapter_count": len(text_adapters),
        "real_non_text_adapter_count": len(non_text_adapters),
        "total_real_proposal_count": len(accepted),
        "total_heuristic_proposal_count": len(heuristic),
        "accepted_evidence_count": len(accepted),
        "rejected_evidence_count": len(rejected),
        "accepted_real_proposals": accepted,
        "rejected_proposals": rejected,
        "proposal_output_hashes": [
            proposal.get("adapter_runtime_evidence", {}).get("output_proposal_sha256")
            for proposal in accepted
            if proposal.get("adapter_runtime_evidence", {}).get("output_proposal_sha256")
        ],
        "input_image_sha256": next(
            (
                proposal.get("adapter_runtime_evidence", {}).get("input_image_sha256")
                for proposal in accepted
                if proposal.get("adapter_runtime_evidence", {}).get("input_image_sha256")
            ),
            None,
        ),
        "canva_parity_claimed": False,
    }


def real_model_evidence_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Real Model Evidence Report",
            "",
            f"- Real adapters: `{report['real_adapter_count']}`",
            f"- Real text adapters: `{report['real_text_adapter_count']}`",
            f"- Real non-text adapters: `{report['real_non_text_adapter_count']}`",
            f"- Total real proposals: `{report['total_real_proposal_count']}`",
            f"- Total heuristic proposals: `{report['total_heuristic_proposal_count']}`",
            f"- Accepted evidence: `{report.get('accepted_evidence_count', len(report.get('accepted_real_proposals', [])))}`",
            f"- Rejected evidence: `{report.get('rejected_evidence_count', len(report.get('rejected_proposals', [])))}`",
            f"- Input image SHA256: `{report['input_image_sha256']}`",
            f"- Proposal output hashes: `{len(report['proposal_output_hashes'])}`",
            "",
            "Accepted evidence requires real runtime evidence, input/output hashes, adapter identity, package/binary evidence, and local model/engine evidence.",
            "",
            "Canva parity claimed: `False`",
        ]
    ) + "\n"


def _real_evidence_rejection_reasons(proposal: dict[str, Any]) -> list[str]:
    evidence = proposal.get("adapter_runtime_evidence") or {}
    reasons = []
    if proposal.get("source_type") == "heuristic_smoke_only":
        reasons.append("heuristic_smoke_only")
    if proposal.get("gate_eligible") is not True:
        reasons.append("not_gate_eligible")
    if proposal.get("adapter_status") != "produced_proposals":
        reasons.append("adapter_status_not_produced")
    if evidence.get("real_inference_ran") is not True:
        reasons.append("real_inference_not_run")
    for field in ("input_image_sha256", "output_proposal_sha256", "adapter_id", "package_or_binary_evidence"):
        if not evidence.get(field):
            reasons.append(f"missing_{field}")
    if not evidence.get("model_weight_or_engine_evidence"):
        reasons.append("missing_model_weight_or_engine_evidence")
    if int(evidence.get("proposal_count") or 0) <= 0:
        reasons.append("proposal_count_zero")
    if evidence.get("runtime_errors"):
        reasons.append("runtime_errors_present")
    return reasons
