"""Invented geometry/profile gate fixtures; no emitter, author or rendered QA.

Public finalization controls reuse the explicitly synthetic upstream unit
fixture, never a production success receipt or real workflow claim.
"""
import copy
import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_package_correspondence as base
import test_source_ref_authoring as authoring
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json, write_json

PROFILE='direct-text-shape-raster-lines-v2'
PRODUCER='pngtopptx-pr1-pr6-emitter-geometry-v1'
REQUEST={**base.REQUEST,'profile':PROFILE}
HASHES={'atoms_pptx.js':'3262e57a847ae4c6fc30e52582bf004975af048c33feb0f512cf41f6623d9ad7',
 'object_manifest.js':'f850cb73728cd1d3808a65506f4f00a9354d6f4897962b07895f6772b192a4a5',
 'atoms_html.js':'b487d59a25c14a872eb803c3d0a6e0e801135f05be2fdd40cd38c59b26b32acb'}

def geometry(normalization='none'):
    return {'schemaVersion':'slide-image-dual-render.emitter-geometry.v1','emitterVersion':'4.0.1','units':'EMU',
      'status':'PROJECTED','reason':None,'sourceNormalization':normalization,
      'transform':{'x':0,'y':0,'cx':12191695,'cy':6858000,'flipH':False,'flipV':False,'rotation':0}}

def fixture(line=False):
    parts,manifest=base.fixture();obj=manifest['slides']['1']['objects'][0]
    # These are diagnostic source coordinates. Exact comparison must use the
    # qualified emitter record rather than infer coordinates from rounded boxes.
    obj.update(x=0.125,y=0.375,w=99.75,h=99.5,emitterGeometry=geometry(),
      sourceRefs={'schemaVersion':'slide-image-dual-render.source-refs.v1','slide':1})
    if line:
        xml=parts['ppt/slides/slide1.xml'];start=xml.index(b'<p:txBody>');end=xml.index(b'</p:txBody>')+len(b'</p:txBody>')
        parts['ppt/slides/slide1.xml']=(xml[:start]+xml[end:]).replace(b'</p:spPr>',b'<a:prstGeom prst="line"/></p:spPr>')
        obj.update(type='rule',source='surface.ln',w=-99.75,h=0,emitterGeometry=geometry('safe-line-geom-v1'))
    return parts,manifest

