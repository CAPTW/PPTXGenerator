from __future__ import annotations

import hashlib
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ATTRIBUTES = ROOT / ".gitattributes"

REQUIRED_BINARY_PATTERNS = {
    "*.pdf",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.ico",
    "*.pptx",
    "*.docx",
    "*.xlsx",
    "*.zip",
}

EXPECTED_PDF_HASHES = {
    "examples/deckcompiler_demo/inputs/cooling_system_overview.pdf":
        "b72c5cbe32f36b1311c618e968d075bc6a921b0380085987e7d17d03a6556d68",
    "examples/deckcompiler_demo/inputs/cooling_risk_decision_report.pdf":
        "912228a063639e78287499c1490a478f6dad590b10a093274b72a0df301775fc",
    "examples/deckcompiler_demo/negative_inputs/malformed.pdf":
        "85a4088661a0b60c987f222df56f01eff17c84db9e34198329fd353840737910",
    "examples/reference-packs/executive-neutral-local/assets/report-sample.pdf":
        "68727bb694fe13fb592b0f59705bba9f72f6e2a5a525902093d5cdd806d30521",
}


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


class GitAttributesBinaryPolicyTests(unittest.TestCase):
    def test_root_attributes_define_only_focused_binary_policy(self) -> None:
        self.assertTrue(ATTRIBUTES.is_file())
        active_lines = [
            line.strip()
            for line in ATTRIBUTES.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        policy = {line.split()[0]: line.split()[1:] for line in active_lines}
        for pattern in REQUIRED_BINARY_PATTERNS:
            self.assertEqual(policy.get(pattern), ["-text"], pattern)
        self.assertFalse(any(line.startswith("* ") for line in active_lines))
        self.assertFalse(
            any(
                line.startswith("*.pdf ") and line != "*.pdf   -text"
                for line in active_lines
            )
        )

    def test_every_tracked_pdf_is_non_text_and_matches_head_blob(self) -> None:
        pdfs = git("ls-files", "*.pdf").splitlines()
        self.assertTrue(pdfs)
        for relative_path in pdfs:
            attribute = git("check-attr", "text", "--", relative_path)
            self.assertTrue(attribute.endswith("text: unset"), attribute)
            head_blob = git("rev-parse", f"HEAD:{relative_path}")
            raw_worktree_blob = git(
                "hash-object",
                "--no-filters",
                "--",
                str(ROOT / relative_path),
            )
            self.assertEqual(raw_worktree_blob, head_blob, relative_path)

    def test_selected_pdf_hashes_are_stable(self) -> None:
        for relative_path, expected_hash in EXPECTED_PDF_HASHES.items():
            actual_hash = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
            self.assertEqual(actual_hash, expected_hash, relative_path)


if __name__ == "__main__":
    unittest.main()
