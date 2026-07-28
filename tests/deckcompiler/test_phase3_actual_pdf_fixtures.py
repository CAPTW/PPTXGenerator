from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


DEMO = ROOT / "examples" / "deckcompiler_demo"
INPUTS = DEMO / "inputs"
EXPECTED = DEMO / "expected" / "phase3" / "pdf_fixtures.json"


class Phase3ActualPdfFixtureTests(unittest.TestCase):
    def test_canonical_pdfs_are_distinct_searchable_repository_authored_documents(self) -> None:
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
        payloads: list[bytes] = []
        for filename, record in expected["pdfs"].items():
            path = INPUTS / filename
            payload = path.read_bytes()
            payloads.append(payload)
            self.assertGreater(len(payload), 0)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), record["sha256"])
            with pymupdf.open(path) as document:
                self.assertEqual(document.page_count, record["page_count"])
                page_texts = [page.get_text("text").strip() for page in document]
                self.assertTrue(all(page_texts))
                joined = "\n".join(page_texts)
                self.assertIn(record["title_token"], joined)
                self.assertIn(record["section_token"], joined)
                self.assertEqual(
                    [hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest() for text in page_texts],
                    record["normalized_page_text_sha256"],
                )
                metadata = document.metadata
                self.assertIn("repository-authored", metadata.get("keywords", "").lower())
                self.assertNotIn("http", json.dumps(metadata).lower())
        self.assertNotEqual(payloads[0], payloads[1])

    def test_negative_scanned_pdf_has_visible_page_but_no_text_layer(self) -> None:
        path = DEMO / "negative_inputs" / "scanned_image_only.pdf"
        with pymupdf.open(path) as document:
            self.assertEqual(document.page_count, 1)
            self.assertEqual(document[0].get_text("text").strip(), "")
            self.assertGreaterEqual(len(document[0].get_images(full=True)), 1)

    def test_negative_malformed_pdf_is_not_parseable(self) -> None:
        path = DEMO / "negative_inputs" / "malformed.pdf"
        self.assertGreater(path.stat().st_size, 0)
        with self.assertRaises(Exception):
            pymupdf.open(path)


if __name__ == "__main__":
    unittest.main()