class EmitterGeometryCorrespondenceTests(unittest.TestCase):
    def setUp(self):
        self.api=importlib.import_module('presentation_agent.deckcompiler.orchestration.package_correspondence')
        self.cap=importlib.import_module('presentation_agent.deckcompiler.orchestration.source_ref_authoring')
    def inspect(self,parts=None,manifest=None,**options):
        p,m=fixture();return self.api.inspect_package(base.package(parts or p),manifest or m,slide=1,physical_index=1,canvas=(100,100),profile=PROFILE,producer_bundle=PRODUCER,**options)
    def reject(self,status,parts=None,manifest=None):
        with self.assertRaises(DeckCompilerError) as caught:self.inspect(parts,manifest)
        self.assertEqual(caught.exception.code,'DC_PPTX_PACKAGE_'+status)
    def test_exact_whole_geometry_bundle_registered_without_changing_old_bundles(self):
        self.assertEqual(self.cap.REVIEWED_BUNDLES.get(PRODUCER),HASHES)
        self.assertEqual(self.cap.REVIEWED_BUNDLES['pngtopptx-pr1-pr6-source-refs-v1']['atoms_pptx.js'],'a01757a582fede4540116940316c171518246f13499f84f0de595e9068ab28da')
    def test_fractional_diagnostic_boxes_do_not_replace_exact_qualified_emu(self):
        p,m=fixture();result=self.inspect(p,m)
        self.assertEqual(result['profile'],PROFILE);self.assertEqual(result['objects'][0]['geometry_emu'],[0,0,12191695,6858000])
        self.assertEqual(result['representation_status'],'NOT_ESTABLISHED');self.assertTrue(all(v is False for v in result['authority'].values()))
        m['slides']['1']['objects'][0]['emitterGeometry']['transform']['x']=1
        self.reject('CORRESPONDENCE_MISMATCH',p,m)
        # A qualified numeric input just below 100 inches can round to this
        # exact upper EMU boundary; do not reject valid producer output.
        p,m=fixture();m['slides']['1']['objects'][0]['emitterGeometry']['transform']['x']=91440000
        p['ppt/slides/slide1.xml']=p['ppt/slides/slide1.xml'].replace(b'<a:off x="0"',b'<a:off x="91440000"')
        self.assertEqual(self.inspect(p,m)['objects'][0]['geometry_emu'][0],91440000)
    def test_supported_line_uses_rule_category_line_preset_and_normalization(self):
        p,m=fixture(line=True);self.assertEqual(self.inspect(p,m)['objects'][0]['kind'],'shape')
        for field,value in [('type','shape'),('source','surface.ell')]:
            changed=copy.deepcopy(m);changed['slides']['1']['objects'][0][field]=value
            self.reject('INVALID_INPUT',p,changed)
        changed=copy.deepcopy(m);changed['slides']['1']['objects'][0]['emitterGeometry']['sourceNormalization']='none';self.reject('INVALID_INPUT',p,changed)
        p['ppt/slides/slide1.xml']=p['ppt/slides/slide1.xml'].replace(b'prst="line"',b'prst="ellipse"');self.reject('CORRESPONDENCE_MISMATCH',p,m)
    def test_missing_null_unknown_or_malformed_evidence_never_falls_back(self):
        for value in (None,{},[],False):
            p,m=fixture();m['slides']['1']['objects'][0]['emitterGeometry']=value
            with self.subTest(value=value):self.reject('INVALID_INPUT',p,m)
        p,m=fixture();m['slides']['1']['objects'][0].pop('emitterGeometry');self.reject('INVALID_INPUT',p,m)
        p,m=fixture();m['slides']['1']['objects'][0].pop('sourceRefs');self.reject('INVALID_INPUT',p,m)
        for key,value,state in [('schemaVersion','unknown','UNSUPPORTED_PROFILE'),('emitterVersion','4.0.2','UNSUPPORTED_PROFILE'),('units','pixels','INVALID_INPUT'),('status','UNSUPPORTED','UNSUPPORTED_PROFILE'),('status','accepted','INVALID_INPUT'),('reason','fallback','INVALID_INPUT'),('sourceNormalization','guess','INVALID_INPUT')]:
            p,m=fixture();m['slides']['1']['objects'][0]['emitterGeometry'][key]=value
            with self.subTest(key=key,value=value):self.reject(state,p,m)
        for key,value in [('schemaVersion',True),('emitterVersion',4.01),('units',None),('status',[]),('reason',False),('sourceNormalization',{})]:
            p,m=fixture();m['slides']['1']['objects'][0]['emitterGeometry'][key]=value
            with self.subTest(key=key,value=value):self.reject('INVALID_INPUT',p,m)
    def test_emu_booleans_float_nonfinite_negative_and_extra_fields_fail_closed(self):
        for key,value in [('x',False),('cx',True),('x',0.0),('y',float('nan')),('y',float('inf')),('x',-1),('cx',0),('cx',91440001),('flipH',0),('flipV',None),('rotation',False),('rotation',0.0),('extra',0)]:
            p,m=fixture();m['slides']['1']['objects'][0]['emitterGeometry']['transform'][key]=value
            with self.subTest(key=key,value=value):self.reject('INVALID_INPUT',p,m)
        p,m=fixture();m['slides']['1']['objects'][0]['emitterGeometry']['extra']=True;self.reject('INVALID_INPUT',p,m)
    def test_unsupported_direction_flip_and_rotation_do_not_qualify(self):
        p,m=fixture(line=True);m['slides']['1']['objects'][0]['emitterGeometry'].update(status='UNSUPPORTED',reason='UNSUPPORTED_LINE_DIRECTION')
        self.reject('UNSUPPORTED_PROFILE',p,m)
        for key,value in [('flipH',True),('flipV',True),('rotation',60000)]:
            p,m=fixture();m['slides']['1']['objects'][0]['emitterGeometry']['transform'][key]=value
            with self.subTest(key=key):self.reject('UNSUPPORTED_PROFILE',p,m)
        p,m=fixture();p['ppt/slides/slide1.xml']=p['ppt/slides/slide1.xml'].replace(b'<a:xfrm>',b'<a:xfrm flipH="1">');self.reject('UNSUPPORTED_PROFILE',p,m)
    def test_v1_ignores_new_field_without_changing_integer_profile_and_v2_needs_producer(self):
        p,m=base.fixture();obj=m['slides']['1']['objects'][0]
        result=self.api.inspect_package(base.package(p),m,slide=1,physical_index=1,canvas=(100,100))
        obj['emitterGeometry']=None
        again=self.api.inspect_package(base.package(p),m,slide=1,physical_index=1,canvas=(100,100))
        self.assertEqual(result['objects'][0]['geometry_emu'],again['objects'][0]['geometry_emu']);self.assertEqual(again['profile'],base.PROFILE)
        for profile,producer in [(PROFILE,None),(PROFILE,self.api.PRODUCER),(base.PROFILE,PRODUCER),('invented',PRODUCER)]:
            with self.subTest(profile=profile,producer=producer),self.assertRaises(DeckCompilerError):
                self.api.inspect_package(base.package(p),m,slide=1,physical_index=1,canvas=(100,100),profile=profile,producer_bundle=producer)
    def test_public_profile_request_matches_whole_bundle_and_default_is_unchanged(self):
        f=authoring.SourceRefAuthoringTests();f.setUp();self.addCleanup(f.doCleanups)
        default=f.build();self.assertEqual(f.build(),default)
        f.path.write_text(json.dumps(authoring.REQUEST));write_json(f.work/base.NAME,REQUEST)
        with patch.object(self.cap,'REVIEWED_BUNDLES',{self.api.PRODUCER:f.bundles['synthetic-a']}):
            with self.assertRaisesRegex(DeckCompilerError,'producer|bundle'):f.build()
        with patch.object(self.cap,'REVIEWED_BUNDLES',{PRODUCER:f.bundles['synthetic-a']}):
            row=f.build();bound=row['job']['package_correspondence'];self.assertEqual(bound['profile'],PROFILE);self.assertEqual(bound['producer_bundle'],PRODUCER)
            write_json(f.work/base.NAME,base.REQUEST)
            with self.assertRaisesRegex(DeckCompilerError,'producer|bundle'):f.build()
            write_json(f.work/base.NAME,REQUEST)
            (f.skill.parent/'scripts/lib/atoms_pptx.js').write_text('// Invented inert fixture synthetic-b atoms_pptx.js; must never execute\n')
            with self.assertRaisesRegex(DeckCompilerError,'whole reviewed'):f.build()
    def public_fixture(self):
        from presentation_agent.deckcompiler.orchestration import reconstruction_jobs as jobs
        f=base.PackageCorrespondenceTests();f.setUp();self.addCleanup(f.doCleanups)
        root,project,work,oldjob,parts=f.public_fixture()
        hashes=copy.deepcopy(self.cap.REVIEWED_BUNDLES[self.api.PRODUCER])
        guard=patch.object(self.cap,'REVIEWED_BUNDLES',{PRODUCER:hashes});guard.start();self.addCleanup(guard.stop)
        write_json(work/base.NAME,REQUEST);jobs.prepare_reconstruction_jobs(root);job=read_json(work/'reconstruction_job.json')
        native=read_json(project/'out/native_object_manifest.json');first=native['slides']['1']['objects'][0]['sourceRefs']
        first['bindings']['jobContentHash']=job['content_hash']
        for i,obj in enumerate(native['slides']['1']['objects']):
            tag=copy.deepcopy(first)
            if i:tag['claim']={'kind':'extra','groupId':f'unresolved-fixture-{i}','purpose':'unresolved'}
            obj.update(sourceRefs=tag,emitterGeometry=geometry())
        write_json(project/'out/native_object_manifest.json',native)
        trace=read_json(project/'out/render_trace.json');trace['nativeObjectManifestHash']=base.sha((project/'out/native_object_manifest.json').read_bytes());write_json(project/'out/render_trace.json',trace)
        return root,project,work,job
    def test_public_finalize_and_completion_recompute_v2_and_reject_stale_evidence(self):
        from presentation_agent.deckcompiler.orchestration import reconstruction_jobs as jobs,shared_render_qa as shared
        root,project,work,job=self.public_fixture();summary=project/'out/visual_qa_summary_final.json'
        shared.finalize_shared_render_qa(root,summary_path=summary)
        receipt=(work/'worker_receipt.json').read_bytes();result=read_json(work/'worker_receipt.json')['packageCorrespondence']
        self.assertEqual(result['profile'],PROFILE);self.assertEqual(result['bindings']['producer_bundle'],PRODUCER)
        self.assertTrue(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
        module=Path(job['source_ref_authoring']['renderer_capability']['modules']['atoms_pptx.js']['path'])
        for path in (work/base.NAME,module):
            saved=path.read_bytes();path.write_bytes(saved+b'\n')
            with self.subTest(stale=path.name):
                self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
                with self.assertRaises(DeckCompilerError):shared.finalize_shared_render_qa(root,summary_path=summary)
                self.assertEqual((work/'worker_receipt.json').read_bytes(),receipt)
            path.write_bytes(saved)
        native_path=project/'out/native_object_manifest.json';native=read_json(native_path)
        native['slides']['1']['objects'][0]['emitterGeometry']['transform']['x']=1;write_json(native_path,native)
        trace=read_json(project/'out/render_trace.json');trace['nativeObjectManifestHash']=base.sha(native_path.read_bytes());write_json(project/'out/render_trace.json',trace)
        self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
        with self.assertRaisesRegex(DeckCompilerError,'CORRESPONDENCE_MISMATCH'):shared.finalize_shared_render_qa(root,summary_path=summary)
        self.assertEqual((work/'worker_receipt.json').read_bytes(),receipt)

if __name__=='__main__':unittest.main()
