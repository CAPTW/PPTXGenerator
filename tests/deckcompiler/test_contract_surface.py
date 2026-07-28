from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
