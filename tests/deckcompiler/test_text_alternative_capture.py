"""Invented additive alternatives; no OCR, semantic adjudication or rendering."""
from __future__ import annotations
import copy
import hashlib
import inspect
import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image
import test_region_candidate_capture as capture
from presentation_agent.deckcompiler import cli
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.identity import content_sha256
from presentation_agent.deckcompiler.manifest_io import read_json, write_json
from presentation_agent.deckcompiler.orchestration import raw_measure_batch as raw
from presentation_agent.deckcompiler.orchestration import vector_preflight as vector
from presentation_agent.deckcompiler.orchestration.reconstruction_jobs import prepare_reconstruction_jobs

COLLECTION = 'text_alternative_evidence.observations'

def alternative_fixture(source, blocks):
    """Explicit three-observation chain, independently specified expected graph."""
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    with Image.open(source) as opened: image = opened.convert('RGB')
    observations = []
    by_text = {}
    for text, confidence, count in [('ABCD', .7, 2), ('ABCE', .8, 1), ('AXCE', .9, 1)]:
        body = {'bbox_px': {'x':20, 'y':12, 'w':64, 'h':16}, 'text':text, 'confidence':confidence}
        ident = 'O' + digest(body); by_text[text] = ident
        observations.append({'observation_id':ident, **body, 'occurrences':count})
    observations.sort(key=lambda row:row['observation_id'])
    ids = sorted(by_text.values()); line = 'L' + digest(ids)
    edges = []
    for left, right in [('ABCD','ABCE'), ('ABCE','AXCE')]:
        a,b = sorted([by_text[left], by_text[right]])
        body = {'a':a, 'b':b, 'line_id':line, 'reason':'same_line_overlap_and_fuzzy_duplicate'}
        edges.append({'edge_id':'E'+digest(body), **body})
    edges.sort(key=lambda row:row['edge_id'])
    group_body = {'observation_ids':ids, 'edge_ids':[row['edge_id'] for row in edges], 'source_line_id':line}
    group = {'group_id':'A'+digest(group_body), **group_body,
             'status':'connected_ambiguity', 'pairwise_equivalence':False}
    assemblies = []
    if blocks:
        assemblies = [{'block_id':blocks[0]['id'], 'block_sha256':digest(blocks[0]),
            'assembly_observation_ids':[by_text['ABCE']], 'source_line_ids':[line],
            'ambiguity_group_ids':[group['group_id']], 'status':'unresolved_legacy_assembly'}]
    return {'schema_version':1, 'status':'unadjudicated', 'method':'pre_nms_mapped_ocr_connected_ambiguity_v1',
        'backend':'easyocr', 'required_consumer_capability':'unresolved_text_alternative_assemblies_v1',
        'canvas_px':{'w':image.width,'h':image.height}, 'canvas_rgb_sha256':hashlib.sha256(image.tobytes()).hexdigest(),
        'duplicate_rule':{'same_line':'_merge_dets_into_lines', 'overlap_fraction':.5,
                          'near_duplicate_ned':.3,'exact_text_must_differ':True},
        'observations':observations, 'source_lines':[{'line_id':line,'observation_ids':ids,'observation_occurrences':4}],
        'edges':edges, 'ambiguity_groups':[group], 'legacy_assemblies':assemblies,
        'coverage':{'observation_occurrences':4,'distinct_observations':3,'source_lines':1,
                    'conflicting_observations':3,'ambiguity_groups':1,'unresolved_legacy_assemblies':len(assemblies)},
        'authority':{key:False for key in ('text_removal','native_admission','vector_eligibility',
                                        'quality_accepted','text_selection','reading_order')}}

class TextAlternativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.base = capture.RegionCandidateCaptureTests(); self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        f=self.base
        self.root,self.runtime,self.pipeline=f.root,f.runtime,f.pipeline
        self.configuration=f.configuration
        detector=self.pipeline/'scripts/detect_elements.py'
        # Existing synthetic detector plus an explicit supported option. No OCR implementation.
        detector.write_text(detector.read_text()+'\n'+inspect.getsource(alternative_fixture)+
            '\n_legacy = build_inventory\n'
            'def build_inventory(image_path, backend="easyocr", canvas="native", reader=None, deep_text=False, *, preserve_region_candidates=False, preserve_text_alternatives=False):\n'
            '    inventory,image = _legacy(image_path,backend,canvas,reader,deep_text,preserve_region_candidates=preserve_region_candidates)\n'
            '    inventory["text_blocks"] = [{"id":"T0","text":"ABCE","bbox_px":{"x":20,"y":12,"w":64,"h":16}}]\n'
            '    if preserve_text_alternatives: inventory["text_alternative_evidence"] = alternative_fixture(image_path,inventory["text_blocks"])\n'
            '    return inventory,image\n')
    def prepare(self, enabled=False, **extra):
        return vector.prepare_vector_preflight(self.runtime, preserve_text_alternatives=enabled, **self.configuration, **extra)
    def validate(self, inventory, required=True):
        raw.validate_text_alternative_evidence(inventory, self.runtime/'pngtopptx-project/src/slide1.png', required=required)
    def fixture(self):
        source=self.runtime/'pngtopptx-project/src/slide1.png'
        block={'id':'T0','text':'ABCE','bbox_px':{'x':20,'y':12,'w':64,'h':16}}
        return {'text_blocks':[block], 'suppressed_text':[], 'notes':[],
                'text_alternative_evidence':alternative_fixture(source,[block])}
    def test_exact_schema_graph_occurrences_and_source_binding(self):
        inventory=self.fixture(); before=copy.deepcopy(inventory); self.validate(inventory)
        self.assertEqual(before,inventory)
        cases=['missing','null','schema_bool','authority_zero','frame','rgb','confidence_bool','occurrences_bool',
               'edge_omitted','edge_extra','group_omitted','line_omitted','observation_omitted','coverage',
               'block_hash','unknown_assembly','assembly_count','outside','rule','extra']
        for case in cases:
            with self.subTest(case=case):
                inv=copy.deepcopy(inventory); e=inv['text_alternative_evidence']
                if case=='missing': inv.pop('text_alternative_evidence')
                elif case=='null': inv['text_alternative_evidence']=None
                elif case=='schema_bool': e['schema_version']=True
                elif case=='authority_zero': e['authority']['text_selection']=0
                elif case=='frame': e['canvas_px']['w']+=1
                elif case=='rgb': e['canvas_rgb_sha256']='0'*64
                elif case=='confidence_bool': e['observations'][0]['confidence']=True
                elif case=='occurrences_bool': e['observations'][0]['occurrences']=True
                elif case=='edge_omitted': e['edges'].pop()
                elif case=='edge_extra': e['edges'].append(copy.deepcopy(e['edges'][0]))
                elif case=='group_omitted': e['ambiguity_groups']=[]
                elif case=='line_omitted': e['source_lines']=[]
                elif case=='observation_omitted': e['observations'].pop()
                elif case=='coverage': e['coverage']['observation_occurrences']-=1
                elif case=='block_hash': inv['text_blocks'][0]['text']='Changed'
                elif case=='unknown_assembly': e['legacy_assemblies'][0]['assembly_observation_ids']=['missing']
                elif case=='assembly_count': e['legacy_assemblies'][0]['assembly_observation_ids']*=5
                elif case=='outside': e['observations'][0]['bbox_px']['x']=-1
                elif case=='rule': e['duplicate_rule']['near_duplicate_ned']=.9
                else: e['permission']=True
                with self.assertRaises(ValueError): self.validate(inv)
        self.validate({},required=False)
        with self.assertRaises(ValueError): self.validate({'text_alternative_evidence':None},required=False)
    def test_empty_success_distinct_from_missing_and_ocr_failure(self):
        inv=self.fixture(); e=inv['text_alternative_evidence']; inv['text_blocks']=[]
        for key in ('observations','source_lines','edges','ambiguity_groups','legacy_assemblies'): e[key]=[]
        e['coverage']={key:0 for key in e['coverage']}; self.validate(inv)
        inv['notes']=['OCR failed (synthetic); falling back to region detection only']
        with self.assertRaises(ValueError): self.validate(inv)
    def test_bulk_cache_mode_and_job_prompt_binding(self):
        self.prepare(); old=self.base.inventory(); self.assertNotIn('text_alternative_evidence',old)
        with self.assertRaises(DeckCompilerError): self.prepare(True,require_cached=True)
        self.prepare(True); captured=self.base.inventory()
        self.assertEqual({k:v for k,v in captured.items() if k!='text_alternative_evidence'},old)
        count=len(self.base.calls()); self.prepare(True,require_cached=True); self.assertEqual(len(self.base.calls()),count)
        prepare_reconstruction_jobs(self.runtime)
        work=self.runtime/'pngtopptx-project/work/slide01'; job=read_json(work/'reconstruction_job.json')
        binding=job['text_alternatives']; self.assertEqual(binding['evidence_sha256'],content_sha256(captured['text_alternative_evidence']))
        self.assertFalse(any(binding['authority'].values()))
        prompt=(work/'worker_prompt.md').read_text(); self.assertIn('unresolved legacy assembly',prompt)
        self.assertIn(captured['text_alternative_evidence']['observations'][0]['observation_id'],prompt)
        self.assertEqual(job['vector_preflight']['regions'],[])
        self.prepare(False); self.assertNotIn('text_alternative_evidence',self.base.inventory())
    def test_protection_is_additive_and_preserves_original_boxes(self):
        inv=self.fixture(); legacy=copy.deepcopy(inv); legacy.pop('text_alternative_evidence')
        old=vector._semantic_boxes(legacy,1600,900); new=vector._semantic_boxes(inv,1600,900)
        self.assertEqual(new[:len(old)],old); self.assertEqual(len(new),len(old)+3)
        self.assertTrue(all(row['id'].startswith(COLLECTION+':') for row in new[len(old):]))
    def test_unassembled_alternatives_protect_regions_before_vector_trace(self):
        source=self.runtime/'pngtopptx-project/src/slide1.png'
        with Image.open(source) as image: width,height=image.size
        legacy={'id':'T0','text':'Separate genuine label','bbox_px':{'x':200,'y':100,'w':60,'h':20}}
        inv={'canvas_px':{'w':width,'h':height},'text_blocks':[legacy],'suppressed_text':[], 'notes':[],
            'text_alternative_evidence':alternative_fixture(source,[]),
            'regions':[{'id':'R1','kind_hint':'flat_shape','bbox_px':{'x':22,'y':14,'w':10,'h':10}},
                       {'id':'R2','kind_hint':'flat_shape','bbox_px':{'x':202,'y':102,'w':10,'h':10}}]}
        output=self.root/'isolated-measurement/inventory.json'; write_json(output,inv)
        batch=write_json(self.root/'isolated-batch.json',{'fixture_only':True})
        with patch.object(vector,'trace_png_to_svg',side_effect=AssertionError('protected geometry traced')) as trace:
            record=vector._build_slide_record(root=self.root,source=source,inventory_path=output,
                inventory=inv,request_row={'slide_number':1,'slide_id':'invented','request_id':'invented'},
                backend='easyocr',deep=False,command=['fixture','--preserve-text-alternatives'],stdout='',stderr='',
                batch_job_path=batch,preserve_text_alternatives=True)
            trace.assert_not_called()
        self.assertTrue(all(r['disposition']=='native_rebuild_text_protected' for r in record['regions']))
        self.assertEqual(record['regions'][1]['semantic_text_overlap_ids'],['T0'])
        self.assertEqual(len(record['regions'][0]['semantic_text_overlap_ids']),3)

    def test_support_is_checked_before_reader_and_cli_is_wired(self):
        source=self.runtime/'pngtopptx-project/src/slide1.png'; jobs=self.root/'batch.json'
        jobs.write_text(json.dumps({'jobs':[{'slide_number':1,'source_png':str(source),'inventory_path':str(self.root/'inventory.json')}]}))
        import types
        fake=types.SimpleNamespace(build_inventory=lambda *args:None,get_easyocr_reader=lambda: (_ for _ in ()).throw(AssertionError('reader called')))
        with patch.object(raw,'_load_module',return_value=fake), patch.object(raw,'_validate_ocr_runtime',side_effect=AssertionError('runtime called')):
            with self.assertRaisesRegex(RuntimeError,'preserve_text_alternatives'):
                raw.main(['--pipeline-root',str(self.pipeline),'--job-file',str(jobs),'--backend','easyocr','--preserve-text-alternatives'])
        self.assertTrue(cli.build_parser().parse_args(['prepare-vector-preflight','--runtime','x','--preserve-text-alternatives']).preserve_text_alternatives)
        arguments=['accept-streaming-image','--runtime','x','--slide','1','--tool-call-id','invented',
            '--queued-at','x','--started-at','x','--completed-at','x','--preserve-text-alternatives']
        with patch.object(cli,'accept_streaming_image',side_effect=ValueError('sentinel')) as call:
            self.assertEqual(cli.main(arguments),1)
            self.assertIs(call.call_args.kwargs['preserve_text_alternatives'],True)
        with patch.object(cli,'prepare_vector_preflight',side_effect=ValueError('sentinel')) as call:
            self.assertEqual(cli.main(['prepare-vector-preflight','--runtime','x','--preserve-text-alternatives']),1)
            self.assertIs(call.call_args.kwargs['preserve_text_alternatives'],True)

    def test_single_cache_both_directions_and_public_resealed_failures(self):
        for enabled in (False, True, True, False):
            vector.prepare_vector_preflight_slide(self.runtime,slide_number=1,
                preserve_text_alternatives=enabled,**self.configuration)
        self.assertEqual(len(self.base.calls()),3)
        self.prepare(True)
        slide_path=vector.slide_preflight_path(self.runtime,1)
        aggregate_path=self.runtime/'pngtopptx-project/work'/vector.MANIFEST_NAME
        record=read_json(slide_path)['slide']
        inventory_path=self.runtime/record['measurement_inventory']['path']
        detector_path=self.runtime/record['detector_record']['path']
        originals={p:p.read_bytes() for p in (slide_path,aggregate_path,inventory_path,detector_path)}
        self.assertTrue(vector.validate_vector_preflight_bundle(self.runtime)['valid'])
        for mutation in ('missing','graph','block','mode','mode_bool','detector_command','rgb'):
            with self.subTest(mutation=mutation):
                for p,data in originals.items(): p.write_bytes(data)
                slide=read_json(slide_path); record=slide['slide']
                inventory_path=self.runtime/record['measurement_inventory']['path']
                inv=read_json(inventory_path)
                if mutation=='missing': inv.pop('text_alternative_evidence')
                elif mutation=='graph': inv['text_alternative_evidence']['edges'].pop()
                elif mutation=='block': inv['text_blocks'][0]['text']='Altered assembly'
                elif mutation=='rgb': inv['text_alternative_evidence']['canvas_rgb_sha256']='0'*64
                elif mutation=='mode': slide['execution']['preserve_text_alternatives']=False
                elif mutation=='mode_bool': slide['execution']['preserve_text_alternatives']=1
                if mutation=='detector_command':
                    dp=self.runtime/record['detector_record']['path']; data=read_json(dp)
                    data['command'].remove('--preserve-text-alternatives'); self.base.seal(dp,data)
                    record['detector_record']['sha256']=hashlib.sha256(dp.read_bytes()).hexdigest()
                write_json(inventory_path,inv)
                record['measurement_inventory']['sha256']=hashlib.sha256(inventory_path.read_bytes()).hexdigest()
                record['slide_content_hash']=content_sha256({k:v for k,v in record.items() if k!='slide_content_hash'})
                self.base.seal(slide_path,slide)
                aggregate=read_json(aggregate_path); aggregate['slides'][0]=record
                aggregate['execution']['preserve_text_alternatives']=slide['execution']['preserve_text_alternatives']
                self.base.seal(aggregate_path,aggregate)
                for report in (vector.validate_vector_preflight_slide_bundle(self.runtime,1),vector.validate_vector_preflight_bundle(self.runtime)):
                    self.assertFalse(report['valid'],report)

    def test_missing_evidence_wrong_backend_and_invalid_mode_fail(self):
        p=self.pipeline/'scripts/detect_elements.py'; original=p.read_text()
        p.write_text(original.replace('if preserve_text_alternatives:', 'if False:'))
        with self.assertRaisesRegex(DeckCompilerError,'text_alternative_evidence'): self.prepare(True)
        p.write_text(original)
        for value in (1,None,'true'):
            with self.subTest(value=value), self.assertRaises(ValueError): self.prepare(value)
        with self.assertRaises(ValueError):
            vector.prepare_vector_preflight(self.runtime,preserve_text_alternatives=True,
                **{**self.configuration,'backend':'tesseract'})

    def stream(self, modes=(True,True)):
        import shutil
        from presentation_agent.deckcompiler.orchestration.streaming_execution import (
            accept_streaming_image,finalize_streaming_images,prepare_streaming_execution)
        (self.runtime/'image_batches/image_generation_batch_manifest.json').unlink()
        work=self.runtime/'pngtopptx-project/work'
        for name in ('reconstruction_job_manifest.json',vector.MANIFEST_NAME): (work/name).unlink()
        for path in work.glob('slide[0-9][0-9]'): shutil.rmtree(path)
        prepare_streaming_execution(self.runtime)
        for slide in (1,2):
            accept_streaming_image(self.runtime,slide_number=slide,tool_call_id=f'fixture-{slide}',
                queued_at='2026-08-11T00:00:00Z',started_at='2026-08-11T00:00:01Z',
                completed_at=f'2026-08-11T00:0{slide}:00Z',pipeline_root=self.pipeline,
                python_executable=sys.executable,vector_backend='easyocr',vector_deep=False,
                preserve_text_alternatives=modes[slide-1])

    def test_streaming_mode_is_bound_and_unchanged_inputs_are_reused(self):
        from presentation_agent.deckcompiler.orchestration.streaming_execution import finalize_streaming_images
        self.stream()
        work=self.runtime/'pngtopptx-project/work'
        before={p:p.read_bytes() for p in work.glob('slide*/**/*') if p.is_file()}
        with patch.object(vector,'_run_measurement_batches',side_effect=AssertionError('remeasure')):
            finalize_streaming_images(self.runtime)
        for p,data in before.items(): self.assertEqual(p.read_bytes(),data)
        self.assertIs(read_json(work/vector.MANIFEST_NAME)['execution']['preserve_text_alternatives'],True)
    def test_streaming_mixed_modes_are_rejected_before_finalization(self):
        from presentation_agent.deckcompiler.orchestration.streaming_execution import finalize_streaming_images
        self.stream((False,True))
        with self.assertRaisesRegex(DeckCompilerError,'mixed measurement configurations'):
            finalize_streaming_images(self.runtime)
        self.assertFalse((self.runtime/'image_batches/image_generation_batch_manifest.json').exists())

    def test_review_namespace_remains_unresolved_and_derivation_accounts_for_it(self):
        import test_source_ref_derivation as fixtures
        from presentation_agent.deckcompiler.orchestration import region_classification_review as review_api
        from presentation_agent.deckcompiler.orchestration.source_ref_authoring import source_ref_authoring_prompt
        f=fixtures.SourceRefDerivationTests(); f.setUp(); self.addCleanup(f.doCleanups)
        r=f.fixture.fixture
        evidence=alternative_fixture(r.root/'pngtopptx-project/src/slide1.png',[])
        r.inventory['text_alternative_evidence']=evidence; r.reseal_inventory()
        r.fixture.args[1]['vector_preflight']['execution']={'preserve_text_alternatives':True}
        write_json(r.fixture.args[1]['vector_preflight_path'],r.fixture.args[1]['vector_preflight'])
        r.review['measurement_inventory_sha256']=r.fixture.args[1]['vector_row']['measurement_inventory']['sha256']
        r.review['decisions'] += [r.decision(COLLECTION,row['observation_id'],'text') for row in evidence['observations']]
        f.job=r.build()['job']; f.fixture.job=f.job
        for obj in f.objects: obj['sourceRefs']=f.tag(obj['sourceRefs']['claim'])
        f.seal()
        derived=f.derive()
        alternatives=[row for row in derived['unresolved'] if row['source']['collection']==COLLECTION]
        self.assertEqual(len(alternatives),3); self.assertTrue(all(row['objects']==[] for row in alternatives))
        result=f.prepare(); self.assertEqual(result['representation_status'],'NOT_ESTABLISHED')
        self.assertEqual(result['unresolved_observations'],5)
        f.fixture.path.unlink()
        for row in evidence['observations']:
            self.assertIn({'collection':COLLECTION,'observation_id':row['observation_id']},f.job['region_classification_review']['coverage']['needs_review'])
        # A fabricated linked claim cannot turn advisory alternatives into represented text.
        f.objects[4]['sourceRefs']=f.tag(f.claim('false-resolution',COLLECTION,evidence['observations'][0]['observation_id']))
        f.seal()
        with self.assertRaises(DeckCompilerError): f.prepare()
        # The normal tagged-author prompt must not advertise the unsupported namespace.
        job=copy.deepcopy(f.job); job['source_ref_authoring']={}
        prompt=source_ref_authoring_prompt(job)
        self.assertIn('review-only',prompt)
        for row in evidence['observations']: self.assertNotIn(row['observation_id'],prompt)
        # Linked legacy blocks remain unresolved even if all declared claims say text.
        evidence=alternative_fixture(r.root/'pngtopptx-project/src/slide1.png',r.inventory['text_blocks'])
        r.inventory['text_alternative_evidence']=evidence; r.reseal_inventory()
        r.review['measurement_inventory_sha256']=r.fixture.args[1]['vector_row']['measurement_inventory']['sha256']
        bound=r.build()['job']['region_classification_review']
        self.assertEqual(next(row for row in bound['decisions'] if row['collection']=='text_blocks' and row['observation_id']=='T1')['review_status'],'needs_review')

if __name__=='__main__': unittest.main()

