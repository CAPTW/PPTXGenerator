from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.intake.config import load_phase3_config
from presentation_agent.deckcompiler.intake.multi_source import build_intake_artifacts
from presentation_agent.deckcompiler.intake.pdf_text import extract_searchable_pdf


DEMO = ROOT / "examples" / "deckcompiler_demo"


class Phase3MultiSourceIntakeTests(unittest.TestCase):
    def test_prompt_plus_two_pdfs_builds_complete_deterministic_source_corpus(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml")
        first = build_intake_artifacts(config, run_id="run_a")
        second = build_intake_artifacts(config, run_id="run_b")

        self.assertEqual(first.source_corpus["schema_name"], "source_corpus")
        self.assertEqual(len(first.source_corpus["sources"]), 3)
        self.assertEqual(
            [source["source_id"] for source in first.source_corpus["sources"]],
            sorted(source["source_id"] for source in first.source_corpus["sources"]),
        )
        self.assertEqual(
            [source["source_id"] for source in first.source_corpus["sources"]],
            [source["source_id"] for source in second.source_corpus["sources"]],
        )
        self.assertEqual(
            first.source_corpus["artifact"]["content_sha256"],
            second.source_corpus["artifact"]["content_sha256"],
        )
        source_types = [source["source_type"] for source in first.source_corpus["sources"]]
        self.assertEqual(source_types.count("user_prompt"), 1)
        self.assertEqual(source_types.count("pdf"), 2)
        for source in first.source_corpus["sources"]:
            if source["source_type"] == "pdf":
                path = next(path for path in config.pdf_paths if path.name == source["original_filename"])
                self.assertEqual(source["stable_identity"]["value"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_pdf_locators_preserve_page_index_page_number_block_and_chunk(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml")
        artifacts = build_intake_artifacts(config)
        pdf_source_ids = {
            item["source_id"] for item in artifacts.source_corpus["sources"] if item["source_type"] == "pdf"
        }
        locators = [
            item for item in artifacts.source_locator_registry["locators"] if item["source_id"] in pdf_source_ids
        ]
        self.assertTrue(locators)
        for locator in locators:
            self.assertEqual(locator["page_number"], locator["page_index"] + 1)
            self.assertGreaterEqual(locator["page_number"], 1)
            self.assertGreaterEqual(locator["block_index"], 0)
            self.assertRegex(locator["chunk_id"], r"^chunk_[0-9a-f]{20}$")
            self.assertRegex(locator["text_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(locator["extraction_method"], "pymupdf_text_blocks")

    def test_page_aware_adapter_records_existing_single_source_compatibility(self) -> None:
        artifacts = build_intake_artifacts(load_phase3_config(DEMO / "demo.yaml"))
        records = artifacts.source_locator_registry["pdf_documents"]
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(
                record["legacy_adapter"],
                "presentation_agent.source_ingestion.ingest_source_file",
            )
            self.assertRegex(record["legacy_structural_hash"], r"^[0-9a-f]{64}$")

    def test_legacy_adapter_hash_is_independent_of_absolute_checkout_path(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml")
        with tempfile.TemporaryDirectory() as tmpdir:
            roots = (Path(tmpdir) / "checkout-a", Path(tmpdir) / "checkout-b")
            copied_paths: list[tuple[Path, Path]] = []
            for root in roots:
                root.mkdir()
                paths: list[Path] = []
                for source_path in config.pdf_paths:
                    destination = root / source_path.name
                    shutil.copyfile(source_path, destination)
                    paths.append(destination)
                copied_paths.append((paths[0], paths[1]))

            first = build_intake_artifacts(config.model_copy(update={"pdf_paths": copied_paths[0]}))
            second = build_intake_artifacts(config.model_copy(update={"pdf_paths": copied_paths[1]}))

        self.assertEqual(
            first.source_locator_registry["pdf_documents"],
            second.source_locator_registry["pdf_documents"],
        )
        self.assertEqual(
            first.source_locator_registry["artifact"]["artifact_id"],
            second.source_locator_registry["artifact"]["artifact_id"],
        )
        self.assertEqual(
            first.source_locator_registry["artifact"]["content_sha256"],
            second.source_locator_registry["artifact"]["content_sha256"],
        )
        self.assertEqual(
            first.evidence_unit_registry["artifact"]["artifact_id"],
            second.evidence_unit_registry["artifact"]["artifact_id"],
        )
        self.assertEqual(
            first.evidence_unit_registry["artifact"]["content_sha256"],
            second.evidence_unit_registry["artifact"]["content_sha256"],
        )

    def test_prompt_only_mode_has_one_source_and_declares_documentary_gap(self) -> None:
        config = load_phase3_config(DEMO / "prompt_only.yaml")
        artifacts = build_intake_artifacts(config)
        self.assertEqual(len(artifacts.source_corpus["sources"]), 1)
        self.assertEqual(artifacts.source_corpus["sources"][0]["source_type"], "user_prompt")
        self.assertEqual(artifacts.source_coverage_report["documentary_source_count"], 0)
        self.assertIn("documentary_evidence_absent", artifacts.source_coverage_report["source_gaps"])

    def test_duplicate_pdf_is_rejected_without_silent_deduplication(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml")
        duplicate = config.model_copy(update={"pdf_paths": (config.pdf_paths[0], config.pdf_paths[0])})
        with self.assertRaisesRegex(DeckCompilerError, "DC_SOURCE_DUPLICATE_CONFLICT"):
            build_intake_artifacts(duplicate)

    def test_missing_pdf_fails_closed(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml")
        missing = config.model_copy(update={"pdf_paths": (config.pdf_paths[0], DEMO / "inputs" / "missing.pdf")})
        with self.assertRaisesRegex(DeckCompilerError, "DC_INPUT_MISSING"):
            build_intake_artifacts(missing)

    def test_pdf_byte_change_changes_source_and_corpus_hash(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml")
        baseline = build_intake_artifacts(config)
        with tempfile.TemporaryDirectory() as tmpdir:
            changed_path = Path(tmpdir) / config.pdf_paths[0].name
            changed_path.write_bytes(config.pdf_paths[0].read_bytes() + b"\n% fixture byte change\n")
            changed = config.model_copy(update={"pdf_paths": (changed_path, config.pdf_paths[1])})
            candidate = build_intake_artifacts(changed)
        baseline_pdf = {
            item["original_filename"]: item for item in baseline.source_corpus["sources"] if item["source_type"] == "pdf"
        }
        candidate_pdf = {
            item["original_filename"]: item for item in candidate.source_corpus["sources"] if item["source_type"] == "pdf"
        }
        self.assertNotEqual(
            baseline_pdf[config.pdf_paths[0].name]["source_id"],
            candidate_pdf[config.pdf_paths[0].name]["source_id"],
        )
        self.assertNotEqual(
            baseline.source_corpus["artifact"]["content_sha256"],
            candidate.source_corpus["artifact"]["content_sha256"],
        )

    def test_image_only_pdf_and_malformed_pdf_return_stable_codes(self) -> None:
        with self.assertRaisesRegex(DeckCompilerError, "DC_PDF_SCANNED_UNSUPPORTED") as scanned:
            extract_searchable_pdf(DEMO / "negative_inputs" / "scanned_image_only.pdf", "src_00000000000000000000")
        self.assertEqual(scanned.exception.stage, "source_preflight")
        with self.assertRaisesRegex(DeckCompilerError, "DC_PDF_INVALID") as malformed:
            extract_searchable_pdf(DEMO / "negative_inputs" / "malformed.pdf", "src_00000000000000000000")
        self.assertEqual(malformed.exception.stage, "source_preflight")


if __name__ == "__main__":
    unittest.main()
