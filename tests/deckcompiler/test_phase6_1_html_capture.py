from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import struct
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.qa.html_capture import (  # noqa: E402
    DEFAULT_ATTEMPT_POLICY,
    HtmlCaptureError,
    bind_attempt_record,
    build_capture_manifest,
    can_retry,
    classify_capture_failure,
    derive_dimension_authority,
    png_dimensions,
    validate_attempt_policy,
    validate_attempt_record,
    validate_capture_manifest,
    validate_readiness_probe,
    verify_capture_manifest_hash,
)


def _png(path: Path, width: int = 1664, height: int = 936) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + b"\0" * 8
        + struct.pack(">II", width, height)
        + b"payload"
    )
    return path


def _html(
    path: Path,
    *,
    body_width: int = 1664,
    body_height: int = 936,
    css_width: int = 1664,
    css_height: int = 936,
) -> Path:
    path.write_text(
        f"""<!doctype html><html><head><style>
.slide {{ position: relative; width: {css_width}px; height: {css_height}px; overflow: hidden; }}
</style></head><body data-deck-pxw=\"{body_width}\" data-deck-pxh=\"{body_height}\"><section class=\"slide\" id=\"slide-1\"></section></body></html>""",
        encoding="utf-8",
    )
    return path


def _readiness(slide: int = 1) -> dict:
    return {
        "slide_id": f"slide-{slide:03d}",
        "document_ready_state": "complete",
        "fonts_ready": True,
        "images_ready": True,
        "layout_stable": True,
        "target_visible": True,
        "qa_static_mode": True,
        "remote_network_dependency": False,
        "viewport": {"width": 1664, "height": 936},
        "device_scale_factor": 1,
        "slide_bounding_rect": {"x": 0, "y": 0, "width": 1664, "height": 936},
    }


def _attempt(
    runtime: Path,
    slide: int,
    html_hash: str,
    *,
    status: str = "PASS",
    selected: bool = True,
    timeout_stage: str | None = None,
) -> dict:
    output = (
        runtime
        / "handoff"
        / "project"
        / "work"
        / f"slide{slide:02d}"
        / "visual_qa"
        / "html_screenshot.png"
    )
    _png(output, 1664, 936)
    output.write_bytes(output.read_bytes() + f"-slide-{slide}".encode("ascii"))
    record = {
        "attempt_id": f"run-alpha-slide-{slide:03d}-attempt-01",
        "prior_attempt_id": None,
        "run_id": "run-alpha",
        "fault_state": "baseline",
        "slide_id": f"slide-{slide:03d}",
        "attempt_number": 1,
        "reason": "initial_capture",
        "current_html_sha256": html_hash,
        "browser_identity": "Playwright Chromium",
        "browser_version": "149.0.7827.55",
        "requested_dimensions": {"width": 1664, "height": 936},
        "actual_dimensions": {"width": 1664, "height": 936},
        "exit_status": 0 if status == "PASS" else 1,
        "output_path": str(output),
        "output_sha256": sha256(output.read_bytes()).hexdigest(),
        "selected": selected,
        "status": status,
        "timeout_stage": timeout_stage,
        "cleanup_status": "PASS",
        "readiness": _readiness(slide),
    }
    return bind_attempt_record(record)


class DimensionAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="html-capture-dim-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_01_body_and_css_dimensions_are_authoritative(self) -> None:
        authority = derive_dimension_authority(_html(self.root / "deck.html"))
        self.assertEqual((authority.width, authority.height), (1664, 936))

    def test_02_css_width_mismatch_blocks(self) -> None:
        with self.assertRaisesRegex(HtmlCaptureError, "DIMENSION_AUTHORITY"):
            derive_dimension_authority(_html(self.root / "deck.html", css_width=1672))

    def test_03_css_height_mismatch_blocks(self) -> None:
        with self.assertRaisesRegex(HtmlCaptureError, "DIMENSION_AUTHORITY"):
            derive_dimension_authority(_html(self.root / "deck.html", css_height=941))

    def test_04_missing_body_width_blocks(self) -> None:
        path = self.root / "deck.html"
        path.write_text(
            '<style>.slide{width:1664px;height:936px}</style><body data-deck-pxh="936">',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(HtmlCaptureError, "DIMENSION_AUTHORITY"):
            derive_dimension_authority(path)

    def test_05_missing_body_height_blocks(self) -> None:
        path = self.root / "deck.html"
        path.write_text(
            '<style>.slide{width:1664px;height:936px}</style><body data-deck-pxw="1664">',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(HtmlCaptureError, "DIMENSION_AUTHORITY"):
            derive_dimension_authority(path)

    def test_06_missing_slide_css_blocks(self) -> None:
        path = self.root / "deck.html"
        path.write_text(
            '<body data-deck-pxw="1664" data-deck-pxh="936">', encoding="utf-8"
        )
        with self.assertRaisesRegex(HtmlCaptureError, "DIMENSION_AUTHORITY"):
            derive_dimension_authority(path)

    def test_07_nonpositive_dimensions_block(self) -> None:
        with self.assertRaisesRegex(HtmlCaptureError, "DIMENSION_AUTHORITY"):
            derive_dimension_authority(
                _html(self.root / "deck.html", body_width=0, css_width=0)
            )

    def test_08_external_defaults_are_not_deck_authority(self) -> None:
        authority = derive_dimension_authority(_html(self.root / "deck.html"))
        self.assertNotEqual((authority.width, authority.height), (1672, 941))

    def test_09_single_quoted_body_attributes_are_supported(self) -> None:
        path = self.root / "deck.html"
        path.write_text(
            "<style>.slide{width:1664px;height:936px}</style><body data-deck-pxw='1664' data-deck-pxh='936'>",
            encoding="utf-8",
        )
        self.assertEqual(derive_dimension_authority(path).width, 1664)

    def test_10_authority_records_both_sources(self) -> None:
        authority = derive_dimension_authority(_html(self.root / "deck.html"))
        self.assertEqual(
            authority.sources, ("html_body_data_attributes", "slide_css_pixels")
        )


class PngAndRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="html-capture-png-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_11_png_dimensions_reads_ihdr(self) -> None:
        self.assertEqual(png_dimensions(_png(self.root / "a.png")), (1664, 936))

    def test_12_png_invalid_signature_blocks(self) -> None:
        path = self.root / "bad.png"
        path.write_bytes(b"not-a-png")
        with self.assertRaisesRegex(HtmlCaptureError, "PNG_DECODE"):
            png_dimensions(path)

    def test_13_png_truncated_header_blocks(self) -> None:
        path = self.root / "bad.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        with self.assertRaisesRegex(HtmlCaptureError, "PNG_DECODE"):
            png_dimensions(path)

    def test_14_browser_startup_failure_is_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "browser failed to launch", False),
            "browser_startup_failure",
        )

    def test_15_navigation_timeout_is_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "page.goto navigation timeout", False),
            "navigation_timeout",
        )

    def test_16_ready_timeout_is_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "official ready condition timeout", False),
            "official_ready_condition_timeout",
        )

    def test_17_browser_crash_is_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "browser process crashed", False),
            "browser_process_crash",
        )

    def test_18_missing_output_after_success_is_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(0, "", "", False), "missing_output_after_success"
        )

    def test_19_locked_profile_is_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(
                1, "", "user data directory is already in use", False
            ),
            "locked_profile_or_cleanup_failure",
        )

    def test_20_dimension_mismatch_is_not_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(
                1,
                "",
                "screenshot dimensions 1664x936 do not match expected 1672x941",
                True,
            ),
            "dimension_mismatch",
        )

    def test_21_html_hash_mismatch_is_not_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "current HTML hash mismatch", True),
            "html_hash_mismatch",
        )

    def test_22_wrong_slide_is_not_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "wrong slide id", True), "wrong_slide_id"
        )

    def test_23_stale_output_is_not_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "stale screenshot", True), "stale_output"
        )

    def test_24_missing_local_asset_is_not_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "missing local asset", False),
            "missing_local_asset",
        )

    def test_25_offcanvas_geometry_is_not_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "off-canvas geometry", True),
            "off_canvas_geometry",
        )

    def test_26_unsupported_format_is_not_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "unsupported output format", True),
            "unsupported_output_format",
        )

    def test_27_first_retryable_attempt_can_retry(self) -> None:
        self.assertTrue(can_retry("navigation_timeout", 1))

    def test_28_second_attempt_cannot_retry(self) -> None:
        self.assertFalse(can_retry("navigation_timeout", 2))

    def test_29_nonretryable_reason_cannot_retry(self) -> None:
        self.assertFalse(can_retry("dimension_mismatch", 1))

    def test_30_unknown_failure_is_not_retryable(self) -> None:
        self.assertEqual(
            classify_capture_failure(1, "", "opaque failure", False),
            "unknown_nonretryable_failure",
        )


