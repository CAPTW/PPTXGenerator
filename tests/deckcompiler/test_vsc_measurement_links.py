"""Real retained-image association regression, with no invented image/geometry.

Set VSC_LINK_FIXTURE_ROOT to the preserved, explicitly labeled integration run.
Tests copy that run and mutate only negative-test inputs. They do not run a
provider, claim a new user approval, or qualify renderer output.
"""
from pathlib import Path
import copy, hashlib, json, os, shutil, tempfile, unittest
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json,write_json
from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import prepare_reconstruction_job
from presentation_agent.deckcompiler.orchestration.semantic_geometry_binding import bind_semantic_geometry
from presentation_agent.deckcompiler.orchestration.vsc_measurement_links import prepare_vsc_associations

FIXTURE=os.environ.get('VSC_LINK_FIXTURE_ROOT')

@unittest.skipUnless(FIXTURE,'requires preserved VSC_LINK_FIXTURE_ROOT; no synthetic replacement')
class VscMeasurementLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'run'; shutil.copytree(FIXTURE,self.root)
        self.work=self.root/'pngtopptx-project/work/slide01'
        self.job=read_json(self.work/'reconstruction_job.json')
        self.association_path=self.work/'semantic_geometry_associations.json'
        self.association=read_json(self.association_path)
        self.review_path=self.root/self.association['vsc_identity_review']['path']
        self.review=read_json(self.review_path)
        self.accepted=read_json(self.root/'image_batches/accepted/slide-001.json')

    def bind(self): return bind_semantic_geometry(self.root,self.job,self.work)
    def save_review(self):
        write_json(self.review_path,self.review)
        self.association['vsc_identity_review']['sha256']=hashlib.sha256(self.review_path.read_bytes()).hexdigest()
        write_json(self.association_path,self.association)
    def assert_rejected(self,pattern):
        with self.assertRaisesRegex(DeckCompilerError,pattern): self.bind()

    def test_real_public_job_consumes_two_links_and_keeps_all_49_raw_observations(self):
        before={ref['path']:(self.root/ref['path']).read_bytes() for ref in (self.job['source_png'],self.job['semantic_sidecar'],self.job['vector_preflight']['measurement_inventory'])}
        result=prepare_reconstruction_job(self.root,slide_number=1,accepted_call=self.accepted)
        job=read_json(result.job_path); evidence=job['semantic_geometry_binding']['vsc_identity_evidence']
        self.assertEqual([x['measurement_id'] for x in evidence['links']],['T01','T02'])
        self.assertEqual(len(evidence['unbound_measured_text_ids']),47)
        self.assertEqual(evidence['unbound_status'],'UNRESOLVED_NOT_SEMANTICALLY_ADMITTED')
        inventory=read_json(self.root/job['vector_preflight']['measurement_inventory']['path'])
        self.assertEqual(len(inventory['text_blocks']),49)
        self.assertEqual([x['content_value'] for x in job['semantic_geometry_binding']['bindings']],['COASTAL FIELD NOTES','Planning workflow fixture'])
        self.assertTrue(all((self.root/path).read_bytes()==data for path,data in before.items()))
        self.assertIn('unbound measured text IDs remain UNRESOLVED',result.worker_prompt_path.read_text())
        self.assertFalse(evidence['authority']['erase']); self.assertFalse(evidence['authority']['native_admission'])
        self.assertEqual(job['authoring_contract'],self.job['authoring_contract'])

    def test_review_missing_is_rejected_by_actual_job_builder(self):
        self.review_path.unlink()
        with self.assertRaises((OSError,DeckCompilerError)):
            prepare_reconstruction_job(self.root,slide_number=1,accepted_call=self.accepted)

    def test_changed_review_invalidates_hash(self):
        self.review['reviewer']='changed'; write_json(self.review_path,self.review)
        self.assert_rejected('sha256 mismatch')

    def test_pending_review_cannot_be_promoted(self):
        self.review['status']='PENDING'; self.save_review(); self.assert_rejected('identity links only')

    def test_swapped_measurement_is_rejected(self):
        self.review['links'][0]['measurement_id']='T02'; self.save_review()
        self.assert_rejected('does not match association')

    def test_same_strings_do_not_authorize_a_misbound_measurement(self):
        self.review['links'][0]['measurement_id']='T02'; self.association['bindings'][0]['measurement_id']='T02'
        self.review['links'][1]['measurement_id']='T01'; self.association['bindings'][1]['measurement_id']='T01'
        self.save_review(); self.assert_rejected('outside.*envelope')

    def test_duplicate_observation_identity_is_rejected(self):
        for key in ('block_id','observation_id','region_id'):
            self.review['links'][1][key]=self.review['links'][0][key]
        self.save_review(); self.assert_rejected('unused existing observation')

    def test_wrong_frame_receipt_is_rejected_even_if_rehashed(self):
        ref=self.review['artifacts']['canvas_receipt']; path=self.root/ref['path']; receipt=read_json(path)
        receipt['transform']['scale_x']['numerator']+=1; write_json(path,receipt)
        ref['sha256']=hashlib.sha256(path.read_bytes()).hexdigest(); self.save_review()
        self.assert_rejected('transform/frame mismatch')

    def test_unrelated_vsc_source_is_rejected_even_if_rehashed(self):
        ref=self.review['artifacts']['vsc_inventory']; path=self.root/ref['path']; inv=read_json(path)
        inv['source']['source_sha256']='0'*64; write_json(path,inv)
        ref['sha256']=hashlib.sha256(path.read_bytes()).hexdigest(); self.save_review()
        self.assert_rejected('source/canvas identity mismatch')

    def test_reviewed_source_crop_changes_are_rejected(self):
        path=self.root/self.review['artifacts']['reviewed_crops'][0]['path']; path.write_bytes(path.read_bytes()+b'changed')
        self.assert_rejected('sha256 mismatch')

    def test_evidence_change_changes_actual_job_content_hash(self):
        old=self.job['content_hash']; self.review['links'][0]['visual_reason']+=' Additional review note.'; self.save_review()
        result=prepare_reconstruction_job(self.root,slide_number=1,accepted_call=self.accepted)
        self.assertNotEqual(read_json(result.job_path)['content_hash'],old)

    def test_adapter_uses_existing_contract_and_preserves_original_content(self):
        before=self.association_path.read_bytes()
        path=prepare_vsc_associations(self.root,slide_number=1,review_path=self.review_path)
        self.assertEqual(path.read_bytes(),before)

    def test_invalid_content_pointer_does_not_publish_or_replace_live_association(self):
        before=self.association_path.read_bytes()
        self.review['links'][0]['content_pointer']='/exact_on_slide_copy/missing'
        write_json(self.review_path,self.review)
        with self.assertRaisesRegex(DeckCompilerError,'content_pointer'):
            prepare_vsc_associations(self.root,slide_number=1,review_path=self.review_path)
        self.assertEqual(self.association_path.read_bytes(),before)
        self.assertEqual(list(self.work.glob('.vsc-association-check-*')),[])

    def test_scope_cannot_grant_geometry_or_quality_authority(self):
        self.review['scope']='geometry_and_quality_approved'; self.save_review()
        self.assert_rejected('identity links only')
