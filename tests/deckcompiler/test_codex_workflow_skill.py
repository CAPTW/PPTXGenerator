from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
SKILL_ROOT = ROOT / ".agents" / "skills" / "pptx-generator-workflow"
ARCHITECT_ROOT = ROOT / ".agents" / "skills" / "pptx-workflow-architect"


class CodexWorkflowSkillTests(unittest.TestCase):
    def test_repo_dispatch_requires_workflow_architect_first(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        first = text.index("pptx-workflow-architect")
        image = text.index("image_gen.imagegen")
        reconstruction = text.index("slide-editable-deck-orchestrator")
        self.assertLess(first, image)
        self.assertLess(first, reconstruction)
        self.assertIn("must not silently bypass approval", text)
        self.assertIn("Do not force a fixed slide count", text)

    def test_skill_dependency_order_is_machine_readable(self) -> None:
        dependencies = json.loads(
            (SKILL_ROOT / "dependencies.json").read_text(encoding="utf-8")
        )
        ordered = dependencies["ordered_dependencies"]
        self.assertEqual(
            [(row["invocation_order"], row["skill_name"]) for row in ordered],
            [
                (1, "pptx-workflow-architect"),
                (2, "imagegen"),
                (3, "slide-editable-deck-orchestrator"),
                (4, "slide-text-layer-inpaint"),
                (5, "slide-image-dual-render"),
                (6, "slide-visual-polish-qa"),
            ],
        )
        self.assertEqual(ordered[1]["platform_tool_id"], "image_gen.imagegen")
        self.assertEqual(ordered[0]["distribution"], "repository_owned")
        self.assertEqual(
            ordered[0]["skill_path"],
            ".agents/skills/pptx-workflow-architect/SKILL.md",
        )
        self.assertEqual(
            ordered[0]["package_files"],
            [
                "SKILL.md",
                "references/design-system.md",
                "references/large-deck.md",
                "references/production-qa.md",
            ],
        )
        self.assertEqual(ordered[2]["default_quality_level"], "polish")
        self.assertEqual(ordered[4]["renderer_quality"], "reconstruction")
        self.assertTrue(ordered[5]["source_slide_mapping_required"])
        self.assertEqual(
            dependencies["completion_requirements"]["visual_qa_blocking_count"],
            0,
        )
        self.assertEqual(
            dependencies["completion_requirements"]["initial_full_deck_visual_qa"],
            "PASS",
        )
        self.assertEqual(
            dependencies["completion_requirements"][
                "final_visual_qa_output_hash_binding"
            ],
            "PASS",
        )

    def test_live_skill_requires_real_generation_and_repair_loop(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Use the built-in `image_gen.imagegen` tool", text)
        self.assertIn("one call per slide", text)
        self.assertIn("zero fail/blocking slides", text)
        self.assertIn("skillset_execution_plan.json", text)
        self.assertIn("--quality reconstruction", text)
        self.assertIn("--source-slides", text)
        self.assertIn("initial full-deck", text)
        self.assertIn("final all-slide", text)
        self.assertIn("CONTINUE", text.upper())
        self.assertNotIn("exactly six slides", text.lower())

    def test_repository_contains_complete_workflow_architect_package(self) -> None:
        expected = {
            "SKILL.md",
            "references/design-system.md",
            "references/large-deck.md",
            "references/production-qa.md",
        }
        actual = {
            path.relative_to(ARCHITECT_ROOT).as_posix()
            for path in ARCHITECT_ROOT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(actual, expected)
        skill = (ARCHITECT_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for relative in sorted(expected - {"SKILL.md"}):
            self.assertIn(relative, skill)


if __name__ == "__main__":
    unittest.main()
