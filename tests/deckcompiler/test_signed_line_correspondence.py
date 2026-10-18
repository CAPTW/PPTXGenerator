"""Constructed standard-canvas OPC fixtures, never a renderer/workflow result.

No Node or serializer execution. Synthetic public-gate metadata/identities reuse
existing unit fixtures; real reviewed module bytes are checked separately.
"""
import copy,io,json,math,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import test_package_correspondence as base
import test_emitter_geometry_correspondence as legacy
import test_optional_paragraph_dependency as dependency_fixture
from presentation_agent.deckcompiler.orchestration import package_correspondence as audit,pptxgenjs_dependency as dep,source_ref_authoring as cap,reconstruction_jobs as jobs,shared_render_qa as shared
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json,write_json
PROFILE='direct-text-shape-raster-signed-lines-v3'
BUNDLE='pngtopptx-pr6-local-preservation-combined-v1'
COMBINED_MODULES={'object_manifest.js': '19b09f7ad0c4abf0838ed2270e89e4e2c81914375aee2fdf19a5b5d265f2016a', 'atoms_pptx.js': '8a02470e8bcbfdb852f7d6f430ab2bfe83cd9c45c705ebb81d15b01956bf36f1', 'atoms_html.js': '9be458cbad2482392844b0e0cdf583a1c544d6dd23c8d304982ffcbf89b2b96e'}
REQUEST={**base.REQUEST,'profile':PROFILE}

def fixture(w=-120,h=75,*,canvas=(1920,1080),x=300,y=200):
 p,m=base.fixture(width=canvas[0],height=canvas[1]);nx=x+min(w,0);ny=y+min(h,0)
 # Existing independent v1 numeric projection oracle, only ordinary integers.
 coords=[audit._emu(v,13.333 if i%2==0 else 7.5,canvas[i%2]) for i,v in enumerate((nx,ny,abs(w),abs(h)))];flipH=w<0;flipV=h<0
 obj={'type':'rule','source':'surface.ln','x':x,'y':y,'w':w,'h':h,'editable':True,'textLength':0,
  'sourceRefs':{'schemaVersion':'slide-image-dual-render.source-refs.v1','slide':1},
  'emitterGeometry':{'schemaVersion':'slide-image-dual-render.emitter-geometry.v2','emitterVersion':'4.0.1','units':'EMU','status':'PROJECTED','reason':None,'sourceNormalization':'safe-line-geom-v1',
   'transform':dict(zip(('x','y','cx','cy'),coords),flipH=flipH,flipV=flipV,rotation=0),
   'sourceLine':{'units':'source-px','numberEncoding':'ecmascript-binary64-shortest-v1','qualifier':'internal-sign-diagonal-v1',**{k:str(v) for k,v in zip(('x','y','w','h'),(x,y,w,h))}}}}
 attrs=(' flipH="1"' if flipH else '')+(' flipV="1"' if flipV else '')
 shape=f'<p:sp><p:spPr><a:xfrm{attrs}><a:off x="{coords[0]}" y="{coords[1]}"/><a:ext cx="{coords[2]}" cy="{coords[3]}"/></a:xfrm><a:prstGeom prst="line"/></p:spPr></p:sp>'
 xml=p['ppt/slides/slide1.xml'].decode();start=xml.index('<p:sp>');end=xml.index('</p:sp>')+len('</p:sp>');p['ppt/slides/slide1.xml']=(xml[:start]+shape+xml[end:]).encode();m['slides']['1']['objects']=[obj];return p,m

