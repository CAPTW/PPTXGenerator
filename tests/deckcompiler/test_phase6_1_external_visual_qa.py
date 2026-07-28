from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.qa.composite import (  # noqa: E402
    CompositeQAError,
    bind_external_visual_reconciliation,
    composite_acceptance_status,
)
from presentation_agent.deckcompiler.qa.evidence_capsule import (  # noqa: E402
    EvidenceCapsuleError,
    require_baseline_reachability,
)
from presentation_agent.deckcompiler.qa.contracts import make_finding  # noqa: E402
from presentation_agent.deckcompiler.qa.external_visual_qa import (  # noqa: E402
    ExternalVisualQAError,
    build_external_visual_qa_reconciliation,
    parse_external_visual_qa,
    validate_resolution_record,
    verify_bound_report_hash,
)
from presentation_agent.deckcompiler.identity import content_sha256  # noqa: E402
from presentation_agent.deckcompiler.pngtopptx_handoff import HandoffError  # noqa: E402
from presentation_agent.deckcompiler.qa.reachability import main as reachability_main  # noqa: E402


SLIDES = tuple(range(1, 7))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, value: bytes | str | dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    elif isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _issue(slide: int, *, comparison: str = "pptx_vs_source", severity: str = "noticeable") -> dict:
    return {
        "id": f"s{slide}_issue_001",
        "type": "spacing" if comparison != "pptx_vs_html" else "pptx_html_mismatch",
        "severity": severity,
        "comparison": comparison,
        "observed": "Measured geometry differs from the source.",
        "expected": "Editable reconstruction preserves intent without material clipping or content loss.",
        "likelyCause": "Editable layout geometry differs from raster source pixels.",
        "recommendedFix": "Inspect current-output evidence before changing geometry.",
        "targetFile": f"work/slide{slide:02d}/s{slide}.fragment.js",
        "safeToAutoApply": False,
        "region": {"x": 10, "y": 10, "w": 100, "h": 100},
    }


def _project(root: Path, *, inline: bool = False, empty_issues: bool = False) -> tuple[Path, Path]:
    project = root / "project"
    rows = []
    counts = {"pass": 0, "fail": 4, "needs_polish": 2, "missing": 0}
    for slide in SLIDES:
        visual = project / "work" / f"slide{slide:02d}" / "visual_qa"
        source = _write(visual / "source.png", f"source-{slide}".encode())
        pptx = _write(visual / "pptx_raster.png", f"pptx-{slide}".encode())
        html = _write(visual / "html_screenshot.png", f"html-{slide}".encode())
        status = "fail" if slide in {1, 3, 4, 5} else "needs_polish"
        severity = "blocking" if status == "fail" else "noticeable"
        issues = [] if empty_issues else [_issue(slide, severity=severity)]
        comparisons = {
            "pptx_vs_source": {
                "pixel_difference_ratio": 0.27,
                "mean_absolute_error": 0.17,
                "approx_ssim": 0.61,
                "metricSignals": {
                    "explicitBlockingContext": False,
                    "knownBadSignals": [
                        {"metric": "pixel_difference_ratio", "value": 0.27, "threshold": 0.25}
                    ],
                },
            }
        }
        metrics = {
            "slide": slide,
            "status": status,
            "overallStatus": status,
            "severity": severity,
            "issues": issues,
            "issueSignals": [],
            "comparisons": comparisons,
            "hashes": {
                "source": _sha(source.read_bytes()),
                "pptx_raster": _sha(pptx.read_bytes()),
                "html_screenshot": _sha(html.read_bytes()),
            },
        }
        metrics_path = _write(visual / "visual_metrics.json", metrics)
        fixes_path = _write(visual / "visual_polish_fixes.json", {"slide": slide, "status": status, "severity": severity, "issues": issues})
        row = {
            "slide": slide,
            "status": status,
            "severity": severity,
            "issueCount": len(issues),
            "metricsPath": str(metrics_path),
            "fixesPath": str(fixes_path),
            "hasMetrics": True,
            "hasFixes": True,
        }
        if inline:
            row["issues"] = issues
        rows.append(row)
    summary = _write(
        project / "out" / "visual_qa_summary.json",
        {"createdAt": "2026-07-22T00:00:00Z", "project": str(project), "slidesRequested": list(SLIDES), "counts": counts, "slides": rows},
    )
    return project, summary


