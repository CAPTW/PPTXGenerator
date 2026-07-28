from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PHASE4 = ROOT / "examples" / "deckcompiler_demo" / "phase4"
PHASE5 = ROOT / "examples" / "deckcompiler_demo" / "phase5"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.qa.composite import (  # noqa: E402
    EXPECTED_BASELINE_HTML,
    EXPECTED_BASELINE_PPTX,
    EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
    EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
    _base_findings_for_prerequisites,
    _semantic_findings,
    run_composite_qa,
    validate_composite_qa,
)
from presentation_agent.deckcompiler.qa.contracts import (  # noqa: E402
    gate_status,
    make_finding,
    verify_finding_hash,
    verify_report_hash,
)
from presentation_agent.deckcompiler.qa.inspection import (  # noqa: E402
    creative_inspection,
    inspect_html,
    load_sidecars,
    source_coverage_inspection,
)
from presentation_agent.deckcompiler.qa.rendering import (  # noqa: E402
    build_contact_sheet,
    inspect_renders,
)


def blocking_finding(*, severity: str = "error", repairable: bool = False, release_blocking: bool = True) -> dict:
    return make_finding(
        gate="test",
        category="test",
        severity=severity,
        rule_id="P6-TEST-001",
        message="test finding",
        evidence={"test": True},
        owning_artifact="test owner",
        recommended_action="test action",
        repairable=repairable,
        release_blocking=release_blocking,
    )


