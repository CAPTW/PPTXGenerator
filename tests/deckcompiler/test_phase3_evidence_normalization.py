from __future__ import annotations

import collections
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.evidence.normalization import validate_evidence_graph
from presentation_agent.deckcompiler.intake.config import load_phase3_config
from presentation_agent.deckcompiler.intake.multi_source import build_intake_artifacts


DEMO = ROOT / "examples" / "deckcompiler_demo"


class Phase3EvidenceNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifacts = build_intake_artifacts(load_phase3_config(DEMO / "demo.yaml"))
        self.evidence = self.artifacts.evidence_unit_registry["evidence_units"]

    def test_canonical_fixture_meets_source_backed_evidence_floor(self) -> None:
        counts = collections.Counter(item["evidence_type"] for item in self.evidence)
        self.assertGreaterEqual(counts["intent"], 1)
        self.assertGreaterEqual(counts["definition"], 2)
        self.assertGreaterEqual(counts["process"], 2)
        self.assertGreaterEqual(counts["claim"], 4)
        self.assertGreaterEqual(counts["statistic"], 2)
        self.assertGreaterEqual(counts["comparison"], 2)
        self.assertGreaterEqual(counts["recommendation"], 1)
        self.assertGreaterEqual(counts["limitation"], 1)
        factual = [item for item in self.evidence if item["factuality_class"] == "documentary_fact"]
        self.assertGreaterEqual(len(factual), 12)
        contributions = collections.Counter(item["source_id"] for item in factual)
        pdf_ids = {
            item["source_id"] for item in self.artifacts.source_corpus["sources"] if item["source_type"] == "pdf"
        }
        self.assertEqual(set(contributions), pdf_ids)
        self.assertTrue(all(contributions[source_id] >= 4 for source_id in pdf_ids))

    def test_prompt_is_intent_not_documentary_evidence(self) -> None:
        prompt_id = next(
            item["source_id"] for item in self.artifacts.source_corpus["sources"] if item["source_type"] == "user_prompt"
        )
        prompt_items = [item for item in self.evidence if item["source_id"] == prompt_id]
        self.assertTrue(prompt_items)
        self.assertTrue(all(item["factuality_class"] == "instruction" for item in prompt_items))
        self.assertFalse(any(item["citation_metadata"]["documentary"] for item in prompt_items))

    def test_every_documentary_fact_has_exact_resolvable_pdf_locator(self) -> None:
        locator_ids = {item["locator_id"] for item in self.artifacts.source_locator_registry["locators"]}
        for item in self.evidence:
            if item["factuality_class"] != "documentary_fact":
                continue
            self.assertTrue(item["source_locator_ids"])
            self.assertTrue(set(item["source_locator_ids"]).issubset(locator_ids))
            self.assertGreaterEqual(item["source_locator"]["page_number"], 1)
            self.assertEqual(item["source_locator"]["page_number"], item["source_locator"]["page_index"] + 1)

    def test_statistics_preserve_value_unit_and_context(self) -> None:
        statistics = [item for item in self.evidence if item["evidence_type"] == "statistic"]
        self.assertTrue(statistics)
        for item in statistics:
            data = item["canonical_content"]["data"]
            self.assertIn("value", data)
            self.assertTrue(data["unit"])
            self.assertTrue(data["context"])

    def test_unknown_relation_and_locator_source_mismatch_fail(self) -> None:
        first = self.evidence[0]
        invalid_relation = {**first, "relations": [{"relation_type": "supports", "target_evidence_id": "ev_00000000000000000000"}]}
        with self.assertRaisesRegex(ValueError, "UNKNOWN_EVIDENCE_RELATION"):
            validate_evidence_graph(
                {**self.artifacts.evidence_unit_registry, "evidence_units": [invalid_relation]},
                self.artifacts.source_corpus,
                self.artifacts.source_locator_registry,
            )
        invalid_locator = {**first, "source_locator": {**first["source_locator"], "source_id": "src_00000000000000000000"}}
        with self.assertRaisesRegex(ValueError, "LOCATOR_SOURCE_MISMATCH"):
            validate_evidence_graph(
                {**self.artifacts.evidence_unit_registry, "evidence_units": [invalid_locator]},
                self.artifacts.source_corpus,
                self.artifacts.source_locator_registry,
            )


if __name__ == "__main__":
    unittest.main()
