from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from presentation_agent.compiler.blueprint_adapter import validate_slide_blueprint_collection
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.intake.config import load_phase3_config
from presentation_agent.deckcompiler.intake.multi_source import build_intake_artifacts
from presentation_agent.deckcompiler.planning.strict_adapter import build_strict_planning
from presentation_agent.deckcompiler.validation import validate_artifact
from presentation_agent.generator_contracts import validatePresentationPlan, validateSlideBlueprint


DEMO = ROOT / "examples" / "deckcompiler_demo"


class Phase3StrictPlanningAdapterTests(unittest.TestCase):
    def test_canonical_pdf_mode_produces_exactly_six_strict_source_bound_blueprints(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml")
        intake = build_intake_artifacts(config)
        planning = build_strict_planning(config, intake)

        validatePresentationPlan(planning.presentation_plan)
        self.assertEqual(planning.presentation_plan["slide_count_target"], 6)
        self.assertEqual(len(planning.slide_blueprint_collection["slides"]), 6)
        validate_slide_blueprint_collection(planning.slide_blueprint_collection)
        self.assertTrue(
            validate_artifact(
                planning.slide_blueprint_collection,
                schema_name="slide_blueprint_collection",
            ).valid
        )
        for slide in planning.slide_blueprint_collection["slides"]:
            validateSlideBlueprint(slide)
        slide_ids = [slide["slide_id"] for slide in planning.slide_blueprint_collection["slides"]]
        self.assertEqual(len(slide_ids), len(set(slide_ids)))
        self.assertEqual(slide_ids, planning.evidence_allocation_report["ordered_slide_ids"])

        evidence_ids = {item["evidence_id"] for item in intake.evidence_unit_registry["evidence_units"]}
        for binding in planning.slide_blueprint_collection["evidence_bindings"]:
            self.assertTrue(set(binding["evidence_ids"]).issubset(evidence_ids))
        objectives = [item["primary_objective"] for item in planning.evidence_allocation_report["slides"]]
        self.assertEqual(len(objectives), len(set(objectives)))
        represented_sources = set(planning.evidence_allocation_report["represented_documentary_source_ids"])
        expected_sources = {
            item["source_id"] for item in intake.source_corpus["sources"] if item["source_type"] == "pdf"
        }
        self.assertEqual(represented_sources, expected_sources)

    def test_workflow_alias_is_honored_through_existing_contract_matrix(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml")
        planning = build_strict_planning(config, build_intake_artifacts(config))
        resolution = planning.workflow_resolution
        self.assertEqual(resolution["requested_workflow"], "decision_brief")
        self.assertEqual(resolution["mapped_workflow_option"], "tight-main-story")
        self.assertEqual(resolution["contract_status"], "honored")
        self.assertEqual(resolution["resolution_code"], "request-honored")
        self.assertTrue(resolution["existing_contract_matrix_used"])

    def test_incompatible_workflow_fails_before_strict_planning(self) -> None:
        config = load_phase3_config(DEMO / "demo.yaml").model_copy(update={"workflow": "modular_briefing"})
        with self.assertRaisesRegex(DeckCompilerError, "DC_WORKFLOW_INCOMPATIBLE") as raised:
            build_strict_planning(config, build_intake_artifacts(config))
        self.assertEqual(raised.exception.stage, "workflow_resolution")

    def test_prompt_only_generic_topic_has_six_slides_no_documentary_claims_or_cooling_hardcode(self) -> None:
        config = load_phase3_config(DEMO / "prompt_only.yaml")
        intake = build_intake_artifacts(config)
        planning = build_strict_planning(config, intake)
        self.assertEqual(len(planning.slide_blueprint_collection["slides"]), 6)
        serialized = json.dumps(
            {
                "plan": planning.presentation_plan,
                "collection": planning.slide_blueprint_collection,
                "allocation": planning.evidence_allocation_report,
            },
            ensure_ascii=False,
        ).lower()
        self.assertNotIn("cooling", serialized)
        self.assertIn("microgrid", serialized)
        self.assertEqual(planning.source_gap_report["documentary_evidence_status"], "absent")
        self.assertTrue(planning.source_gap_report["gaps"])
        self.assertEqual(planning.evidence_allocation_report["represented_documentary_source_ids"], [])
        self.assertTrue(
            all(item["claim_origin"] in {"prompt_derived", "inference"} for item in planning.evidence_allocation_report["slides"])
        )


if __name__ == "__main__":
    unittest.main()