class PolicyAndReadinessTests(unittest.TestCase):
    def test_31_default_attempt_policy_is_valid(self) -> None:
        validate_attempt_policy(DEFAULT_ATTEMPT_POLICY)

    def test_32_max_attempts_must_be_two(self) -> None:
        policy = dict(DEFAULT_ATTEMPT_POLICY, max_attempts_per_slide=3)
        with self.assertRaisesRegex(HtmlCaptureError, "ATTEMPT_POLICY"):
            validate_attempt_policy(policy)

    def test_33_hidden_retry_must_be_false(self) -> None:
        policy = dict(DEFAULT_ATTEMPT_POLICY, automatic_hidden_retry=True)
        with self.assertRaisesRegex(HtmlCaptureError, "ATTEMPT_POLICY"):
            validate_attempt_policy(policy)

    def test_34_explicit_retry_must_be_true(self) -> None:
        policy = dict(DEFAULT_ATTEMPT_POLICY, explicit_retry=False)
        with self.assertRaisesRegex(HtmlCaptureError, "ATTEMPT_POLICY"):
            validate_attempt_policy(policy)

    def test_35_parallelism_must_be_one(self) -> None:
        policy = dict(DEFAULT_ATTEMPT_POLICY, parallelism=2)
        with self.assertRaisesRegex(HtmlCaptureError, "ATTEMPT_POLICY"):
            validate_attempt_policy(policy)

    def test_36_valid_readiness_passes(self) -> None:
        validate_readiness_probe(
            _readiness(), slide_id="slide-001", width=1664, height=936
        )

    def test_37_document_incomplete_blocks(self) -> None:
        payload = _readiness()
        payload["document_ready_state"] = "interactive"
        with self.assertRaisesRegex(HtmlCaptureError, "READY_CONDITION"):
            validate_readiness_probe(
                payload, slide_id="slide-001", width=1664, height=936
            )

    def test_38_fonts_not_ready_blocks(self) -> None:
        payload = _readiness()
        payload["fonts_ready"] = False
        with self.assertRaisesRegex(HtmlCaptureError, "READY_CONDITION"):
            validate_readiness_probe(
                payload, slide_id="slide-001", width=1664, height=936
            )

    def test_39_images_not_ready_blocks(self) -> None:
        payload = _readiness()
        payload["images_ready"] = False
        with self.assertRaisesRegex(HtmlCaptureError, "READY_CONDITION"):
            validate_readiness_probe(
                payload, slide_id="slide-001", width=1664, height=936
            )

    def test_40_unstable_layout_blocks(self) -> None:
        payload = _readiness()
        payload["layout_stable"] = False
        with self.assertRaisesRegex(HtmlCaptureError, "READY_CONDITION"):
            validate_readiness_probe(
                payload, slide_id="slide-001", width=1664, height=936
            )

    def test_41_invisible_target_blocks(self) -> None:
        payload = _readiness()
        payload["target_visible"] = False
        with self.assertRaisesRegex(HtmlCaptureError, "READY_CONDITION"):
            validate_readiness_probe(
                payload, slide_id="slide-001", width=1664, height=936
            )

    def test_42_missing_qa_static_blocks(self) -> None:
        payload = _readiness()
        payload["qa_static_mode"] = False
        with self.assertRaisesRegex(HtmlCaptureError, "READY_CONDITION"):
            validate_readiness_probe(
                payload, slide_id="slide-001", width=1664, height=936
            )

    def test_43_remote_network_dependency_blocks(self) -> None:
        payload = _readiness()
        payload["remote_network_dependency"] = True
        with self.assertRaisesRegex(HtmlCaptureError, "READY_CONDITION"):
            validate_readiness_probe(
                payload, slide_id="slide-001", width=1664, height=936
            )


class AttemptAndManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="html-capture-manifest-")
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        self.project = self.runtime / "handoff" / "project"
        self.project.mkdir(parents=True)
        self.html = _html(self.project / "out.html")
        self.html_hash = sha256(self.html.read_bytes()).hexdigest()

    def manifest(self, *, count: int = 6, fault_state: str = "baseline") -> dict:
        attempts = [
            _attempt(self.runtime, slide, self.html_hash)
            for slide in range(1, count + 1)
        ]
        if fault_state != "baseline":
            for record in attempts:
                record["fault_state"] = fault_state
                record.pop("record_hash")
                record.update(bind_attempt_record(record))
        return build_capture_manifest(
            run_id="run-alpha",
            fault_state=fault_state,
            runtime_root=self.runtime,
            source_html=self.html,
            browser_identity="Playwright Chromium",
            browser_version="149.0.7827.55",
            dimension_authority=derive_dimension_authority(self.html),
            attempts=attempts,
            ordered_slide_ids=tuple(f"slide-{n:03d}" for n in range(1, count + 1)),
            created_at="2026-07-22T09:00:00+09:00",
        )

    def test_44_valid_attempt_passes(self) -> None:
        validate_attempt_record(
            _attempt(self.runtime, 1, self.html_hash),
            runtime_root=self.runtime,
            run_id="run-alpha",
            html_sha256=self.html_hash,
        )

    def test_45_attempt_hash_mismatch_blocks(self) -> None:
        record = _attempt(self.runtime, 1, self.html_hash)
        record["record_hash"] = "0" * 64
        with self.assertRaisesRegex(HtmlCaptureError, "ATTEMPT_HASH"):
            validate_attempt_record(
                record,
                runtime_root=self.runtime,
                run_id="run-alpha",
                html_sha256=self.html_hash,
            )

    def test_46_attempt_parent_html_mismatch_blocks(self) -> None:
        record = _attempt(self.runtime, 1, self.html_hash)
        record["current_html_sha256"] = "0" * 64
        record = bind_attempt_record(
            {k: v for k, v in record.items() if k != "record_hash"}
        )
        with self.assertRaisesRegex(HtmlCaptureError, "HTML_HASH"):
            validate_attempt_record(
                record,
                runtime_root=self.runtime,
                run_id="run-alpha",
                html_sha256=self.html_hash,
            )

    def test_47_attempt_dimension_mismatch_blocks(self) -> None:
        record = _attempt(self.runtime, 1, self.html_hash)
        record["actual_dimensions"] = {"width": 1672, "height": 941}
        record = bind_attempt_record(
            {k: v for k, v in record.items() if k != "record_hash"}
        )
        with self.assertRaisesRegex(HtmlCaptureError, "DIMENSION_MISMATCH"):
            validate_attempt_record(
                record,
                runtime_root=self.runtime,
                run_id="run-alpha",
                html_sha256=self.html_hash,
            )

    def test_48_attempt_output_outside_runtime_blocks(self) -> None:
        record = _attempt(self.runtime, 1, self.html_hash)
        record["output_path"] = str(ROOT / "outside.png")
        record = bind_attempt_record(
            {k: v for k, v in record.items() if k != "record_hash"}
        )
        with self.assertRaisesRegex(HtmlCaptureError, "OUTPUT_PATH"):
            validate_attempt_record(
                record,
                runtime_root=self.runtime,
                run_id="run-alpha",
                html_sha256=self.html_hash,
            )

    def test_49_attempt_wrong_run_blocks(self) -> None:
        record = _attempt(self.runtime, 1, self.html_hash)
        record["run_id"] = "other"
        record = bind_attempt_record(
            {k: v for k, v in record.items() if k != "record_hash"}
        )
        with self.assertRaisesRegex(HtmlCaptureError, "RUN_ID"):
            validate_attempt_record(
                record,
                runtime_root=self.runtime,
                run_id="run-alpha",
                html_sha256=self.html_hash,
            )

    def test_50_attempt_wrong_slide_blocks(self) -> None:
        record = _attempt(self.runtime, 1, self.html_hash)
        record["slide_id"] = "slide-009"
        record = bind_attempt_record(
            {k: v for k, v in record.items() if k != "record_hash"}
        )
        with self.assertRaisesRegex(HtmlCaptureError, "SLIDE_ID"):
            validate_attempt_record(
                record,
                runtime_root=self.runtime,
                run_id="run-alpha",
                html_sha256=self.html_hash,
                expected_slide_id="slide-001",
            )

    def test_51_full_six_slide_manifest_passes(self) -> None:
        self.assertEqual(
            validate_capture_manifest(self.manifest(), runtime_root=self.runtime)[
                "selected_screenshot_count"
            ],
            6,
        )

    def test_52_five_slide_manifest_blocks(self) -> None:
        with self.assertRaisesRegex(HtmlCaptureError, "SELECTED_COUNT"):
            validate_capture_manifest(
                self.manifest(count=5),
                runtime_root=self.runtime,
                require_full_deck=True,
            )

    def test_53_duplicate_slide_blocks(self) -> None:
        payload = self.manifest()
        payload["ordered_slide_ids"][5] = "slide-005"
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "SLIDE_ORDER"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_54_wrong_slide_order_blocks(self) -> None:
        payload = self.manifest()
        payload["ordered_slide_ids"] = list(reversed(payload["ordered_slide_ids"]))
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "SLIDE_ORDER"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_55_missing_count_blocks(self) -> None:
        payload = self.manifest()
        payload["missing_count"] = 1
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "MANIFEST_COUNTS"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_56_timeout_count_blocks(self) -> None:
        payload = self.manifest()
        payload["timeout_count"] = 1
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "MANIFEST_COUNTS"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_57_dimension_mismatch_count_blocks(self) -> None:
        payload = self.manifest()
        payload["dimension_mismatch_count"] = 1
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "MANIFEST_COUNTS"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_58_stale_count_blocks(self) -> None:
        payload = self.manifest()
        payload["stale_record_count"] = 1
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "MANIFEST_COUNTS"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_59_cross_run_reuse_blocks(self) -> None:
        payload = self.manifest()
        payload["cross_run_reuse_count"] = 1
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "CROSS_RUN"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_60_duplicate_selected_output_hash_blocks(self) -> None:
        payload = self.manifest()
        payload["records"][1]["output_sha256"] = payload["records"][0]["output_sha256"]
        payload["records"][1] = bind_attempt_record(
            {k: v for k, v in payload["records"][1].items() if k != "record_hash"}
        )
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "DUPLICATE_OUTPUT"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_61_manifest_hash_verifies(self) -> None:
        self.assertTrue(verify_capture_manifest_hash(self.manifest()))

    def test_62_manifest_hash_mismatch_blocks(self) -> None:
        payload = self.manifest()
        payload["manifest_hash"] = "0" * 64
        with self.assertRaisesRegex(HtmlCaptureError, "MANIFEST_HASH"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_63_fault_state_enum_is_enforced(self) -> None:
        payload = self.manifest()
        payload["fault_state"] = "unknown"
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "FAULT_STATE"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_64_source_html_path_must_be_inside_runtime(self) -> None:
        payload = self.manifest()
        payload["source_html_path"] = str(ROOT / "outside.html")
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "SOURCE_HTML_PATH"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_65_source_html_hash_must_match_file(self) -> None:
        payload = self.manifest()
        payload["source_html_sha256"] = "0" * 64
        payload.pop("manifest_hash")
        with self.assertRaisesRegex(HtmlCaptureError, "HTML_HASH"):
            validate_capture_manifest(payload, runtime_root=self.runtime)

    def test_66_faulty_manifest_is_supported(self) -> None:
        self.assertEqual(
            validate_capture_manifest(
                self.manifest(fault_state="faulty"), runtime_root=self.runtime
            )["fault_state"],
            "faulty",
        )

    def test_71_ordered_micro_canary_subset_passes_without_weakening_full_deck_gate(
        self,
    ) -> None:
        attempts = [_attempt(self.runtime, slide, self.html_hash) for slide in (1, 6)]
        payload = build_capture_manifest(
            run_id="run-alpha",
            fault_state="baseline",
            runtime_root=self.runtime,
            source_html=self.html,
            browser_identity="Playwright Chromium",
            browser_version="149.0.7827.55",
            dimension_authority=derive_dimension_authority(self.html),
            attempts=attempts,
            ordered_slide_ids=("slide-001", "slide-006"),
            created_at="2026-07-22T09:00:00+09:00",
        )
        self.assertEqual(
            validate_capture_manifest(payload, runtime_root=self.runtime)[
                "selected_screenshot_count"
            ],
            2,
        )
        with self.assertRaisesRegex(HtmlCaptureError, "SELECTED_COUNT"):
            validate_capture_manifest(
                payload, runtime_root=self.runtime, require_full_deck=True
            )

    def test_67_repaired_manifest_is_supported(self) -> None:
        self.assertEqual(
            validate_capture_manifest(
                self.manifest(fault_state="repaired"), runtime_root=self.runtime
            )["fault_state"],
            "repaired",
        )

    def test_68_manifest_records_exact_attempt_policy(self) -> None:
        self.assertEqual(self.manifest()["attempt_policy"], DEFAULT_ATTEMPT_POLICY)

    def test_69_manifest_uses_current_html_hash_for_every_record(self) -> None:
        self.assertEqual(
            {row["current_html_sha256"] for row in self.manifest()["records"]},
            {self.html_hash},
        )

    def test_70_manifest_selected_paths_are_current_runtime_paths(self) -> None:
        payload = self.manifest()
        self.assertTrue(
            all(
                Path(row["output_path"])
                .resolve()
                .is_relative_to(self.runtime.resolve())
                for row in payload["records"]
            )
        )


if __name__ == "__main__":
    unittest.main()
