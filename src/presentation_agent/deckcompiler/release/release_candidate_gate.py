"""Independent Phase 7C release-candidate evaluator."""

from __future__ import annotations

from typing import Any, Mapping

from .contracts import bind_content_hash, verify_content_hash


REQUIRED_PREREQUISITES = (
    "demo_run_pass",
    "fresh_pptx_html",
    "render_6_of_6",
    "html_screenshot_6_of_6",
    "composite_qa_pass",
    "phase6_proof_pass",
    "package_complete",
    "manifest_valid",
    "zip_valid",
    "security_path_scan_pass",
    "license_provenance_pass",
    "repeat_semantic_determinism_pass",
    "source_tree_clean",
    "external_skill_unchanged",
    "phase4_phase5_phase6_unchanged",
)


class CandidateGateError(RuntimeError):
    """Stable release-candidate gate error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def build_release_candidate_gate(
    *,
    gate_id: str,
    tested_runtime_commit: str,
    prerequisites: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    checks = {
        name: bool(prerequisites.get(name, False)) for name in REQUIRED_PREREQUISITES
    }
    release_actions = {
        "submission_performed": bool(prerequisites.get("submission_performed", False)),
        "push_performed": bool(prerequisites.get("push_performed", False)),
        "tag_created": bool(prerequisites.get("tag_created", False)),
    }
    eligible = all(checks.values()) and not any(release_actions.values())
    payload = {
        "schema_name": "release_candidate_gate",
        "schema_version": "1.0.0",
        "gate_id": gate_id,
        "tested_runtime_commit": tested_runtime_commit,
        "prerequisites": checks,
        "status": (
            "ELIGIBLE_FOR_FRESH_CLONE_PROOF" if eligible else "BLOCKED"
        ),
        "phase7c_accepted": eligible,
        "phase7d_ready": eligible,
        "phase7d_required": True,
        "final_release_eligible": False,
        "devpost_release_eligible": False,
        **release_actions,
        "created_at": created_at,
    }
    return bind_content_hash(payload, "gate_hash")


def validate_release_candidate_gate(payload: Mapping[str, Any]) -> bool:
    gate = dict(payload)
    if not verify_content_hash(gate, "gate_hash"):
        raise CandidateGateError("DC_CANDIDATE_GATE_HASH_MISMATCH")
    prerequisites = gate.get("prerequisites", {})
    if set(prerequisites) != set(REQUIRED_PREREQUISITES):
        raise CandidateGateError("DC_CANDIDATE_GATE_PREREQUISITE_SET_INVALID")
    actions = (
        gate.get("submission_performed"),
        gate.get("push_performed"),
        gate.get("tag_created"),
    )
    if any(value is not False for value in actions):
        raise CandidateGateError("DC_RELEASE_ACTION_FORBIDDEN")
    expected_eligible = all(prerequisites.values())
    expected_status = (
        "ELIGIBLE_FOR_FRESH_CLONE_PROOF" if expected_eligible else "BLOCKED"
    )
    if gate.get("status") != expected_status:
        raise CandidateGateError("DC_CANDIDATE_GATE_STATUS_INVALID")
    if any(
        gate.get(field) is not expected
        for field, expected in (
            ("phase7c_accepted", expected_eligible),
            ("phase7d_ready", expected_eligible),
            ("phase7d_required", True),
            ("final_release_eligible", False),
            ("devpost_release_eligible", False),
        )
    ):
        raise CandidateGateError("DC_CANDIDATE_GATE_FLAGS_INVALID")
    return True


__all__ = [
    "CandidateGateError",
    "REQUIRED_PREREQUISITES",
    "build_release_candidate_gate",
    "validate_release_candidate_gate",
]
