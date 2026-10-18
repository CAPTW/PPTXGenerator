"""Invented VSC contract fixtures; no retained user pixels, text, or geometry.

These tests synthesize evidence to exercise validation. No detector, independent
visual review, user approval, renderer, or quality-acceptance stage is executed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration.semantic_geometry_binding import bind_semantic_geometry


class VscObservationClosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "work"
        self.association_path = self.work / "semantic_geometry_associations.json"
        self.review_path = self.root / "fixture-review.json"
        source = Image.new("RGB", (80, 45), (24, 36, 48))
        canvas = source.resize((2880, 1620), Image.Resampling.LANCZOS)
        source_path = self.root / "synthetic-source.png"
        canvas_path = self.root / "synthetic-canvas.png"
        crop_path = self.root / "synthetic-crop.png"
        source.save(source_path)
        canvas.save(canvas_path)
        canvas.crop((140, 140, 868, 292)).save(crop_path)
        source_ref = {**self.artifact(source_path), "width": 80, "height": 45}
        canvas_ref = self.artifact(canvas_path)
        sidecar_ref = self.write_artifact("sidecar.json", {
            "schema_name": "codex_semantic_sidecar", "schema_version": "1.1.0",
            "workflow_id": "synthetic-workflow", "slide_number": 1,
            "slide_id": "synthetic-slide", "request_id": "synthetic-request",
            "exact_title": "Approved synthetic title",
            "exact_on_slide_copy": {"detail": "Approved synthetic detail"},
        })
        measurement_ref = self.write_artifact("measurements.json", {
            "canvas_px": {"w": 80, "h": 45}, "regions": [],
            "text_blocks": [
                {"id": "native-a", "bbox_px": {"x": 4, "y": 4, "w": 20, "h": 4}},
                {"id": "native-b", "bbox_px": {"x": 4, "y": 20, "w": 28, "h": 5}},
                {"id": "native-unbound", "bbox_px": {"x": 65, "y": 35, "w": 8, "h": 4}},
            ],
        })
        receipt_ref = self.write_artifact("canvas-receipt.json", {
            "version": 1, "capability": "ordinary_rgb_canvas_preparation_v1",
            "source": {"file_sha256": source_ref["sha256"], "size_px": list(source.size),
                       "rgb_sha256": hashlib.sha256(source.tobytes()).hexdigest()},
            "canvas": {"file_sha256": canvas_ref["sha256"], "size_px": list(canvas.size),
                       "rgb_sha256": hashlib.sha256(canvas.tobytes()).hexdigest()},
            "transform": {"policy": "contain", "padding_ltrb": [0, 0, 0, 0],
                          "resized_px": [2880, 1620],
                          "scale_x": {"numerator": 36, "denominator": 1},
                          "scale_y": {"numerator": 36, "denominator": 1},
                          "edge_mapping": "canvas_edge = source_edge * effective_axis_scale + leading_padding"},
        })
        observations, blocks, links = [], [], []
        for suffix, box, text, pointer in (
            ("a", {"x": 140, "y": 140, "w": 728, "h": 152}, "Observed alpha", "/exact_title"),
            ("b", {"x": 140, "y": 716, "w": 1016, "h": 188}, "Observed beta", "/exact_on_slide_copy/detail"),
        ):
            identities = {"block_id": "block-" + suffix, "observation_id": "observation-" + suffix,
                          "region_id": "region-" + suffix}
            x, y, w, h = (box[k] for k in ("x", "y", "w", "h"))
            observations.append({**identities, "raw": {"text": text},
                                 "polygon_canvas_px": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                                 "sampling_bbox_px": copy.deepcopy(box)})
            blocks.append({"id": identities["block_id"], "text": text, "text_raw": text,
                           "bbox_px": copy.deepcopy(box), "members": [
                               {"observation_id": identities["observation_id"], "text": text,
                                "bbox_px": copy.deepcopy(box)}]})
            links.append({**identities, "content_pointer": pointer, "measurement_collection": "text_blocks",
                          "measurement_id": "native-" + suffix,
                          "visual_reason": "Invented contract evidence; no visual review was performed."})
        inventory_ref = self.write_artifact("vsc-inventory.json", {
            "version": 1, "capability": "reviewed_observations_core_inventory_v1",
            "source": {"canvas_px": {"w": 2880, "h": 1620},
                       "canvas_rgb_sha256": hashlib.sha256(canvas.tobytes()).hexdigest(),
                       "source_sha256": source_ref["sha256"]},
            "inventory": {"canvas_px": {"w": 2880, "h": 1620}, "text_blocks": blocks},
            "block_observation_links": observations,
        })
        self.job = {"workflow_id": "synthetic-workflow", "slide_number": 1, "slide_id": "synthetic-slide",
                    "request_lineage": {"request_id": "synthetic-request"}, "source_png": source_ref,
                    "semantic_sidecar": sidecar_ref, "vector_preflight": {"measurement_inventory": measurement_ref}}
        self.review = {
            "status": "REVIEWED_IDENTITY_LINKS", "scope": "content_identity_only",
            "method": "independent_source_and_crop_visual_review", "reviewer": "Synthetic contract test",
            "source_png_sha256": source_ref["sha256"], "semantic_sidecar_sha256": sidecar_ref["sha256"],
            "measurement_inventory_sha256": measurement_ref["sha256"], "links": links,
            "artifacts": {"vsc_inventory": inventory_ref, "canvas_receipt": receipt_ref,
                          "canvas_png": canvas_ref, "reviewed_crops": [self.artifact(crop_path)]},
        }
        review_ref = self.write_artifact(self.review_path.name, self.review)
        self.association = {
            "workflow_id": self.job["workflow_id"], "slide_number": 1, "slide_id": self.job["slide_id"],
            "request_id": "synthetic-request", "source_png_sha256": source_ref["sha256"],
            "semantic_sidecar_sha256": sidecar_ref["sha256"], "measurement_inventory_sha256": measurement_ref["sha256"],
            "bindings": [{k: link[k] for k in ("content_pointer", "measurement_collection", "measurement_id")} for link in links],
            "vsc_identity_review": review_ref,
        }
        write_json(self.association_path, self.association)

    def artifact(self, path):
        return {"path": path.relative_to(self.root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def write_artifact(self, name, value):
        return self.artifact(write_json(self.root / name, value))

    def bind(self):
        return bind_semantic_geometry(self.root, self.job, self.work)

    def change_inventory(self, change):
        ref = self.review["artifacts"]["vsc_inventory"]
        path = self.root / ref["path"]
        inventory = read_json(path)
        change(inventory)
        # Adversarial external JSON may contain nonfinite numbers; keep them
        # here so the consumer, rather than our production writer, rejects it.
        path.write_text(json.dumps(inventory), encoding="utf-8")
        ref.update(self.artifact(path))
        write_json(self.review_path, self.review)
        self.association["vsc_identity_review"] = self.artifact(self.review_path)
        write_json(self.association_path, self.association)

    def assert_closure_rejected(self):
        with self.assertRaisesRegex(DeckCompilerError, "VSC .* (closure|sampling geometry)"):
            self.bind()

    def test_valid_singletons_preserve_canonical_text_and_geometry(self):
        inventory_path = self.root / self.job["vector_preflight"]["measurement_inventory"]["path"]
        before = inventory_path.read_bytes()
        result = self.bind()
        self.assertEqual([row["content_value"] for row in result["bindings"]],
                         ["Approved synthetic title", "Approved synthetic detail"])
        evidence = result["vsc_identity_evidence"]
        self.assertEqual(evidence["unbound_measured_text_ids"], ["native-unbound"])
        self.assertEqual(inventory_path.read_bytes(), before)
        self.assertFalse(evidence["authority"]["vsc_sampling_geometry_promoted"])

    def test_only_exact_supported_inventory_version_is_admitted(self):
        for version in (None, True, 2):
            with self.subTest(version=version):
                self.change_inventory(lambda inventory: inventory.update(version=version))
                with self.assertRaisesRegex(DeckCompilerError, "unsupported VSC inventory capability"):
                    self.bind()

    def test_malformed_member_is_a_domain_error(self):
        def change(inventory):
            inventory["inventory"]["text_blocks"][0]["members"] = ["not a member"]
        self.change_inventory(change)
        self.assert_closure_rejected()

    def test_changed_link_sampling_envelope_is_rejected_even_when_rehashed(self):
        def change(inventory):
            inventory["block_observation_links"][0]["sampling_bbox_px"]["x"] -= 1
            inventory["block_observation_links"][0]["sampling_bbox_px"]["w"] += 1
        self.change_inventory(change)
        self.assert_closure_rejected()

    def test_changed_block_sampling_box_is_rejected_even_when_rehashed(self):
        def change(inventory):
            inventory["inventory"]["text_blocks"][0]["bbox_px"]["x"] += 1
        self.change_inventory(change)
        self.assert_closure_rejected()

    def test_changed_member_sampling_box_is_rejected_even_when_rehashed(self):
        def change(inventory):
            inventory["inventory"]["text_blocks"][0]["members"][0]["bbox_px"]["x"] += 1
        self.change_inventory(change)
        self.assert_closure_rejected()

    def test_merged_observations_cannot_masquerade_as_single_observation(self):
        def change(inventory):
            first, second = inventory["inventory"]["text_blocks"]
            first["members"].append(copy.deepcopy(second["members"][0]))
        self.change_inventory(change)
        self.assert_closure_rejected()

    def test_duplicate_member_is_not_unique_identity_closure(self):
        def change(inventory):
            members = inventory["inventory"]["text_blocks"][0]["members"]
            members.append(copy.deepcopy(members[0]))
        self.change_inventory(change)
        self.assert_closure_rejected()

    def test_one_observation_cannot_be_reused_in_two_blocks(self):
        oid = self.review["links"][0]["observation_id"]
        self.review["links"][1]["observation_id"] = oid
        def change(inventory):
            inventory["block_observation_links"][1]["observation_id"] = oid
            inventory["inventory"]["text_blocks"][1]["members"][0]["observation_id"] = oid
        self.change_inventory(change)
        self.assert_closure_rejected()

    def test_coherently_enlarged_boxes_cannot_admit_swapped_measurements(self):
        for records in (self.review["links"], self.association["bindings"]):
            records[0]["measurement_id"], records[1]["measurement_id"] = records[1]["measurement_id"], records[0]["measurement_id"]
        def change(inventory):
            for observation, block in zip(inventory["block_observation_links"], inventory["inventory"]["text_blocks"]):
                box = {"x": 0, "y": 0, "w": 2880, "h": 1620}
                observation["sampling_bbox_px"] = copy.deepcopy(box)
                block["bbox_px"] = copy.deepcopy(box)
                block["members"][0]["bbox_px"] = copy.deepcopy(box)
        self.change_inventory(change)
        self.assert_closure_rejected()

    def test_fractional_quadrilateral_uses_floor_ceil_envelope(self):
        def change(inventory):
            inventory["block_observation_links"][0]["polygon_canvas_px"] = [
                [140.25, 140.5], [867.75, 140.25], [867.5, 291.75], [140.5, 291.5]]
        self.change_inventory(change)
        self.assertEqual(self.bind()["status"], "EXPLICIT_ASSOCIATIONS_BOUND")

    def test_malformed_and_nonfinite_polygon_coordinates_are_domain_errors(self):
        bad_values = (None, [], [[0, 1]], [[True, 140], [868, 140], [868, 292], [140, 292]],
                      [[float("nan"), 140], [868, 140], [868, 292], [140, 292]],
                      [[140, float("inf")], [868, 140], [868, 292], [140, 292]],
                      [[10 ** 1000, 140], [868, 140], [868, 292], [140, 292]],
                      [[-1, 140], [868, 140], [868, 292], [140, 292]],
                      [["140", 140], [868, 140], [868, 292], [140, 292]])
        for polygon in bad_values:
            with self.subTest(polygon=polygon):
                def change(inventory):
                    inventory["block_observation_links"][0]["polygon_canvas_px"] = polygon
                self.change_inventory(change)
                self.assert_closure_rejected()

    def test_internal_text_copies_require_exact_code_points(self):
        for location in ("block_text", "block_text_raw", "member", "observation"):
            with self.subTest(location=location):
                def change(inventory):
                    block = inventory["inventory"]["text_blocks"][0]
                    block["text"] = block["text_raw"] = block["members"][0]["text"] = "Observed alpha"
                    inventory["block_observation_links"][0]["raw"]["text"] = "Observed alpha"
                    if location == "block_text":
                        block["text"] = "Observed  alpha"
                    elif location == "block_text_raw":
                        block["text_raw"] = "Observed  alpha"
                    elif location == "member":
                        block["members"][0]["text"] = "Observed  alpha"
                    else:
                        inventory["block_observation_links"][0]["raw"]["text"] = "Observed  alpha"
                self.change_inventory(change)
                self.assert_closure_rejected()

    def test_block_and_observation_array_order_has_no_identity_authority(self):
        def change(inventory):
            inventory["inventory"]["text_blocks"].reverse()
            inventory["block_observation_links"].reverse()
        self.change_inventory(change)
        self.assertEqual([row["measurement_id"] for row in self.bind()["bindings"]], ["native-a", "native-b"])


if __name__ == "__main__":
    unittest.main()
