from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.identity import content_sha256  # noqa: E402
from presentation_agent.deckcompiler.repair.closure import (  # noqa: E402
    INVALIDATED_ARTIFACT_IDS,
    RepairClosureError,
    build_before_after_manifest,
    build_invalidation_manifest,
    build_phase6_acceptance,
    build_repair_history,
    build_repair_plan,
    build_unified_release_gate,
)
from presentation_agent.deckcompiler.repair.fixture import bind_hash  # noqa: E402
from presentation_agent.deckcompiler.schemas import validator_for  # noqa: E402


def _report(payload: dict) -> dict:
    result = dict(payload)
    result["report_hash"] = content_sha256(result)
    return result


class Phase6RepairClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.finding = {
            "finding_id": "VISUAL_TEXT_OFF_CANVAS_SLIDE_001",
            "detector": "DeckCompiler composite QA",
            "severity": "severe",
            "slide_id": "slide-001",
            "artifact_id": "pptx-slide-001-shape-17",
        }
        self.detection = _report(
            {
                "schema_name": "phase6_failure_detection_report",
                "fixture_id": "phase6-fixture-text-off-canvas-slide-001",
                "status": "NEEDS_REPAIR",
                "detected_finding": self.finding,
                "canonical_repair_owner": "src/presentation_agent/deckcompiler/qa/reconstruction_source/slides.js",
                "target_field": "#/functions/s1/recommended_decision_body/x",
                "checks": {"expected_finding_detected": True, "repair_owner_proven": True},
            }
        )
        self.application = {
            "fixture_id": self.detection["fixture_id"],
            "before_sha256": "a" * 64,
            "after_sha256": "b" * 64,
            "application_hash": "c" * 64,
            "changed_paths": ["lib/slides.js"],
            "mutation_count": 1,
            "canonical_owner_path": self.detection["canonical_repair_owner"],
            "target_field": self.detection["target_field"],
        }
        self.spec = bind_hash(
            {
                "fixture_id": self.detection["fixture_id"],
                "canonical_repair_owner": {"path": self.detection["canonical_repair_owner"], "sha256": "a" * 64},
                "target_field": self.detection["target_field"],
                "expected_invalidated_artifacts": list(INVALIDATED_ARTIFACT_IDS),
            },
            "fixture_hash",
        )
        self.contract = bind_hash(
            {
                "fixture_id": self.detection["fixture_id"],
                "owner_artifact": self.detection["canonical_repair_owner"],
                "owner_field": self.detection["target_field"],
                "owner_sha256": "a" * 64,
                "expected_after_value": 210,
                "maximum_outer_waves": 3,
                "repair_action_type": "rematerialize_canonical_owner",
                "direct_final_pptx_patch": False,
                "direct_final_html_patch": False,
                "semantic_content_change": False,
                "evidence_binding_change": False,
                "visual_target_change": False,
            },
            "contract_hash",
        )
        self.plan = build_repair_plan(
            self.detection,
            self.application,
            self.spec,
            self.contract,
            source_commit="d" * 40,
            created_at="2026-07-22T13:00:00+09:00",
        )

    def test_plan_references_actual_detection_and_owner(self) -> None:
        self.assertEqual(self.plan["finding_ids"], [self.finding["finding_id"]])
        self.assertEqual(self.plan["source_detector"], self.finding["detector"])
        self.assertEqual(self.plan["canonical_repair_owner"], self.detection["canonical_repair_owner"])
        self.assertEqual(self.plan["baseline_sha256"], "a" * 64)
        self.assertEqual(self.plan["faulty_sha256"], "b" * 64)

    def test_plan_is_schema_valid_and_forbids_direct_output_patch(self) -> None:
        self.assertEqual(list(validator_for("repair_plan").iter_errors(self.plan)), [])
        self.assertFalse(self.plan["direct_final_pptx_patch"])
        self.assertFalse(self.plan["direct_final_html_patch"])
        self.assertEqual(self.plan["maximum_outer_waves"], 3)
        self.assertEqual(self.plan["current_wave"], 1)

    def test_repair_cannot_start_without_actual_detection(self) -> None:
        blocked = deepcopy(self.detection)
        blocked["checks"]["expected_finding_detected"] = False
        blocked["report_hash"] = content_sha256({key: value for key, value in blocked.items() if key != "report_hash"})
        with self.assertRaisesRegex(RepairClosureError, "CONTROLLED_DETECTION_REQUIRED"):
            build_repair_plan(blocked, self.application, self.spec, self.contract, source_commit="d" * 40)

    def test_invalidation_is_complete_deterministic_and_schema_valid(self) -> None:
        hashes = {name: f"{index:064x}" for index, name in enumerate(INVALIDATED_ARTIFACT_IDS, 1)}
        first = build_invalidation_manifest(self.plan, hashes, created_at="2026-07-22T13:01:00+09:00")
        second = build_invalidation_manifest(self.plan, dict(reversed(list(hashes.items()))), created_at="2026-07-22T13:01:00+09:00")
        self.assertEqual(first, second)
        self.assertEqual(first["invalidated_artifact_count"], len(INVALIDATED_ARTIFACT_IDS))
        self.assertEqual([row["artifact_id"] for row in first["invalidated_artifacts"]], list(INVALIDATED_ARTIFACT_IDS))
        self.assertEqual(first["stale_artifact_policy"], "reject_all_prior_downstream_evidence")
        self.assertEqual(list(validator_for("invalidation_manifest").iter_errors(first)), [])

    def _repaired(self) -> dict:
        return {
            "run_id": "repaired-run-new",
            "fault_state": "repaired",
            "prior_runtime_reused": False,
            "source_commit": "d" * 40,
            "upstream_sha256": "a" * 64,
            "pptx_sha256": "e" * 64,
            "html_sha256": "f" * 64,
            "pptx_render_sha256_by_slide": {f"slide-{slide:03d}": f"{slide:064x}" for slide in range(1, 7)},
            "html_screenshot_sha256_by_slide": {f"slide-{slide:03d}": f"{slide + 6:064x}" for slide in range(1, 7)},
            "html_screenshot_capture_manifest_hash": "1" * 64,
            "objective_evidence_hash": "2" * 64,
            "evidence_capsule_manifest_hash": "3" * 64,
            "external_reconciliation_report_hash": "4" * 64,
            "composite_report_hash": "5" * 64,
            "official_final_gate": "PASS",
            "render_count": 6,
            "html_screenshot_count": 6,
            "repaired_micro_canary_count": 2,
            "timeout_count": 0,
            "dimension_mismatch_count": 0,
            "missing_artifact_count": 0,
            "stale_artifact_count": 0,
            "hash_mismatch_count": 0,
            "expected_finding_resolved": True,
            "new_severe_finding_count": 0,
            "external_reconciliation": "PASS",
            "composite_qa": "PASS",
            "semantic_fidelity": 1.0,
            "source_coverage": 1.0,
            "native_editability": 1.0,
            "raster_violation_count": 0,
            "pptx_html_parity": 1.0,
        }

    def test_repair_history_closes_one_wave_without_direct_patch(self) -> None:
        invalidation = build_invalidation_manifest(
            self.plan,
            {name: f"{index:064x}" for index, name in enumerate(INVALIDATED_ARTIFACT_IDS, 1)},
        )
        history = build_repair_history(self.plan, invalidation, self._repaired(), created_at="2026-07-22T13:02:00+09:00")
        self.assertEqual(history["waves_used"], 1)
        self.assertEqual(history["waves_allowed"], 3)
        self.assertEqual(history["status"], "CONVERGED")
        self.assertFalse(history["waves"][0]["direct_output_patch"])
        self.assertEqual(list(validator_for("repair_history").iter_errors(history)), [])

    def test_repaired_run_must_be_fresh_complete_and_resolved(self) -> None:
        repaired = self._repaired()
        repaired["prior_runtime_reused"] = True
        invalidation = build_invalidation_manifest(self.plan, {name: "1" * 64 for name in INVALIDATED_ARTIFACT_IDS})
        with self.assertRaisesRegex(RepairClosureError, "FRESH_REPAIRED_RUNTIME_REQUIRED"):
            build_repair_history(self.plan, invalidation, repaired)
        repaired = self._repaired()
        repaired["expected_finding_resolved"] = False
        with self.assertRaisesRegex(RepairClosureError, "EXPECTED_FINDING_NOT_RESOLVED"):
            build_repair_history(self.plan, invalidation, repaired)

    def test_new_severe_finding_or_wave_overflow_blocks(self) -> None:
        invalidation = build_invalidation_manifest(self.plan, {name: "1" * 64 for name in INVALIDATED_ARTIFACT_IDS})
        repaired = self._repaired()
        repaired["new_severe_finding_count"] = 1
        with self.assertRaisesRegex(RepairClosureError, "NEW_SEVERE_FINDING"):
            build_repair_history(self.plan, invalidation, repaired)
        overflow = deepcopy(self.plan)
        overflow["current_wave"] = 4
        with self.assertRaisesRegex(RepairClosureError, "REPAIR_LIMIT"):
            build_repair_history(overflow, invalidation, self._repaired())

    def test_before_after_manifest_binds_three_states(self) -> None:
        baseline = {"upstream_sha256": "a" * 64, "pptx_sha256": "6" * 64, "html_sha256": "7" * 64}
        faulty = {"upstream_sha256": "b" * 64, "pptx_sha256": "8" * 64, "html_sha256": "9" * 64}
        result = build_before_after_manifest(
            self.plan,
            baseline,
            faulty,
            self._repaired(),
            semantic_content_unchanged=True,
            evidence_bindings_unchanged=True,
            visual_targets_unchanged=True,
        )
        self.assertEqual(result["states"]["repaired"]["upstream_sha256"], "a" * 64)
        self.assertEqual(list(validator_for("before_after_manifest").iter_errors(result)), [])

    def test_unified_gate_is_eligible_but_not_release_eligible(self) -> None:
        evidence = {
            "phase6a_baseline_composite": "PASS",
            "phase61a1_reconciliation": "PASS",
            "postcommit_baseline_reachability": "PASS",
            "html_screenshot_stabilization": "PASS",
            "controlled_fault_detection": "PASS",
            "canonical_repair_owner_valid": True,
            "invalidation_complete": True,
            "repair_waves_used": 1,
            "repair_waves_allowed": 3,
            "repaired_official_final_gate": "PASS",
            "repaired_render_count": 6,
            "repaired_screenshot_count": 6,
            "repaired_external_reconciliation": "PASS",
            "repaired_composite_qa": "PASS",
            "external_skill_unchanged": True,
            "phase4_unchanged": True,
            "phase5_unchanged": True,
            "removed_skill_absent": True,
            "protected_outputs_absent": True,
            "git_clean_at_evaluation": True,
        }
        gate = build_unified_release_gate(evidence, source_commit="d" * 40)
        acceptance = build_phase6_acceptance(gate)
        self.assertEqual(gate["status"], "ELIGIBLE_FOR_PACKAGING")
        self.assertTrue(gate["phase6_accepted"])
        self.assertFalse(gate["final_release_eligible"])
        self.assertFalse(gate["devpost_release_eligible"])
        self.assertTrue(gate["phase7_required"])
        self.assertEqual(gate["active_output_set"], "phase5_baseline")
        self.assertEqual(acceptance["status"], "ELIGIBLE_FOR_PACKAGING")
        self.assertEqual(list(validator_for("unified_release_gate_report").iter_errors(gate)), [])
        self.assertEqual(list(validator_for("phase6_acceptance").iter_errors(acceptance)), [])

    def test_unified_gate_fails_closed_on_any_missing_prerequisite(self) -> None:
        with self.assertRaisesRegex(RepairClosureError, "BLOCKED_RELEASE_EVIDENCE_INCOMPLETE"):
            build_unified_release_gate({"phase6a_baseline_composite": "PASS"}, source_commit="d" * 40)


if __name__ == "__main__":
    unittest.main()
