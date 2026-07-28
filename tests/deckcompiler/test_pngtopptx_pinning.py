from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from presentation_agent.deckcompiler.pngtopptx_pinning import (
    EXPECTED_SKILLS,
    PinningError,
    build_external_skillset_pin,
    build_installation_inventory,
    canonical_text_linkage_hash,
    validate_external_skillset_pin,
    validate_pin_claims,
)
from presentation_agent.deckcompiler.schemas import validator_for


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PNGtoPPTXPinningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.installation = self.root / "installed"
        self.expected_hashes: dict[str, str] = {}
        for index, skill in enumerate(EXPECTED_SKILLS, start=1):
            skill_root = self.installation / skill
            (skill_root / "scripts").mkdir(parents=True)
            skill_bytes = f"---\nname: {skill}\n---\nfixture {index}\n".encode()
            (skill_root / "SKILL.md").write_bytes(skill_bytes)
            (skill_root / "scripts" / "run.py").write_text(
                f"print({index})\n", encoding="utf-8", newline="\n"
            )
            self.expected_hashes[skill] = _sha(skill_bytes)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _git(self, repository: Path, *args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repository), *args], text=True
        ).strip()

    def _source_repository(self, *, two_commits: bool = False) -> Path:
        repository = self.root / "source"
        repository.mkdir()
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        self._git(repository, "config", "user.name", "DeckCompiler Tests")
        self._git(repository, "config", "user.email", "deckcompiler@example.invalid")
        self._git(
            repository,
            "remote",
            "add",
            "origin",
            "https://github.com/CAPTW/pngtopptx.git",
        )
        for skill in EXPECTED_SKILLS:
            source_root = repository / "skills" / skill
            source_root.mkdir(parents=True)
            for installed in sorted((self.installation / skill).rglob("*")):
                if installed.is_file() and "__pycache__" not in installed.parts:
                    relative = installed.relative_to(self.installation / skill)
                    target = source_root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(installed.read_bytes().replace(b"\r\n", b"\n"))
        (repository / "README.md").write_text("fixture\n", encoding="utf-8")
        self._git(repository, "add", ".")
        self._git(repository, "commit", "-q", "-m", "fixture skillset")
        if two_commits:
            (repository / "README.md").write_text("fixture two\n", encoding="utf-8")
            self._git(repository, "add", "README.md")
            self._git(repository, "commit", "-q", "-m", "docs only")
        return repository

    def _pin(self, **overrides):
        arguments = {
            "installation_root": self.installation,
            "deckcompiler_commit": "3d3ad0c101a6f2cec390597da2ea52dd5ac55e3d",
            "expected_skill_hashes": self.expected_hashes,
            "created_at": "2026-07-20T12:00:00+09:00",
            "timezone": "Asia/Seoul",
        }
        arguments.update(overrides)
        return build_external_skillset_pin(**arguments)

    def test_01_four_expected_skills_are_present(self) -> None:
        inventory = build_installation_inventory(
            self.installation, expected_skill_hashes=self.expected_hashes
        )
        self.assertEqual(
            [skill["skill_name"] for skill in inventory["skills"]],
            sorted(EXPECTED_SKILLS),
        )

    def test_02_known_skill_hashes_match(self) -> None:
        inventory = build_installation_inventory(
            self.installation, expected_skill_hashes=self.expected_hashes
        )
        self.assertTrue(inventory["known_skill_hashes_match"])

    def test_03_missing_skill_blocks(self) -> None:
        missing = self.installation / EXPECTED_SKILLS[0]
        for path in sorted(missing.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
        missing.rmdir()
        with self.assertRaisesRegex(PinningError, "MISSING_SKILL"):
            build_installation_inventory(
                self.installation, expected_skill_hashes=self.expected_hashes
            )

    def test_04_modified_skill_md_blocks(self) -> None:
        skill = EXPECTED_SKILLS[0]
        (self.installation / skill / "SKILL.md").write_text("modified\n", encoding="utf-8")
        with self.assertRaisesRegex(PinningError, "SKILL_HASH_MISMATCH"):
            build_installation_inventory(
                self.installation, expected_skill_hashes=self.expected_hashes
            )

    def test_05_unexpected_executable_extra_blocks(self) -> None:
        source = self._source_repository()
        rogue = self.installation / EXPECTED_SKILLS[0] / "scripts" / "rogue.ps1"
        rogue.write_text("Write-Output rogue\n", encoding="utf-8")
        with self.assertRaisesRegex(PinningError, "UNEXPECTED_SOURCE_EXTRA"):
            self._pin(source_repository=source)

    def test_06_cache_extra_does_not_change_fingerprint(self) -> None:
        before = build_installation_inventory(
            self.installation, expected_skill_hashes=self.expected_hashes
        )
        cache = self.installation / EXPECTED_SKILLS[0] / "scripts" / "__pycache__"
        cache.mkdir()
        (cache / "run.cpython-311.pyc").write_bytes(b"cache")
        after = build_installation_inventory(
            self.installation, expected_skill_hashes=self.expected_hashes
        )
        self.assertEqual(
            before["combined_aggregate_sha256"], after["combined_aggregate_sha256"]
        )
        self.assertEqual(after["excluded_file_count"], 1)

    def test_07_inventory_order_is_deterministic(self) -> None:
        first = build_installation_inventory(
            self.installation, expected_skill_hashes=self.expected_hashes
        )
        second = build_installation_inventory(
            self.installation, expected_skill_hashes=self.expected_hashes
        )
        self.assertEqual(first["skills"], second["skills"])

    def test_08_combined_hash_is_deterministic(self) -> None:
        hashes = {
            build_installation_inventory(
                self.installation, expected_skill_hashes=self.expected_hashes
            )["combined_aggregate_sha256"]
            for _ in range(3)
        }
        self.assertEqual(len(hashes), 1)

    def test_09_raw_installed_hashes_are_recorded(self) -> None:
        inventory = build_installation_inventory(
            self.installation, expected_skill_hashes=self.expected_hashes
        )
        first = inventory["skills"][0]
        skill_md = next(
            record for record in first["files"] if record["relative_path"] == "SKILL.md"
        )
        self.assertEqual(
            skill_md["sha256"],
            _sha((self.installation / first["skill_name"] / "SKILL.md").read_bytes()),
        )

    def test_10_text_linkage_normalization_does_not_replace_execution_pin(self) -> None:
        lf = b"line one\nline two\n"
        crlf = b"line one\r\nline two\r\n"
        self.assertEqual(canonical_text_linkage_hash(lf), canonical_text_linkage_hash(crlf))
        self.assertNotEqual(_sha(lf), _sha(crlf))

    def test_11_git_revision_claim_requires_evidence(self) -> None:
        payload = self._pin()
        payload["source_commit"] = "deadbeef"
        with self.assertRaisesRegex(PinningError, "UNSUPPORTED_GIT_REVISION_CLAIM"):
            validate_pin_claims(payload)

    def test_12_ambiguous_commits_cannot_be_claimed_as_unique(self) -> None:
        source = self._source_repository(two_commits=True)
        payload = self._pin(source_repository=source)
        self.assertEqual(payload["pinning_mode"], "git_tree_pin")
        self.assertIsNone(payload["source_commit"])
        self.assertEqual(len(payload["candidate_commits"]), 2)
        self.assertFalse(payload["git_revision_verified"])

    def test_13_fingerprint_bundle_fallback_is_execution_eligible(self) -> None:
        payload = self._pin()
        self.assertEqual(payload["pinning_mode"], "installation_fingerprint_bundle_v1")
        self.assertTrue(payload["installation_bundle_verified"])
        self.assertTrue(payload["execution_allowed"])
        self.assertTrue(payload["final_provenance_limitation"])

    def test_14_pin_artifact_is_schema_valid(self) -> None:
        payload = self._pin()
        self.assertEqual(
            list(validator_for("external_skillset_pin").iter_errors(payload)), []
        )

    def test_15_mutation_after_pin_is_detected(self) -> None:
        payload = self._pin()
        target = self.installation / EXPECTED_SKILLS[-1] / "scripts" / "run.py"
        target.write_text("print('mutated')\n", encoding="utf-8")
        with self.assertRaisesRegex(PinningError, "INSTALLATION_MUTATED"):
            validate_external_skillset_pin(
                self.installation,
                payload,
                expected_skill_hashes=self.expected_hashes,
            )

    def test_16_symlink_or_reparse_path_blocks(self) -> None:
        with mock.patch(
            "presentation_agent.deckcompiler.pngtopptx_pinning._is_reparse_or_symlink",
            return_value=True,
        ):
            with self.assertRaisesRegex(PinningError, "REPARSE_POINT_BLOCKED"):
                build_installation_inventory(
                    self.installation, expected_skill_hashes=self.expected_hashes
                )

    def test_17_pinning_does_not_modify_external_files(self) -> None:
        def snapshot() -> dict[str, str]:
            return {
                path.relative_to(self.installation).as_posix(): _sha(path.read_bytes())
                for path in sorted(self.installation.rglob("*"))
                if path.is_file()
            }

        before = snapshot()
        payload = self._pin(source_repository=self._source_repository())
        after = snapshot()
        self.assertEqual(before, after)
        self.assertTrue(payload["external_skill_modified"] is False)


if __name__ == "__main__":
    unittest.main()
