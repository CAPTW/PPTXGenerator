from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
FIXTURE_DIR = ROOT / "examples" / "deckcompiler_demo" / "phase6" / "fixtures" / "intentional_repair"
PHASE5_PPTX = ROOT / "examples" / "deckcompiler_demo" / "phase5" / "outputs" / "pptx_generator_demo.pptx"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.manifest_io import read_json  # noqa: E402
from presentation_agent.deckcompiler.identity import content_sha256  # noqa: E402
from presentation_agent.deckcompiler.qa.contracts import make_finding, sha256_file, with_report_hash  # noqa: E402
from presentation_agent.deckcompiler.qa.reachability import ReachabilityConfig, _stage_reconstruction_source  # noqa: E402
from presentation_agent.deckcompiler.repair.fixture import (  # noqa: E402
    FaultFixtureError,
    apply_fault_fixture,
    bind_hash,
    evaluate_fault_detection,
    validate_fault_fixture,
    verify_bound_hash,
)
from presentation_agent.deckcompiler.schemas import validator_for  # noqa: E402


ORIGINAL = "  T(s, d.body[0], 210, 246, 452, 128, { sz: 16.5, b: true, color: P.ink, valign: 'middle', lh: 1.06, shrink: true });"
INJECTED = "  T(s, d.body[0], -220, 246, 452, 128, { sz: 16.5, b: true, color: P.ink, valign: 'middle', lh: 1.06, shrink: true });"