class SignedLineCorrespondenceTests(unittest.TestCase):
 def inspect(self,p=None,m=None,**kw):
  a,b=fixture();return audit.inspect_package(base.package(p or a),m or b,slide=1,physical_index=1,canvas=(1920,1080),profile=kw.pop('profile',PROFILE),producer_bundle=kw.pop('producer_bundle',BUNDLE),**kw)
 def reject(self,state,p,m,**kw):
  with self.assertRaises(DeckCompilerError) as c:self.inspect(p,m,**kw)
  self.assertEqual(c.exception.code,'DC_PPTX_PACKAGE_'+state)
 def test_registry_is_exact_new_nine_bundle_without_v1_v2_promotion(self):
  self.assertEqual(audit.PROFILE_PRODUCERS[PROFILE],(BUNDLE,));self.assertNotIn(BUNDLE,audit.PROFILE_PRODUCERS[audit.GEOMETRY_PROFILE]);self.assertEqual(audit.PROFILE_PRODUCERS[audit.PROFILE],(audit.PRODUCER,))
  old=dep.REVIEWED_BUNDLES[dep.BUILTIN_IMPORT_BUNDLE];new=dep.REVIEWED_BUNDLES[BUNDLE];self.assertEqual(len(new),9);self.assertEqual({k:v for k,v in new.items() if v!=old[k]},COMBINED_MODULES);self.assertEqual(cap.REVIEWED_BUNDLES[BUNDLE],new)
 def test_three_signed_directions_match_exact_flags_and_keep_authority_false(self):
  for w,h in [(-120,75),(120,-75),(-120,-75)]:
   p,m=fixture(w,h);before=copy.deepcopy(m);r=self.inspect(p,m);self.assertEqual(r['object_count'],1);self.assertEqual(r['representation_status'],'NOT_ESTABLISHED');self.assertTrue(all(v is False for v in r['authority'].values()));self.assertEqual(m,before)
   self.assertEqual(r['objects'][0]['line_direction']['flipH'],w<0);self.assertEqual(r['objects'][0]['line_direction']['flipV'],h<0)
 def test_canonical_finite_binary64_strings_and_exact_rounding_helpers(self):
  values={'0':0.0,'-0':-0.0,'1e-7':1e-7,'0.000001':1e-6,'1e+21':1e21,'100000000000000000000':1e20,'5e-324':5e-324,'1.7976931348623157e+308':float.fromhex('0x1.fffffffffffffp+1023'),'0.1':0.1}
  for text,value in values.items():
   self.assertEqual(audit._source_number(text).hex(),value.hex());self.assertEqual(audit._shortest_source_number(value),text)
  for bad in [None,True,0,'NaN','Infinity','-Infinity','+0','00','0.0','-0.0','1E-7','1e-07','0.0000001','1e21','01','1e-999','1e309','１',' 1','1 ','0.'+'0'*100]:
   with self.subTest(bad=bad),self.assertRaises(ValueError):audit._source_number(bad)
  self.assertEqual(audit._fixed3(1.0625),1.063);self.assertEqual(audit._fixed3(-1.0625),-1.063);self.assertEqual(audit._fixed3(-0.0001).hex(),(-0.0).hex());self.assertEqual(audit._round_nonnegative(math.nextafter(.5,0)),0);self.assertEqual(audit._round_nonnegative(.5),1)
 def test_fractional_boundary_collision_uses_exact_values_not_rounded_bbox(self):
  # Invented 1920x1080 source: adjacent binary64 inputs share the diagnostic
  # width but fall on opposite sides of ix(...).toFixed(3). Pure Node capture
  # verifies these exact constants separately; this test emits no package.
  outputs=[]
  for raw,cx in [('-0.21600540013500333',914),('-0.21600540013500336',1829)]:
   p,m=fixture();o=m['slides']['1']['objects'][0];o['w']=-.216
   e=o['emitterGeometry'];e['sourceLine']['w']=raw;e['transform'].update(x=1903781,y=1270102,cx=cx,cy=476402)
   import re
   p['ppt/slides/slide1.xml']=re.sub(rb'<a:off[^>]*/><a:ext[^>]*/>',f'<a:off x="1903781" y="1270102"/><a:ext cx="{cx}" cy="476402"/>'.encode(),p['ppt/slides/slide1.xml'])
   outputs.append(self.inspect(p,m)['objects'][0]['geometry_emu'])
   e['transform']['cx']=1829 if cx==914 else 914
   self.reject('CORRESPONDENCE_MISMATCH',p,m)
  self.assertEqual(outputs,[[1903781,1270102,914,476402],[1903781,1270102,1829,476402]])
 def test_missing_invalid_or_cross_version_evidence_has_no_fallback(self):
  p,m=fixture()
  for key,value in [('sourceLine',None),('sourceLine',{}),('schemaVersion','slide-image-dual-render.emitter-geometry.v1'),('status','UNSUPPORTED'),('units','px'),('sourceNormalization','none'),('emitterVersion','4.0.2')]:
   v=copy.deepcopy(m);v['slides']['1']['objects'][0]['emitterGeometry'][key]=value
   with self.subTest(key=key,value=value),self.assertRaises(DeckCompilerError):self.inspect(p,v)
  for profile,producer in [(audit.PROFILE,audit.PRODUCER),(audit.GEOMETRY_PROFILE,dep.BUILTIN_IMPORT_BUNDLE),(PROFILE,dep.BUILTIN_IMPORT_BUNDLE)]:
   with self.subTest(profile=profile),self.assertRaises(DeckCompilerError):self.inspect(p,m,profile=profile,producer_bundle=producer)
 def test_source_flag_emu_and_diagnostic_mutations_fail(self):
  for location,key,value in [('source','w','120'),('source','x','301'),('source','w','-0'),('source','h','0'),('source','x',True),('source','extra','0'),('source','qualifier','caller-flip'),('source','numberEncoding','decimal'),('source','units','inches'),('transform','flipH',False),('transform','flipV',True),('transform','rotation',1),('transform','x',False),('transform','cx',1.0),('object','x',301),('object','type','shape'),('object','source','surface.ell')]:
   p,m=fixture();o=m['slides']['1']['objects'][0];target=o['emitterGeometry']['sourceLine'] if location=='source' else o['emitterGeometry']['transform'] if location=='transform' else o;target[key]=value
   with self.subTest(location=location,key=key),self.assertRaises(DeckCompilerError):self.inspect(p,m)
 def test_xml_flag_offset_rotation_and_non_line_reflections_reject(self):
  for change in ('remove-flip','extra-flip','false-flag','rotation','offset','preset'):
   p,m=fixture();xml=p['ppt/slides/slide1.xml']
   if change=='remove-flip':xml=xml.replace(b' flipH="1"',b'')
   elif change=='extra-flip':xml=xml.replace(b'<a:xfrm ',b'<a:xfrm flipV="1" ',1)
   elif change=='false-flag':xml=xml.replace(b'flipH="1"',b'flipH="false"')
   elif change=='rotation':xml=xml.replace(b'<a:xfrm ',b'<a:xfrm rot="0" ',1)
   elif change=='offset':xml=xml.replace(b'<a:off x="',b'<a:off x="1',1)
   else:xml=xml.replace(b'prst="line"',b'prst="ellipse"')
   p['ppt/slides/slide1.xml']=xml
   with self.subTest(change=change),self.assertRaises(DeckCompilerError):self.inspect(p,m)
  p,m=legacy.fixture();m['slides']['1']['objects'][0]['emitterGeometry']['transform']['flipH']=True
  with self.assertRaisesRegex(DeckCompilerError,'UNSUPPORTED_PROFILE'):self.inspect(p,m)
 def test_old_normal_and_axis_records_still_use_unchanged_v1_geometry(self):
  for line in (False,True):
   p,m=legacy.fixture(line);r=self.inspect(p,m);self.assertEqual(r['object_count'],1);self.assertNotIn('line_direction',r['objects'][0]);self.assertEqual(self.inspect(p,m,profile=audit.GEOMETRY_PROFILE,producer_bundle=legacy.PRODUCER)['objects'],r['objects'])
 def public_fixture(self,actual=None):
  f=dependency_fixture.OptionalParagraphDependencyTests();f.setUp();f.bundle_id=BUNDLE;self.addCleanup(f.doCleanups)
  root,project,work,_=f.public_fixture(patched=False,package_audit=False,actual=actual);write_json(work/audit.REQUEST_NAME,REQUEST);jobs.prepare_reconstruction_jobs(root);job=read_json(work/'reconstruction_job.json')
  native_path=project/'out/native_object_manifest.json';native=read_json(native_path)
  for o in native['slides']['1']['objects']:o['sourceRefs']['bindings']['jobContentHash']=job['content_hash']
  canvas=tuple(job['source_png'][k] for k in ('width','height'));parts,manifest=fixture(-20,10,canvas=canvas,x=60,y=60);line=manifest['slides']['1']['objects'][0];line['sourceRefs']=copy.deepcopy(native['slides']['1']['objects'][0]['sourceRefs']);line['sourceRefs']['claim']={'kind':'extra','groupId':'invented-signed-line','purpose':'unresolved'}
  native['slides']['1']['objects'].append(line);native['slides']['1']['counts']['rules']=1;native['slides']['1']['editableObjectCount']+=1;write_json(native_path,native)
  metadata_path=work/'visual_qa/pptx_raster_metadata.json';metadata=read_json(metadata_path);package_path=Path(metadata['pptx'])
  with zipfile.ZipFile(io.BytesIO(package_path.read_bytes())) as z:contents={n:z.read(n) for n in z.namelist()}
  xml=parts['ppt/slides/slide1.xml'];shape=xml[xml.index(b'<p:sp>'):xml.index(b'</p:sp>')+len(b'</p:sp>')];contents['ppt/slides/slide1.xml']=contents['ppt/slides/slide1.xml'].replace(b'</p:spTree>',shape+b'</p:spTree>');package_path.write_bytes(base.package(contents));metadata['pptxSha256']=base.sha(package_path.read_bytes());write_json(metadata_path,metadata)
  trace_path=project/'out/render_trace.json';trace=read_json(trace_path);trace['nativeObjectManifestHash']=base.sha(native_path.read_bytes());write_json(trace_path,trace)
  return root,project,work,job
 def test_public_audit_finalization_completion_and_resealed_line_mutation(self):
  root,p,w,job=self.public_fixture();result=audit.audit_job_package(root,job,w);self.assertEqual(result['profile'],PROFILE);self.assertEqual(result['object_count'],13)
  shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json');self.assertTrue(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid']);receipt=(w/'worker_receipt.json').read_bytes()
  native_path=p/'out/native_object_manifest.json';native=read_json(native_path);native['slides']['1']['objects'][-1]['emitterGeometry']['sourceLine']['w']='20';write_json(native_path,native);trace=read_json(p/'out/render_trace.json');trace['nativeObjectManifestHash']=base.sha(native_path.read_bytes());write_json(p/'out/render_trace.json',trace)
  self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
  with self.assertRaises(DeckCompilerError):shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json')
  self.assertEqual((w/'worker_receipt.json').read_bytes(),receipt)
 def test_public_profile_and_module_mutations_stale_job(self):
  root,p,w,job=self.public_fixture();shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json');receipt=(w/'worker_receipt.json').read_bytes()
  module=Path(job['source_ref_authoring']['renderer_capability']['modules']['atoms_pptx.js']['path'])
  for target in (w/audit.REQUEST_NAME,module):
   saved=target.read_bytes();target.write_bytes(saved+b'\n')
   with self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
   self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid']);self.assertEqual((w/'worker_receipt.json').read_bytes(),receipt);target.write_bytes(saved)
