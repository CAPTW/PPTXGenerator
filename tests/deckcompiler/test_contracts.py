from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCHEMAS = ROOT / "schemas" / "deckcompiler"
VALID_RUN = ROOT / "examples" / "deckcompiler_demo" / "fixtures" / "contracts" / "valid_run"
INVALID = ROOT / "tests" / "deckcompiler" / "fixtures" / "invalid"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


EXPECTED_SCHEMA_FILES = {
    "architecture-validation-report.schema.json",
    "artifact-envelope.schema.json",
    "baseline-reachability-report.schema.json",
    "bundle-fingerprint-authority.schema.json",
    "bundle-fingerprint-cross-clone-report.schema.json",
    "bundle-fingerprint-history-replay.schema.json",
    "bundle-fingerprint-policy.schema.json",
    "deckcompiler-run-manifest.schema.json",
    "dependency-closure-validation-report.schema.json",
    "creative-fit-report.schema.json",
    "composite-qa-acceptance.schema.json",
    "composite-qa-report.schema.json",
    "contact-sheet-manifest.schema.json",
    "design-invariants.schema.json",
    "evidence-allocation-report.schema.json",
    "evidence-unit-registry.schema.json",
    "evidence-unit.schema.json",
    "external-execution-acceptance.schema.json",
    "external-execution-record.schema.json",
    "external-execution-request.schema.json",
    "external-execution-verification-report.schema.json",
    "external-entrypoint-canary-report.schema.json",
    "external-entrypoint-record.schema.json",
    "external-python-runtime-dependency-manifest.schema.json",
    "external-skillset-pin.schema.json",
    "external-visual-qa-output-contract-audit.schema.json",
    "external-visual-qa-reconciliation.schema.json",
    "external-visual-qa-source-results.schema.json",
    "expected-finding.schema.json",
    "expected-output-contract.schema.json",
    "failure-detection-report.schema.json",
    "fault-application-record.schema.json",
    "fault-injection-spec.schema.json",
    "fault-run-evidence-capsule-manifest.schema.json",
    "fixture-provenance.schema.json",
    "input-request.schema.json",
    "git-object-bundle-fingerprint.schema.json",
    "legacy-bundle-fingerprint-correction.schema.json",
    "module-art-directions.schema.json",
    "phase3-evidence-unit-registry.schema.json",
    "phase3-artifact-graph.schema.json",
    "phase3-run-manifest.schema.json",
    "phase3-validation-report.schema.json",
    "phase4-design-system.schema.json",
    "phase4-editable-template-spec.schema.json",
    "phase4-generation-provenance.schema.json",
    "phase4-geometry-fit-report.schema.json",
    "phase4-input-provenance.schema.json",
    "phase4-pending-visual-target-manifest.schema.json",
    "phase4-regeneration-history.schema.json",
    "phase4-semantic-sidecar.schema.json",
    "phase4-validation-report.schema.json",
    "phase4-visual-bundle-acceptance.schema.json",
    "phase4-visual-target-manifest.schema.json",
    "platform-image-capability-attestation.schema.json",
    "platform-image-attempt-seal.schema.json",
    "platform-image-execution-record.schema.json",
    "platform-image-regeneration-history.schema.json",
    "platform-image-request.schema.json",
    "platform-image-verification-report.schema.json",
    "platform-image-visual-review.schema.json",
    "phase4c-canary-report.schema.json",
    "png-reconstruction-manifest.schema.json",
    "pngtopptx-handoff-manifest.schema.json",
    "pngtopptx-invocation-plan.schema.json",
    "pngtopptx-project-asset-manifest.schema.json",
    "pngtopptx-project-crop-plan.schema.json",
    "qa-dimension-report.schema.json",
    "qa-finding.schema.json",
    "reconstruction-constraints.schema.json",
    "repair-contract.schema.json",
    "repair-plan.schema.json",
    "invalidation-manifest.schema.json",
    "repair-history.schema.json",
    "before-after-manifest.schema.json",
    "unified-release-gate-report.schema.json",
    "phase6-acceptance.schema.json",
    "slide-blueprint-collection.schema.json",
    "source-corpus.schema.json",
    "source-coverage-report.schema.json",
    "source-gap-report.schema.json",
    "source-item.schema.json",
    "source-locator.schema.json",
    "source-locator-registry.schema.json",
    "visual-target-manifest.schema.json",
    "visual-dna.schema.json",
    "workflow-resolution.schema.json",
    "release-contract.schema.json",
    "runtime-environment-manifest.schema.json",
    "runtime-bundle-compatibility.schema.json",
    "external-prerequisite-manifest.schema.json",
    "component-provenance-manifest.schema.json",
    "build-week-provenance.schema.json",
    "demo-run-manifest.schema.json",
    "semantic-reproducibility-report.schema.json",
    "delivery-manifest.schema.json",
    "package-inventory.schema.json",
    "package-validation-report.schema.json",
    "release-candidate-gate.schema.json",
    "fresh-clone-environment-report.schema.json",
    "fresh-clone-reproduction-report.schema.json",
    "fresh-locked-environment-report.schema.json",
    "canonical-vs-fresh-comparison-report.schema.json",
    "final-release-gate.schema.json",
    "phase-7-0-3-acceptance.schema.json",
    "devpost-evidence-index.schema.json",
}


