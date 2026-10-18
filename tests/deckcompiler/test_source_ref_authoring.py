"""Synthetic capability/prompt tests; no JS execution, author, OCR or render."""
from __future__ import annotations
import copy
import hashlib
import importlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_region_classification_review as fixtures
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import reconstruction_jobs as jobs

NAME = 'source_ref_authoring.json'
REQUEST = {'schema_name':'codex_source_ref_authoring_request','schema_version':'1.0.0','enabled':True}
MODULES = ['object_manifest.js','atoms_pptx.js','atoms_html.js']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

class SourceRefAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.RegionClassificationReviewTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root,self.work=self.fixture.root,self.fixture.work
        self.path=self.work/NAME
        self.skill=self.root/'installed/slide-image-dual-render/SKILL.md'
        self.skill.parent.mkdir(parents=True);self.skill.write_text('Synthetic renderer instructions only\n')
        self.bundles=self.install_modules(self.skill.parent)
        self.fixture.fixture.args[1]['renderer']={'skill_path':str(self.skill),'sha256':sha(self.skill)}
        self.default=self.fixture.build()
        try:self.api=importlib.import_module('presentation_agent.deckcompiler.orchestration.source_ref_authoring')
        except ModuleNotFoundError:self.api=None
        if self.api:
            self.registry=patch.object(self.api,'REVIEWED_BUNDLES',self.bundles);self.registry.start();self.addCleanup(self.registry.stop)

    @staticmethod
    def install_modules(root):
        lib=root/'scripts/lib';lib.mkdir(parents=True,exist_ok=True)
        bundles={}
        for version in ('synthetic-a','synthetic-b'):
            hashes={}
            for name in MODULES:
                content=f'// Invented inert fixture {version} {name}; must never execute\n'.encode()
                hashes[name]=hashlib.sha256(content).hexdigest()
                if version=='synthetic-a':(lib/name).write_bytes(content)
            bundles[version]=hashes
        return bundles

    def build(self):return self.fixture.fixture.build()
    def enable(self):write_json(self.path,REQUEST);return self.build()
    def optin(self,row):
        self.assertIn('source_ref_authoring',row['job']);return row['job']['source_ref_authoring']

    def test_absent_request_preserves_row_and_prompt_with_review_and_unknown_renderer(self):
        self.assertEqual(self.build(),self.default)
        for p in (self.skill.parent/'scripts/lib').iterdir():p.write_text('Unsupported capability\n')
        self.assertEqual(self.build(),self.default)
        self.assertNotIn('withSourceRefs',self.default['worker_prompt'])

    def test_request_capability_and_exact_digest_prompt_bindings(self):
        row=self.enable();bound=self.optin(row);job=row['job']
        self.assertEqual(bound['request'],{'path':self.path.relative_to(self.root).as_posix(),'sha256':sha(self.path)})
        self.assertEqual(bound['renderer_capability']['bundle_id'],'synthetic-a')
        self.assertEqual({n:v['sha256'] for n,v in bound['renderer_capability']['modules'].items()},self.bundles['synthetic-a'])
        self.assertEqual(job['content_hash'],content_sha256({k:v for k,v in job.items() if k!='content_hash'}))
        self.assertNotIn('jobContentHash',json.dumps(bound))
        prompt=row['worker_prompt'];blocks=[json.loads(b) for b in re.findall(r'```json\n(\{.*?\})\n```',prompt,re.S)]
        starter=next(b for b in blocks if b.get('schemaVersion')=='slide-image-dual-render.source-refs.v1')
        self.assertEqual(starter['bindings'],{'jobContentHash':job['content_hash'],'sourcePngSha256':job['source_png']['sha256'],
            'measurementInventorySha256':job['vector_preflight']['measurement_inventory']['sha256'],
            'reviewArtifactSha256':job['region_classification_review']['review_artifact']['sha256']})
        self.assertEqual(starter['slide'],1);self.assertTrue(all(x is False for x in starter['authority'].values()))
        self.assertEqual(starter['claim']['purpose'],'unresolved')
        self.assertIn('s.withSourceRefs',prompt);self.assertIn('No objects may be invented',prompt)
        self.assertEqual(row,self.build())

    def test_unknown_disputed_and_glyph_ids_remain_advisory(self):
        f=self.fixture;f.review['decisions']=[f.decision('text_blocks','T1','text'),f.decision(fixtures.CANDIDATES,'U01','text'),
            f.decision(fixtures.CANDIDATES,'U02','graphic')]
        f.build();row=self.enable();prompt=row['worker_prompt']
        blocks=[json.loads(b) for b in re.findall(r'```json\n(\{.*?\})\n```',prompt,re.S)]
        ids=next(b for b in blocks if 'recorded_claims' in b)
        self.assertEqual({(r['collection'],r['observation_id']) for r in ids['recorded_claims']},{('text_blocks','T1'),(fixtures.CANDIDATES,'U01')})
        self.assertIn({'collection':fixtures.CANDIDATES,'observation_id':'U02'},ids['unresolved_observations'])
        self.assertIn({'collection':'text_blocks','observation_id':'T2'},ids['unresolved_observations'])
        self.assertIn('Do not infer glyph grouping',prompt)
        self.assertIn('not permission to remove protected OCR',prompt)
        for field in ('vector_preflight','semantic_geometry_binding','authoring_contract'):
            self.assertEqual(row['job'][field],self.default['job'][field])

    def test_malformed_requests_fail_closed(self):
        for value in (None,[],{},False,{**REQUEST,'enabled':False},{**REQUEST,'enabled':1},{**REQUEST,'unknown':True},{**REQUEST,'schema_version':'2.0.0'}):
            with self.subTest(value=value):
                self.path.write_text(json.dumps(value))
                with self.assertRaises(DeckCompilerError):self.build()
        for raw in ('{','{"schema_name":"x","schema_name":"y"}'):
            self.path.write_text(raw)
            with self.assertRaises(DeckCompilerError):self.build()

    def test_missing_review_old_marker_only_and_mixed_bundles_reject(self):
        self.enable();self.fixture.path.unlink()
        with self.assertRaisesRegex(DeckCompilerError,'review'):self.build()
        self.fixture.build()
        lib=self.skill.parent/'scripts/lib'
        for payload in ('// withSourceRefs exists (claim only)\n','// Old renderer\n','// Invented inert fixture synthetic-b atoms_pptx.js; must never execute\n'):
            (lib/'atoms_pptx.js').write_text(payload)
            with self.assertRaisesRegex(DeckCompilerError,'reviewed.*bundle'):self.build()

    def test_second_complete_bundle_recognized_and_missing_module_rejected(self):
        self.enable();lib=self.skill.parent/'scripts/lib'
        for name in MODULES:(lib/name).write_text(f'// Invented inert fixture synthetic-b {name}; must never execute\n')
        self.assertEqual(self.optin(self.build())['renderer_capability']['bundle_id'],'synthetic-b')
        (lib/'object_manifest.js').unlink()
        with self.assertRaises(DeckCompilerError):self.build()

    def test_present_out_of_root_request_rejected(self):
        self.assertIsNotNone(self.api,'source-ref authoring boundary missing')
        with tempfile.TemporaryDirectory() as temporary:
            outside=Path(temporary);write_json(outside/NAME,REQUEST)
            with self.assertRaisesRegex(DeckCompilerError,'inside its local root'):
                self.api.bind_source_ref_authoring(self.root,self.default['job'],outside,self.fixture.fixture.args[1]['renderer'])

    def test_request_and_module_nonregular_or_symlink_reject_before_read(self):
        self.path.mkdir()
        with self.assertRaises(DeckCompilerError):self.build()
        self.path.rmdir();outside=self.root/'outside.json';outside.write_text(json.dumps(REQUEST));self.path.symlink_to(outside)
        with self.assertRaises(DeckCompilerError):self.build()
        self.path.unlink();self.path.symlink_to(self.work/'missing.json')
        with self.assertRaises(DeckCompilerError):self.build()
        self.path.unlink();self.enable()
        module=self.skill.parent/'scripts/lib/atoms_html.js';raw=module.read_bytes();module.unlink();module.symlink_to(outside)
        with self.assertRaises(DeckCompilerError):self.build()
        module.unlink();module.mkdir()
        with self.assertRaises(DeckCompilerError):self.build()
        module.rmdir();module.write_bytes(raw)

    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX named pipe required')
    def test_fifo_request_is_rejected_without_read(self):
        os.mkfifo(self.path)
        self.assertIsNotNone(self.api,'source-ref authoring boundary missing')
        with patch.object(Path,'read_bytes',side_effect=AssertionError('FIFO read')) as read:
            with self.assertRaisesRegex(DeckCompilerError,'regular file'):
                self.api.bind_source_ref_authoring(self.root,self.default['job'],self.work,self.fixture.fixture.args[1]['renderer'])
            read.assert_not_called()

    def test_empty_observation_scope_is_explicitly_unsupported(self):
        f=self.fixture
        f.inventory['text_blocks']=[];f.inventory['suppressed_text']=[];f.inventory['region_candidate_evidence']['candidates']=[];f.reseal_inventory()
        f.review['measurement_inventory_sha256']=sha(f.inventory_path);f.review['region_candidate_evidence_sha256']=content_sha256(f.inventory['region_candidate_evidence']);f.review['decisions']=[]
        f.build()
        with self.assertRaisesRegex(DeckCompilerError,'empty observation'):self.enable()

    def test_public_validation_rechecks_capability_request_review_and_zero_tags(self):
        import test_source_ref_derivation as upstream
        f=upstream.SourceRefDerivationTests();f.setUp();self.addCleanup(f.doCleanups)
        root,project,work,oldjob=f.public_fixture()
        skill=Path(oldjob['authoring_contract']['renderer_skill_path']);bundles=self.install_modules(skill.parent)
        if self.api:self.api.REVIEWED_BUNDLES=bundles
        request=write_json(work/NAME,REQUEST)
        jobs.prepare_reconstruction_jobs(root)
        job=read_json(work/'reconstruction_job.json');self.assertIn('source_ref_authoring',job)
        self.assertTrue(jobs.validate_reconstruction_job_bundle(root)['valid'])
        originals={p:p.read_bytes() for p in (request,skill.parent/'scripts/lib/atoms_html.js',work/'region_classification_review.json')}
        for p,raw in originals.items():
            p.write_bytes(raw+b'\n')
            with self.subTest(stale=p.name):self.assertFalse(jobs.validate_reconstruction_job_bundle(root)['valid'])
            p.write_bytes(raw)
        native=read_json(project/'out/native_object_manifest.json')
        tagged=copy.deepcopy(native)
        for obj in native['slides']['1']['objects']:obj.pop('sourceRefs',None)
        write_json(project/'out/native_object_manifest.json',native)
        report=jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)
        self.assertFalse(report['valid']);self.assertTrue(any('requires at least one tagged surface row' in x for x in report['issues']),report)
        from presentation_agent.deckcompiler.orchestration.source_ref_derivation import derive_surface_call_accounting
        with self.assertRaisesRegex(DeckCompilerError,'requires at least one tagged surface row'):derive_surface_call_accounting(root,job,work)
        from presentation_agent.deckcompiler.orchestration.shared_render_qa import finalize_shared_render_qa
        receipt=(work/'worker_receipt.json').read_bytes()
        with self.assertRaisesRegex(DeckCompilerError,'requires at least one tagged surface row'):
            finalize_shared_render_qa(root,summary_path=project/'out/visual_qa_summary_final.json')
        self.assertEqual(receipt,(work/'worker_receipt.json').read_bytes())
        self.assertFalse((work/'surface_call_accounting.json').exists())
        # Synthetic official-shaped record, not an actual renderer invocation.
        for obj in tagged['slides']['1']['objects']:
            if 'sourceRefs' in obj:obj['sourceRefs']['bindings']['jobContentHash']=job['content_hash']
        write_json(project/'out/native_object_manifest.json',tagged)
        trace=read_json(project/'out/render_trace.json');trace['nativeObjectManifestHash']=sha(project/'out/native_object_manifest.json')
        write_json(project/'out/render_trace.json',trace)
        completed=finalize_shared_render_qa(root,summary_path=project/'out/visual_qa_summary_final.json')
        self.assertEqual(read_json(completed.receipt_paths[0])['surfaceCallAccounting']['representation_status'],'NOT_ESTABLISHED')
        self.assertTrue(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])

if __name__=='__main__':unittest.main()
