from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from presentation_agent.deckcompiler.cli import main as deckcompiler_main
from presentation_agent.deckcompiler.pngtopptx_handoff import (
    HandoffError,
    export_phase4_handoff,
    validate_handoff,
)
from presentation_agent.deckcompiler.pngtopptx_handoff.crop_contract import (
    validate_asset_manifest,
    validate_crop_plan,
)
from presentation_agent.deckcompiler.schemas import REPO_ROOT, validator_for


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


class PNGtoPPTXHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.phase4 = self.root / "phase4"
        self.pin = self.root / "pin.json"
        self.external = self.root / "external"
        self.profile = self.external / "slide-image-dual-render" / "styles" / "corporate-light.json"
        self.node_path = self.root / "node_modules"
        self.node_path.mkdir()
        for package in ("pptxgenjs", "sharp", "react", "react-dom", "react-icons"):
            (self.node_path / package).mkdir()
        self.profile.parent.mkdir(parents=True)
        _write_json(self.profile, {"id": "corporate-light"})
        for skill in (
            "slide-editable-deck-orchestrator",
            "slide-text-layer-inpaint",
            "slide-image-dual-render",
            "slide-visual-polish-qa",
        ):
            skill_root = self.external / skill
            skill_root.mkdir(parents=True, exist_ok=True)
            (skill_root / "SKILL.md").write_text(skill, encoding="utf-8")
        entrypoints = (
            self.external / "slide-editable-deck-orchestrator" / "scripts" / "plan_deck_workflow.js",
            self.external / "slide-image-dual-render" / "scripts" / "make_crops.py",
            self.external / "slide-image-dual-render" / "scripts" / "slide_pipeline.js",
            self.external / "slide-image-dual-render" / "scripts" / "final_gate.js",
            self.external / "slide-visual-polish-qa" / "scripts" / "enforce_visual_qa.js",
        )
        for entrypoint in entrypoints:
            entrypoint.parent.mkdir(parents=True, exist_ok=True)
            entrypoint.write_text("// fixture\n", encoding="utf-8")
        self._make_phase4_fixture()
        _write_json(
            self.pin,
            {
                "schema_name": "external_skillset_pin",
                "schema_version": "1.0.0",
                "pin_id": "pngpin_11111111111111111111",
                "pin_hash": "1" * 64,
                "combined_aggregate_sha256": "2" * 64,
                "expected_orchestrator": "slide-editable-deck-orchestrator",
                "execution_allowed": True,
                "installation_bundle_verified": True,
                "external_skill_modified": False,
                "validation_status": "PASS",
            },
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _make_phase4_fixture(self) -> None:
        targets = []
        for number in range(1, 7):
            image = self.phase4 / "visual_targets" / f"slide-{number:03d}.png"
            image.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (1664, 936), (245 - number, 246, 248)).save(image)
            target_id = f"visualtarget_{number:020d}"
            sidecar_id = f"sidecar_{number:020d}"
            slide_id = f"slide-{number:02d}-fixture"
            targets.append(
                {
                    "slide_id": slide_id,
                    "visual_target_id": target_id,
                    "sidecar_id": sidecar_id,
                    "image_relative_path": f"visual_targets/slide-{number:03d}.png",
                    "sha256": _sha(image),
                    "dimensions": {"width": 1664, "height": 936},
                    "format": "PNG",
                    "validation_status": "PASS",
                    "final_surface_role_prohibited": True,
                }
            )
            _write_json(
                self.phase4 / "semantic_sidecars" / f"slide-{number:03d}.semantic.json",
                {
                    "schema_name": "phase4_semantic_sidecar",
                    "schema_version": "1.0.0",
                    "sidecar_id": sidecar_id,
                    "expected_visual_target_id": target_id,
                    "artifact_hash": f"{number}" * 64,
                    "phase4_metadata": {
                        "exact_title": f"Title {number}",
                        "exact_subtitle": f"Subtitle {number}",
                        "exact_body_blocks": [
                            {
                                "content_item_id": f"body-{number}",
                                "slot": "body",
                                "text": f"Body {number}",
                                "type": "source_evidence",
                            }
                        ],
                        "exact_labels": ["TITLE", "BODY"],
                        "exact_numbers": [],
                        "exact_units": [],
                        "citations": [],
                        "native_required_slot_ids": ["title", "subtitle", "body", "footer"],
                        "raster_allowed_slot_ids": ["bounded_illustration"],
                        "full_slide_raster_forbidden": True,
                        "ocr_canonical_text_forbidden": True,
                        "visual_target_is_not_semantic_source": True,
                    },
                    "sidecar": {
                        "slide_id": slide_id,
                        "canonical_content": [
                            {"kind": "text", "slot_id": "title", "value": f"Title {number}"}
                        ],
                    },
                },
            )
        _write_json(
            self.phase4 / "visual_target_manifest.json",
            {
                "schema_name": "phase4_visual_target_manifest",
                "schema_version": "1.0.0",
                "manifest_id": "phase4targets_fixture",
                "manifest_hash": "3" * 64,
                "selected_target_count": 6,
                "targets": targets,
            },
        )
        for name in (
            "input_provenance.json",
            "visual_dna.json",
            "design_system.json",
            "editable_template_spec.json",
            "generation_provenance.json",
            "geometry_fit_report.json",
            "regeneration_history.json",
        ):
            payload = {"fixture": name}
            if name == "input_provenance.json":
                payload["source_commit"] = "0" * 40
            _write_json(self.phase4 / name, payload)
        _write_json(
            self.phase4 / "phase4_bundle_acceptance.json",
            {
                "phase4_accepted": True,
                "bundle_status": "ELIGIBLE_FOR_PNGTOPPTX_HANDOFF",
                "final_release_eligible": False,
            },
        )

    def _export(self, *, output: Path | None = None, **overrides):
        arguments = {
            "phase4_bundle": self.phase4,
            "external_skillset_pin": self.pin,
            "output_dir": output or (self.root / "run"),
            "deckcompiler_commit": "72dadc711f9fb80f3d7162b3b7bae1868e64b0bf",
            "external_skill_root": self.external,
            "profile_path": self.profile,
            "node_path": self.node_path,
            "created_at": "2026-07-20T12:00:00+09:00",
            "timezone": "Asia/Seoul",
            "repository_root": REPO_ROOT,
        }
        arguments.update(overrides)
        return export_phase4_handoff(**arguments)

    def _snapshot(self, root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): _sha(path)
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def _materialize_zero_manifest(self, result) -> Path:
        manifest_path = result.project_root / "assets" / "manifest.json"
        _write_json(manifest_path, {})
        return manifest_path

    def _read_crop_plan(self, result) -> tuple[Path, dict]:
        path = result.project_root / "work" / "crop_plan.json"
        return path, json.loads(path.read_text(encoding="utf-8"))

    def _refresh_crop_plan_id(self, plan: dict) -> None:
        identity_payload = {key: value for key, value in plan.items() if key != "plan_id"}
        encoded = (
            json.dumps(identity_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        plan["plan_id"] = f"cropplan_{hashlib.sha256(encoded).hexdigest()[:20]}"

    def _add_crop(self, plan: dict, *, slide: int = 1, slot_id: str = "bounded_illustration") -> dict:
        source = plan["source_assets"][slide - 1]
        crop = {
            "name": f"slide{slide}_bounded_illustration",
            "source_asset_id": source["source_asset_id"],
            "slide": slide,
            "slot_id": slot_id,
            "x": 100,
            "y": 120,
            "w": 240,
            "h": 180,
            "feather_edges": "LRTB",
            "content_type": "illustration",
            "reconstruction_reason": "bounded visual cannot be faithfully reconstructed with primitives",
            "editable_replacement": "replaceable_image_frame",
        }
        plan["slides"][str(slide)].append(crop)
        plan["crop_count"] = sum(len(items) for items in plan["slides"].values())
        plan["crop_state"] = "RASTER_CROPS_PRESENT"
        plan["crop_state_reason"] = "one or more declared raster-allowed slots require bounded crops"
        self._refresh_crop_plan_id(plan)
        return crop

    def test_01_invalid_phase4_bundle_is_rejected(self) -> None:
        (self.phase4 / "phase4_bundle_acceptance.json").unlink()
        with self.assertRaisesRegex(HandoffError, "INVALID_PHASE4_BUNDLE"):
            self._export()

    def test_02_modified_visual_target_is_rejected(self) -> None:
        target = self.phase4 / "visual_targets" / "slide-001.png"
        target.write_bytes(target.read_bytes() + b"modified")
        with self.assertRaisesRegex(HandoffError, "TARGET_HASH_MISMATCH"):
            self._export()

    def test_03_modified_sidecar_is_rejected(self) -> None:
        sidecar = self.phase4 / "semantic_sidecars" / "slide-001.semantic.json"
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        payload["sidecar_id"] = "sidecar_modified"
        _write_json(sidecar, payload)
        with self.assertRaisesRegex(HandoffError, "SIDECAR_ID_MISMATCH"):
            self._export()

    def test_04_missing_target_is_rejected(self) -> None:
        (self.phase4 / "visual_targets" / "slide-006.png").unlink()
        with self.assertRaisesRegex(HandoffError, "MISSING_TARGET"):
            self._export()

    def test_05_missing_sidecar_is_rejected(self) -> None:
        (self.phase4 / "semantic_sidecars" / "slide-006.semantic.json").unlink()
        with self.assertRaisesRegex(HandoffError, "SIDECAR_COUNT_MISMATCH"):
            self._export()

    def test_06_duplicate_slide_mapping_is_rejected(self) -> None:
        manifest = self.phase4 / "visual_target_manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["targets"][1]["slide_id"] = payload["targets"][0]["slide_id"]
        _write_json(manifest, payload)
        with self.assertRaisesRegex(HandoffError, "DUPLICATE_SLIDE"):
            self._export()

    def test_07_order_mismatch_is_rejected(self) -> None:
        manifest = self.phase4 / "visual_target_manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["targets"][0], payload["targets"][1] = payload["targets"][1], payload["targets"][0]
        _write_json(manifest, payload)
        with self.assertRaisesRegex(HandoffError, "SLIDE_ORDER_MISMATCH"):
            self._export()

    def test_08_target_sidecar_mismatch_is_rejected(self) -> None:
        sidecar = self.phase4 / "semantic_sidecars" / "slide-001.semantic.json"
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        payload["expected_visual_target_id"] = "visualtarget_wrong"
        _write_json(sidecar, payload)
        with self.assertRaisesRegex(HandoffError, "TARGET_SIDECAR_MISMATCH"):
            self._export()

    def test_09_non_16_by_9_target_is_rejected(self) -> None:
        target = self.phase4 / "visual_targets" / "slide-001.png"
        Image.new("RGB", (1000, 1000), "white").save(target)
        manifest = self.phase4 / "visual_target_manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["targets"][0]["sha256"] = _sha(target)
        payload["targets"][0]["dimensions"] = {"width": 1000, "height": 1000}
        _write_json(manifest, payload)
        with self.assertRaisesRegex(HandoffError, "INVALID_TARGET_DIMENSIONS"):
            self._export()

    def test_10_external_pin_mismatch_is_rejected(self) -> None:
        payload = json.loads(self.pin.read_text(encoding="utf-8"))
        payload["execution_allowed"] = False
        _write_json(self.pin, payload)
        with self.assertRaisesRegex(HandoffError, "EXTERNAL_PIN_INVALID"):
            self._export()

    def test_10b_incomplete_official_node_dependency_set_is_rejected(self) -> None:
        (self.node_path / "react-icons").rmdir()
        with self.assertRaisesRegex(HandoffError, "PNGTOPPTX_RUNTIME_PREREQUISITE_MISSING"):
            self._export()

    def test_11_protected_output_path_is_rejected(self) -> None:
        protected = REPO_ROOT / "outputs" / "final_deck_large_premium.pptx"
        with self.assertRaisesRegex(HandoffError, "PROTECTED_OUTPUT_PATH"):
            self._export(output=protected)

    def test_12_output_inside_repository_is_rejected(self) -> None:
        with self.assertRaisesRegex(HandoffError, "OUTPUT_INSIDE_REPOSITORY"):
            self._export(output=REPO_ROOT / "phase5-runtime-forbidden")

    def test_13_non_empty_output_root_is_rejected(self) -> None:
        output = self.root / "run"
        output.mkdir()
        (output / "existing.txt").write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "OUTPUT_ROOT_NOT_EMPTY"):
            self._export(output=output)

    def test_14_full_slide_background_permission_is_rejected(self) -> None:
        sidecar = self.phase4 / "semantic_sidecars" / "slide-001.semantic.json"
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        payload["phase4_metadata"]["full_slide_raster_forbidden"] = False
        _write_json(sidecar, payload)
        with self.assertRaisesRegex(HandoffError, "FULL_SLIDE_RASTER_PERMISSION"):
            self._export()

    def test_15_ocr_canonical_text_permission_is_rejected(self) -> None:
        sidecar = self.phase4 / "semantic_sidecars" / "slide-001.semantic.json"
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        payload["phase4_metadata"]["ocr_canonical_text_forbidden"] = False
        _write_json(sidecar, payload)
        with self.assertRaisesRegex(HandoffError, "OCR_CANONICAL_TEXT_PERMISSION"):
            self._export()

    def test_16_native_raster_overlap_is_rejected(self) -> None:
        sidecar = self.phase4 / "semantic_sidecars" / "slide-001.semantic.json"
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        payload["phase4_metadata"]["raster_allowed_slot_ids"].append("title")
        _write_json(sidecar, payload)
        with self.assertRaisesRegex(HandoffError, "NATIVE_RASTER_OVERLAP"):
            self._export()

    def test_17_exported_targets_are_byte_equal(self) -> None:
        result = self._export()
        for number in range(1, 7):
            self.assertEqual(
                (self.phase4 / "visual_targets" / f"slide-{number:03d}.png").read_bytes(),
                (result.project_root / "src" / f"slide{number}.png").read_bytes(),
            )

    def test_18_phase4_source_bundle_is_unchanged(self) -> None:
        before = self._snapshot(self.phase4)
        self._export()
        self.assertEqual(before, self._snapshot(self.phase4))

    def test_19_invocation_plan_uses_exact_official_interface(self) -> None:
        result = self._export()
        plan = json.loads(result.invocation_plan.read_text(encoding="utf-8"))
        self.assertEqual(plan["exact_orchestrator_skill"], "slide-editable-deck-orchestrator")
        self.assertTrue(plan["official_entrypoints"]["pipeline"].endswith("slide_pipeline.js"))
        self.assertIn("--quality", plan["planned_commands"]["full_reconstruction"])
        self.assertIn("reconstruction", plan["planned_commands"]["full_reconstruction"])

    def test_20_no_new_skill_directory_is_created(self) -> None:
        result = self._export()
        forbidden = [path for path in result.output_dir.rglob("*") if path.is_dir() and path.name in {"skills", ".agents"}]
        self.assertEqual(forbidden, [])

    def test_21_external_files_are_not_modified(self) -> None:
        before = self._snapshot(self.external)
        self._export()
        self.assertEqual(before, self._snapshot(self.external))

    def test_22_all_handoff_manifests_are_schema_valid(self) -> None:
        result = self._export()
        artifacts = {
            "pngtopptx_handoff_manifest": result.handoff_manifest,
            "reconstruction_constraints": result.reconstruction_constraints,
            "expected_output_contract": result.expected_output_contract,
            "pngtopptx_invocation_plan": result.invocation_plan,
            "pngtopptx_project_crop_plan": result.crop_plan,
        }
        for schema_name, path in artifacts.items():
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(list(validator_for(schema_name).iter_errors(payload)), [])

    def test_23_cli_exits_nonzero_on_invalid_input(self) -> None:
        exit_code = deckcompiler_main(
            [
                "export-pngtopptx-handoff",
                "--phase4-bundle",
                str(self.root / "missing"),
                "--external-skillset-pin",
                str(self.pin),
                "--output-dir",
                str(self.root / "run"),
                "--external-skill-root",
                str(self.external),
                "--profile",
                str(self.profile),
                "--node-path",
                str(self.node_path),
                "--deckcompiler-commit",
                "72dadc711f9fb80f3d7162b3b7bae1868e64b0bf",
            ]
        )
        self.assertEqual(exit_code, 1)

    def test_24_preflight_does_not_invoke_external_skill(self) -> None:
        with mock.patch("subprocess.run") as run:
            result = self._export()
            with self.assertRaisesRegex(HandoffError, "MISSING_ASSET_MANIFEST"):
                validate_handoff(result.handoff_root)
            self._materialize_zero_manifest(result)
            report = validate_handoff(result.handoff_root)
        run.assert_not_called()
        self.assertTrue(report["valid"])

    def test_25_export_writes_rich_crop_plan_at_exact_path(self) -> None:
        result = self._export()
        path, plan = self._read_crop_plan(result)
        self.assertEqual(path, result.project_root / "work" / "crop_plan.json")
        self.assertEqual(plan["schema_name"], "pngtopptx_project_crop_plan")
        self.assertEqual(plan["contract_classification"], "observed_external_contract_v1")
        self.assertEqual(plan["slide_count"], 6)
        self.assertEqual(plan["crop_count"], 0)
        self.assertEqual(plan["crop_state"], "ZERO_RASTER_CROPS")
        self.assertEqual(list(plan["slides"]), ["1", "2", "3", "4", "5", "6"])
        self.assertTrue(all(plan["slides"][str(number)] == [] for number in range(1, 7)))
        self.assertEqual(len(plan["source_assets"]), 6)
        self.assertFalse((result.project_root / "assets" / "manifest.json").exists())

    def test_26_invocation_plan_runs_official_crop_stage_and_never_skips_crops(self) -> None:
        result = self._export()
        plan = json.loads(result.invocation_plan.read_text(encoding="utf-8"))
        crop_generator = plan["official_entrypoints"]["crop_generator"]
        self.assertTrue(crop_generator.endswith("make_crops.py"))
        self.assertEqual(plan["planned_commands"]["crop_preparation"], ["python", crop_generator])
        self.assertEqual(plan["planned_environment"]["crop_preparation"]["CROP_PLAN"], str(result.project_root / "work" / "crop_plan.json"))
        self.assertEqual(plan["planned_environment"]["crop_preparation"]["SRC_DIR"], str(result.project_root / "src"))
        self.assertEqual(plan["planned_environment"]["crop_preparation"]["DECK_ASSETS"], str(result.project_root / "assets"))
        for command_name in ("dry_run", "canary", "full_reconstruction"):
            command = plan["planned_commands"][command_name]
            self.assertNotIn("--skip-crops", command)
            self.assertIn("--crop-plan", command)
            self.assertEqual(command[command.index("--crop-plan") + 1], str(result.project_root / "work" / "crop_plan.json"))
        self.assertIn("--allow-large-batch", plan["planned_commands"]["dry_run"])

    def test_27_missing_crop_plan_fails_before_reconstruction(self) -> None:
        result = self._export()
        self._materialize_zero_manifest(result)
        (result.project_root / "work" / "crop_plan.json").unlink()
        with self.assertRaisesRegex(HandoffError, "MISSING_CROP_PLAN"):
            validate_handoff(result.handoff_root)

    def test_28_missing_asset_manifest_fails_before_reconstruction(self) -> None:
        result = self._export()
        with self.assertRaisesRegex(HandoffError, "MISSING_ASSET_MANIFEST"):
            validate_handoff(result.handoff_root)

    def test_29_placeholder_crop_plan_bypasses_are_rejected(self) -> None:
        for index, placeholder in enumerate(({}, [], {"crops": []}), start=1):
            with self.subTest(placeholder=placeholder):
                result = self._export(output=self.root / f"run-placeholder-{index}")
                crop_plan, _ = self._read_crop_plan(result)
                crop_plan.write_text(json.dumps(placeholder), encoding="utf-8")
                self._materialize_zero_manifest(result)
                with self.assertRaisesRegex(HandoffError, "CROP_PLAN_SCHEMA_INVALID"):
                    validate_handoff(result.handoff_root)

    def test_30_invalid_crop_plan_json_is_rejected(self) -> None:
        result = self._export()
        crop_plan, _ = self._read_crop_plan(result)
        crop_plan.write_text("{not-json", encoding="utf-8")
        with self.assertRaisesRegex(Exception, "INVALID_CROP_PLAN"):
            validate_crop_plan(crop_plan, result.project_root)

    def test_31_unknown_or_duplicate_slide_mapping_is_rejected(self) -> None:
        for index, mutate in enumerate((
            lambda plan: plan["slides"].update({"7": []}),
            lambda plan: plan["ordered_slide_ids"].__setitem__(1, plan["ordered_slide_ids"][0]),
        ), start=1):
            with self.subTest(case=index):
                result = self._export(output=self.root / f"run-slide-{index}")
                path, plan = self._read_crop_plan(result)
                mutate(plan)
                self._refresh_crop_plan_id(plan)
                _write_json(path, plan)
                self._materialize_zero_manifest(result)
                with self.assertRaisesRegex(HandoffError, "CROP_PLAN_SLIDE_MISMATCH"):
                    validate_handoff(result.handoff_root)

    def test_32_unknown_or_duplicate_source_asset_is_rejected(self) -> None:
        for index, mutate in enumerate((
            lambda plan: plan["ordered_source_asset_ids"].__setitem__(0, "cropsource_ffffffffffffffffffff"),
            lambda plan: plan["source_assets"][1].__setitem__("source_asset_id", plan["source_assets"][0]["source_asset_id"]),
        ), start=1):
            with self.subTest(case=index):
                result = self._export(output=self.root / f"run-asset-{index}")
                path, plan = self._read_crop_plan(result)
                mutate(plan)
                self._refresh_crop_plan_id(plan)
                _write_json(path, plan)
                self._materialize_zero_manifest(result)
                with self.assertRaisesRegex(HandoffError, "CROP_PLAN_SOURCE_ASSET_MISMATCH"):
                    validate_handoff(result.handoff_root)

    def test_33_source_hash_or_dimensions_mismatch_is_rejected(self) -> None:
        cases = (
            ("hash", lambda source: source.__setitem__("sha256", "f" * 64), "CROP_PLAN_SOURCE_HASH_MISMATCH"),
            ("dimensions", lambda source: source["dimensions"].__setitem__("width", 1600), "CROP_PLAN_SOURCE_DIMENSIONS_MISMATCH"),
        )
        for label, mutate, code in cases:
            with self.subTest(case=label):
                result = self._export(output=self.root / f"run-source-{label}")
                path, plan = self._read_crop_plan(result)
                mutate(plan["source_assets"][0])
                self._refresh_crop_plan_id(plan)
                _write_json(path, plan)
                self._materialize_zero_manifest(result)
                with self.assertRaisesRegex(HandoffError, code):
                    validate_handoff(result.handoff_root)

    def test_34_source_path_escape_or_absolute_path_is_rejected(self) -> None:
        for index, unsafe in enumerate(("../outside.png", str((self.root / "outside.png").resolve())), start=1):
            with self.subTest(path=unsafe):
                result = self._export(output=self.root / f"run-path-{index}")
                path, plan = self._read_crop_plan(result)
                plan["source_assets"][0]["path"] = unsafe
                self._refresh_crop_plan_id(plan)
                _write_json(path, plan)
                with self.assertRaisesRegex(Exception, "CROP_PLAN_PATH_ESCAPE"):
                    validate_crop_plan(path, result.project_root)

    def test_35_invalid_crop_bbox_is_rejected(self) -> None:
        result = self._export()
        path, plan = self._read_crop_plan(result)
        crop = self._add_crop(plan)
        crop["x"] = 1600
        crop["w"] = 100
        self._refresh_crop_plan_id(plan)
        _write_json(path, plan)
        with self.assertRaisesRegex(Exception, "CROP_PLAN_BBOX_INVALID"):
            validate_crop_plan(path, result.project_root)

    def test_36_native_semantic_slot_crop_is_rejected(self) -> None:
        result = self._export()
        path, plan = self._read_crop_plan(result)
        self._add_crop(plan, slot_id="title")
        _write_json(path, plan)
        with self.assertRaisesRegex(Exception, "CROP_PLAN_SEMANTIC_SLOT"):
            validate_crop_plan(path, result.project_root)

    def test_37_undeclared_raster_slot_crop_is_rejected(self) -> None:
        result = self._export()
        path, plan = self._read_crop_plan(result)
        self._add_crop(plan, slot_id="undeclared_visual")
        _write_json(path, plan)
        with self.assertRaisesRegex(Exception, "CROP_PLAN_RASTER_SLOT_NOT_ALLOWED"):
            validate_crop_plan(path, result.project_root)

    def test_38_rich_zero_crop_plan_and_official_empty_manifest_pass(self) -> None:
        result = self._export()
        manifest_path = self._materialize_zero_manifest(result)
        crop_plan_path, crop_plan = self._read_crop_plan(result)
        crop_report = validate_crop_plan(crop_plan_path, result.project_root)
        manifest_report = validate_asset_manifest(manifest_path, result.project_root, crop_plan)
        handoff_report = validate_handoff(result.handoff_root)
        self.assertEqual(crop_report["crop_count"], 0)
        self.assertEqual(manifest_report["asset_count"], 0)
        self.assertEqual(handoff_report["crop_contract_status"], "PASS_ZERO_RASTER")

    def test_39_manifest_must_match_nonzero_plan_and_asset_file(self) -> None:
        result = self._export()
        crop_plan_path, plan = self._read_crop_plan(result)
        crop = self._add_crop(plan)
        _write_json(crop_plan_path, plan)
        manifest_path = result.project_root / "assets" / "manifest.json"
        _write_json(manifest_path, {})
        with self.assertRaisesRegex(Exception, "ASSET_MANIFEST_MISMATCH"):
            validate_asset_manifest(manifest_path, result.project_root, plan)
        Image.new("RGBA", (crop["w"], crop["h"]), (255, 255, 255, 255)).save(
            result.project_root / "assets" / f"{crop['name']}.png"
        )
        _write_json(
            manifest_path,
            {
                crop["name"]: {
                    key: value
                    for key, value in crop.items()
                    if key != "feather_edges"
                }
                | {"file": f"{crop['name']}.png"},
            },
        )
        report = validate_asset_manifest(manifest_path, result.project_root, plan)
        self.assertEqual(report["asset_count"], 1)

    def test_40_invalid_asset_manifest_schema_is_rejected(self) -> None:
        result = self._export()
        crop_plan_path, plan = self._read_crop_plan(result)
        manifest_path = result.project_root / "assets" / "manifest.json"
        _write_json(manifest_path, {"unexpected": {"name": "unexpected"}})
        with self.assertRaisesRegex(Exception, "ASSET_MANIFEST_SCHEMA_INVALID"):
            validate_asset_manifest(manifest_path, result.project_root, plan)

    def test_41_crop_plan_generation_is_deterministic(self) -> None:
        first = self._export(output=self.root / "run-a")
        second = self._export(output=self.root / "run-b")
        first_plan = json.loads((first.project_root / "work" / "crop_plan.json").read_text(encoding="utf-8"))
        second_plan = json.loads((second.project_root / "work" / "crop_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(first_plan["plan_id"], second_plan["plan_id"])
        self.assertEqual(first_plan, second_plan)

    def test_42_handoff_manifest_links_both_crop_artifacts(self) -> None:
        result = self._export()
        manifest = json.loads(result.handoff_manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["artifact_paths"]["crop_plan"], "project/work/crop_plan.json")
        self.assertEqual(manifest["artifact_paths"]["asset_manifest"], "project/assets/manifest.json")

    def test_43_crop_contract_validation_never_invokes_external_processes(self) -> None:
        result = self._export()
        self._materialize_zero_manifest(result)
        with mock.patch("subprocess.run") as run:
            report = validate_handoff(result.handoff_root)
        run.assert_not_called()
        self.assertTrue(report["valid"])


if __name__ == "__main__":
    unittest.main()
