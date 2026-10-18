"""Invented cache identity regressions; no actual OCR or rendered-quality claim."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_general_generate_workflow as fixtures
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import vector_preflight as vector


class VectorInventoryBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "invented-region-runtime"
        helper = fixtures.GeneralGenerateWorkflowTests()
        started = helper._start(self.root)
        helper._build_run_draft(self.root, workflow_id=started.workflow_id, slide_count=1,
                                status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0)
        self.slide_path = vector.slide_preflight_path(self.root, 1)
        self.aggregate_path = self.root / vector.PROJECT_DIRECTORY / "work" / vector.MANIFEST_NAME
        self.slide = read_json(self.slide_path)
        self.aggregate = read_json(self.aggregate_path)
        self.inputs = vector._load_inputs(self.root)
        self.configuration = {"pipeline_root": Path(self.slide["pipeline_provenance"]["root"]),
                              "python_executable": self.slide["execution"]["python_executable"],
                              "backend": self.slide["execution"]["backend"],
                              "deep": self.slide["execution"]["deep_scan"]}

    @staticmethod
    def inventory(fractional=True):
        box = {"x": 42.3, "y": 31.8, "w": 12.4, "h": 8.3} if fractional else {"x": 42, "y": 31, "w": 13, "h": 10}
        return {"canvas_px": {"w": 1600, "h": 900}, "text_blocks": [], "suppressed_text": [],
                "notes": ["Invented region identity input"],
                "regions": [{"id": "invented-alpha", "kind_hint": "photo", "bbox_px": box,
                             "confidence": 0.73},
                            {"id": "invented-beta", "kind_hint": "complex_graphic",
                             "bbox_px": {"x": 93, "y": 77, "w": 19, "h": 11}, "confidence": 0.81}]}

    def install(self, inventory=None):
        inventory = self.inventory() if inventory is None else inventory
        seed = self.slide["slide"]
        source = self.root / seed["source_png"]["path"]
        inventory_path = self.root / seed["measurement_inventory"]["path"]
        batch = self.root / seed["measurement_batch_job"]["path"]
        write_json(inventory_path, inventory)
        self.measurement = {1: {"inventory_path": inventory_path, "batch_job_path": batch,
                                "command": ["invented-contract-input"], "stdout": "", "stderr": ""}}
        with patch.object(vector, "trace_png_to_svg", side_effect=AssertionError("no fixture region should trace")):
            record = vector._build_slide_record(root=self.root, source=source,
                inventory_path=inventory_path, inventory=inventory, request_row=self.inputs["slides"][0],
                backend=self.configuration["backend"], deep=self.configuration["deep"],
                command=["invented-contract-input"], stdout="", stderr="", batch_job_path=batch)
        self.write_record(record)
        return record

    def write_record(self, record):
        record = copy.deepcopy(record)
        record["slide_content_hash"] = content_sha256({k: v for k, v in record.items() if k != "slide_content_hash"})
        for path, original, key in ((self.slide_path, self.slide, "slide"),
                                    (self.aggregate_path, self.aggregate, "slides")):
            payload = copy.deepcopy(original)
            payload[key] = record if key == "slide" else [record]
            payload["measured_region_count"] = len(record["regions"])
            payload["passed_vector_count"] = sum(r["disposition"] == "bounded_svg_asset" for r in record["regions"])
            payload["content_hash"] = content_sha256({k: v for k, v in payload.items() if k != "content_hash"})
            write_json(path, payload)

    def reports(self):
        return (vector.validate_vector_preflight_slide_bundle(self.root, 1),
                vector.validate_vector_preflight_bundle(self.root))

    def assert_rejected(self):
        for validator, report in zip(("slide", "aggregate"), self.reports()):
            with self.subTest(validator=validator):
                self.assertFalse(report["valid"], report)
                self.assertTrue(any("measurement inventory" in issue for issue in report["issues"]), report)

    def test_resealed_region_ids_must_match_measurement_inventory(self):
        record = self.install()
        record["regions"][0]["region_id"] = "unmeasured-region"
        self.write_record(record)
        self.assert_rejected()

    def test_resealed_geometry_and_normalization_must_match_measured_enclosure(self):
        for change in ("bbox", "normalization", "kind", "confidence"):
            with self.subTest(change=change):
                record = self.install()
                row = record["regions"][0]
                if change == "bbox":
                    row["bbox_px"] = {"x": 400, "y": 250, "w": 13, "h": 10}
                    row["bbox_norm"] = vector._norm_bbox(row["bbox_px"], 1600, 900)
                    row["area_ratio"] = round(130 / (1600 * 900), 8)
                elif change == "normalization":
                    row["bbox_norm"]["x"] = 0.8
                elif change == "kind":
                    row["kind_hint"] = "line"
                else:
                    row["measurement_confidence"] = 0.99
                self.write_record(record)
                self.assert_rejected()

    def test_resealed_dropped_extra_and_duplicate_regions_are_rejected(self):
        for change in ("drop", "extra", "duplicate"):
            with self.subTest(change=change):
                record = self.install()
                if change == "drop":
                    record["regions"].pop()
                elif change == "extra":
                    extra = copy.deepcopy(record["regions"][0]); extra["region_id"] = "extra"
                    record["regions"].append(extra)
                else:
                    record["regions"][1] = copy.deepcopy(record["regions"][0])
                self.write_record(record)
                self.assert_rejected()

    def test_exact_integer_and_fractional_caches_remain_reusable(self):
        for fractional in (False, True):
            with self.subTest(fractional=fractional):
                self.install(self.inventory(fractional))
                for report in self.reports(): self.assertTrue(report["valid"], report)
                before = (self.slide_path.read_bytes(), self.aggregate_path.read_bytes())
                with patch.object(vector, "_run_measurement_batches", side_effect=AssertionError("valid cache must not remeasure")):
                    vector.prepare_vector_preflight_slide(self.root, slide_number=1, **self.configuration)
                    vector.prepare_vector_preflight(self.root, require_cached=True, **self.configuration)
                self.assertEqual(before, (self.slide_path.read_bytes(), self.aggregate_path.read_bytes()))

    def test_wrong_current_cache_requires_rebuild_and_cannot_be_reused(self):
        record = self.install(); record["regions"].pop(); self.write_record(record)
        before = (self.slide_path.read_bytes(), self.aggregate_path.read_bytes())
        with patch.object(vector, "_run_measurement_batches") as measure:
            with self.assertRaises(DeckCompilerError):
                vector.prepare_vector_preflight(self.root, require_cached=True, **self.configuration)
            measure.assert_not_called()
        self.assertEqual(before, (self.slide_path.read_bytes(), self.aggregate_path.read_bytes()))
        with patch.object(vector, "_run_measurement_batches", return_value=self.measurement) as measure:
            vector.prepare_vector_preflight(self.root, **self.configuration)
            measure.assert_called_once()
        for report in self.reports(): self.assertTrue(report["valid"], report)

    def test_zero_regions_and_fallback_identifiers_keep_existing_behavior(self):
        inventory = self.inventory(); inventory["regions"] = []
        self.install(inventory)
        for report in self.reports(): self.assertTrue(report["valid"], report)
        inventory = self.inventory()
        inventory["regions"][0].pop("id")
        record = self.install(inventory)
        self.assertEqual(record["regions"][0]["region_id"], "R01")
        for report in self.reports(): self.assertTrue(report["valid"], report)

    def test_order_numeric_source_ids_and_skipped_rows_keep_existing_behavior(self):
        inventory = self.inventory(False)
        inventory["regions"][0]["id"] = 42
        inventory["regions"][1].pop("id")
        inventory["regions"].insert(0, None)
        record = self.install(inventory)
        self.assertEqual([r["region_id"] for r in record["regions"]], ["42", "R03"])
        record["regions"].reverse()
        self.write_record(record)
        for report in self.reports(): self.assertTrue(report["valid"], report)

    def test_integer_supplied_normalization_is_preserved_exactly(self):
        inventory = self.inventory(False)
        normalization = {"x": 42 / 1600, "y": 31 / 900, "w": 13 / 1600, "h": 10 / 900}
        inventory["regions"][0]["bbox_norm"] = normalization
        record = self.install(inventory)
        self.assertEqual(record["regions"][0]["bbox_norm"], normalization)
        for report in self.reports(): self.assertTrue(report["valid"], report)

    def test_duplicate_normalized_measurement_ids_are_ambiguous(self):
        for ids in ((42, "42"), (None, "R01")):
            with self.subTest(ids=ids):
                inventory = self.inventory()
                for row, identifier in zip(inventory["regions"], ids): row["id"] = identifier
                self.install(inventory)
                self.assert_rejected()

    def test_fractional_stored_box_cannot_substitute_for_integer_enclosure(self):
        inventory = self.inventory()
        record = self.install(inventory)
        record["regions"][0]["bbox_px"] = inventory["regions"][0]["bbox_px"]
        self.write_record(record)
        self.assert_rejected()

    def test_measured_fields_require_presence_and_json_type_identity(self):
        for change in ("missing_null_confidence", "boolean_confidence", "boolean_normalization"):
            with self.subTest(change=change):
                inventory = self.inventory(False)
                inventory["regions"][0]["confidence"] = None if change == "missing_null_confidence" else 1
                inventory["regions"][0]["bbox_px"]["x"] = 0
                record = self.install(inventory)
                row = record["regions"][0]
                if change == "missing_null_confidence":
                    del row["measurement_confidence"]
                elif change == "boolean_confidence":
                    row["measurement_confidence"] = True
                else:
                    row["bbox_norm"]["x"] = False
                self.write_record(record)
                self.assert_rejected()

    def test_equivalent_integer_float_json_numbers_remain_compatible(self):
        inventory = self.inventory(False)
        inventory["regions"][0]["confidence"] = 1
        record = self.install(inventory)
        record["regions"][0]["measurement_confidence"] = 1.0
        record["regions"][0]["bbox_px"] = {k: float(v) for k, v in record["regions"][0]["bbox_px"].items()}
        self.write_record(record)
        for report in self.reports(): self.assertTrue(report["valid"], report)


if __name__ == "__main__":
    unittest.main()