def _qa_reports(
    root: Path,
    *,
    semantic: str = "PASS",
    visual_findings: list[dict] | None = None,
    off_canvas_count: int = 0,
) -> Path:
    qa = root / "qa"
    reports = {
        "semantic_qa_report.json": {"status": semantic, "checks": {"pptx_fidelity": 1.0, "html_fidelity": 1.0}},
        "editability_qa_report.json": {"status": "PASS", "checks": {"native_requirement_coverage": 1.0, "semantic_raster_violation_count": 0}},
        "package_render_qa_report.json": {"status": "PASS", "checks": {"render_count": 6}},
        "visual_qa_report.json": {
            "status": "NEEDS_REPAIR" if visual_findings else "PASS",
            "checks": {
                "off_canvas_count": off_canvas_count,
                "title_safe_area_failures": [],
                "footer_citation_safe_area_failures": [],
                "severe_overlap_count": 0,
                "model_assisted_review": {"hierarchy": "PASS", "legibility": "PASS", "spacing_quality": "PASS", "visual_target_intent_fidelity": "PASS"},
            },
            "findings": visual_findings or [],
        },
        "raster_crop_qa_report.json": {"status": "PASS", "checks": {"full_slide_raster_count": 0, "screenshot_slide_count": 0}},
        "cross_output_parity_qa_report.json": {"status": "PASS", "checks": {"parity_fidelity": 1.0, "mismatch_count": 0}},
    }
    current_outputs = [
        {"artifact_id": "active-pptx", "path": "active-output/current.pptx", "sha256": "a" * 64},
        {"artifact_id": "active-html", "path": "active-output/current.html", "sha256": "b" * 64},
    ]
    for name, payload in reports.items():
        payload["source_artifacts"] = deepcopy(current_outputs)
        payload["report_hash"] = content_sha256(payload)
        _write(qa / name, payload)
    return qa


def _parse(root: Path, **kwargs) -> tuple[dict, dict]:
    project, summary = _project(root, **kwargs)
    return parse_external_visual_qa(
        summary,
        project_root=project,
        source_tool_root=None,
        source_command=("node", "enforce_visual_qa.js", "--mode", "qa-polish"),
        created_at="2026-07-22T00:00:00+09:00",
    )


def _reconcile(root: Path, *, empty_issues: bool = False, semantic: str = "PASS") -> dict:
    project, summary = _project(root, empty_issues=empty_issues)
    _audit, sources = parse_external_visual_qa(
        summary,
        project_root=project,
        source_command=("node", "enforce_visual_qa.js", "--mode", "qa-polish"),
        created_at="2026-07-22T00:00:00+09:00",
    )
    return build_external_visual_qa_reconciliation(
        sources,
        _qa_reports(root, semantic=semantic),
        project_root=project,
        current_pptx_sha256="a" * 64,
        current_html_sha256="b" * 64,
        created_at="2026-07-22T00:00:00+09:00",
    )


