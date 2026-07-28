from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.intake.config import load_phase3_config
from presentation_agent.deckcompiler.intake.multi_source import build_intake_artifacts
from presentation_agent.deckcompiler.planning.strict_adapter import build_strict_planning
from presentation_agent.deckcompiler.architecture.creative_frontend_adapter import build_architecture_artifacts
from presentation_agent.deckcompiler.validation import validate_artifact


DEMO = ROOT / "examples" / "deckcompiler_demo"


class Phase3ContractValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifacts = build_intake_artifacts(load_phase3_config(DEMO / "demo.yaml"))

    def test_all_phase3a_artifacts_pass_registered_schemas_and_semantics(self) -> None:
        cases = {
            "input_request": self.artifacts.input_request,
            "source_corpus": self.artifacts.source_corpus,
            "source_locator_registry": self.artifacts.source_locator_registry,
            "phase3_evidence_unit_registry": self.artifacts.evidence_unit_registry,
            "source_coverage_report": self.artifacts.source_coverage_report,
        }
        for schema_name, payload in cases.items():
            with self.subTest(schema_name=schema_name):
                report = validate_artifact(payload, schema_name=schema_name)
                self.assertTrue(report.valid, report.to_human())

    def test_page_index_and_number_must_agree(self) -> None:
        payload = copy.deepcopy(self.artifacts.source_locator_registry)
        locator = next(item for item in payload["locators"] if item["locator_type"] == "pdf_text_block")
        locator["page_index"] = locator["page_number"]
        report = validate_artifact(payload, schema_name="source_locator_registry")
        self.assertFalse(report.valid)
        self.assertIn("PDF_PAGE_INDEX_MISMATCH", {issue.code for issue in report.issues})

    def test_phase3_producer_hash_mismatch_is_a_validation_error(self) -> None:
        payload = copy.deepcopy(self.artifacts.source_coverage_report)
        payload["documentary_fact_count"] += 1
        report = validate_artifact(payload, schema_name="source_coverage_report")
        self.assertFalse(report.valid)
        self.assertIn("PRODUCER_CONTENT_HASH_MISMATCH", {issue.code for issue in report.issues})

    def test_phase3b_support_artifacts_pass_registered_schemas(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml")
        planning = build_strict_planning(config, self.artifacts)
        architecture = build_architecture_artifacts(config, self.artifacts, planning)
        cases = {
            "workflow_resolution": planning.workflow_resolution,
            "source_gap_report": planning.source_gap_report,
            "evidence_allocation_report": planning.evidence_allocation_report,
            "design_invariants": architecture.design_invariants,
            "module_art_directions": architecture.module_art_directions,
            "creative_fit_report": architecture.creative_fit_report,
            "architecture_validation_report": architecture.architecture_validation_report,
        }
        for schema_name, payload in cases.items():
            with self.subTest(schema_name=schema_name):
                report = validate_artifact(payload, schema_name=schema_name)
                self.assertTrue(report.valid, report.to_human())


if __name__ == "__main__":
    unittest.main()
