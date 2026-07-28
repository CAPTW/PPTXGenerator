from __future__ import annotations

import sys
import unittest
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.deckcompiler.architecture.creative_frontend_adapter import build_architecture_artifacts
from presentation_agent.deckcompiler.architecture.validation import validate_phase3_architecture_graph
from presentation_agent.deckcompiler.intake.config import load_phase3_config
from presentation_agent.deckcompiler.intake.multi_source import build_intake_artifacts
from presentation_agent.deckcompiler.planning.strict_adapter import build_strict_planning
from presentation_agent.deckcompiler.validation import validate_artifact
from presentation_agent.generator_contracts import validateCreativeTemplateArchitecture, validatePresentationArchitecture


DEMO = ROOT / "examples" / "deckcompiler_demo"


class Phase3ArchitectureIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_phase3_config(DEMO / "demo.yaml")
        self.intake = build_intake_artifacts(self.config)
        self.planning = build_strict_planning(self.config, self.intake)
        self.architecture = build_architecture_artifacts(self.config, self.intake, self.planning)

    def test_existing_presentation_architecture_builder_preserves_six_slide_order_and_evidence(self) -> None:
        presentation = self.architecture.presentation_architecture
        validatePresentationArchitecture(presentation)
        slide_ids = [slide["slide_id"] for slide in self.planning.slide_blueprint_collection["slides"]]
        self.assertEqual([slide["slide_id"] for slide in presentation["slides"]], slide_ids)
        self.assertGreaterEqual(len(presentation["modules"]), 2)
        self.assertGreaterEqual(sum(len(module["batches"]) for module in presentation["modules"]), 2)
        self.assertFalse(presentation["policies"]["allow_full_slide_raster"])
        self.assertTrue(presentation["policies"]["slot_binding_required"])
        self.assertEqual(self.architecture.architecture_validation_report["orphan_slide_ids"], [])
        self.assertTrue(self.architecture.architecture_validation_report["module_ranges_contiguous"])
        self.assertTrue(self.architecture.architecture_validation_report["batch_ranges_contiguous"])
        self.assertEqual(self.architecture.architecture_validation_report["slide_assignment_count"], 6)
        validate_phase3_architecture_graph(self.intake, self.planning, self.architecture)

    def test_design_invariants_and_distinct_module_art_directions_are_complete(self) -> None:
        invariants = set(self.architecture.design_invariants["invariants"])
        self.assertIn("full-slide raster forbidden", invariants)
        self.assertIn("native slot binding required", invariants)
        self.assertIn("source traceability", invariants)
        directions = self.architecture.module_art_directions["modules"]
        self.assertEqual(len(directions), len(self.architecture.presentation_architecture["modules"]))
        self.assertEqual(len({item["module_id"] for item in directions}), len(directions))
        self.assertEqual(len({item["visual_metaphor"] for item in directions}), len(directions))
        for item in directions:
            self.assertTrue(item["narrative_objective"])
            self.assertTrue(item["composition_energy"])
            self.assertTrue(item["density_range"])
            self.assertTrue(item["forbidden_visual_patterns"])

    def test_planning_level_creative_architecture_has_candidates_and_safe_fit_decisions(self) -> None:
        creative = self.architecture.creative_template_architecture
        validateCreativeTemplateArchitecture(creative)
        for module in creative["modules"]:
            for batch in module["batch_template_families"]:
                self.assertGreaterEqual(len(batch["candidate_family_ids"]), 2)
                self.assertTrue(set(batch["selected_family_ids"]).issubset(batch["candidate_family_ids"]))
        decisions = creative["slide_fit_decisions"]
        self.assertEqual(len(decisions), 6)
        for decision in decisions:
            self.assertEqual(decision["scores"]["semantic"], 1.0)
            self.assertEqual(decision["scores"]["editability"], 1.0)
            self.assertGreaterEqual(decision["scores"]["capacity"], 0.8)
            self.assertEqual(decision["status"], "pass")
        layout_ids = [item["layout_id"] for item in decisions]
        for index in range(len(layout_ids) - 2):
            self.assertNotEqual(layout_ids[index : index + 3], [layout_ids[index]] * 3)
        actions = self.architecture.creative_fit_report["decisions"]
        self.assertFalse(any(item["forbidden_action_detected"] for item in actions))
        self.assertFalse(self.architecture.creative_fit_report["repair_executed"])

    def test_all_documentary_sources_remain_represented_after_architecture(self) -> None:
        source_counts = Counter(self.architecture.architecture_validation_report["documentary_source_slide_counts"])
        expected = {
            item["source_id"] for item in self.intake.source_corpus["sources"] if item["source_type"] == "pdf"
        }
        self.assertEqual(set(source_counts), expected)
        self.assertTrue(all(count > 0 for count in source_counts.values()))

    def test_unknown_evidence_and_reordered_slides_fail_cross_artifact_validation(self) -> None:
        unknown = deepcopy(self.architecture.presentation_architecture)
        unknown["slides"][0]["evidence_ids"] = ["ev_00000000000000000000"]
        with self.assertRaises(ValueError):
            validate_phase3_architecture_graph(
                self.intake,
                self.planning,
                replace(self.architecture, presentation_architecture=unknown),
            )

        reordered = deepcopy(self.architecture.presentation_architecture)
        reordered["slides"][0], reordered["slides"][1] = reordered["slides"][1], reordered["slides"][0]
        with self.assertRaises(ValueError):
            validate_phase3_architecture_graph(
                self.intake,
                self.planning,
                replace(self.architecture, presentation_architecture=reordered),
            )

    def test_declared_orphan_artifact_fails_graph_schema(self) -> None:
        payload = {
            "schema_name": "phase3_artifact_graph",
            "schema_version": "1.0.0",
            "artifact": self.intake.source_corpus["artifact"],
            "graph_id": "graph_00000000000000000000",
            "run_id": self.intake.input_request["run_id"],
            "nodes": [],
            "edges": [],
            "root_artifact_ids": [self.intake.input_request["artifact"]["artifact_id"]],
            "orphan_artifact_ids": [self.intake.source_corpus["artifact"]["artifact_id"]],
            "validation_status": "valid",
        }
        report = validate_artifact(payload, schema_name="phase3_artifact_graph")
        self.assertFalse(report.valid)
        self.assertIn("orphan_artifact_ids", report.to_human())


if __name__ == "__main__":
    unittest.main()
