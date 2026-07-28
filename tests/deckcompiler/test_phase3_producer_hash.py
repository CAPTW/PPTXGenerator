from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.provenance import semantic_content_sha256, verify_artifact_content_hash
from presentation_agent.deckcompiler.intake.config import load_phase3_config
from presentation_agent.deckcompiler.intake.multi_source import build_intake_artifacts


DEMO = ROOT / "examples" / "deckcompiler_demo"


class Phase3ProducerHashTests(unittest.TestCase):
    def test_actual_payload_hash_matches_and_rejects_mutation(self) -> None:
        payload = build_intake_artifacts(load_phase3_config(DEMO / "demo.yaml")).source_corpus
        verify_artifact_content_hash(payload)
        changed = copy.deepcopy(payload)
        changed["normalized_segments"][0]["canonical_text"] += " changed"
        with self.assertRaisesRegex(ValueError, "DC_PRODUCER_CONTENT_HASH_MISMATCH"):
            verify_artifact_content_hash(changed)

    def test_runtime_fields_and_key_order_do_not_change_semantic_hash(self) -> None:
        payload = build_intake_artifacts(load_phase3_config(DEMO / "demo.yaml")).source_corpus
        changed = copy.deepcopy(payload)
        changed["run_id"] = "run_different"
        changed["artifact"]["provenance"]["created_at"] = "2099-01-01T00:00:00Z"
        reversed_keys = {key: changed[key] for key in reversed(changed)}
        self.assertEqual(semantic_content_sha256(payload), semantic_content_sha256(reversed_keys))


if __name__ == "__main__":
    unittest.main()
