from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.external_execution.openai_adapter import OpenAIAdapterSkeleton
from presentation_agent.deckcompiler.orchestration.phase3_runner import run_phase3
from presentation_agent.deckcompiler.schemas import REPO_ROOT, validator_for
from presentation_agent.deckcompiler.validation import validate_run_directory
from presentation_agent.deckcompiler.visuals.preparation import (
    prepare_visuals,
    validate_semantic_sidecar,
    validate_visual_preparation,
)


DEMO_CONFIG = REPO_ROOT / "examples" / "deckcompiler_demo" / "demo.yaml"
PHASE2_FIXTURE = REPO_ROOT / "examples" / "deckcompiler_demo" / "fixtures" / "contracts" / "valid_run"


class Phase4VisualPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(prefix="deckcompiler-phase4b-tests-")
        cls.root = Path(cls._temporary.name)
        cls.phase3_run = cls.root / "phase3"
        run_phase3(DEMO_CONFIG, cls.phase3_run)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def _prepare(self, name: str):
        return prepare_visuals(self.phase3_run, self.root / name)

    def _mutated_phase3(self, name: str) -> Path:
        target = self.root / name
        shutil.copytree(self.phase3_run, target)
        return target

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_invalid_phase3_run_is_rejected(self) -> None:
        invalid = self.root / "invalid-empty"
        invalid.mkdir()
        with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_INPUT_INVALID"):
            prepare_visuals(invalid, self.root / "invalid-empty-output")

    def test_source_commit_mismatch_is_rejected(self) -> None:
        mutated = self._mutated_phase3("phase3-wrong-commit")
        manifest_path = mutated / "deckcompiler_run_manifest.json"
        manifest = self._read(manifest_path)
        manifest["source_commit"] = "0" * 40
        self._write(manifest_path, manifest)
        with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_SOURCE_COMMIT_MISMATCH"):
            prepare_visuals(mutated, self.root / "wrong-commit-output")

    def test_slide_count_other_than_six_is_rejected(self) -> None:
        mutated = self._mutated_phase3("phase3-five-slides")
        blueprints_path = mutated / "slide_blueprint_collection.json"
        blueprints = self._read(blueprints_path)
        blueprints["slides"] = blueprints["slides"][:-1]
        self._write(blueprints_path, blueprints)
        with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_SLIDE_COUNT"):
            prepare_visuals(mutated, self.root / "five-slides-output")

    def test_slide_order_mismatch_is_rejected(self) -> None:
        mutated = self._mutated_phase3("phase3-wrong-order")
        blueprints_path = mutated / "slide_blueprint_collection.json"
        blueprints = self._read(blueprints_path)
        blueprints["slides"][0], blueprints["slides"][1] = blueprints["slides"][1], blueprints["slides"][0]
        self._write(blueprints_path, blueprints)
        with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_SLIDE_ORDER"):
            prepare_visuals(mutated, self.root / "wrong-order-output")

    def test_exactly_six_sidecars_are_created(self) -> None:
        result = self._prepare("six-sidecars")
        self.assertEqual(len(result.sidecar_paths), 6)
        self.assertEqual(len(list((result.output_dir / "preparation" / "semantic_sidecars").glob("*.semantic.json"))), 6)

    def test_sidecar_ids_are_unique(self) -> None:
        result = self._prepare("unique-sidecars")
        sidecars = [self._read(path) for path in result.sidecar_paths]
        ids = [item["sidecar_id"] for item in sidecars]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_factual_content_item_is_evidence_bound(self) -> None:
        result = self._prepare("evidence-bound")
        for path in result.sidecar_paths:
            sidecar = self._read(path)
            bound = {binding["element"] for binding in sidecar["sidecar"]["source_bindings"]}
            factual = set(sidecar["phase4_metadata"]["factual_content_item_ids"])
            self.assertTrue(factual)
            self.assertTrue(factual <= bound)

    def test_unknown_evidence_id_is_rejected(self) -> None:
        result = self._prepare("unknown-evidence")
        sidecar = self._read(result.sidecar_paths[0])
        sidecar["sidecar"]["source_bindings"][0]["evidence_ids"] = ["ev_unknown"]
        with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_UNKNOWN_EVIDENCE"):
            validate_semantic_sidecar(sidecar, result.evidence_ids)

    def test_native_raster_overlap_is_rejected(self) -> None:
        result = self._prepare("native-raster-overlap")
        sidecar = self._read(result.sidecar_paths[0])
        sidecar["sidecar"]["raster_allowed"][0]["slot_id"] = sidecar["sidecar"]["native_required"][0]["slot_id"]
        with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_NATIVE_RASTER_OVERLAP"):
            validate_semantic_sidecar(sidecar, result.evidence_ids)

    def test_full_slide_raster_slot_is_rejected(self) -> None:
        result = self._prepare("full-slide-raster")
        sidecar = self._read(result.sidecar_paths[0])
        sidecar["sidecar"]["raster_allowed"].append(
            {"slot_id": "full_slide_background", "usage": "replaceable_image_frame"}
        )
        with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_FULL_SLIDE_RASTER"):
            validate_semantic_sidecar(sidecar, result.evidence_ids)

    def test_ocr_canonical_text_is_rejected(self) -> None:
        result = self._prepare("ocr-canonical")
        sidecar = self._read(result.sidecar_paths[0])
        sidecar["phase4_metadata"]["ocr_canonical_text_forbidden"] = False
        with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_OCR_CANONICAL_TEXT"):
            validate_semantic_sidecar(sidecar, result.evidence_ids)

    def test_target_sidecar_relation_is_one_to_one(self) -> None:
        result = self._prepare("target-sidecar-pairing")
        manifest = self._read(result.pending_manifest_path)
        sidecars = [self._read(path) for path in result.sidecar_paths]
        expected = {item["expected_visual_target_id"]: item["sidecar_id"] for item in sidecars}
        actual = {item["visual_target_id"]: item["expected_sidecar_id"] for item in manifest["targets"]}
        self.assertEqual(actual, expected)

    def test_visual_dna_validates(self) -> None:
        result = self._prepare("visual-dna-schema")
        errors = list(validator_for("visual_dna").iter_errors(self._read(result.visual_dna_path)))
        self.assertEqual(errors, [])

    def test_design_system_validates(self) -> None:
        result = self._prepare("design-system-schema")
        errors = list(validator_for("phase4_design_system").iter_errors(self._read(result.design_system_path)))
        self.assertEqual(errors, [])

    def test_editable_template_spec_validates(self) -> None:
        result = self._prepare("template-spec-schema")
        errors = list(
            validator_for("phase4_editable_template_spec").iter_errors(self._read(result.editable_template_spec_path))
        )
        self.assertEqual(errors, [])

    def test_all_required_slots_are_available(self) -> None:
        result = self._prepare("required-slots")
        spec = self._read(result.editable_template_spec_path)
        layouts = {item["layout_id"]: {slot["slot_id"] for slot in item["slots"]} for item in spec["template_spec"]["layouts"]}
        for assignment in spec["planning_contract"]["slide_layout_assignments"]:
            self.assertTrue(set(assignment["required_slot_ids"]) <= layouts[assignment["layout_id"]])

    def test_canvas_is_exact_sixteen_by_nine(self) -> None:
        result = self._prepare("canvas-ratio")
        spec = self._read(result.editable_template_spec_path)
        canvas = spec["template_spec"]["canvas"]
        self.assertEqual(canvas["aspect_ratio"], "16:9")
        self.assertEqual(canvas["width_in"] * 9, canvas["height_in"] * 16)

    def test_exactly_thirteen_prompt_artifacts_are_created(self) -> None:
        result = self._prepare("prompt-count")
        self.assertEqual(len(result.prompt_paths), 13)
        self.assertEqual(len(list((result.output_dir / "preparation" / "prompts").glob("*.prompt.json"))), 13)

    def test_prompt_artifacts_are_deterministic(self) -> None:
        first = self._prepare("prompt-determinism-a")
        second = self._prepare("prompt-determinism-b")
        first_payloads = [self._read(path) for path in first.prompt_paths]
        second_payloads = [self._read(path) for path in second.prompt_paths]
        self.assertEqual(first_payloads, second_payloads)

    def test_prompt_hashes_are_stable_and_valid(self) -> None:
        result = self._prepare("prompt-hashes")
        report = validate_visual_preparation(result.output_dir)
        self.assertTrue(report.valid, report.issues)
        self.assertEqual(report.checks["prompt_hash_mismatch_count"], 0)

    def test_reference_prompts_contain_no_final_factual_copy(self) -> None:
        result = self._prepare("reference-prompt-policy")
        blueprints = self._read(self.phase3_run / "slide_blueprint_collection.json")
        facts = [block["content"] for slide in blueprints["slides"] for block in slide["content_blocks"]]
        for path in result.prompt_paths[:7]:
            prompt_text = self._read(path)["prompt_text"]
            self.assertFalse(any(fact in prompt_text for fact in facts))

    def test_slide_prompts_consume_sidecars(self) -> None:
        result = self._prepare("slide-prompt-sidecars")
        slide_prompts = [self._read(path) for path in result.prompt_paths if path.name.startswith("slide-")]
        self.assertEqual(len(slide_prompts), 6)
        self.assertTrue(all(item["semantic_sidecar_reference"] is not None for item in slide_prompts))

    def test_pending_manifest_contains_exactly_six_targets(self) -> None:
        result = self._prepare("pending-targets")
        manifest = self._read(result.pending_manifest_path)
        self.assertEqual(len(manifest["targets"]), 6)

    def test_pending_targets_have_no_actual_generation(self) -> None:
        result = self._prepare("pending-generation-false")
        manifest = self._read(result.pending_manifest_path)
        self.assertTrue(all(item["generation_status"] == "PENDING" for item in manifest["targets"]))
        self.assertTrue(all(item["actual_generation"] is False and item["selected"] is False for item in manifest["targets"]))

    def test_platform_tool_call_count_is_zero(self) -> None:
        result = self._prepare("platform-call-zero")
        report = self._read(result.validation_report_path)
        self.assertEqual(report["execution_counts"]["platform_tool_invocations"], 0)

    def test_external_transport_call_count_is_zero(self) -> None:
        result = self._prepare("external-call-zero")
        report = self._read(result.validation_report_path)
        self.assertEqual(report["execution_counts"]["external_provider_transport_calls"], 0)
        self.assertEqual(report["execution_counts"]["repository_network_calls"], 0)
        self.assertEqual(report["execution_counts"]["credential_lookups"], 0)

    def test_output_root_must_be_outside_repository(self) -> None:
        with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_OUTPUT_PROTECTED"):
            prepare_visuals(self.phase3_run, REPO_ROOT / "analysis_runs" / "phase4-forbidden")

    def test_protected_output_paths_are_rejected(self) -> None:
        for name in (
            "editable_template_spec.final.json",
            "golden_template_masters.pptx",
            "final_deck_large_premium.pptx",
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(DeckCompilerError, "DC_PHASE4B_OUTPUT_PROTECTED"):
                    prepare_visuals(self.phase3_run, REPO_ROOT / "outputs" / name)

    def test_phase4a_adapter_remains_transport_disabled(self) -> None:
        adapter = OpenAIAdapterSkeleton()
        self.assertFalse(adapter.enabled)
        self.assertEqual(adapter.adapter_id, "deckcompiler-openai-disabled-v1")

    def test_phase2_and_phase3_regressions_remain_valid(self) -> None:
        self.assertTrue(validate_run_directory(PHASE2_FIXTURE).valid)
        report = self._read(self.phase3_run / "phase3_validation_report.json")
        self.assertEqual(report["verdict"], "GO")
        self.assertEqual(len(self._read(self.phase3_run / "artifact_graph.json")["orphan_artifact_ids"]), 0)

    def test_platform_contract_schemas_are_registered(self) -> None:
        for schema_name in (
            "platform_image_capability_attestation",
            "platform_image_request",
            "platform_image_execution_record",
            "platform_image_verification_report",
            "platform_image_visual_review",
            "phase4_visual_bundle_acceptance",
            "phase4_pending_visual_target_manifest",
        ):
            with self.subTest(schema_name=schema_name):
                self.assertIsNotNone(validator_for(schema_name))


if __name__ == "__main__":
    unittest.main()