class DeckCompilerContractTests(unittest.TestCase):
    def _module(self, relative_path: str, module_name: str):
        self.assertTrue((SRC / "presentation_agent" / "deckcompiler" / relative_path).is_file())
        return importlib.import_module(module_name)

    def _load(self, path: Path) -> dict:
        self.assertTrue(path.is_file(), f"missing fixture: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_schema_inventory_is_complete_and_draft_2020_12(self) -> None:
        self.assertTrue(SCHEMAS.is_dir())
        actual = {path.name for path in SCHEMAS.glob("*.schema.json")}
        self.assertEqual(actual, EXPECTED_SCHEMA_FILES)
        for path in SCHEMAS.glob("*.schema.json"):
            schema = self._load(path)
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_product_and_system_metadata_are_binding(self) -> None:
        module = importlib.import_module("presentation_agent.deckcompiler")
        self.assertEqual(module.PRODUCT_NAME, "PPTX Generator")
        self.assertEqual(module.PRODUCT_SLUG, "pptx-generator")
        self.assertEqual(module.SYSTEM_NAME, "DeckCompiler")
        self.assertEqual(module.SYSTEM_ID, "deckcompiler")
        self.assertEqual(module.RECONSTRUCTION_ENGINE, "PNGtoPPTX")

    def test_typed_artifact_envelope_parses_valid_fixture(self) -> None:
        models = self._module("models.py", "presentation_agent.deckcompiler.models")
        self.assertTrue(hasattr(models, "ArtifactEnvelope"))
        payload = self._load(VALID_RUN / "source_corpus.json")
        envelope = models.ArtifactEnvelope.model_validate(payload["artifact"])
        self.assertEqual(envelope.artifact_type, "source_corpus")
        self.assertEqual(envelope.product.product_name, "PPTX Generator")
        self.assertEqual(envelope.product.system_id, "deckcompiler")

    def test_source_locator_helpers_emit_traceable_one_based_locators(self) -> None:
        locators = self._module("locators.py", "presentation_agent.deckcompiler.locators")
        locator = locators.pdf_text_locator(
            "src_11111111111111111111",
            page_number=2,
            start=10,
            end=24,
            quote="synthetic quote",
        )
        self.assertEqual(locator["locator_type"], "pdf_text_span")
        self.assertEqual(locator["page_number"], 2)
        self.assertEqual(locator["char_range"], {"start": 10, "end": 24})
        with self.assertRaisesRegex(ValueError, "page_number"):
            locators.pdf_text_locator("src_11111111111111111111", page_number=0, start=0, end=1)

    def test_deterministic_ids_and_hashes_are_stable(self) -> None:
        identity = self._module("identity.py", "presentation_agent.deckcompiler.identity")
        value_a = {"b": [2, 1], "a": "cooling"}
        value_b = {"a": "cooling", "b": [2, 1]}
        self.assertEqual(identity.content_sha256(value_a), identity.content_sha256(value_b))
        first = identity.stable_id("src", "pdf", value_a)
        second = identity.stable_id("src", "pdf", value_b)
        self.assertEqual(first, second)
        self.assertRegex(first, r"^src_[0-9a-f]{20}$")
        self.assertNotEqual(first, identity.stable_id("src", "pdf", {"a": "changed"}))

    def test_source_id_must_match_stable_identity(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        payload = deepcopy(self._load(VALID_RUN / "source_corpus.json"))
        payload["sources"][0]["source_id"] = "src_00000000000000000000"
        report = validator.validate_artifact(payload, schema_name="source_corpus")
        self.assertFalse(report.valid)
        self.assertIn("NONDETERMINISTIC_SOURCE_ID", {issue.code for issue in report.issues})

    def test_evidence_id_must_match_source_locator_and_content(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        payload = deepcopy(self._load(VALID_RUN / "evidence_unit_registry.json"))
        payload["evidence_units"][0]["evidence_id"] = "ev_00000000000000000000"
        report = validator.validate_artifact(payload, schema_name="evidence_unit_registry")
        self.assertFalse(report.valid)
        self.assertIn("NONDETERMINISTIC_EVIDENCE_ID", {issue.code for issue in report.issues})

    def test_manifest_io_round_trip_is_canonical(self) -> None:
        io = self._module("manifest_io.py", "presentation_agent.deckcompiler.manifest_io")
        payload = {"z": 2, "a": {"k": "v"}}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "artifact.json"
            io.write_json(path, payload)
            self.assertEqual(io.read_json(path), payload)
            text = path.read_text(encoding="utf-8")
            self.assertLess(text.index('"a"'), text.index('"z"'))
            self.assertTrue(text.endswith("\n"))

    def test_valid_contract_artifacts_pass_schema_validation(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        cases = {
            "source_corpus": "source_corpus.json",
            "evidence_unit_registry": "evidence_unit_registry.json",
            "slide_blueprint_collection": "slide_blueprint_collection.json",
            "visual_target_manifest": "visual_target_manifest.json",
            "png_reconstruction_manifest": "png_reconstruction_manifest.json",
            "deckcompiler_run_manifest": "deckcompiler_run_manifest.json",
        }
        for schema_name, filename in cases.items():
            payload = self._load(VALID_RUN / filename)
            report = validator.validate_artifact(payload, schema_name=schema_name, artifact_path=filename)
            self.assertTrue(report.valid, report.to_human())

    def test_evidence_without_source_locator_fails(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        payload = self._load(INVALID / "evidence_without_locator.json")
        report = validator.validate_artifact(payload, schema_name="evidence_unit_registry")
        self.assertFalse(report.valid)
        self.assertIn("SCHEMA_VALIDATION_ERROR", {issue.code for issue in report.issues})
        self.assertIn("source_locator", report.to_human())

    def test_duplicate_evidence_id_fails_semantic_validation(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        report = validator.validate_artifact(
            self._load(INVALID / "duplicate_evidence_id.json"),
            schema_name="evidence_unit_registry",
        )
        self.assertFalse(report.valid)
        self.assertIn("DUPLICATE_ID", {issue.code for issue in report.issues})

    def test_source_order_must_be_deterministic(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        report = validator.validate_artifact(
            self._load(INVALID / "unsorted_source_corpus.json"),
            schema_name="source_corpus",
        )
        self.assertFalse(report.valid)
        self.assertIn("NONDETERMINISTIC_ORDER", {issue.code for issue in report.issues})

    def test_source_without_stable_identity_fails(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        report = validator.validate_artifact(
            self._load(INVALID / "source_without_stable_identity.json"),
            schema_name="source_corpus",
        )
        self.assertFalse(report.valid)
        self.assertIn("stable_identity", report.to_human())

    def test_source_locator_page_numbers_are_one_based(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        report = validator.validate_artifact(
            self._load(INVALID / "invalid_page_locator.json"),
            schema_name="evidence_unit_registry",
        )
        self.assertFalse(report.valid)
        self.assertIn("page_number", report.to_human())

    def test_visual_target_dimensions_must_be_16_by_9(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        report = validator.validate_artifact(
            self._load(INVALID / "invalid_visual_target_dimensions.json"),
            schema_name="visual_target_manifest",
        )
        self.assertFalse(report.valid)
        self.assertIn("INVALID_ASPECT_RATIO", {issue.code for issue in report.issues})

    def test_unsafe_png_reconstruction_policy_fails(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        report = validator.validate_artifact(
            self._load(INVALID / "unsafe_png_reconstruction.json"),
            schema_name="png_reconstruction_manifest",
        )
        self.assertFalse(report.valid)
        self.assertIn("full_slide_raster", report.to_human())

    def test_unknown_evidence_reference_fails_graph_validation(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        artifacts = {
            "source_corpus": self._load(VALID_RUN / "source_corpus.json"),
            "evidence_unit_registry": self._load(VALID_RUN / "evidence_unit_registry.json"),
            "slide_blueprint_collection": self._load(INVALID / "unknown_evidence_reference.json"),
        }
        report = validator.validate_artifact_graph(artifacts)
        self.assertFalse(report.valid)
        self.assertIn("UNKNOWN_EVIDENCE_REFERENCE", {issue.code for issue in report.issues})

    def test_unknown_visual_target_reference_fails_graph_validation(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        artifacts = {
            "visual_target_manifest": self._load(VALID_RUN / "visual_target_manifest.json"),
            "png_reconstruction_manifest": self._load(INVALID / "unknown_visual_target_reference.json"),
        }
        report = validator.validate_artifact_graph(artifacts)
        self.assertFalse(report.valid)
        self.assertIn("UNKNOWN_VISUAL_TARGET_REFERENCE", {issue.code for issue in report.issues})

    def test_blueprint_and_visual_target_slide_references_must_resolve(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        blueprints = deepcopy(self._load(VALID_RUN / "slide_blueprint_collection.json"))
        targets = deepcopy(self._load(VALID_RUN / "visual_target_manifest.json"))
        blueprints["evidence_bindings"][0]["slide_id"] = "slide-does-not-exist"
        targets["targets"][0]["slide_id"] = "slide-does-not-exist"
        artifacts = {
            "evidence_unit_registry": self._load(VALID_RUN / "evidence_unit_registry.json"),
            "slide_blueprint_collection": blueprints,
            "visual_target_manifest": targets,
        }
        report = validator.validate_artifact_graph(artifacts)
        self.assertFalse(report.valid)
        self.assertIn("UNKNOWN_SLIDE_REFERENCE", {issue.code for issue in report.issues})

    def test_provenance_inputs_must_resolve_within_run_graph(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        corpus = deepcopy(self._load(VALID_RUN / "source_corpus.json"))
        corpus["artifact"]["provenance"]["input_artifact_ids"] = ["art_00000000000000000000"]
        report = validator.validate_artifact_graph({"source_corpus": corpus})
        self.assertFalse(report.valid)
        self.assertIn("UNKNOWN_PROVENANCE_INPUT", {issue.code for issue in report.issues})

    def test_missing_required_run_artifact_fails(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        report = validator.validate_run_directory(INVALID / "missing_artifact_run")
        self.assertFalse(report.valid)
        self.assertIn("MISSING_ARTIFACT", {issue.code for issue in report.issues})

    def test_full_fixture_graph_passes_and_is_printable(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        report = validator.validate_run_directory(VALID_RUN)
        self.assertTrue(report.valid, report.to_human())
        self.assertEqual(len(self._load(VALID_RUN / "source_corpus.json")["sources"]), 3)
        self.assertEqual(len(self._load(VALID_RUN / "evidence_unit_registry.json")["evidence_units"]), 8)
        self.assertEqual(len(self._load(VALID_RUN / "slide_blueprint_collection.json")["slides"]), 6)
        self.assertEqual(len(self._load(VALID_RUN / "visual_target_manifest.json")["targets"]), 6)
        self.assertEqual(len(self._load(VALID_RUN / "png_reconstruction_manifest.json")["reconstructions"]), 6)
        graph = validator.build_artifact_graph(VALID_RUN)
        self.assertEqual(len(graph["nodes"]), 6)
        self.assertGreaterEqual(len(graph["edges"]), 4)
        self.assertEqual(graph["product_name"], "PPTX Generator")
        self.assertEqual(graph["system_id"], "deckcompiler")

    def test_human_readable_validation_report_is_stable(self) -> None:
        validator = self._module("validation.py", "presentation_agent.deckcompiler.validation")
        report = validator.validate_artifact(
            self._load(INVALID / "evidence_without_locator.json"),
            schema_name="evidence_unit_registry",
            artifact_path="evidence_without_locator.json",
        )
        text = report.to_human()
        self.assertIn("INVALID evidence_unit_registry", text)
        self.assertIn("SCHEMA_VALIDATION_ERROR", text)
        self.assertIn("evidence_without_locator.json", text)

    def test_cli_validates_artifact_run_and_graph(self) -> None:
        self.assertTrue((SRC / "presentation_agent" / "deckcompiler" / "cli.py").is_file())
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        commands = [
            [
                sys.executable,
                "-B",
                "-m",
                "presentation_agent.deckcompiler",
                "validate",
                str(VALID_RUN / "source_corpus.json"),
                "--schema",
                "source_corpus",
            ],
            [
                sys.executable,
                "-B",
                "-m",
                "presentation_agent.deckcompiler",
                "validate-run",
                str(VALID_RUN),
            ],
            [
                sys.executable,
                "-B",
                "-m",
                "presentation_agent.deckcompiler",
                "graph",
                str(VALID_RUN),
                "--format",
                "json",
            ],
        ]
        expected = ("VALID source_corpus", "VALID deckcompiler_run", '"nodes"')
        for command, marker in zip(commands, expected, strict=True):
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(marker, result.stdout)

    def test_cli_returns_nonzero_human_report_for_invalid_artifact(self) -> None:
        self.assertTrue((SRC / "presentation_agent" / "deckcompiler" / "cli.py").is_file())
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "presentation_agent.deckcompiler",
                "validate",
                str(INVALID / "evidence_without_locator.json"),
                "--schema",
                "evidence_unit_registry",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("INVALID evidence_unit_registry", result.stdout)
        self.assertIn("SCHEMA_VALIDATION_ERROR", result.stdout)


if __name__ == "__main__":
    unittest.main()
