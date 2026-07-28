from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.qa.evidence_capsule import (  # noqa: E402
    CAPSULE_STATUS_ORDER,
    EVIDENCE_PREREQUISITE_DAG,
    EvidenceCapsuleError,
    bind_current_output_evidence,
    build_evidence_capsule,
    materialize_per_slide_crop_evidence,
    reconcile_external_visual_qa,
    require_baseline_reachability,
    seal_reconstruction_scores,
    validate_forensic_inventory,
    verify_manifest_hash,
)
from presentation_agent.deckcompiler.qa.contracts import sha256_file  # noqa: E402
from presentation_agent.deckcompiler.identity import content_sha256  # noqa: E402
from presentation_agent.deckcompiler.qa.html_capture import (  # noqa: E402
    DimensionAuthority,
    bind_attempt_record,
    build_capture_manifest,
)


SLIDES = tuple(range(1, 7))


def _write(path: Path, value: bytes | str | dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    elif isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _png_stub(width: int, height: int, marker: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sII", 13, b"IHDR", width, height) + bytes([marker])


def _project(root: Path, *, run_id: str = "run-baseline", fault_state: str = "baseline") -> dict[str, Path | str]:
    project = root / "project"
    pptx = _write(project / "out" / "deck.pptx", b"current-pptx")
    html = _write(
        project / "out" / "deck.html",
        '<html><style>.slide{width:1664px;height:936px;}</style><body data-deck-pxw="1664" data-deck-pxh="936">current</body></html>',
    )
    pptx_hash = sha256_file(pptx)
    html_hash = sha256_file(html)
    _write(
        project / "work" / "crop_plan.json",
        {
            "schema_name": "pngtopptx_project_crop_plan",
            "schema_version": "1.0.0",
            "contract_classification": "observed_external_contract_v1",
            "run_id": run_id,
            "fault_state": fault_state,
            "crop_count": 0,
            "zero_raster_state": "not_applicable_zero_raster",
            "slides": {str(slide): [] for slide in SLIDES},
        },
    )
    _write(project / "assets" / "manifest.json", {})
    capture_attempts = []
    for slide in SLIDES:
        source = _write(project / "src" / f"slide{slide}.png", f"source-{slide}".encode())
        visual = project / "work" / f"slide{slide:02d}" / "visual_qa"
        raster = _write(visual / "pptx_raster.png", f"pptx-raster-{slide}".encode())
        screenshot = _write(visual / "html_screenshot.png", _png_stub(1664, 936, slide))
        _write(
            visual / "pptx_raster_metadata.json",
            {
                "slide": slide,
                "pptxSha256": pptx_hash,
                "outputSha256": sha256_file(raster),
                "tool": "powerpoint-com",
                "rendererIdentity": "Microsoft PowerPoint COM",
                "rendererVersion": "16.0",
                "width": 1920,
                "height": 1080,
            },
        )
        _write(
            visual / "html_screenshot_metadata.json",
            {
                "slide": slide,
                "htmlSha256": html_hash,
                "outputSha256": sha256_file(screenshot),
                "tool": "chrome-cli",
                "qaStaticModeUsed": True,
                "viewport": {"width": 1664, "height": 936},
            },
        )
        _write(
            visual / "visual_metrics.json",
            {
                "slide": slide,
                "status": "pass",
                "hashes": {
                    "source": sha256_file(source),
                    "pptx_raster": sha256_file(raster),
                    "html_screenshot": sha256_file(screenshot),
                },
                "dimensions": {
                    "pptx_raster": {"width": 1920, "height": 1080},
                    "html_screenshot": {"width": 1664, "height": 936},
                },
            },
        )
        slide_id = f"slide-{slide:03d}"
        capture_attempts.append(
            bind_attempt_record(
                {
                    "attempt_id": f"{run_id}-{slide_id}-attempt-01",
                    "prior_attempt_id": None,
                    "run_id": run_id,
                    "fault_state": fault_state,
                    "slide_id": slide_id,
                    "attempt_number": 1,
                    "reason": "initial_capture",
                    "current_html_sha256": html_hash,
                    "requested_dimensions": {"width": 1664, "height": 936},
                    "actual_dimensions": {"width": 1664, "height": 936},
                    "output_path": str(screenshot.resolve()),
                    "output_sha256": sha256_file(screenshot),
                    "selected": True,
                    "status": "PASS",
                    "readiness": {
                        "slide_id": slide_id,
                        "document_ready_state": "complete",
                        "fonts_ready": True,
                        "images_ready": True,
                        "layout_stable": True,
                        "target_visible": True,
                        "qa_static_mode": True,
                        "remote_network_dependency": False,
                        "device_scale_factor": 1,
                        "viewport": {"width": 1664, "height": 936},
                        "slide_bounding_rect": {"width": 1664, "height": 936},
                    },
                }
            )
        )
    capture_manifest = build_capture_manifest(
        run_id=run_id,
        fault_state=fault_state,
        runtime_root=root,
        source_html=html,
        browser_identity="test-browser",
        browser_version="1",
        dimension_authority=DimensionAuthority(
            width=1664,
            height=936,
            sources=("html_body_data_attributes", "slide_css_pixels"),
            html_body_dimensions={"width": 1664, "height": 936},
            slide_css_dimensions={"width": 1664, "height": 936},
        ),
        attempts=capture_attempts,
        ordered_slide_ids=tuple(f"slide-{slide:03d}" for slide in SLIDES),
        created_at="2026-07-22T00:00:00+09:00",
    )
    _write(project / "out" / "html_screenshot_capture_manifest.json", capture_manifest)
    _write(
        project / "out" / "native_object_manifest.json",
        {
            "slides": {
                str(slide): {
                    "counts": {
                        "text": 10,
                        "panels": 4,
                        "rules": 2,
                        "icons": 0,
                        "tables": 0,
                        "charts": 0,
                        "badges": 0,
                        "callouts": 0,
                    },
                    "editableObjectCount": 16,
                    "editableTextLength": 200,
                }
                for slide in SLIDES
            }
        },
    )
    _write(
        project / "out" / "crop_coverage_summary.json",
        {
            "slides": {
                str(slide): {
                    "totalCropAreaRatio": 0,
                    "largestCropAreaRatio": 0,
                    "textOrTableCropAreaRatio": 0,
                    "photorealCropAreaRatio": 0,
                    "denseInfographicCropAreaRatio": 0,
                    "crops": [],
                }
                for slide in SLIDES
            }
        },
    )
    materialize_per_slide_crop_evidence(project, run_id=run_id, fault_state=fault_state)
    objective = bind_current_output_evidence(
        project,
        run_id=run_id,
        fault_state=fault_state,
        pptx_path=pptx,
        html_path=html,
        checked_at="2026-07-22T00:00:00+09:00",
    )
    return {
        "project": project,
        "pptx": pptx,
        "html": html,
        "run_id": run_id,
        "fault_state": fault_state,
        "objective": objective,
    }


def _capsule(ctx: dict[str, Path | str], **changes):
    values = {
        "project_root": ctx["project"],
        "run_id": ctx["run_id"],
        "fault_state": ctx["fault_state"],
        "source_commit": "a" * 40,
        "input_bundles": [
            {"bundle_id": "phase4", "sha256": "1" * 64},
            {"bundle_id": "phase5", "sha256": "2" * 64},
        ],
        "handoff": {"handoff_id": "handoff-test", "sha256": "3" * 64},
        "pptx_path": ctx["pptx"],
        "html_path": ctx["html"],
        "created_at": "2026-07-22T00:01:00+09:00",
    }
    values.update(changes)
    return build_evidence_capsule(**values)


def _qa_reports(root: Path, *, semantic: str = "PASS") -> Path:
    qa = root / "qa"
    rows = {
        "semantic_qa_report.json": {"status": semantic, "checks": {"pptx_fidelity": 1.0, "html_fidelity": 1.0}},
        "editability_qa_report.json": {"status": "PASS", "checks": {"native_requirement_coverage": 1.0, "semantic_raster_violation_count": 0}},
        "package_render_qa_report.json": {"status": "PASS", "checks": {"render_count": 6, "render_dimension_failures": []}},
        "visual_qa_report.json": {"status": "PASS", "checks": {"off_canvas_count": 0, "title_safe_area_failures": [], "footer_citation_safe_area_failures": [], "severe_overlap_count": 0, "model_assisted_review": {"hierarchy": "PASS", "legibility": "PASS", "visual_target_intent_fidelity": "PASS"}}},
        "raster_crop_qa_report.json": {"status": "PASS", "checks": {"semantic_raster_violation_count": 0, "full_slide_raster_count": 0, "screenshot_slide_count": 0}},
        "cross_output_parity_qa_report.json": {"status": "PASS", "checks": {"parity_fidelity": 1.0, "mismatch_count": 0}},
    }
    current_outputs = [
        {"artifact_id": "active-pptx", "path": "active-output/current.pptx", "sha256": "a" * 64},
        {"artifact_id": "active-html", "path": "active-output/current.html", "sha256": "a" * 64},
    ]
    for name, payload in rows.items():
        payload["source_artifacts"] = deepcopy(current_outputs)
        payload["report_hash"] = content_sha256(payload)
        _write(qa / name, payload)
    return qa


def _external_summary(root: Path) -> Path:
    return _write(
        root / "visual_qa_summary.json",
        {
            "counts": {"fail": 4, "needs_polish": 2, "pass": 0, "missing": 0},
            "slides": [
                {
                    "slide": slide,
                    "status": "fail" if slide in {1, 3, 4, 5} else "needs_polish",
                    "severity": "blocking" if slide in {1, 3, 4, 5} else "noticeable",
                    "issues": [
                        {"id": f"s{slide}_issue_001", "type": "spacing", "comparison": "pptx_vs_source", "severity": "blocking" if slide in {1, 3, 4, 5} else "noticeable", "metric": "pixel_difference_ratio", "actual": 0.27, "threshold": 0.25, "observed": "Measured spacing delta."},
                        {"id": f"s{slide}_issue_002", "type": "pptx_html_mismatch", "comparison": "pptx_vs_html", "severity": "noticeable", "metric": "approx_ssim", "actual": 0.71, "threshold": 0.72, "observed": "Measured surface delta."},
                    ],
                }
                for slide in SLIDES
            ],
        },
    )


class Phase61EvidenceCapsuleTests(unittest.TestCase):
    def test_01_prerequisite_dag_and_status_order_are_explicit(self) -> None:
        self.assertGreaterEqual(len(EVIDENCE_PREREQUISITE_DAG), 15)
        self.assertEqual(EVIDENCE_PREREQUISITE_DAG[-2:], (("reconstruction_score", "official_final_gate"), ("official_final_gate", "composite_qa")))
        self.assertEqual(CAPSULE_STATUS_ORDER["INCOMPLETE"], 0)
        self.assertLess(CAPSULE_STATUS_ORDER["EVIDENCE_VALID"], CAPSULE_STATUS_ORDER["FINAL_GATE_VALID"])

    def test_02_complete_current_output_evidence_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _project(Path(tmpdir))
            first = _capsule(ctx)
            second = _capsule(ctx)
            self.assertEqual(first, second)
            self.assertEqual(first["capsule_status"], "EVIDENCE_VALID")
            self.assertEqual(first["missing_artifact_count"], 0)
            self.assertEqual(first["stale_artifact_count"], 0)
            self.assertEqual(first["hash_mismatch_count"], 0)
            self.assertEqual(len(first["per_slide_crop_plan_records"]), 6)
            self.assertEqual(len(first["pptx_raster_evidence_records"]), 6)
            self.assertEqual(len(first["html_screenshot_evidence_records"]), 6)
            self.assertTrue(verify_manifest_hash(first))
            self.assertNotIn(str(Path(tmpdir)), json.dumps(first))

    def test_03_missing_required_capsule_nodes_fail_closed(self) -> None:
        removals = (
            "work/crop_plan.json",
            "assets/manifest.json",
            "work/slide03/crop_plan.json",
            "work/slide04/visual_qa/pptx_raster.png",
            "work/slide05/visual_qa/html_screenshot.png",
            "out/current_output_objective_evidence.json",
        )
        for relative in removals:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmpdir:
                ctx = _project(Path(tmpdir))
                (Path(ctx["project"]) / relative).unlink()
                capsule = _capsule(ctx)
                self.assertEqual(capsule["capsule_status"], "BLOCKED")
                self.assertGreater(capsule["missing_artifact_count"], 0)

    def test_04_parent_hash_mismatch_and_stale_run_fail_closed(self) -> None:
        mutations = (
            ("work/slide01/visual_qa/pptx_raster_metadata.json", "pptxSha256", "f" * 64),
            ("work/slide02/visual_qa/html_screenshot_metadata.json", "htmlSha256", "e" * 64),
            ("out/current_output_objective_evidence.json", "run_id", "other-run"),
            ("out/current_output_objective_evidence.json", "fault_state", "faulty"),
        )
        for relative, field, value in mutations:
            with self.subTest(relative=relative, field=field), tempfile.TemporaryDirectory() as tmpdir:
                ctx = _project(Path(tmpdir))
                path = Path(ctx["project"]) / relative
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload[field] = value
                _write(path, payload)
                capsule = _capsule(ctx)
                self.assertEqual(capsule["capsule_status"], "BLOCKED")
                self.assertGreater(capsule["stale_artifact_count"] + capsule["hash_mismatch_count"], 0)

    def test_05_cross_state_objective_evidence_reuse_is_rejected(self) -> None:
        cases = (("baseline", "faulty"), ("faulty", "repaired"))
        for evidence_state, requested_state in cases:
            with self.subTest(evidence_state=evidence_state, requested_state=requested_state), tempfile.TemporaryDirectory() as tmpdir:
                ctx = _project(Path(tmpdir), fault_state=evidence_state)
                capsule = _capsule(ctx, fault_state=requested_state)
                self.assertEqual(capsule["capsule_status"], "BLOCKED")
                self.assertGreater(capsule["stale_artifact_count"], 0)

    def test_06_duplicate_or_wrong_slide_order_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _project(Path(tmpdir))
            objective_path = Path(ctx["project"]) / "out" / "current_output_objective_evidence.json"
            payload = json.loads(objective_path.read_text(encoding="utf-8"))
            payload["slides"][1]["slide"] = 1
            payload["slides"] = list(reversed(payload["slides"]))
            _write(objective_path, payload)
            capsule = _capsule(ctx)
            self.assertEqual(capsule["capsule_status"], "BLOCKED")

    def test_07_score_pass_requires_evidence_valid_and_binds_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _project(Path(tmpdir))
            capsule = _capsule(ctx)
            scores = seal_reconstruction_scores(Path(ctx["project"]), capsule)
            self.assertEqual(len(scores), 6)
            for score in scores:
                self.assertEqual(score["status"], "pass")
                self.assertEqual(score["parent_binding"]["run_id"], ctx["run_id"])
                self.assertEqual(score["parent_binding"]["pptx_sha256"], sha256_file(Path(ctx["pptx"])))
                self.assertEqual(score["parent_binding"]["html_sha256"], sha256_file(Path(ctx["html"])))
                self.assertNotIn("phase6_accepted", score)
                self.assertNotIn("final_release_eligible", score)

    def test_08_score_overstatement_is_structurally_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _project(Path(tmpdir))
            bad = _capsule(ctx)
            bad["capsule_status"] = "BLOCKED"
            bad["missing_artifact_count"] = 1
            with self.assertRaisesRegex(EvidenceCapsuleError, "BLOCKED_OBJECTIVE_EVIDENCE_INVALID"):
                seal_reconstruction_scores(Path(ctx["project"]), bad)

    def test_09_manual_score_pass_cannot_override_invalid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _project(Path(tmpdir))
            _write(Path(ctx["project"]) / "work" / "slide01" / "reconstruction_score.json", {"slide": 1, "status": "pass"})
            (Path(ctx["project"]) / "work" / "slide01" / "visual_qa" / "pptx_raster.png").unlink()
            capsule = _capsule(ctx)
            self.assertEqual(capsule["capsule_status"], "BLOCKED")
            self.assertNotEqual(capsule["reconstruction_score_record"]["status"], "pass")

    def test_10_inline_only_external_qa_cannot_claim_complete_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = reconcile_external_visual_qa(
                _external_summary(root),
                _qa_reports(root),
                canonical_output_sha256="a" * 64,
                decision_id="D-040",
                created_at="2026-07-22T00:00:00+09:00",
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["unresolved_external_finding_count"], 6)
            self.assertEqual(result["unsupported_informational_classification_count"], 0)
            self.assertEqual(len(result["findings"]), 6)
            self.assertEqual(result["resolved_covered_count"], 0)
            self.assertTrue(all(row["finding_id"] and row["final_status"] == "UNRESOLVED_BLOCKING" for row in result["findings"]))

    def test_11_reconciliation_cannot_hide_semantic_or_editability_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = reconcile_external_visual_qa(
                _external_summary(root),
                _qa_reports(root, semantic="NEEDS_REPAIR"),
                canonical_output_sha256="a" * 64,
                decision_id="D-040",
                created_at="2026-07-22T00:00:00+09:00",
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertGreater(result["unresolved_external_finding_count"], 0)

    def test_12_accepted_limitation_requires_an_exact_decision_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaisesRegex(EvidenceCapsuleError, "DECISION"):
                reconcile_external_visual_qa(
                    _external_summary(root),
                    _qa_reports(root),
                    canonical_output_sha256="a" * 64,
                    resolution_category="ACCEPTED_LIMITATION",
                    decision_id=None,
                    created_at="2026-07-22T00:00:00+09:00",
                )

    def test_13_forensic_inventory_blocks_unclassified_or_unrelated_changes(self) -> None:
        base = {
            "records": [
                {
                    "path": "src/example.py",
                    "owner_classification": "A",
                    "contains_absolute_runtime_path": False,
                    "contains_failed_output_hash": False,
                    "generated_binary": False,
                    "proposed_disposition": "preserve",
                }
            ],
            "quarantine_moves": [],
        }
        self.assertEqual(validate_forensic_inventory(base)["status"], "PASS")
        for classification in (None, "E"):
            with self.subTest(classification=classification):
                payload = deepcopy(base)
                payload["records"][0]["owner_classification"] = classification
                with self.assertRaisesRegex(EvidenceCapsuleError, "BLOCKED_UNRELATED_WORKTREE_CHANGES"):
                    validate_forensic_inventory(payload)

    def test_14_generic_or_curated_records_reject_runtime_paths_and_binaries(self) -> None:
        payload = {
            "records": [
                {
                    "path": "examples/deckcompiler_demo/phase6/evidence_capsule/capsule.json",
                    "owner_classification": "A",
                    "contains_absolute_runtime_path": True,
                    "contains_failed_output_hash": False,
                    "generated_binary": False,
                    "proposed_disposition": "commit",
                }
            ],
            "quarantine_moves": [],
        }
        with self.assertRaisesRegex(EvidenceCapsuleError, "ABSOLUTE_RUNTIME_PATH"):
            validate_forensic_inventory(payload)
        payload["records"][0].update({"contains_absolute_runtime_path": False, "generated_binary": True})
        with self.assertRaisesRegex(EvidenceCapsuleError, "GENERATED_BINARY"):
            validate_forensic_inventory(payload)

    def test_15_quarantine_move_requires_equal_before_after_hashes(self) -> None:
        payload = {
            "records": [],
            "quarantine_moves": [{"path": "debug.bin", "before_sha256": "a" * 64, "after_sha256": "b" * 64}],
        }
        with self.assertRaisesRegex(EvidenceCapsuleError, "QUARANTINE_HASH_MISMATCH"):
            validate_forensic_inventory(payload)

    def test_16_fault_injection_requires_fresh_passing_baseline_reachability(self) -> None:
        passing = {
            "status": "PASS",
            "source_commit": "a" * 40,
            "prior_runtime_reused": False,
            "official_final_gate": "PASS",
            "composite_qa": "PASS",
            "render_count": 6,
            "html_screenshot_count": 6,
            "missing_artifact_count": 0,
            "stale_artifact_count": 0,
            "hash_mismatch_count": 0,
            "external_qa_reconciliation": "PASS",
        }
        require_baseline_reachability(passing, expected_source_commit="a" * 40)
        for key, value in (
            ("status", "BLOCKED"),
            ("source_commit", "b" * 40),
            ("prior_runtime_reused", True),
            ("official_final_gate", "BLOCKED"),
            ("composite_qa", "NEEDS_REPAIR"),
            ("render_count", 5),
            ("html_screenshot_count", 5),
            ("missing_artifact_count", 1),
            ("external_qa_reconciliation", "BLOCKED"),
        ):
            with self.subTest(key=key):
                report = dict(passing)
                report[key] = value
                with self.assertRaisesRegex(EvidenceCapsuleError, "BLOCKED_POSTCOMMIT_REACHABILITY_FAILED"):
                    require_baseline_reachability(report, expected_source_commit="a" * 40)


if __name__ == "__main__":
    unittest.main()