class ExternalVisualQAParserTests(unittest.TestCase):
    def test_01_rule_level_output_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = {"counts": {"fail": 1, "needs_polish": 0, "pass": 0, "missing": 0}, "results": [{"slide": 1, "status": "fail", "severity": "blocking", "rule_id": "official-1", "message": "rule failed"}]}
            report = _write(root / "rule.json", payload)
            _audit, sources = parse_external_visual_qa(report, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")
            self.assertEqual(sources["source_results"][0]["source_granularity"], "rule_record")

    def test_02_slide_level_output_and_child_rules_are_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit, sources = _parse(Path(tmpdir))
            self.assertEqual(audit["detected_output_format"], "slide_verdict_with_rule_records")
            self.assertEqual(sources["parsed_source_result_count"], 6)
            self.assertEqual(sources["parsed_rule_record_count"], 6)

    def test_03_summary_only_output_is_identified_and_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = _write(root / "summary.json", {"counts": {"fail": 4, "needs_polish": 2, "pass": 0, "missing": 0}})
            audit, sources = parse_external_visual_qa(report, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")
            self.assertEqual(audit["detected_output_format"], "summary_only")
            self.assertEqual(sources["source_results"][0]["covered_result_count"], 6)
            self.assertEqual(sources["status"], "BLOCKED")

    def test_04_unknown_explicit_output_version_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = _write(root / "unknown.json", {"schema_version": "999", "counts": {"fail": 0, "needs_polish": 0, "pass": 1, "missing": 0}, "slides": [{"slide": 1, "status": "pass", "severity": "pass"}]})
            with self.assertRaisesRegex(ExternalVisualQAError, "BLOCKED_EXTERNAL_VISUAL_QA_OUTPUT_UNSUPPORTED"):
                parse_external_visual_qa(report, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")

    def test_05_nonzero_summary_with_explicit_empty_results_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = _write(root / "empty.json", {"counts": {"fail": 1, "needs_polish": 0, "pass": 0, "missing": 0}, "slides": []})
            with self.assertRaisesRegex(ExternalVisualQAError, "CONSERVATION"):
                parse_external_visual_qa(report, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")

    def test_06_stdout_only_json_result_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            stdout = _write(root / "stdout.log", json.dumps({"counts": {"fail": 0, "needs_polish": 0, "pass": 1, "missing": 0}, "slides": [{"slide": 1, "status": "pass", "severity": "pass", "issues": []}]}))
            audit, sources = parse_external_visual_qa(None, stdout_path=stdout, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")
            self.assertEqual(audit["source_channel"], "stdout_json")
            self.assertEqual(sources["parsed_source_result_count"], 1)

    def test_07_json_report_result_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit, sources = _parse(Path(tmpdir))
            self.assertEqual(audit["source_channel"], "json_report")
            self.assertEqual(sources["status"], "PASS")

    def test_08_duplicate_source_results_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project, summary = _project(root)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            payload["slides"][1]["slide"] = 1
            _write(summary, payload)
            with self.assertRaisesRegex(ExternalVisualQAError, "DUPLICATE"):
                parse_external_visual_qa(summary, project_root=project, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")

    def test_09_malformed_status_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = _write(root / "bad.json", {"counts": {"fail": 1, "needs_polish": 0, "pass": 0, "missing": 0}, "slides": [{"slide": 1, "status": 7, "severity": "blocking", "issues": [_issue(1)]}]})
            with self.assertRaisesRegex(ExternalVisualQAError, "STATUS"):
                parse_external_visual_qa(report, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")

    def test_10_unknown_status_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = _write(root / "bad.json", {"counts": {"fail": 1, "needs_polish": 0, "pass": 0, "missing": 0}, "slides": [{"slide": 1, "status": "maybe", "severity": "blocking", "issues": [_issue(1)]}]})
            with self.assertRaisesRegex(ExternalVisualQAError, "STATUS"):
                parse_external_visual_qa(report, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")

    def test_10a_multiple_rule_records_on_one_slide_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = {
                "counts": {"fail": 2, "needs_polish": 0, "pass": 0, "missing": 0},
                "results": [
                    {"id": "issue-a", "slide": 1, "rule_id": "official-a", "status": "fail", "severity": "blocking", "metric": "x", "actual": 2, "threshold": 1},
                    {"id": "issue-b", "slide": 1, "rule_id": "official-b", "status": "fail", "severity": "blocking", "metric": "y", "actual": 3, "threshold": 1},
                ],
            }
            report = _write(root / "rules.json", payload)
            _audit, sources = parse_external_visual_qa(report, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")
            self.assertEqual(sources["parsed_source_result_count"], 2)
            self.assertEqual(len({row["source_result_id"] for row in sources["source_results"]}), 2)


class ExternalVisualQAConservationTests(unittest.TestCase):
    def test_11_reported_total_equation_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = _write(root / "bad.json", {"total": 7, "counts": {"fail": 1, "needs_polish": 0, "pass": 0, "missing": 0}, "slides": [{"slide": 1, "status": "fail", "severity": "blocking", "issues": [_issue(1)]}]})
            with self.assertRaisesRegex(ExternalVisualQAError, "CONSERVATION"):
                parse_external_visual_qa(report, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")

    def test_12_parsed_total_equals_summary_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _audit, sources = _parse(Path(tmpdir))
            self.assertEqual(sources["parsed_source_result_count"], sources["reported_total"])

    def test_13_nonpass_covered_count_equals_summary_nonpass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _reconcile(Path(tmpdir))
            self.assertEqual(result["mapped_nonpass_covered_count"], result["reported_nonpass_count"])

    def test_14_missing_source_result_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project, summary = _project(root)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            payload["slides"].pop()
            _write(summary, payload)
            with self.assertRaisesRegex(ExternalVisualQAError, "CONSERVATION"):
                parse_external_visual_qa(summary, project_root=project, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")

    def test_15_duplicate_rule_record_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project, summary = _project(root)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            fixes_path = Path(payload["slides"][0]["fixesPath"])
            fixes = json.loads(fixes_path.read_text(encoding="utf-8"))
            fixes["issues"].append(deepcopy(fixes["issues"][0]))
            _write(fixes_path, fixes)
            with self.assertRaisesRegex(ExternalVisualQAError, "DUPLICATE"):
                parse_external_visual_qa(summary, project_root=project, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")

    def test_16_summary_only_covered_count_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = _write(root / "summary.json", {"counts": {"fail": 4, "needs_polish": 2, "pass": 0, "missing": 0}})
            _audit, sources = parse_external_visual_qa(report, project_root=root, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")
            self.assertEqual(sources["parsed_summary_record_count"], 1)
            self.assertEqual(sources["source_results"][0]["covered_result_count"], 6)

    def test_17_nonpass_with_zero_rule_evidence_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _reconcile(Path(tmpdir), empty_issues=True)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertGreater(result["unresolved_covered_count"], 0)

    def test_18_mapped_coverage_below_full_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project, summary = _project(root)
            _audit, sources = parse_external_visual_qa(summary, project_root=project, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")
            sources["source_results"].pop()
            result = build_external_visual_qa_reconciliation(sources, _qa_reports(root), project_root=project, current_pptx_sha256="a" * 64, current_html_sha256="b" * 64, created_at="2026-07-22T00:00:00+09:00")
            self.assertEqual(result["status"], "BLOCKED")


class ExternalVisualQAResolutionTests(unittest.TestCase):
    def _record(self, category: str = "RESOLVED_METRIC_DELTA") -> dict:
        return {
            "resolution_category": category,
            "canonical_rule_id": "EXT-VIS-SPACING-001",
            "current_pptx_sha256": "a" * 64,
            "current_html_sha256": "b" * 64,
            "source_report_hash": "c" * 64,
            "independent_evidence": {"rule_specific": True, "current_output_bound": True},
            "metric_evidence": [{"metric": "pixel_difference_ratio", "actual": 0.27, "threshold": 0.25}],
            "resolution_evidence_fresh": True,
        }

    def test_19_false_positive_without_independent_evidence_blocks(self) -> None:
        record = self._record("RESOLVED_FALSE_POSITIVE")
        record["independent_evidence"] = {}
        with self.assertRaises(ExternalVisualQAError):
            validate_resolution_record(record)

    def test_20_metric_delta_without_exact_rule_blocks(self) -> None:
        record = self._record()
        record["canonical_rule_id"] = None
        with self.assertRaises(ExternalVisualQAError):
            validate_resolution_record(record)

    def test_21_metric_delta_without_current_output_hash_blocks(self) -> None:
        record = self._record()
        record["current_pptx_sha256"] = None
        with self.assertRaises(ExternalVisualQAError):
            validate_resolution_record(record)

    def test_22_accepted_limitation_without_decision_id_blocks(self) -> None:
        record = self._record("ACCEPTED_LIMITATION")
        with self.assertRaises(ExternalVisualQAError):
            validate_resolution_record(record)

    def test_23_stale_resolution_evidence_blocks(self) -> None:
        record = self._record()
        record["resolution_evidence_fresh"] = False
        with self.assertRaises(ExternalVisualQAError):
            validate_resolution_record(record)

    def test_24_unresolved_finding_prevents_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _reconcile(Path(tmpdir), semantic="BLOCKED")
            self.assertNotEqual(result["status"], "PASS")

    def test_25_repaired_finding_requires_before_and_after_hashes(self) -> None:
        record = self._record("REPAIRED")
        with self.assertRaises(ExternalVisualQAError):
            validate_resolution_record(record)

    def test_26_generic_composite_pass_cannot_resolve_external_finding(self) -> None:
        record = self._record()
        record["independent_evidence"] = {"composite_status": "PASS"}
        with self.assertRaises(ExternalVisualQAError):
            validate_resolution_record(record)

    def test_27_rule_specific_current_evidence_can_resolve_metric_delta(self) -> None:
        record = self._record()
        self.assertEqual(validate_resolution_record(record)["status"], "PASS")

    def test_28_all_six_nonpass_results_are_individually_accounted_for(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _reconcile(Path(tmpdir))
            self.assertEqual(result["canonical_finding_count"], 6)
            self.assertEqual(result["resolved_covered_count"], 6)

    def test_29_expected_material_fault_is_scoped_to_its_source_slide(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project, summary = _project(root)
            _audit, sources = parse_external_visual_qa(
                summary,
                project_root=project,
                source_command=("node", "enforce_visual_qa.js", "--mode", "qa-polish"),
                created_at="2026-07-22T00:00:00+09:00",
            )
            expected = make_finding(
                finding_id="VISUAL_TEXT_OFF_CANVAS_SLIDE_001",
                gate="visual",
                category="safe_area",
                severity="severe",
                slide_id="slide-001",
                artifact_id="pptx-slide-001-shape-15",
                rule_id="P6-VIS-TEXT-OFF-CANVAS-001",
                message="Editable text extends outside the slide canvas.",
                evidence={"bbox_emu": {"left": -100}, "slide_width_emu": 12192000, "slide_height_emu": 6858000},
                owning_artifact="handoff/project/lib/slides.js",
                recommended_action="Rematerialize the canonical reconstruction geometry source.",
                repairable=True,
                release_blocking=True,
            )
            result = build_external_visual_qa_reconciliation(
                sources,
                _qa_reports(root, visual_findings=[expected], off_canvas_count=1),
                project_root=project,
                current_pptx_sha256="a" * 64,
                current_html_sha256="b" * 64,
                created_at="2026-07-22T00:00:00+09:00",
                expected_finding_ids=(expected["finding_id"],),
            )
            self.assertEqual(result["status"], "NEEDS_REPAIR")
            self.assertEqual(result["resolved_covered_count"], 5)
            self.assertEqual(result["unresolved_covered_count"], 1)
            self.assertEqual(
                [row["source_slide_id"] for row in result["findings"] if row["final_status"] == "NEEDS_REPAIR"],
                ["slide-001"],
            )

    def test_30_unexpected_material_fault_cannot_use_expected_fault_scoping(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project, summary = _project(root)
            _audit, sources = parse_external_visual_qa(
                summary,
                project_root=project,
                source_command=("node", "enforce_visual_qa.js", "--mode", "qa-polish"),
                created_at="2026-07-22T00:00:00+09:00",
            )
            unexpected = make_finding(
                finding_id="UNEXPECTED_SEVERE",
                gate="visual",
                category="safe_area",
                severity="severe",
                slide_id="slide-001",
                artifact_id="pptx-slide-001-shape-15",
                rule_id="P6-VIS-TEXT-OFF-CANVAS-001",
                message="Unexpected material fault.",
                evidence={"bbox_emu": {"left": -100}},
                owning_artifact="handoff/project/lib/slides.js",
                recommended_action="Stop.",
                repairable=True,
                release_blocking=True,
            )
            result = build_external_visual_qa_reconciliation(
                sources,
                _qa_reports(root, visual_findings=[unexpected], off_canvas_count=1),
                project_root=project,
                current_pptx_sha256="a" * 64,
                current_html_sha256="b" * 64,
                created_at="2026-07-22T00:00:00+09:00",
                expected_finding_ids=("VISUAL_TEXT_OFF_CANVAS_SLIDE_001",),
            )
            self.assertEqual(result["status"], "BLOCKED")


class CompositeDependencyTests(unittest.TestCase):
    def test_29_blocked_reconciliation_blocks_composite(self) -> None:
        self.assertEqual(composite_acceptance_status(["PASS"] * 10, "BLOCKED"), "BLOCKED")

    def test_30_needs_repair_reconciliation_marks_composite_needs_repair(self) -> None:
        self.assertEqual(composite_acceptance_status(["PASS"] * 10, "NEEDS_REPAIR"), "NEEDS_REPAIR")

    def test_31_passing_reconciliation_and_dimensions_pass_composite(self) -> None:
        self.assertEqual(composite_acceptance_status(["PASS"] * 10, "PASS"), "PASS")

    def test_32_generic_informational_finding_does_not_substitute_source_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _reconcile(Path(tmpdir), empty_issues=True)
            self.assertEqual(result["canonical_finding_count"], 6)
            self.assertEqual(result["status"], "BLOCKED")

    def test_33_reconciliation_report_hash_mismatch_blocks_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            recon = _write(root / "reconciliation.json", {"schema_name": "external_visual_qa_reconciliation", "status": "PASS", "report_hash": "0" * 64})
            with self.assertRaisesRegex(CompositeQAError, "hash"):
                bind_external_visual_reconciliation(root / "qa", recon)

    def test_34_missing_reconciliation_blocks_composite(self) -> None:
        self.assertEqual(composite_acceptance_status(["PASS"] * 10, None), "BLOCKED")


class ExternalVisualQAReachabilityTests(unittest.TestCase):
    def test_35_fresh_raw_output_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ExternalVisualQAError):
                parse_external_visual_qa(None, project_root=Path(tmpdir), source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")

    def test_36_source_report_hash_is_bound_and_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _audit, sources = _parse(Path(tmpdir))
            self.assertTrue(verify_bound_report_hash(sources))
            sources["reported_total"] += 1
            self.assertFalse(verify_bound_report_hash(sources))

    def test_37_current_pptx_and_html_hashes_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project, summary = _project(root)
            _audit, sources = parse_external_visual_qa(summary, project_root=project, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")
            with self.assertRaises(ExternalVisualQAError):
                build_external_visual_qa_reconciliation(sources, _qa_reports(root), project_root=project, current_pptx_sha256="", current_html_sha256="", created_at="2026-07-22T00:00:00+09:00")

    def test_38_mapping_coverage_must_be_full(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _reconcile(Path(tmpdir))
            self.assertEqual(result["mapped_coverage_ratio"], 1.0)

    def test_39_reachability_requires_reconciliation_pass(self) -> None:
        report = {"status": "PASS", "source_commit": "a" * 40, "prior_runtime_reused": False, "official_final_gate": "PASS", "composite_qa": "PASS", "render_count": 6, "html_screenshot_count": 6, "missing_artifact_count": 0, "stale_artifact_count": 0, "hash_mismatch_count": 0, "external_qa_reconciliation": "BLOCKED"}
        with self.assertRaisesRegex(EvidenceCapsuleError, "BLOCKED_POSTCOMMIT_REACHABILITY_FAILED"):
            require_baseline_reachability(report, expected_source_commit="a" * 40)

    def test_40_fault_injection_remains_disabled_before_reachability_pass(self) -> None:
        report = {"status": "BLOCKED", "source_commit": "a" * 40, "prior_runtime_reused": False, "official_final_gate": "PASS", "composite_qa": "BLOCKED", "render_count": 6, "html_screenshot_count": 6, "missing_artifact_count": 0, "stale_artifact_count": 0, "hash_mismatch_count": 0, "external_qa_reconciliation": "BLOCKED"}
        with self.assertRaisesRegex(EvidenceCapsuleError, "BLOCKED_POSTCOMMIT_REACHABILITY_FAILED"):
            require_baseline_reachability(report, expected_source_commit="a" * 40)

    def test_41_dimension_reports_must_bind_the_declared_current_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project, summary = _project(root)
            _audit, sources = parse_external_visual_qa(summary, project_root=project, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")
            qa = _qa_reports(root)
            semantic_path = qa / "semantic_qa_report.json"
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            semantic["source_artifacts"][0]["sha256"] = "c" * 64
            semantic["report_hash"] = content_sha256({key: value for key, value in semantic.items() if key != "report_hash"})
            _write(semantic_path, semantic)
            result = build_external_visual_qa_reconciliation(sources, qa, project_root=project, current_pptx_sha256="a" * 64, current_html_sha256="b" * 64, created_at="2026-07-22T00:00:00+09:00")
            self.assertEqual(result["status"], "BLOCKED")

    def test_42_tampered_dimension_report_hash_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project, summary = _project(root)
            _audit, sources = parse_external_visual_qa(summary, project_root=project, source_command=("qa",), created_at="2026-07-22T00:00:00+09:00")
            qa = _qa_reports(root)
            semantic_path = qa / "semantic_qa_report.json"
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            semantic["checks"]["tampered"] = True
            _write(semantic_path, semantic)
            with self.assertRaisesRegex(ExternalVisualQAError, "hash"):
                build_external_visual_qa_reconciliation(sources, qa, project_root=project, current_pptx_sha256="a" * 64, current_html_sha256="b" * 64, created_at="2026-07-22T00:00:00+09:00")

    def test_43_handoff_prerequisite_error_is_reported_without_traceback(self) -> None:
        args = [
            "--repo-root", ".", "--runtime-root", "runtime", "--source-commit", "a" * 40,
            "--run-id", "run-test", "--created-at", "2026-07-22T00:00:00+09:00",
            "--external-skill-root", "skills", "--profile", "profile.json",
            "--node-modules", "node_modules", "--node", "node", "--python", "python",
        ]
        stderr = io.StringIO()
        with patch(
            "presentation_agent.deckcompiler.qa.reachability.run_fresh_evidence_pipeline",
            side_effect=HandoffError("PNGTOPPTX_RUNTIME_PREREQUISITE_MISSING", "react"),
        ), redirect_stderr(stderr):
            self.assertEqual(reachability_main(args), 1)
        self.assertIn("DECKCOMPILER_PHASE6_1_REACHABILITY_BLOCKED", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
