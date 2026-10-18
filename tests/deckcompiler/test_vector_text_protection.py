"""Protected-text ingestion regressions; synthetic contracts, no render/QA claims."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import test_general_generate_workflow as fixtures
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import vector_preflight as vector


class VectorTextProtectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source.png"
        Image.new("RGB", (320, 180), (31, 45, 59)).save(self.source)
        self.inventory_path = self.root / "work/measurement_inventory.json"
        self.batch = write_json(self.root / "batch.json", {"fixture_only": True})

    @staticmethod
    def inventory():
        return {
            "canvas_px": {"w": 320, "h": 180},
            "text_blocks": [], "suppressed_text": [],
            "regions": [{"id": "R1", "kind_hint": "flat_shape",
                         "bbox_px": {"x": 20, "y": 20, "w": 40, "h": 30}}],
            "notes": ["Synthetic contract fixture; not detector evidence"],
        }

    def build(self, inventory):
        # Match the external detector's JSON writer, including malformed numeric input.
        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
        self.inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
        return vector._build_slide_record(
            root=self.root, source=self.source, inventory_path=self.inventory_path,
            inventory=inventory, request_row={"slide_number": 1, "slide_id": "fixture",
                                               "request_id": "fixture-request"},
            backend="tesseract", deep=False, command=["synthetic-fixture"],
            stdout="", stderr="", batch_job_path=self.batch,
        )

    def assert_rejected_before_trace(self, inventory):
        with patch.object(vector, "trace_png_to_svg", return_value={"status": "rejected", "reason": "test-sentinel"}) as trace:
            with self.assertRaisesRegex(DeckCompilerError, "text_blocks|suppressed_text"):
                self.build(inventory)
            trace.assert_not_called()

    def test_generation_rejects_malformed_protected_text_rows_before_trace(self):
        for collection in ("text_blocks", "suppressed_text"):
            for row in (None, "text", 7, {}, {"id": "T1", "text": "keep editable"},
                        {"bbox_px": None}, {"bbox_px": [20, 20, 40, 30]},
                        {"bbox_px": {"x": 20, "y": 20, "w": 40}}):
                with self.subTest(collection=collection, row=row):
                    inventory = self.inventory(); inventory[collection] = [row]
                    self.assert_rejected_before_trace(inventory)

    def test_generation_rejects_non_array_protected_text_collections(self):
        for collection in ("text_blocks", "suppressed_text"):
            for value in (None, {}, {"T1": {"bbox_px": {"x": 20, "y": 20, "w": 40, "h": 30}}}, "text", 1):
                with self.subTest(collection=collection, value=value):
                    inventory = self.inventory(); inventory[collection] = value
                    self.assert_rejected_before_trace(inventory)

    def test_generation_rejects_missing_text_collection(self):
        inventory = self.inventory(); inventory.pop("text_blocks")
        self.assert_rejected_before_trace(inventory)

    def test_generation_rejects_nonfinite_non_numeric_and_out_of_canvas_text(self):
        invalid = (("x", -1), ("y", -1), ("w", 0), ("h", -1), ("w", 301),
                   ("h", 161), ("x", float("nan")), ("y", float("inf")),
                   ("w", float("-inf")), ("x", True), ("y", "20"), ("w", 10 ** 1000))
        for collection in ("text_blocks", "suppressed_text"):
            for key, value in invalid:
                with self.subTest(collection=collection, key=key, value=value):
                    inventory = self.inventory()
                    bbox = {"x": 20, "y": 20, "w": 40, "h": 30}; bbox[key] = value
                    inventory[collection] = [{"id": "T1", "bbox_px": bbox}]
                    self.assert_rejected_before_trace(inventory)

    def test_valid_fractional_text_and_suppressed_text_stay_exact_and_protected(self):
        inventory = self.inventory()
        inventory["text_blocks"] = [{"id": "T1", "bbox_px": {"x": 59.75, "y": 25.5, "w": .5, "h": 5.25}}]
        inventory["suppressed_text"] = [{"id": "S1", "bbox_px": {"x": 25.5, "y": 49.75, "w": 5.25, "h": .5}}]
        before = copy.deepcopy(inventory)
        with patch.object(vector, "trace_png_to_svg") as trace:
            result = self.build(inventory)
            trace.assert_not_called()
        self.assertEqual(inventory, before)
        self.assertEqual(read_json(self.inventory_path), before)
        self.assertEqual(result["text_block_count"], 2)
        self.assertEqual(result["regions"][0]["semantic_text_overlap_ids"], ["T1", "S1"])
        self.assertEqual(result["regions"][0]["disposition"], "native_rebuild_text_protected")

    def test_huge_integer_with_fractional_partner_is_structurally_rejected(self):
        for changes in ({"x": 10 ** 1000, "w": .5}, {"x": .5, "w": 10 ** 1000},
                        {"y": 10 ** 1000, "h": .5}, {"y": .5, "h": 10 ** 1000}):
            with self.subTest(changes=changes):
                inventory = self.inventory()
                bbox = {"x": 20, "y": 20, "w": 40, "h": 30}; bbox.update(changes)
                inventory["text_blocks"] = [{"id": "T1", "bbox_px": bbox}]
                self.assert_rejected_before_trace(inventory)

    def test_valid_empty_text_preserves_nontext_regions_and_original_inventory(self):
        inventory = self.inventory()
        inventory.pop("suppressed_text")  # Older detector inventories may omit this optional list.
        inventory["regions"][0]["kind_hint"] = "photo"
        inventory["regions"].append({"id": "R2", "kind_hint": "complex_graphic",
                                     "bbox_px": {"x": 80, "y": 30, "w": 50, "h": 40}})
        before = copy.deepcopy(inventory)
        with patch.object(vector, "trace_png_to_svg") as trace:
            result = self.build(inventory)
            trace.assert_not_called()
        self.assertEqual(inventory, before)
        self.assertEqual(read_json(self.inventory_path), before)
        self.assertEqual([row["region_id"] for row in result["regions"]], ["R1", "R2"])
        self.assertEqual([row["bbox_px"] for row in result["regions"]], [row["bbox_px"] for row in before["regions"]])
        self.assertEqual(result["regions"][0]["disposition"], "bounded_raster_candidate")
        self.assertEqual(result["regions"][1]["disposition"], "native_rebuild_or_skill_review")

    def public_runtime(self):
        helper = fixtures.GeneralGenerateWorkflowTests()
        runtime = self.root / "runtime"
        started = helper._start(runtime)
        helper._build_run_draft(runtime, workflow_id=started.workflow_id, slide_count=1,
                                status="COMPLETED", qa_status="PASS", fail_count=0, blocking_count=0)
        return runtime

    @staticmethod
    def seal(path, payload):
        payload["content_hash"] = content_sha256({k: v for k, v in payload.items() if k != "content_hash"})
        write_json(path, payload)

    def reseal_inventory(self, runtime, change, *, source_dimensions=None):
        slide_path = vector.slide_preflight_path(runtime, 1)
        slide = read_json(slide_path)
        inventory_path = runtime / slide["slide"]["measurement_inventory"]["path"]
        inventory = read_json(inventory_path); change(inventory); write_json(inventory_path, inventory)
        inventory_sha = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
        aggregate_path = runtime / vector.PROJECT_DIRECTORY / "work" / vector.MANIFEST_NAME
        aggregate = read_json(aggregate_path)
        for record in (slide["slide"], aggregate["slides"][0]):
            record["measurement_inventory"]["sha256"] = inventory_sha
            if source_dimensions is not None:
                record["source_png"].update(source_dimensions)
            record["slide_content_hash"] = content_sha256({k: v for k, v in record.items() if k != "slide_content_hash"})
        self.seal(slide_path, slide); self.seal(aggregate_path, aggregate)

    def test_public_slide_validation_rejects_malformed_text_despite_resealed_hashes(self):
        runtime = self.public_runtime()
        self.reseal_inventory(runtime, lambda data: data.update(text_blocks=[{"id": "T1", "text": "must not disappear"}]))
        report = vector.validate_vector_preflight_slide_bundle(runtime, 1)
        self.assertFalse(report["valid"], report)
        self.assertTrue(any("text_blocks" in issue for issue in report["issues"]), report)

    def test_public_aggregate_validation_rejects_malformed_suppressed_text(self):
        runtime = self.public_runtime()
        self.reseal_inventory(runtime, lambda data: data.update(suppressed_text=[{"id": "S1", "bbox_px": None}]))
        report = vector.validate_vector_preflight_bundle(runtime)
        self.assertFalse(report["valid"], report)
        self.assertTrue(any("suppressed_text" in issue for issue in report["issues"]), report)

    def test_public_slide_validation_uses_actual_png_frame(self):
        runtime = self.public_runtime()
        self.reseal_inventory(runtime, lambda data: data.update(canvas_px={"w": 32000, "h": 18000}),
                              source_dimensions={"width": 32000, "height": 18000})
        report = vector.validate_vector_preflight_slide_bundle(runtime, 1)
        self.assertFalse(report["valid"], report)
        self.assertTrue(any("canvas" in issue or "dimensions" in issue for issue in report["issues"]), report)


if __name__ == "__main__":
    unittest.main()
