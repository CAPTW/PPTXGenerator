"""Report writers for E01X-R5."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def r5_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E01X-R5 Minimal Model Pack Report",
        "",
        f"- Previous R4 decision: `{report.get('previous_r4_decision')}`",
        f"- Final R5 decision: `{report.get('final_r5_decision')}`",
        f"- Manifest status: `{report.get('manifest_status')}`",
        f"- Real proposals: `{report.get('total_real_proposal_count', 0)}`",
        f"- Heuristic proposals: `{report.get('total_heuristic_proposal_count', 0)}`",
        f"- Text-first lock readiness: `{report.get('text_first_lock_readiness')}`",
        f"- Non-text model readiness: `{report.get('non_text_model_readiness')}`",
        f"- Fusion readiness: `{report.get('fusion_readiness')}`",
        f"- Exact next commands: `{report.get('next_commands')}`",
        "- Canva parity claimed: `False`",
    ]
    return "\n".join(lines) + "\n"


def evidence_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Real Model Evidence Report",
            "",
            f"- Real adapters: `{report.get('real_adapter_count', 0)}`",
            f"- Real text adapters: `{report.get('real_text_adapter_count', 0)}`",
            f"- Real non-text adapters: `{report.get('real_non_text_adapter_count', 0)}`",
            f"- Total real proposals: `{report.get('total_real_proposal_count', 0)}`",
            f"- Total heuristic proposals: `{report.get('total_heuristic_proposal_count', 0)}`",
            f"- Accepted evidence: `{report.get('accepted_evidence_count', 0)}`",
            f"- Rejected evidence: `{report.get('rejected_evidence_count', 0)}`",
            f"- Input image SHA256: `{report.get('input_image_sha256')}`",
            f"- Proposal output hashes: `{len(report.get('proposal_output_hashes', []))}`",
            "- Canva parity claimed: `False`",
        ]
    ) + "\n"
