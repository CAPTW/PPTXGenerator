from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from PIL import Image

from presentation_agent.deckcompiler.platform_image_execution.contracts import verify_hash_bound_payload
from presentation_agent.deckcompiler.schemas import REPO_ROOT, validator_for


ROOT = REPO_ROOT / "examples" / "deckcompiler_demo" / "phase4"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class Phase4VisualBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = _read(ROOT / "visual_target_manifest.json")
        cls.provenance = _read(ROOT / "generation_provenance.json")
        cls.history = _read(ROOT / "regeneration_history.json")
        cls.geometry = _read(ROOT / "geometry_fit_report.json")
        cls.validation = _read(ROOT / "phase4_validation_report.json")
        cls.acceptance = _read(ROOT / "phase4_bundle_acceptance.json")
        cls.input_provenance = _read(ROOT / "input_provenance.json")
        cls.sidecars = [_read(path) for path in sorted((ROOT / "semantic_sidecars").glob("*.semantic.json"))]
        cls.prompts = [_read(path) for path in sorted((ROOT / "prompts").glob("*.prompt.json"))]
        cls.records = [_read(path) for path in sorted((ROOT / "records" / "execution").glob("*.json"))]
        cls.reviews = [_read(path) for path in sorted((ROOT / "records" / "visual_review").glob("*.json"))]
        cls.images = sorted((ROOT / "references").glob("*.png")) + sorted((ROOT / "visual_targets").glob("*.png"))

    def test_01_design_board_count(self) -> None:
        self.assertEqual(len(list((ROOT / "references").glob("design_board.png"))), 1)

    def test_02_module_anchor_count(self) -> None:
        self.assertEqual(len(list((ROOT / "references").glob("module-*-anchor.png"))), 3)

    def test_03_batch_reference_count(self) -> None:
        self.assertEqual(len(list((ROOT / "references").glob("batch-*-template-reference.png"))), 3)

    def test_04_slide_target_count(self) -> None:
        self.assertEqual(len(list((ROOT / "visual_targets").glob("slide-*.png"))), 6)

    def test_05_total_selected_image_count(self) -> None:
        self.assertEqual(len(self.images), 13)

    def test_06_all_selected_files_exist(self) -> None:
        self.assertTrue(all(path.is_file() for path in self.images))

    def test_07_all_selected_images_are_exact_16_by_9(self) -> None:
        for path in self.images:
            with Image.open(path) as image:
                self.assertEqual(image.width * 9, image.height * 16, path)

    def test_08_all_selected_images_meet_minimum_resolution(self) -> None:
        for path in self.images:
            with Image.open(path) as image:
                self.assertGreaterEqual(image.width, 1600, path)
                self.assertGreaterEqual(image.height, 900, path)

    def test_09_all_selected_images_are_valid_png(self) -> None:
        for path in self.images:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                self.assertEqual(image.format, "PNG", path)

    def test_10_all_selected_file_hashes_match(self) -> None:
        by_path = {item["path"]: item["sha256"] for item in self.provenance["selected_artifacts"]}
        for path in self.images:
            relative = path.relative_to(ROOT).as_posix()
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), by_path[relative], path)

    def test_11_all_selected_records_are_actual_generation(self) -> None:
        selected = [record for record in self.records if record["output"]["selected"]]
        self.assertEqual(len(selected), 13)
        self.assertTrue(all(record["actual_generation"] for record in selected))

    def test_12_selected_attempt_is_unique_per_target(self) -> None:
        selected = [record for record in self.records if record["output"]["selected"]]
        self.assertEqual(len({record["target_artifact_id"] for record in selected}), 13)
        self.assertEqual(len({record["attempt_id"] for record in selected}), 13)

    def test_13_rejected_binaries_are_not_curated(self) -> None:
        rejected_hashes = {item["output_hash"] for item in self.history["attempts"] if item["rejected"]}
        curated_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in self.images}
        self.assertTrue(rejected_hashes.isdisjoint(curated_hashes))

    def test_14_semantic_sidecar_count(self) -> None:
        self.assertEqual(len(self.sidecars), 6)

    def test_15_semantic_sidecar_ids_are_unique(self) -> None:
        self.assertEqual(len({item["sidecar_id"] for item in self.sidecars}), 6)

    def test_16_sidecar_target_relation_is_one_to_one(self) -> None:
        targets = {item["visual_target_id"] for item in self.manifest["targets"]}
        self.assertEqual({item["expected_visual_target_id"] for item in self.sidecars}, targets)

    def test_17_evidence_bindings_resolve(self) -> None:
        evidence = set(_read(ROOT / "input_provenance.json")["evidence_unit_ids"])
        for sidecar in self.sidecars:
            self.assertTrue(set(sidecar["phase4_metadata"]["evidence_unit_bindings"]).issubset(evidence))

    def test_18_native_raster_overlap_is_zero(self) -> None:
        for sidecar in self.sidecars:
            native = set(sidecar["phase4_metadata"]["native_required_slot_ids"])
            raster = set(sidecar["phase4_metadata"]["raster_allowed_slot_ids"])
            self.assertFalse(native & raster)

    def test_19_full_slide_raster_slot_count_is_zero(self) -> None:
        for sidecar in self.sidecars:
            self.assertNotIn("full_slide", sidecar["phase4_metadata"]["raster_allowed_slot_ids"])

    def test_20_ocr_canonical_text_is_forbidden(self) -> None:
        self.assertTrue(all(item["phase4_metadata"]["ocr_canonical_text_forbidden"] for item in self.sidecars))

    def test_21_layout_repetition_violation_is_zero(self) -> None:
        self.assertEqual(self.geometry["layout_repetition_violation_count"], 0)
        self.assertEqual(self.geometry["unique_layout_count"], 6)

    def test_22_module_differentiation_passes(self) -> None:
        self.assertEqual(self.geometry["module_differentiation_status"], "PASS")

    def test_23_batch_reference_linkage_passes(self) -> None:
        batch_ids = {prompt["batch_id"]: prompt["target_artifact_id"] for prompt in self.prompts if prompt["artifact_type"] == "batch_template_reference"}
        for target in self.manifest["targets"]:
            self.assertIn(batch_ids[target["batch_id"]], target["reference_ids"])

    def test_24_slide_prompts_consume_sidecars(self) -> None:
        slide_prompts = [prompt for prompt in self.prompts if prompt["artifact_type"] == "slide_visual_target"]
        self.assertEqual(len(slide_prompts), 6)
        self.assertTrue(all(prompt["semantic_sidecar_reference"] for prompt in slide_prompts))

    def test_25_reference_prompts_contain_no_final_facts(self) -> None:
        reference_prompts = [prompt for prompt in self.prompts if prompt["artifact_type"] != "slide_visual_target"]
        for prompt in reference_prompts:
            self.assertNotIn("AI Data", prompt["prompt_text"])
            self.assertNotRegex(prompt["prompt_text"], r"ev_[0-9a-f]{20}")

    def test_26_invented_citation_count_is_zero(self) -> None:
        selected_reviews = [review for review in self.reviews if review["selected"]]
        self.assertFalse(any("citation" in " ".join(review["findings"]).lower() for review in selected_reviews))

    def test_27_invented_number_count_is_zero(self) -> None:
        selected_reviews = [review for review in self.reviews if review["selected"]]
        for review in selected_reviews:
            checks = review["checks"]
            self.assertTrue(checks.get("no_numeric_glyphs", checks.get("no_invented_number", False)))

    def test_28_curated_paths_are_relative(self) -> None:
        for target in self.manifest["targets"]:
            for field in ("image_relative_path", "normalized_path", "original_runtime_path_reference"):
                self.assertFalse(Path(target[field]).is_absolute())

    def test_29_temp_paths_are_absent(self) -> None:
        text = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.rglob("*.json"))
        self.assertNotRegex(text, re.compile(r"[A-Za-z]:\\Users\\", re.I))
        self.assertNotRegex(text, re.compile(r"AppData[/\\]Local[/\\]Temp", re.I))

    def test_30_external_transport_calls_are_zero(self) -> None:
        self.assertEqual(self.provenance["external_transport_call_count"], 0)
        self.assertTrue(all(record["external_transport_used"] is False for record in self.records))

    def test_31_credential_lookups_are_zero(self) -> None:
        self.assertEqual(self.provenance["credential_lookup_count"], 0)
        self.assertTrue(all(record["credential_lookups"] == 0 for record in self.records))

    def test_32_phase4a_contract_remains_blocked_only(self) -> None:
        schema = _read(REPO_ROOT / "schemas" / "deckcompiler" / "external-execution-acceptance.schema.json")
        self.assertEqual(schema["properties"]["status"]["const"], "BLOCKED")

    def test_33_pngtopptx_was_not_used(self) -> None:
        self.assertFalse(self.provenance["pngtopptx_used"])

    def test_34_pptx_count_is_zero(self) -> None:
        self.assertEqual(len(list(ROOT.rglob("*.pptx"))), 0)

    def test_35_html_count_is_zero(self) -> None:
        self.assertEqual(len(list(ROOT.rglob("*.html"))), 0)

    def test_36_removed_skill_reference_is_zero_in_active_bundle(self) -> None:
        active_text = "\n".join(path.read_text(encoding="utf-8") for path in [*ROOT.rglob("*.json"), *ROOT.rglob("*.md")])
        self.assertNotIn("image-to-editable-ppt-template", active_text)

    def test_37_phase2_regression_passes(self) -> None:
        self.assertEqual(self.validation["phase2_result"], "VALID")

    def test_38_phase3_regression_passes(self) -> None:
        self.assertEqual(self.validation["phase3_result"], "GO")

    def test_39_phase4a_regression_passes(self) -> None:
        self.assertEqual(self.validation["phase4a_result"], "31 passed, 80 subtests passed")

    def test_40_binary_checkout_result_passes(self) -> None:
        self.assertEqual(self.validation["binary_result"], "3 passed; selected PNG raw blobs match staged bytes")

    def test_41_curated_file_sizes_pass(self) -> None:
        sizes = [path.stat().st_size for path in self.images]
        self.assertTrue(all(size < 15 * 1024 * 1024 for size in sizes))
        self.assertLess(sum(sizes), 150 * 1024 * 1024)

    def test_42_bundle_acceptance_is_valid(self) -> None:
        artifacts = (
            (self.input_provenance, "phase4_input_provenance", None),
            (self.manifest, "phase4_visual_target_manifest", "manifest_hash"),
            (self.provenance, "phase4_generation_provenance", "provenance_hash"),
            (self.history, "phase4_regeneration_history", "history_hash"),
            (self.geometry, "phase4_geometry_fit_report", "report_hash"),
            (self.validation, "phase4_validation_report", "report_hash"),
            (self.acceptance, "phase4_visual_bundle_acceptance", "acceptance_hash"),
        )
        for payload, schema_name, hash_field in artifacts:
            self.assertEqual(list(validator_for(schema_name).iter_errors(payload)), [])
            if hash_field:
                self.assertTrue(verify_hash_bound_payload(payload, hash_field))
        self.assertEqual(self.acceptance["bundle_status"], "ELIGIBLE_FOR_PNGTOPPTX_HANDOFF")
        self.assertTrue(self.acceptance["phase4_accepted"])
        self.assertFalse(self.acceptance["final_release_eligible"])


if __name__ == "__main__":
    unittest.main()
