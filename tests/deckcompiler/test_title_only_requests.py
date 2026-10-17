"""Title-only request preparation; helper skills are explicitly unit-test fixtures."""
import json
from pathlib import Path
import tempfile
import unittest

from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json,write_json
from presentation_agent.deckcompiler.orchestration.image_requests import prepare_image_requests,validate_image_request_bundle
import test_general_generate_workflow as general_fixture


class TitleOnlyRequestTests(unittest.TestCase):
    def create(self,copy,title="Coastal",missing=False):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)/"runtime"
        general_fixture.GeneralGenerateWorkflowTests()._start(root)
        p={"fixture_only":True,"approval_and_provider_lineage":"simulated unit-test approval; no generation"}
        write_json(root/"architect/workflow_design.json",p)
        write_json(root/"architect/approval_record.json",{**p,"gate1":{"status":"APPROVED","approved_by":"user"},"gate2":{"status":"APPROVED","approved_by":"user"}})
        write_json(root/"architect/design_system.json",{"global_prompt_cues":["Retain source content"],"visual_routes":[{"route_id":"retained","prompt_cues":["Flat source"]}],"layouts":[{"layout_id":"retained","prompt_cues":["Retain source composition"]}]})
        slide={"slide_number":1,"slide_id":"single-title","purpose":"Validate title-only content","title":title,"on_slide_copy":copy,"layout_id":"retained","visual_direction":"Retain source composition","presenter_notes":"Fixture only"}
        if missing:del slide["on_slide_copy"]
        write_json(root/"architect/blueprint.json",{"deck_title":"Fixture","audience":"Validation","approved_visual_route_id":"retained","slides":[slide]})
        return root

    def test_explicit_empty_containers_preserve_single_exact_title(self):
        for copy in ({},[]):
            with self.subTest(copy=copy):
                root=self.create(copy)
                prepared=prepare_image_requests(root)
                sidecar=read_json(root/"semantic_sidecars/slide-001.semantic.json")
                prompt=read_json(root/"image_requests/slide-001.prompt.json")
                self.assertEqual(sidecar["exact_title"],"Coastal")
                self.assertEqual(sidecar["exact_on_slide_copy"],copy)
                self.assertEqual(prompt["prompt_text"].count("Coastal"),1)
                report=validate_image_request_bundle(root)
                self.assertTrue(report["valid"],report)

    def test_missing_null_and_implicit_empty_copy_remain_invalid(self):
        for copy in (None,"","   ",{"subtitle":""},[""]):
            with self.subTest(copy=copy):
                with self.assertRaises(DeckCompilerError):prepare_image_requests(self.create(copy))
        with self.assertRaises(DeckCompilerError):prepare_image_requests(self.create(None,missing=True))

    def test_title_is_still_required(self):
        for title in (None,"","   "):
            with self.subTest(title=title):
                with self.assertRaises(DeckCompilerError):prepare_image_requests(self.create({},title=title))

    def test_normal_body_copy_is_preserved(self):
        copy={"subtitle":"Existing subtitle","labels":["A","B"]}
        root=self.create(copy);prepare_image_requests(root)
        self.assertEqual(read_json(root/"semantic_sidecars/slide-001.semantic.json")["exact_on_slide_copy"],copy)

    def test_post_preparation_copy_change_invalidates_binding(self):
        root=self.create({});prepare_image_requests(root)
        path=root/"architect/blueprint.json";blueprint=read_json(path)
        blueprint["slides"][0]["on_slide_copy"]={"subtitle":"Changed"};write_json(path,blueprint)
        report=validate_image_request_bundle(root)
        self.assertFalse(report["valid"],report)


if __name__=="__main__":unittest.main()