class Phase6FaultFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="phase6-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.spec = read_json(FIXTURE_DIR / "fault_injection_spec.json")
        self.repository = self.base / "repository"
        canonical_source = ROOT / self.spec["canonical_repair_owner"]["path"]
        canonical_copy = self.repository / self.spec["canonical_repair_owner"]["path"]
        canonical_copy.parent.mkdir(parents=True)
        canonical_copy.write_bytes(canonical_source.read_bytes())
        self.project = self.base / "project"
        target = self.project / "lib" / "slides.js"
        target.parent.mkdir(parents=True)
        target.write_bytes(canonical_source.read_bytes())
        self.spec["target_upstream_artifact"]["sha256"] = sha256_file(target)
        self.spec["canonical_repair_owner"]["sha256"] = sha256_file(canonical_copy)
        self.spec = bind_hash(self.spec, "fixture_hash")
        self.spec_path = self.base / "fault_injection_spec.json"
        self._write(self.spec_path, self.spec)
        self.expected = read_json(FIXTURE_DIR / "expected_finding.json")

    @staticmethod
    def _write(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _apply(self, project: Path | None = None):
        return apply_fault_fixture(self.spec_path, project or self.project, self.repository)

    def _expected_finding(self) -> dict:
        return make_finding(
            gate="visual",
            category="geometry",
            severity="severe",
            rule_id="P6-VIS-TEXT-OFF-CANVAS-001",
            message="Editable text crosses the slide canvas boundary.",
            evidence={
                "bbox_emu": {"left": -1676400, "top": 1874520, "width": 3444240, "height": 975360, "right": 1767840, "bottom": 2849880, "area_ratio": 0.04013568},
                "slide_width_emu": 12192000,
                "slide_height_emu": 6858000,
            },
            owning_artifact="handoff/project/lib/slides.js",
            recommended_action="Restore upstream slot geometry and fully rebuild.",
            repairable=True,
            release_blocking=True,
            slide_id="slide-001",
            artifact_id="pptx-slide-001-shape-15",
            finding_id="VISUAL_TEXT_OFF_CANVAS_SLIDE_001",
        )

    def _composite(self, *findings: dict, status: str = "NEEDS_REPAIR") -> dict:
        return with_report_hash(
            {
                "schema_name": "phase6_composite_qa_report",
                "status": status,
                "checks": {
                    "composite_dimension_checks": status,
                    "external_visual_reconciliation": "NEEDS_REPAIR",
                    "composite_acceptance": status,
                },
                "findings": list(findings),
                "implementation_provenance": {"component": "presentation_agent.deckcompiler.qa"},
            }
        )

    def _application(self) -> dict:
        return self._apply().to_dict()

    @staticmethod
    def _capsule(*, fault_state: str = "faulty", missing: int = 0) -> dict:
        pptx_sha256 = "b" * 64
        html_sha256 = "c" * 64
        payload = {
            "fault_state": fault_state,
            "pptx_sha256": pptx_sha256,
            "html_sha256": html_sha256,
            "capsule_status": "COMPOSITE_QA_COMPLETE",
            "missing_artifact_count": missing,
            "stale_artifact_count": 0,
            "hash_mismatch_count": 0,
            "per_slide_crop_plan_records": [{} for _ in range(6)],
            "pptx_raster_evidence_records": [
                {"slide": slide, "sha256": f"{slide:064x}", "parent_pptx_sha256": pptx_sha256}
                for slide in range(1, 7)
            ],
            "html_screenshot_evidence_records": [
                {"slide": slide, "sha256": f"{slide + 6:064x}", "parent_html_sha256": html_sha256}
                for slide in range(1, 7)
            ],
            "html_screenshot_capture_manifest_record": {"manifest_hash": "d" * 64, "status": "PASS"},
            "objective_evidence": {"status": "EVIDENCE_VALID", "objective_evidence_hash": "a" * 64},
            "reconstruction_score_record": {"status": "pass", "slide_records": [{"status": "pass", "binding_valid": True} for _ in range(6)]},
            "official_final_gate_record": {"status": "PASS"},
            "composite_qa_record": {"status": "NEEDS_REPAIR"},
        }
        payload["manifest_hash"] = content_sha256(payload)
        return payload

    @staticmethod
    def _reconciliation(*, status: str = "NEEDS_REPAIR") -> dict:
        payload = {
            "status": status,
            "mapped_coverage_ratio": 1.0,
            "reported_nonpass_count": 6,
            "mapped_nonpass_covered_count": 6,
            "unresolved_external_finding_count": 1,
        }
        payload["report_hash"] = content_sha256(payload)
        return payload

    def _evaluate(
        self,
        composite: dict,
        *,
        expected: dict | None = None,
        application: dict | None = None,
        capsule: dict | None = None,
        reconciliation: dict | None = None,
        unchanged: bool = True,
    ):
        return evaluate_fault_detection(
            composite,
            expected or self.expected,
            application or self._application(),
            evidence_capsule=capsule or self._capsule(),
            external_reconciliation=reconciliation or self._reconciliation(),
            official_final_gate_status="PASS",
            renderer_status="PASS",
            canonical_baseline_unchanged=unchanged,
            created_at="2026-07-22T11:30:00+09:00",
            deckcompiler_commit="ea6b8bc09011418cc2ca9d9d3e44e1b1f82d05c6",
        )

    def test_fixture_schema_is_valid(self) -> None:
        self.assertEqual(list(validator_for("fault_injection_spec").iter_errors(self.spec)), [])
        validate_fault_fixture(self.spec)

    def test_target_upstream_artifact_exists(self) -> None:
        self.assertTrue((self.project / self.spec["target_upstream_artifact"]["path"]).is_file())

    def test_runtime_derivative_is_not_canonical_repair_owner(self) -> None:
        self.assertEqual(self.spec["target_upstream_artifact"]["path"], "lib/slides.js")
        self.assertEqual(
            self.spec["canonical_repair_owner"]["path"],
            "src/presentation_agent/deckcompiler/qa/reconstruction_source/slides.js",
        )
        self.assertNotEqual(self.spec["target_upstream_artifact"]["path"], self.spec["canonical_repair_owner"]["path"])

    def test_canonical_repair_owner_hash_and_producer_are_proven(self) -> None:
        owner = self.spec["canonical_repair_owner"]
        self.assertEqual(sha256_file(ROOT / owner["path"]), owner["sha256"])
        self.assertEqual(owner["producer_function"], "presentation_agent.deckcompiler.qa.reachability._stage_reconstruction_source")
        self.assertFalse(owner["higher_geometry_source_present"])

    def test_handoff_producer_materializes_the_canonical_owner_byte_for_byte(self) -> None:
        project = self.base / "staged-project"
        (project / "lib").mkdir(parents=True)
        config = ReachabilityConfig(
            repo_root=ROOT,
            runtime_root=self.base / "unused-runtime",
            source_commit="35da79c81714947964b6e93c71f1e160f02896af",
            run_id="owner-audit",
            fault_state="faulty",
            created_at="2026-07-22T11:30:00+09:00",
            external_skill_root=self.base / "skills",
            profile_path=self.base / "profile.json",
            node_modules=self.base / "node_modules",
            node_executable=Path("node.exe"),
            python_executable=Path("python.exe"),
            baseline=False,
        )
        provenance = _stage_reconstruction_source(config, project)
        self.assertEqual(
            sha256_file(project / "lib" / "slides.js"),
            sha256_file(ROOT / self.spec["canonical_repair_owner"]["path"]),
        )
        self.assertEqual(provenance["owner"], "deck_owned_canonical_reconstruction_geometry_source")
        self.assertFalse(provenance["higher_geometry_source_present"])

    def test_expected_detector_owner_is_the_materialized_handoff_derivative(self) -> None:
        self.assertEqual(self.expected["owning_artifact"], "handoff/project/lib/slides.js")
        self.assertEqual(self.expected["canonical_repair_owner"], self.spec["canonical_repair_owner"]["path"])
        self.assertEqual(self.expected["injection_surface"], self.spec["target_upstream_artifact"]["path"])

    def test_expected_finding_binds_exact_object_slot_and_owner_field(self) -> None:
        self.assertEqual(self.expected["object_id"], "recommended-decision-body-text")
        self.assertEqual(self.expected["slot_id"], "recommended-decision-body")
        self.assertEqual(self.expected["target_field"], self.spec["target_field"])

    def test_original_field_value_matches(self) -> None:
        self.assertEqual((self.project / "lib" / "slides.js").read_text(encoding="utf-8").count(ORIGINAL), 1)

    def test_mutation_is_deterministic(self) -> None:
        first = self._apply()
        second_project = self.base / "project-2"
        (second_project / "lib").mkdir(parents=True)
        (second_project / "lib" / "slides.js").write_bytes(
            (self.repository / self.spec["canonical_repair_owner"]["path"]).read_bytes()
        )
        second = apply_fault_fixture(self.spec_path, second_project, self.repository)
        self.assertEqual(first.after_sha256, second.after_sha256)
        self.assertEqual(first.application_hash, second.application_hash)

    def test_exactly_one_intended_upstream_mutation(self) -> None:
        result = self._apply()
        self.assertEqual(result.changed_paths, ("lib/slides.js",))
        self.assertEqual(result.mutation_count, 1)

    def test_semantic_evidence_and_visual_authorities_are_unchanged(self) -> None:
        result = self._apply()
        self.assertFalse(result.semantic_content_changed)
        self.assertFalse(result.evidence_binding_changed)
        self.assertFalse(result.visual_target_changed)

    def test_direct_final_pptx_mutation_is_rejected(self) -> None:
        bad = deepcopy(self.spec)
        bad["target_upstream_artifact"]["path"] = "out/deck.pptx"
        bad["expected_owner"] = "out/deck.pptx"
        bad = bind_hash(bad, "fixture_hash")
        with self.assertRaisesRegex(FaultFixtureError, "DIRECT_FINAL_OUTPUT_MUTATION_REJECTED"):
            validate_fault_fixture(bad)

    def test_random_injection_is_rejected(self) -> None:
        bad = deepcopy(self.spec)
        bad["injection_type"] = "random_corruption"
        bad = bind_hash(bad, "fixture_hash")
        with self.assertRaisesRegex(FaultFixtureError, "PROHIBITED_NONDETERMINISTIC"):
            validate_fault_fixture(bad)

    def test_path_traversal_is_rejected(self) -> None:
        bad = deepcopy(self.spec)
        bad["target_upstream_artifact"]["path"] = "../slides.js"
        bad["expected_owner"] = "../slides.js"
        bad = bind_hash(bad, "fixture_hash")
        with self.assertRaisesRegex(FaultFixtureError, "PROJECT_RELATIVE"):
            validate_fault_fixture(bad)

    def test_repository_runtime_is_rejected(self) -> None:
        with self.assertRaisesRegex(FaultFixtureError, "OUTSIDE_REPOSITORY"):
            apply_fault_fixture(self.spec_path, self.repository, self.repository)

    def test_target_hash_mismatch_is_rejected(self) -> None:
        (self.project / "lib" / "slides.js").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(FaultFixtureError, "HASH_MISMATCH"):
            self._apply()

    def test_multiple_original_fragments_are_rejected(self) -> None:
        target = self.project / "lib" / "slides.js"
        target.write_text(f"{ORIGINAL}\n{ORIGINAL}\n", encoding="utf-8", newline="")
        owner = self.repository / self.spec["canonical_repair_owner"]["path"]
        owner.write_bytes(target.read_bytes())
        self.spec["target_upstream_artifact"]["sha256"] = sha256_file(target)
        self.spec["canonical_repair_owner"]["sha256"] = sha256_file(owner)
        self.spec = bind_hash(self.spec, "fixture_hash")
        self._write(self.spec_path, self.spec)
        with self.assertRaisesRegex(FaultFixtureError, "OCCURRENCE_COUNT"):
            self._apply()

    def test_injected_fragment_already_present_is_rejected(self) -> None:
        target = self.project / "lib" / "slides.js"
        target.write_text(f"{ORIGINAL}\n{INJECTED}\n", encoding="utf-8", newline="")
        owner = self.repository / self.spec["canonical_repair_owner"]["path"]
        owner.write_bytes(target.read_bytes())
        self.spec["target_upstream_artifact"]["sha256"] = sha256_file(target)
        self.spec["canonical_repair_owner"]["sha256"] = sha256_file(owner)
        self.spec = bind_hash(self.spec, "fixture_hash")
        self._write(self.spec_path, self.spec)
        with self.assertRaisesRegex(FaultFixtureError, "ALREADY_PRESENT"):
            self._apply()

    def test_application_record_is_schema_valid(self) -> None:
        output = self.base / "application.json"
        self._apply()
        second_project = self.base / "project-output"
        (second_project / "lib").mkdir(parents=True)
        (second_project / "lib" / "slides.js").write_bytes(
            (self.repository / self.spec["canonical_repair_owner"]["path"]).read_bytes()
        )
        apply_fault_fixture(self.spec_path, second_project, self.repository, output_path=output)
        self.assertEqual(list(validator_for("fault_application_record").iter_errors(read_json(output))), [])

    def test_expected_finding_is_detected_exactly(self) -> None:
        report = self._evaluate(self._composite(self._expected_finding()))
        self.assertEqual(report["detected_finding"]["finding_id"], self.expected["finding_id"])
        self.assertEqual(report["status"], "NEEDS_REPAIR")

    def test_detection_report_binds_current_faulty_visual_evidence(self) -> None:
        report = self._evaluate(self._composite(self._expected_finding()))
        evidence = report["current_faulty_evidence"]
        self.assertEqual(evidence["pptx_sha256"], "b" * 64)
        self.assertEqual(evidence["html_sha256"], "c" * 64)
        self.assertEqual(evidence["html_screenshot_capture_manifest_hash"], "d" * 64)
        self.assertEqual(len(evidence["pptx_render_sha256_by_slide"]), 6)
        self.assertEqual(len(evidence["html_screenshot_sha256_by_slide"]), 6)
        self.assertEqual(report["target_object"], "recommended-decision-body-text")
        self.assertEqual(report["target_slot"], "recommended-decision-body")
        self.assertEqual(report["target_field"], self.spec["target_field"])

    def test_expected_owner_matches_exactly(self) -> None:
        report = self._evaluate(self._composite(self._expected_finding()))
        self.assertEqual(report["detected_finding"]["owning_artifact"], "handoff/project/lib/slides.js")
        self.assertEqual(
            report["canonical_repair_owner"],
            "src/presentation_agent/deckcompiler/qa/reconstruction_source/slides.js",
        )

    def test_missing_capsule_prerequisite_is_not_detection(self) -> None:
        with self.assertRaisesRegex(FaultFixtureError, "BLOCKED_FAULT_FIXTURE_UNCONTROLLED"):
            self._evaluate(self._composite(self._expected_finding()), capsule=self._capsule(missing=1))

    def test_prior_baseline_capsule_reuse_is_rejected(self) -> None:
        with self.assertRaisesRegex(FaultFixtureError, "FRESH_FAULT_CAPSULE_REQUIRED"):
            self._evaluate(self._composite(self._expected_finding()), capsule=self._capsule(fault_state="baseline"))

    def test_external_reconciliation_must_reach_controlled_needs_repair(self) -> None:
        with self.assertRaisesRegex(FaultFixtureError, "EXTERNAL_RECONCILIATION"):
            self._evaluate(self._composite(self._expected_finding()), reconciliation=self._reconciliation(status="BLOCKED"))

    def test_manual_finding_without_detector_geometry_is_rejected(self) -> None:
        finding = self._expected_finding()
        finding["detector"] = "manual insertion"
        finding["finding_hash"] = content_sha256({key: value for key, value in finding.items() if key != "finding_hash"})
        with self.assertRaisesRegex(FaultFixtureError, "DETECTOR_PROVENANCE"):
            self._evaluate(self._composite(finding))

    def test_missing_detector_fails_closed(self) -> None:
        with self.assertRaisesRegex(FaultFixtureError, "BLOCKED_INTENTIONAL_FAILURE_NOT_DETECTED"):
            self._evaluate(self._composite())

    def test_wrong_finding_id_fails_closed(self) -> None:
        wrong = self._expected_finding()
        wrong["finding_id"] = "OTHER_FINDING"
        wrong["finding_hash"] = "0" * 64
        with self.assertRaisesRegex(FaultFixtureError, "NOT_DETECTED"):
            self._evaluate(self._composite(wrong))

    def test_uncontrolled_extra_severe_finding_blocks(self) -> None:
        extra = make_finding(
            gate="visual", category="other", severity="severe", rule_id="P6-OTHER-001", message="other",
            evidence={"other": True}, owning_artifact="lib/other.js", recommended_action="stop", repairable=True,
            release_blocking=True, finding_id="UNCONTROLLED_SEVERE",
        )
        with self.assertRaisesRegex(FaultFixtureError, "BLOCKED_FAULT_FIXTURE_UNCONTROLLED"):
            self._evaluate(self._composite(self._expected_finding(), extra))

    def test_semantic_corruption_blocks(self) -> None:
        extra = make_finding(
            gate="semantic", category="fidelity", severity="error", rule_id="P6-SEM-001", message="semantic",
            evidence={"semantic": False}, owning_artifact="mapping", recommended_action="stop", repairable=False,
            release_blocking=True, finding_id="SEMANTIC_CORRUPTION",
        )
        with self.assertRaisesRegex(FaultFixtureError, "BLOCKED_FAULT_FIXTURE_UNCONTROLLED"):
            self._evaluate(self._composite(self._expected_finding(), extra))

    def test_package_corruption_blocks(self) -> None:
        extra = make_finding(
            gate="package_render", category="package", severity="error", rule_id="P6-PKG-001", message="package",
            evidence={"crc": False}, owning_artifact="pptx", recommended_action="stop", repairable=False,
            release_blocking=True, finding_id="PACKAGE_CORRUPTION",
        )
        with self.assertRaisesRegex(FaultFixtureError, "BLOCKED_FAULT_FIXTURE_UNCONTROLLED"):
            self._evaluate(self._composite(self._expected_finding(), extra))

    def test_invalid_composite_hash_blocks(self) -> None:
        report = self._composite(self._expected_finding())
        report["report_hash"] = "0" * 64
        with self.assertRaisesRegex(FaultFixtureError, "COMPOSITE_REPORT_HASH_INVALID"):
            self._evaluate(report)

    def test_faulty_composite_cannot_self_accept(self) -> None:
        with self.assertRaisesRegex(FaultFixtureError, "MUST_BE_NEEDS_REPAIR"):
            self._evaluate(self._composite(self._expected_finding(), status="PASS"))

    def test_baseline_mutation_blocks(self) -> None:
        with self.assertRaisesRegex(FaultFixtureError, "BLOCKED_CANONICAL_BASELINE_MUTATION"):
            self._evaluate(self._composite(self._expected_finding()), unchanged=False)

    def test_canonical_baseline_file_is_unchanged_by_fixture(self) -> None:
        before = sha256_file(PHASE5_PPTX)
        self._apply()
        self.assertEqual(sha256_file(PHASE5_PPTX), before)

    def test_fault_builder_does_not_create_faulty_outputs(self) -> None:
        self._apply()
        self.assertEqual(list(self.project.rglob("*.pptx")), [])
        self.assertEqual(list(self.project.rglob("*.html")), [])

    def test_repair_contract_exists_and_is_hash_bound(self) -> None:
        contract = read_json(FIXTURE_DIR / "repair_contract.json")
        self.assertEqual(list(validator_for("repair_contract").iter_errors(contract)), [])
        self.assertTrue(verify_bound_hash(contract, "contract_hash"))
        self.assertFalse(contract["direct_final_pptx_patch"])
        self.assertEqual(contract["owner_artifact"], self.spec["canonical_repair_owner"]["path"])
        self.assertEqual(contract["injection_surface"], self.spec["target_upstream_artifact"]["path"])

    def test_fixture_provenance_is_hash_bound(self) -> None:
        provenance = read_json(FIXTURE_DIR / "fixture_provenance.json")
        self.assertEqual(list(validator_for("fixture_provenance").iter_errors(provenance)), [])
        self.assertTrue(verify_bound_hash(provenance, "provenance_hash"))
        self.assertFalse(provenance["old_phase5_repair_history_reused"])


if __name__ == "__main__":
    unittest.main()
