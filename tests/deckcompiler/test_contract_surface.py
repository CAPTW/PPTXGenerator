from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class DeckCompilerContractSurfaceTests(unittest.TestCase):
    def test_deckcompiler_namespace_exists(self) -> None:
        package_init = SRC / "presentation_agent" / "deckcompiler" / "__init__.py"
        self.assertTrue(package_init.is_file())

    def test_deckcompiler_cli_boots_without_loading_optional_cairo_surface(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        completed = subprocess.run(
            [sys.executable, "-m", "presentation_agent.deckcompiler", "--help"],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("generate", completed.stdout)

    def test_package_import_keeps_legacy_compat_modules_lazy(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys, presentation_agent; "
                    "assert 'cairosvg' not in sys.modules; "
                    "import presentation_agent.deckcompiler.cli; "
                    "assert 'cairosvg' not in sys.modules"
                ),
            ],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
