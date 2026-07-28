from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PATH = ROOT / "scripts" / "install_pngtopptx_skillset.py"
SPEC = importlib.util.spec_from_file_location("install_pngtopptx_skillset", INSTALLER_PATH)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def _records_hash(records: list[dict]) -> str:
    return hashlib.sha256(
        json.dumps(
            records,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _fixture_pin(skill_root: Path) -> dict:
    skill_name = "fixture-skill"
    records = []
    files = []
    skill_directory = skill_root / skill_name
    for path in sorted(
        skill_directory.rglob("*"),
        key=lambda item: item.relative_to(skill_directory).as_posix(),
    ):
        if not path.is_file():
            continue
        data = path.read_bytes()
        relative = path.relative_to(skill_directory).as_posix()
        record = {
            "skill_name": skill_name,
            "relative_path": relative,
            "byte_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        records.append(record)
        files.append(dict(record))
    aggregate = _records_hash(records)
    return {
        "skill_names": [skill_name],
        "combined_aggregate_sha256": aggregate,
        "inventory": [
            {
                "skill_name": skill_name,
                "file_count": len(files),
                "aggregate_sha256": aggregate,
                "files": files,
            }
        ],
    }


class PngToPptxInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        skill = self.source / "fixture-skill"
        (skill / "scripts").mkdir(parents=True)
        (skill / "SKILL.md").write_text("# fixture\n", encoding="utf-8", newline="\n")
        (skill / "scripts" / "run.py").write_text(
            "print('ok')\n", encoding="utf-8", newline="\n"
        )
        self.pin = _fixture_pin(self.source)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_01_missing_installation_is_detected(self) -> None:
        result = installer.inspect_installation(self.root / "target", self.pin)
        self.assertEqual(result["status"], "MISSING")

    def test_02_exact_installation_passes(self) -> None:
        target = self.root / "target"
        target.mkdir()
        shutil.copytree(self.source / "fixture-skill", target / "fixture-skill")
        result = installer.inspect_installation(target, self.pin)
        self.assertEqual(result["status"], "PASS")

    def test_03_modified_installation_fails_closed(self) -> None:
        target = self.root / "target"
        target.mkdir()
        shutil.copytree(self.source / "fixture-skill", target / "fixture-skill")
        changed = target / "fixture-skill" / "SKILL.md"
        changed.write_text("# changed\n", encoding="utf-8", newline="\n")
        result = installer.inspect_installation(target, self.pin)
        self.assertEqual(result["status"], "MISMATCH")
        self.assertIn("SKILL.md", result["skills"][0]["content_mismatch"])

    def test_04_public_pin_binds_installer_commit_and_four_trees(self) -> None:
        pin = installer.load_pin()
        self.assertIn(
            installer.PINNED_SOURCE_COMMIT,
            pin["candidate_commits"],
        )
        self.assertEqual(len(pin["skill_names"]), 4)
        self.assertEqual(set(pin["skill_names"]), set(pin["source_tree_oids"]))
        self.assertEqual(
            pin["combined_aggregate_sha256"],
            "027336f1a61641bfb6e891199fe24ab77aee0c31287c7e8d88613a458310e529",
        )

    def test_05_repository_local_target_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            installer.SkillsetInstallError,
            "PNGTPPTX_TARGET_INSIDE_REPOSITORY",
        ):
            installer._reject_repository_target(ROOT / "installed-skills")

    def test_06_codex_home_is_used_when_no_explicit_skill_root_exists(self) -> None:
        codex_home = self.root / "codex-home"
        with mock.patch.dict(
            os.environ,
            {"CODEX_HOME": str(codex_home)},
            clear=True,
        ):
            self.assertEqual(
                installer._default_target_root(),
                codex_home / "skills",
            )


if __name__ == "__main__":
    unittest.main()