class Phase6CompositeQATests(unittest.TestCase):
    def test_canonical_prerequisite_hashes_are_independently_recomputed(self) -> None:
        phase4 = json.loads(
            (ROOT / "examples" / "deckcompiler_demo" / "phase7" / "contract" / "phase4_bundle_fingerprint_authority.json").read_text(encoding="utf-8")
        )
        phase5 = json.loads(
            (ROOT / "examples" / "deckcompiler_demo" / "phase7" / "contract" / "phase5_bundle_fingerprint_authority.json").read_text(encoding="utf-8")
        )
        self.assertEqual(phase4["git_object_fingerprint"]["aggregate_sha256"], EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE)
        self.assertEqual(phase5["git_object_fingerprint"]["aggregate_sha256"], EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE)
        self.assertEqual(phase4["file_count"], 107)
        self.assertEqual(phase5["file_count"], 38)

    def test_missing_phase5_prerequisite_blocks(self) -> None:
        findings = _base_findings_for_prerequisites(
            phase4_hash=EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
            phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            expected_phase4_hash=EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
            expected_phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            pptx_hash=EXPECTED_BASELINE_PPTX,
            html_hash=EXPECTED_BASELINE_HTML,
            missing=["official gate"],
            embedded_hash_failures=[],
            baseline=True,
        )
        self.assertEqual(gate_status(findings), "BLOCKED")

    def test_modified_phase4_bundle_blocks(self) -> None:
        findings = _base_findings_for_prerequisites(
            phase4_hash="0" * 64,
            phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            expected_phase4_hash=EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
            expected_phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            pptx_hash=EXPECTED_BASELINE_PPTX,
            html_hash=EXPECTED_BASELINE_HTML,
            missing=[],
            embedded_hash_failures=[],
            baseline=True,
        )
        self.assertEqual(findings[0]["gate"], "prerequisite_integrity")
        self.assertEqual(gate_status(findings), "BLOCKED")

    def test_modified_phase5_pptx_blocks(self) -> None:
        findings = _base_findings_for_prerequisites(
            phase4_hash=EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
            phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            expected_phase4_hash=EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
            expected_phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            pptx_hash="1" * 64,
            html_hash=EXPECTED_BASELINE_HTML,
            missing=[],
            embedded_hash_failures=[],
            baseline=True,
        )
        self.assertEqual(gate_status(findings), "BLOCKED")

    def test_modified_html_blocks(self) -> None:
        findings = _base_findings_for_prerequisites(
            phase4_hash=EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
            phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            expected_phase4_hash=EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
            expected_phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            pptx_hash=EXPECTED_BASELINE_PPTX,
            html_hash="2" * 64,
            missing=[],
            embedded_hash_failures=[],
            baseline=True,
        )
        self.assertEqual(gate_status(findings), "BLOCKED")

    def test_report_hash_mismatch_blocks_prerequisite(self) -> None:
        findings = _base_findings_for_prerequisites(
            phase4_hash=EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
            phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            expected_phase4_hash=EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE,
            expected_phase5_hash=EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE,
            pptx_hash=EXPECTED_BASELINE_PPTX,
            html_hash=EXPECTED_BASELINE_HTML,
            missing=[],
            embedded_hash_failures=["report.json"],
            baseline=True,
        )
        self.assertEqual(gate_status(findings), "BLOCKED")

    def test_semantic_fidelity_below_one_blocks(self) -> None:
        metrics = {
            "pptx_fidelity": 0.99,
            "html_fidelity": 1.0,
            "unknown_factual_addition_count": 0,
            "pptx_number_unit_pass_count": 79,
            "html_number_unit_pass_count": 79,
            "number_unit_token_count": 79,
            "pptx_table_cell_pass_count": 4,
            "html_table_cell_pass_count": 4,
            "table_cell_count": 4,
            "pptx_citation_source_note_pass_count": 30,
            "html_citation_source_note_pass_count": 30,
            "citation_source_note_count": 30,
        }
        self.assertEqual(gate_status(_semantic_findings(metrics)), "BLOCKED")

    def test_unknown_factual_addition_blocks(self) -> None:
        metrics = {
            "pptx_fidelity": 1.0,
            "html_fidelity": 1.0,
            "unknown_factual_addition_count": 1,
            "pptx_number_unit_pass_count": 79,
            "html_number_unit_pass_count": 79,
            "number_unit_token_count": 79,
            "pptx_table_cell_pass_count": 4,
            "html_table_cell_pass_count": 4,
            "table_cell_count": 4,
            "pptx_citation_source_note_pass_count": 30,
            "html_citation_source_note_pass_count": 30,
            "citation_source_note_count": 30,
        }
        self.assertEqual(gate_status(_semantic_findings(metrics)), "BLOCKED")

    def test_source_coverage_recomputes_all_sidecar_bindings(self) -> None:
        sidecars = load_sidecars(PHASE4)
        phase4_input = json.loads((PHASE4 / "input_provenance.json").read_text(encoding="utf-8"))
        result = source_coverage_inspection(sidecars, phase4_input)
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["unresolved_evidence_ids"], [])
        self.assertGreater(result["binding_count"], 0)

    def test_unknown_evidence_binding_reduces_coverage(self) -> None:
        sidecars = load_sidecars(PHASE4)
        mutated = deepcopy(sidecars)
        mutated[0]["sidecar"]["source_bindings"][0]["evidence_ids"] = ["ev_missing"]
        phase4_input = json.loads((PHASE4 / "input_provenance.json").read_text(encoding="utf-8"))
        result = source_coverage_inspection(mutated, phase4_input)
        self.assertEqual(result["coverage"], 0.0)
        self.assertEqual(result["unresolved_evidence_ids"], ["ev_missing"])

    def test_creative_layout_repetition_and_modules_pass(self) -> None:
        result = creative_inspection(load_sidecars(PHASE4), PHASE4)
        self.assertLessEqual(result["maximum_consecutive_layout_repetition"], 2)
        self.assertEqual(result["layout_repetition_violation_count"], 0)
        self.assertEqual(result["module_differentiation"], "PASS")

    def test_severe_visual_finding_requires_repair(self) -> None:
        self.assertEqual(gate_status([blocking_finding(severity="severe", repairable=True)]), "NEEDS_REPAIR")

    def test_nonrepairable_error_is_blocked(self) -> None:
        self.assertEqual(gate_status([blocking_finding(severity="error", repairable=False)]), "BLOCKED")

    def test_release_blocking_warning_requires_repair(self) -> None:
        self.assertEqual(gate_status([blocking_finding(severity="warning", repairable=True)]), "NEEDS_REPAIR")

    def test_unresolved_repairable_info_requires_repair(self) -> None:
        self.assertEqual(
            gate_status([blocking_finding(severity="info", repairable=True, release_blocking=False)]),
            "NEEDS_REPAIR",
        )

    def test_resolved_nonblocking_external_info_cannot_self_block_or_accept(self) -> None:
        finding = blocking_finding(severity="info", repairable=False, release_blocking=False)
        finding["resolved"] = True
        finding_without_hash = {key: value for key, value in finding.items() if key != "finding_hash"}
        from presentation_agent.deckcompiler.identity import content_sha256

        finding["finding_hash"] = content_sha256(finding_without_hash)
        self.assertEqual(gate_status([finding]), "PASS")

    def test_finding_hash_is_bound_to_evidence(self) -> None:
        finding = blocking_finding()
        self.assertEqual(len(finding["finding_hash"]), 64)
        mutated = deepcopy(finding)
        mutated["evidence"] = {"changed": True}
        self.assertFalse(verify_finding_hash(mutated))

    def test_render_count_mismatch_prevents_contact_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for source in sorted((PHASE5 / "renders").glob("slide-*.png"))[:5]:
                shutil.copy2(source, root / source.name)
            result = inspect_renders(root)
            with self.assertRaisesRegex(ValueError, "exactly six"):
                build_contact_sheet(result, root / "sheet.png")

    def test_html_package_has_six_ordered_slides_and_native_table(self) -> None:
        result = inspect_html(PHASE5 / "outputs" / "html" / "index.html")
        self.assertEqual(result.slide_order, list(range(1, 7)))
        self.assertGreaterEqual(result.table_count, 1)
        self.assertEqual(result.missing_assets, [])
        self.assertEqual(result.absolute_paths, [])

    def test_full_composite_baseline_passes_with_fresh_render_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            renders = root / "renders"
            shutil.copytree(PHASE5 / "renders", renders)
            result = run_composite_qa(
                PHASE4,
                PHASE5,
                root / "baseline",
                deckcompiler_commit="e2a6fabb1916680800097981fbda27abfe02b852",
                renders_dir=renders,
                renderer_version="16.0",
                external_visual_summary=PHASE5 / "validation" / "external_visual_qa_summary.json",
                external_visual_exit_code=1,
                created_at="2026-07-22T10:30:00+09:00",
            )
            self.assertEqual(result.status, "PASS")
            validation = validate_composite_qa(result.qa_dir)
            self.assertTrue(validation["valid"], validation["issues"])
            acceptance = json.loads((result.qa_dir / "baseline_composite_acceptance.json").read_text(encoding="utf-8"))
            self.assertFalse(acceptance["final_release_eligible"])
            self.assertTrue(acceptance["phase7_required"])

    def test_missing_report_blocks_composite_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_composite_qa(Path(tmpdir))
            self.assertFalse(result["valid"])
            self.assertTrue(any(issue.startswith("MISSING_REPORT") for issue in result["issues"]))

    def test_report_hash_mismatch_blocks_composite_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            renders = root / "renders"
            shutil.copytree(PHASE5 / "renders", renders)
            result = run_composite_qa(
                PHASE4,
                PHASE5,
                root / "baseline",
                deckcompiler_commit="e2a6fabb1916680800097981fbda27abfe02b852",
                renders_dir=renders,
                renderer_version="16.0",
                external_visual_summary=PHASE5 / "validation" / "external_visual_qa_summary.json",
                external_visual_exit_code=1,
                created_at="2026-07-22T10:30:00+09:00",
            )
            path = result.qa_dir / "semantic_qa_report.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["checks"]["pptx_fidelity"] = 0.5
            path.write_text(json.dumps(payload), encoding="utf-8")
            validation = validate_composite_qa(result.qa_dir)
            self.assertIn("REPORT_HASH_MISMATCH semantic_qa_report.json", validation["issues"])

    def test_prerequisite_link_hash_mismatch_blocks_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            renders = root / "renders"
            shutil.copytree(PHASE5 / "renders", renders)
            result = run_composite_qa(
                PHASE4,
                PHASE5,
                root / "baseline",
                deckcompiler_commit="e2a6fabb1916680800097981fbda27abfe02b852",
                renders_dir=renders,
                renderer_version="16.0",
                external_visual_summary=PHASE5 / "validation" / "external_visual_qa_summary.json",
                external_visual_exit_code=1,
                created_at="2026-07-22T10:30:00+09:00",
            )
            path = result.qa_dir / "composite_qa_report.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["dimension_reports"][0]["report_hash"] = "0" * 64
            from presentation_agent.deckcompiler.qa.contracts import with_report_hash

            path.write_text(json.dumps(with_report_hash(payload)), encoding="utf-8")
            validation = validate_composite_qa(result.qa_dir)
            self.assertTrue(any("LINKED_REPORT_HASH_MISMATCH" in issue for issue in validation["issues"]))

    def test_valid_reports_have_hashes_and_no_final_release_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            renders = root / "renders"
            shutil.copytree(PHASE5 / "renders", renders)
            result = run_composite_qa(
                PHASE4,
                PHASE5,
                root / "baseline",
                deckcompiler_commit="e2a6fabb1916680800097981fbda27abfe02b852",
                renders_dir=renders,
                renderer_version="16.0",
                external_visual_summary=PHASE5 / "validation" / "external_visual_qa_summary.json",
                external_visual_exit_code=1,
                created_at="2026-07-22T10:30:00+09:00",
            )
            for path in result.reports:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(verify_report_hash(payload), path.name)
                self.assertNotEqual(payload.get("final_release_eligible"), True)


if __name__ == "__main__":
    unittest.main()
