"""Crop-plan contract fixtures; no renderer or visual-quality claims."""
from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import (
    _validate_crops, validate_reconstruction_job_bundle,
)


class ReconstructionCropContractTests(unittest.TestCase):
    def crop(self, **overrides):
        return {
            "name": "s1_photo", "slide": 1,
            "x": 1500, "y": 800, "w": 100, "h": 100,
            "content_type": "photoreal",
            "reconstruction_reason": "Original photograph cannot be rebuilt natively",
            "editable_replacement": "none",
            **overrides,
        }

    def validate(self, crop, *, source=None, as_mapping=False):
        issues = []
        crops = {crop["name"]: crop} if as_mapping else [crop]
        _validate_crops(
            {"crops": crops}, 1, source or {"width": 1600, "height": 900}, issues,
        )
        return issues

    def test_exact_canvas_edge_remains_valid(self):
        self.assertEqual(self.validate(self.crop()), [])
        self.assertEqual(self.validate(self.crop(), as_mapping=True), [])

    def test_empty_crop_plans_remain_valid(self):
        for payload in ({"crops": []}, {"crops": {}}, {}):
            issues = []
            _validate_crops(payload, 1, {"width": 1600, "height": 900}, issues)
            self.assertEqual(issues, [])

    def test_finite_numeric_strings_and_fractional_pixels_remain_valid(self):
        self.assertEqual(self.validate(self.crop(slide="1.0", x="1499.4", y=799.4, w=100.4, h=100.4)), [])

    def test_crops_cannot_be_silently_clamped_at_source_edges(self):
        for override in ({"w": 101}, {"h": 101}, {"x": 1600}, {"y": 900}):
            with self.subTest(override=override):
                self.assertTrue(self.validate(self.crop(**override)))

    def test_rounded_geometry_cannot_cross_source_edges(self):
        # Raw right edge is 1599; make_crops rounds x and w independently.
        self.assertTrue(self.validate(self.crop(x=1499.5, w=99.5), source={"width": 1599, "height": 900}))

    def test_nonfinite_geometry_is_reported_without_crashing(self):
        for field in ("x", "y", "w", "h"):
            for value in (float("nan"), float("inf"), -float("inf"), "NaN", "Infinity"):
                with self.subTest(field=field, value=value):
                    self.assertTrue(self.validate(self.crop(**{field: value})))

    def test_invalid_numeric_geometry_is_reported_without_crashing(self):
        for value in (None, "not-a-number", True, 10**400):
            with self.subTest(value=value):
                self.assertTrue(self.validate(self.crop(w=value)))

    def test_fractional_slide_cannot_select_another_source(self):
        for value in (1.1, 1.6, "1.6"):
            with self.subTest(slide=value):
                self.assertTrue(self.validate(self.crop(slide=value)))

    def test_nonfinite_or_invalid_slide_is_reported_without_crashing(self):
        for value in (float("nan"), float("inf"), -float("inf"), "NaN", "Infinity", True, 10**400):
            with self.subTest(slide=value):
                self.assertTrue(self.validate(self.crop(slide=value)))

    def test_width_or_height_rounding_to_zero_is_rejected(self):
        for override in ({"w": 0.4}, {"h": 0.5}):
            with self.subTest(override=override):
                self.assertTrue(self.validate(self.crop(**override)))

    def test_crop_area_gate_also_checks_actual_rounded_pixels(self):
        crop = self.crop(x=0, y=0, w=75.51, h=59.51)
        self.assertTrue(self.validate(crop, source={"width": 100, "height": 100}))

    def test_existing_negative_zero_and_area_rejections_remain(self):
        for override in ({"x": -1}, {"y": -1}, {"w": 0}, {"h": 0}, {"x": 0, "y": 0, "w": 1600, "h": 500}):
            with self.subTest(override=override):
                self.assertTrue(self.validate(self.crop(**override)))

    def test_public_authoring_and_completion_gates_reject_invalid_crops(self):
        # Reuse the upstream's explicitly synthetic workflow contract fixture.
        # No detector/model/rendered-quality acceptance is claimed here.
        from test_general_generate_workflow import GeneralGenerateWorkflowTests

        fixture = GeneralGenerateWorkflowTests()
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            started = fixture._start(runtime)
            fixture._build_run_draft(
                runtime, workflow_id=started.workflow_id, slide_count=1,
                status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0,
            )
            work = runtime / "pngtopptx-project/work/slide01"
            crop_path = work / "crop_plan.json"
            receipt_path = work / "worker_receipt.json"
            for override, valid in (({}, True), ({"w": 200}, False), ({"slide": 1.6}, False)):
                write_json(crop_path, {"crops": [self.crop(**override)]})
                receipt = read_json(receipt_path)
                receipt["artifactHashes"]["crop_plan.json"] = fixture._sha256(crop_path)
                write_json(receipt_path, receipt)
                for flag in ("require_authoring_outputs", "require_worker_outputs"):
                    with self.subTest(override=override, gate=flag):
                        report = validate_reconstruction_job_bundle(runtime, **{flag: True})
                        self.assertEqual(report["valid"], valid, report)
                        if not valid:
                            self.assertTrue(any("worker crop" in issue for issue in report["issues"]), report)


if __name__ == "__main__":
    unittest.main()
