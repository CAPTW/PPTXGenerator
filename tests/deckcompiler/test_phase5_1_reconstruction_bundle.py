from __future__ import annotations

import hashlib
import json
import re
import unittest
import zipfile
from pathlib import Path

from PIL import Image
from pptx import Presentation


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPO_ROOT / "examples" / "deckcompiler_demo" / "phase5"
PPTX = ROOT / "outputs" / "pptx_generator_demo.pptx"
HTML = ROOT / "outputs" / "html" / "index.html"

PPTX_SHA256 = "805eb4aa3d44d90ebe5b78c0247d02e412ebfc9468e57c778516b90de2d27676"
HTML_SHA256 = "b1f161bed4d1dc37be576eceda0cf01d125580df4a767c4722582c8671983085"
PHASE4_SHA256 = "4ad86fcc50ed669d57966dd471d50ea791c21499c3c280c8b29f484a49b8473c"
EXTERNAL_SHA256 = "3dd4541fb0f2f4cf421d2a5c3cf2002390c0b00661a2e4d3a588d4467600022a"
CROP_PLAN_SHA256 = "8ca5934c049864fc69b856f0841ccba731980e2f6d756f04905b4086939aa089"
ASSET_MANIFEST_SHA256 = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


def _read(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _content_hash(payload: dict) -> str:
    content = dict(payload)
    expected = content.pop("content_sha256_without_this_field")
    canonical = (
        json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    actual = hashlib.sha256(canonical).hexdigest()
    if actual != expected:
        raise AssertionError(f"content hash mismatch: {actual} != {expected}")
    return actual


class Phase51ReconstructionBundleTests(unittest.TestCase):
    def test_01_required_curated_bundle_is_complete(self) -> None:
        required = {
            "README.md",
            "input_provenance.json",
            "external_skillset_pin.json",
            "prior_failed_run_reference.json",
            "handoff/crop_plan.json",
            "handoff/asset_manifest.json",
            "outputs/pptx_generator_demo.pptx",
            "outputs/html/index.html",
            "manifests/reconstruction_manifest.json",
            "manifests/native_object_manifest.json",
            "manifests/crop_coverage_summary.json",
            "manifests/pptx_object_inventory.json",
            "manifests/html_element_manifest.json",
            "validation/official_pngtopptx_final_gate_report.json",
            "validation/phase5_reconstruction_acceptance.json",
            "validation/independent_validation_summary.json",
            "validation/pptx_package_validation_report.json",
            "validation/pptx_semantic_fidelity_report.json",
            "validation/html_semantic_fidelity_report.json",
            "validation/cross_output_semantic_parity_report.json",
            "validation/html_package_validation_report.json",
            "validation/render_manifest.json",
            "validation/external_visual_qa_summary.json",
            "provenance/orchestrator_execution_record.json",
            "provenance/repair_history.json",
            "provenance/external_skillset_pre_post_fingerprint.json",
            "provenance/phase4_bundle_pre_post_fingerprint.json",
            "provenance/handoff_source_pre_post_fingerprint.json",
        }
        actual = {
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file()
        }
        self.assertTrue(required <= actual, sorted(required - actual))
        self.assertEqual(len(actual), 38)
        attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn(
            "examples/deckcompiler_demo/phase5/**/*.json                 -text whitespace=cr-at-eol",
            attributes,
        )
        self.assertIn(
            "examples/deckcompiler_demo/phase5/outputs/html/index.html   -text whitespace=cr-at-eol",
            attributes,
        )

    def test_02_json_content_and_acceptance_dependency_hashes_resolve(self) -> None:
        for path in ROOT.rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if "content_sha256_without_this_field" in payload:
                with self.subTest(path=path.relative_to(ROOT).as_posix()):
                    _content_hash(payload)

        acceptance = _read("validation/phase5_reconstruction_acceptance.json")
        for relative_path, expected in acceptance["prerequisite_report_sha256"].items():
            with self.subTest(path=relative_path):
                self.assertEqual(_sha(ROOT / relative_path), expected)

    def test_03_phase5_acceptance_is_composite_qa_only(self) -> None:
        acceptance = _read("validation/phase5_reconstruction_acceptance.json")
        summary = _read("validation/independent_validation_summary.json")
        self.assertEqual(acceptance["status"], "ELIGIBLE_FOR_COMPOSITE_QA")
        self.assertTrue(acceptance["phase5_accepted"])
        self.assertFalse(acceptance["final_release_eligible"])
        self.assertFalse(acceptance["devpost_release_eligible"])
        self.assertTrue(acceptance["phase6_required"])
        self.assertEqual(set(acceptance["checks"].values()), {"PASS"})
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["failed_checks"], [])
        self.assertEqual(set(summary["checks"].values()), {"PASS"})

    def test_04_official_execution_and_final_gate_passed(self) -> None:
        execution = _read("provenance/orchestrator_execution_record.json")
        gate = _read("validation/official_pngtopptx_final_gate_report.json")
        self.assertEqual(execution["preflight"], "PASS")
        self.assertEqual(execution["official_dry_run"], "PASS")
        self.assertEqual(execution["official_orchestration_plan"], "PASS")
        self.assertEqual(execution["official_single_slide_canary"], {"slide": 1, "status": "PASS"})
        self.assertEqual(execution["official_six_slide_reconstruction"], "PASS")
        self.assertEqual(execution["official_final_gate"], "PASS")
        self.assertFalse(execution["fallback_converter_used"])
        self.assertFalse(execution["legacy_fallback_used"])
        self.assertFalse(execution["full_slide_screenshot_route_used"])
        self.assertEqual(gate["exit_code"], 0)
        self.assertEqual(gate["final_verdict"], "PASS")
        self.assertEqual(gate["crop_plan_status"], "PASS")
        self.assertEqual(gate["asset_manifest_status"], "PASS")
        self.assertTrue(all(gate["parsed_checks"].values()))

    def test_05_pptx_bytes_package_and_openability_are_real(self) -> None:
        report = _read("validation/pptx_package_validation_report.json")
        self.assertEqual(_sha(PPTX), PPTX_SHA256)
        self.assertEqual(PPTX.stat().st_size, 261_527)
        self.assertEqual(report["pptx_sha256"], PPTX_SHA256)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["zip_open"])
        self.assertIsNone(report["zip_crc_failure"])
        self.assertTrue(report["required_parts_present"])
        self.assertEqual(report["slide_count"], 6)
        self.assertTrue(report["python_pptx_open"])
        self.assertEqual(len(Presentation(PPTX).slides), 6)
        with zipfile.ZipFile(PPTX) as package:
            self.assertIsNone(package.testzip())
            self.assertEqual(len([name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]), 6)

    def test_06_pptx_has_no_picture_screenshot_or_semantic_raster(self) -> None:
        report = _read("validation/pptx_package_validation_report.json")
        inventory = _read("manifests/pptx_object_inventory.json")
        for key in (
            "picture_shape_count",
            "full_slide_picture_count",
            "screenshot_slide_count",
            "semantic_raster_violation_count",
            "media_part_count",
            "macro_part_count",
            "missing_part_count",
        ):
            self.assertEqual(report[key], 0, key)
        self.assertEqual(inventory["slide_count"], 6)

    def test_07_native_and_semantic_fidelity_are_complete(self) -> None:
        native = _read("manifests/native_object_manifest.json")
        self.assertEqual(native["status"], "PASS")
        self.assertEqual(native["native_requirement_count"], 38)
        self.assertEqual(native["native_requirement_pass_count"], 38)
        self.assertEqual(native["native_requirement_coverage"], 1.0)
        self.assertEqual(native["failure_count"], 0)

        for relative_path in (
            "validation/pptx_semantic_fidelity_report.json",
            "validation/html_semantic_fidelity_report.json",
        ):
            report = _read(relative_path)
            with self.subTest(path=relative_path):
                self.assertEqual(report["status"], "PASS")
                self.assertEqual((report["canonical_item_pass_count"], report["canonical_item_count"]), (66, 66))
                self.assertEqual(report["canonical_text_fidelity"], 1.0)
                self.assertEqual((report["number_unit_token_pass_count"], report["number_unit_token_count"]), (79, 79))
                self.assertEqual((report["table_cell_pass_count"], report["table_cell_count"]), (4, 4))
                self.assertEqual((report["citation_source_note_pass_count"], report["citation_source_note_count"]), (30, 30))
                self.assertEqual(report["unknown_factual_addition_count"], 0)

        parity = _read("validation/cross_output_semantic_parity_report.json")
        self.assertEqual((parity["parity_pass_count"], parity["canonical_item_count"]), (66, 66))
        self.assertEqual(parity["parity_fidelity"], 1.0)
        self.assertEqual(parity["mismatch_count"], 0)

    def test_08_zero_crop_semantics_are_explicit_and_not_a_false_percentage(self) -> None:
        crop_plan = _read("handoff/crop_plan.json")
        crop = _read("manifests/crop_coverage_summary.json")
        self.assertEqual(_sha(ROOT / "handoff/crop_plan.json"), CROP_PLAN_SHA256)
        self.assertEqual((ROOT / "handoff/asset_manifest.json").read_bytes(), b"{}")
        self.assertEqual(_sha(ROOT / "handoff/asset_manifest.json"), ASSET_MANIFEST_SHA256)
        self.assertEqual(crop_plan["contract_classification"], "observed_external_contract_v1")
        self.assertEqual(crop_plan["crop_state"], "ZERO_RASTER_CROPS")
        self.assertEqual(crop_plan["slide_count"], 6)
        self.assertEqual(crop_plan["crop_count"], 0)
        self.assertEqual(set(crop_plan["slides"]), {str(number) for number in range(1, 7)})
        self.assertTrue(all(crop_plan["slides"][str(number)] == [] for number in range(1, 7)))
        self.assertEqual(crop["crop_source_trace_status"], "not_applicable_zero_raster")
        self.assertIn("N/A rather than a 0/0 percentage", crop["crop_trace_denominator_policy"])
        self.assertEqual(crop["unknown_source_count"], 0)

    def test_09_html_is_self_contained_selectable_and_native(self) -> None:
        report = _read("validation/html_package_validation_report.json")
        text = HTML.read_text(encoding="utf-8")
        self.assertEqual(_sha(HTML), HTML_SHA256)
        self.assertEqual(HTML.stat().st_size, 85_014)
        self.assertEqual(report["html_sha256"], HTML_SHA256)
        self.assertEqual(report["slide_count"], 6)
        self.assertTrue(report["selectable_text"])
        self.assertEqual(report["native_table_count"], 1)
        self.assertEqual(report["full_slide_screenshot_count"], 0)
        self.assertEqual(report["image_count"], 0)
        self.assertEqual(report["external_network_dependency_count"], 0)
        self.assertEqual(report["absolute_machine_path_count"], 0)
        self.assertEqual(report["missing_local_asset_count"], 0)
        self.assertEqual(len(re.findall(r'<section\b[^>]*class="[^"]*slide', text)), 6)
        self.assertIn("<table", text)
        self.assertNotRegex(text, r"https?://")

    def test_10_powerpoint_render_evidence_matches_six_real_pngs(self) -> None:
        manifest = _read("validation/render_manifest.json")
        self.assertEqual(manifest["status"], "PASS")
        self.assertEqual(manifest["renderer_identity"], "Microsoft PowerPoint COM")
        self.assertEqual(manifest["renderer_version"], "16.0")
        self.assertEqual(manifest["render_count"], 6)
        self.assertEqual(manifest["repair_warning_count"], 0)
        self.assertEqual(manifest["warning_count"], 0)
        for record in manifest["slides"]:
            image_path = ROOT / record["path"]
            with self.subTest(path=record["path"]):
                self.assertEqual(_sha(image_path), record["sha256"])
                self.assertEqual(image_path.stat().st_size, record["byte_size"])
                with Image.open(image_path) as rendered:
                    self.assertEqual(rendered.size, (1920, 1080))
                    self.assertEqual(rendered.format, "PNG")

    def test_11_external_phase4_and_handoff_sources_are_unchanged(self) -> None:
        external = _read("provenance/external_skillset_pre_post_fingerprint.json")
        phase4 = _read("provenance/phase4_bundle_pre_post_fingerprint.json")
        handoff = _read("provenance/handoff_source_pre_post_fingerprint.json")
        self.assertEqual(external["status"], "PASS")
        self.assertFalse(external["external_skill_modified"])
        self.assertEqual((external["pre_file_count"], external["post_file_count"]), (99, 99))
        self.assertEqual(external["pre_aggregate_sha256"], EXTERNAL_SHA256)
        self.assertEqual(external["post_aggregate_sha256"], EXTERNAL_SHA256)
        self.assertEqual(phase4["status"], "PASS")
        self.assertTrue(phase4["matches_head"])
        self.assertEqual((phase4["pre_file_count"], phase4["post_file_count"]), (107, 107))
        self.assertEqual(phase4["pre_aggregate_sha256"], PHASE4_SHA256)
        self.assertEqual(phase4["post_aggregate_sha256"], PHASE4_SHA256)
        self.assertEqual(handoff["status"], "PASS")
        self.assertEqual(handoff["mismatch_count"], 0)
        for component in handoff["components"].values():
            self.assertEqual(component["pre_sha256"], component["post_sha256"])

    def test_12_repair_budget_and_prior_failure_are_preserved(self) -> None:
        repairs = _read("provenance/repair_history.json")
        prior = _read("prior_failed_run_reference.json")
        self.assertEqual(repairs["repair_waves_used"], 3)
        self.assertEqual(repairs["repair_waves_allowed"], 3)
        self.assertEqual(repairs["repair_status"], "completed_at_limit")
        self.assertTrue(repairs["run_closed"])
        self.assertEqual([wave["wave"] for wave in repairs["waves"]], [1, 2, 3])
        self.assertEqual(repairs["waves"][-1]["status"], "accepted")
        self.assertFalse(repairs["prior_run_is_continuation"])
        self.assertFalse(repairs["prior_output_is_input"])
        self.assertEqual(prior["status"], "FAILED_CLOSED")
        self.assertEqual(prior["classification"], "immutable_diagnostic_evidence")
        self.assertEqual((prior["repair_waves_used"], prior["repair_waves_allowed"]), (3, 3))
        self.assertFalse(prior["accepted"])
        self.assertFalse(prior["curated"])
        self.assertFalse(prior["committed"])
        self.assertFalse(prior["used_as_new_run_input"])
        self.assertFalse(prior["modified_by_phase5_1"])

    def test_13_curated_text_has_no_machine_paths_or_secret_material(self) -> None:
        forbidden_paths = re.compile(r"(?:[A-Za-z]:[\\/]|AppData[\\/]Local[\\/]Temp)")
        secret_assignments = re.compile(
            r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}"
        )
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() in {".pptx", ".png"}:
                continue
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertIsNone(forbidden_paths.search(text))
                self.assertIsNone(secret_assignments.search(text))

    def test_14_protected_outputs_and_removed_skill_are_absent(self) -> None:
        for relative_path in (
            "outputs/editable_template_spec.final.json",
            "outputs/golden_template_masters.pptx",
            "outputs/final_deck_large_premium.pptx",
            ".agents/skills/image-to-editable-ppt-template",
            "skills/image-to-editable-ppt-template",
        ):
            with self.subTest(path=relative_path):
                self.assertFalse((REPO_ROOT / relative_path).exists())


if __name__ == "__main__":
    unittest.main()
