"""Invented region enclosure regressions; no detector or render-quality claims."""
from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import vector_preflight as vector


class VectorRegionEnclosureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "invented-source.png"
        Image.new("RGB", (320, 180), (32, 48, 64)).save(self.source)
        self.inventory_path = self.root / "work/inventory.json"
        self.batch = write_json(self.root / "batch.json", {"fixture_only": True})

    @staticmethod
    def inventory():
        return {"canvas_px": {"w": 320, "h": 180}, "text_blocks": [], "suppressed_text": [],
                "regions": [{"id": "synthetic-region", "kind_hint": "flat_shape",
                             "bbox_px": {"x": 10.9, "y": 20.4, "w": 9.2, "h": 7.1}}],
                "notes": ["Invented input; not an executed detector"]}

    def build(self, inventory):
        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
        self.inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
        return vector._build_slide_record(
            root=self.root, source=self.source, inventory_path=self.inventory_path,
            inventory=inventory, request_row={"slide_number": 1, "slide_id": "invented",
                                             "request_id": "invented-request"},
            backend="tesseract", deep=False, command=["synthetic-fixture"],
            stdout="", stderr="", batch_job_path=self.batch)

    def test_integral_measurements_preserve_integer_contract(self):
        expected = {"x": 10, "y": 20, "w": 9, "h": 7}
        for box in (expected, {k: float(v) for k, v in expected.items()}):
            result = vector._validated_bbox(box, 320, 180, "invented")
            self.assertEqual(result, expected)
            self.assertTrue(all(type(v) is int for v in result.values()))

    def test_fractional_region_uses_edge_floor_and_ceil(self):
        box = self.inventory()["regions"][0]["bbox_px"]
        before = copy.deepcopy(box)
        self.assertEqual(vector._validated_bbox(box, 320, 180, "invented"),
                         {"x": 10, "y": 20, "w": 11, "h": 8})
        self.assertEqual(box, before)

    def test_positive_subpixel_region_is_not_truncated_to_zero(self):
        self.assertEqual(vector._validated_bbox({"x": .1, "y": .2, "w": .2, "h": .3}, 320, 180, "tiny"),
                         {"x": 0, "y": 0, "w": 1, "h": 1})

    def test_invalid_original_coordinates_fail_before_integer_conversion(self):
        bad = (("x", -.1), ("y", -.2), ("w", 0), ("h", -.1), ("x", "10"),
               ("y", "20.2"), ("w", True), ("x", False), ("x", None),
               ("x", float("nan")), ("y", float("inf")), ("w", float("-inf")),
               ("x", 10 ** 1000), ("w", 10 ** 1000))
        for key, value in bad:
            with self.subTest(key=key, value=value):
                box = {"x": 10, "y": 20, "w": 9, "h": 7}; box[key] = value
                with self.assertRaises(DeckCompilerError):
                    vector._validated_bbox(box, 320, 180, "invalid")

    def test_unchanged_integer_region_preserves_supplied_normalization(self):
        inventory = self.inventory()
        inventory["regions"][0].update(kind_hint="photo", bbox_px={"x": 10, "y": 20, "w": 9, "h": 7},
                                      bbox_norm={"x": 10 / 320, "y": 20 / 180, "w": 9 / 320, "h": 7 / 180})
        original = copy.deepcopy(inventory)
        row = self.build(inventory)["regions"][0]
        self.assertEqual(row["bbox_px"], original["regions"][0]["bbox_px"])
        self.assertEqual(row["bbox_norm"], original["regions"][0]["bbox_norm"])
        self.assertEqual(inventory, original)

    def test_float_sum_cannot_hide_original_canvas_escape(self):
        x = math.nextafter(1.0, math.inf)
        self.assertEqual(x + 319, 320)
        with self.assertRaises(DeckCompilerError):
            vector._validated_bbox({"x": x, "y": 1, "w": 319, "h": 1}, 320, 180, "outside")

    def test_malformed_boxes_fail_with_domain_error(self):
        for value in (None, [], "box", {}, {"x": 10, "y": 20, "w": 9}):
            with self.subTest(value=value), self.assertRaises(DeckCompilerError):
                vector._validated_bbox(value, 320, 180, "malformed")

    def test_fractional_canvas_escape_is_not_hidden_by_truncation(self):
        for box in ({"x": 319.9, "y": 1, "w": .2, "h": 1},
                    {"x": 1, "y": 179.9, "w": 1, "h": .2}):
            with self.subTest(box=box), self.assertRaises(DeckCompilerError):
                vector._validated_bbox(box, 320, 180, "outside")

    def test_enclosure_does_not_lose_a_float_sum_rounded_to_integer(self):
        x = math.nextafter(1.0, 0.0)
        width = math.nextafter(2 ** -53, math.inf)
        self.assertEqual(x + width, 1.0)  # ordinary float addition loses a real edge remainder
        self.assertGreater(Fraction(x) + Fraction(width), 1)
        result = vector._validated_bbox({"x": x, "y": 1, "w": width, "h": 1}, 320, 180, "edge")
        self.assertEqual(result, {"x": 0, "y": 1, "w": 2, "h": 1})

    def test_actual_region_overlap_cannot_disappear_during_build(self):
        for collection in ("text_blocks", "suppressed_text"):
            with self.subTest(collection=collection):
                inventory = self.inventory()
                inventory[collection] = [{"id": "protected", "bbox_px": {"x": 19.5, "y": 22, "w": 2, "h": 2}}]
                before = copy.deepcopy(inventory)
                with patch.object(vector, "trace_png_to_svg", return_value={"status": "rejected"}) as trace:
                    record = self.build(inventory)
                trace.assert_not_called()
                row = record["regions"][0]
                self.assertEqual(row["disposition"], "native_rebuild_text_protected")
                self.assertEqual(row["semantic_text_overlap_ids"], ["protected"])
                self.assertEqual(row["bbox_px"], {"x": 10, "y": 20, "w": 11, "h": 8})
                self.assertEqual(inventory, before)
                self.assertEqual(read_json(self.inventory_path), before)

    def test_pixels_added_by_enclosure_are_also_text_protected(self):
        inventory = self.inventory()
        inventory["text_blocks"] = [{"id": "margin-text", "bbox_px": {"x": 10.1, "y": 22, "w": .2, "h": 2}}]
        with patch.object(vector, "trace_png_to_svg") as trace:
            row = self.build(inventory)["regions"][0]
        trace.assert_not_called()
        self.assertEqual(row["semantic_text_overlap_ids"], ["margin-text"])

    def test_generated_crop_matches_recorded_enclosure(self):
        inventory = self.inventory()
        inventory["regions"][0]["bbox_norm"] = {"x": .9, "y": .9, "w": .1, "h": .1}
        before = copy.deepcopy(inventory)
        with patch.object(vector, "trace_png_to_svg", return_value={"status": "rejected", "reason": "sentinel"}) as trace:
            row = self.build(inventory)["regions"][0]
        trace.assert_called_once()
        with Image.open(self.root / row["candidate_png"]["path"]) as crop:
            self.assertEqual(crop.size, (11, 8))
        self.assertEqual(row["bbox_norm"], vector._norm_bbox(row["bbox_px"], 320, 180))
        self.assertEqual(row["area_ratio"], round(88 / (320 * 180), 8))
        self.assertEqual(inventory, before)

    def test_conservative_enclosure_cannot_evade_area_budget(self):
        inventory = self.inventory()
        inventory["regions"][0]["bbox_px"] = {"x": .1, "y": .1, "w": 112.1, "h": 179}
        with patch.object(vector, "trace_png_to_svg") as trace:
            row = self.build(inventory)["regions"][0]
        trace.assert_not_called()
        self.assertGreater(row["area_ratio"], vector.MAX_VECTOR_REGION_AREA_RATIO)
        self.assertEqual(row["disposition"], "native_rebuild_large_region")

    def test_generation_invalid_region_fails_before_trace(self):
        for value in (-.1, "10", False, float("inf")):
            with self.subTest(value=value):
                inventory = self.inventory(); inventory["regions"][0]["bbox_px"]["x"] = value
                with patch.object(vector, "trace_png_to_svg", return_value={"status": "rejected"}) as trace:
                    with self.assertRaises(DeckCompilerError):
                        self.build(inventory)
                trace.assert_not_called()

    def test_region_validator_detects_fractional_text_overlap(self):
        row = {"region_id": "invented", "kind_hint": "flat_shape",
               "bbox_px": {"x": 10.9, "y": 20.4, "w": 9.2, "h": 7.1},
               "area_ratio": round(88 / (320 * 180), 8),
               "semantic_text_overlap_ids": [], "disposition": "bounded_svg_asset"}
        issues = []
        vector._validate_region(self.root, row, 320, 180,
                                [{"id": "protected", "bbox_px": {"x": 19.5, "y": 22, "w": 2, "h": 2}}], "slide", issues)
        self.assertTrue(any("vectorizes semantic text" in issue for issue in issues), issues)

    def test_region_validator_converts_bad_bbox_to_issue(self):
        for value in (-.1, "10", False, float("inf")):
            with self.subTest(value=value):
                issues = []
                vector._validate_region(self.root, {"region_id": "invented", "bbox_px": {"x": value, "y": 1, "w": 2, "h": 2}},
                                        320, 180, [], "slide", issues)
                self.assertTrue(any("bbox" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
