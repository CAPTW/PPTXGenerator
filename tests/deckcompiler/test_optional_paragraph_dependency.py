"""Invented portable dependency/public-gate fixtures; no JS or renderer execution.

Synthetic byte identities are explicitly substituted in tests. Actual reviewed
bytes and saved XML are checked separately, without emitting a new package.
"""
import copy,hashlib,importlib,json,os,unittest
from pathlib import Path
from unittest.mock import patch
import test_source_ref_authoring as authoring
import test_emitter_geometry_correspondence as geometry
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json,write_json
from presentation_agent.deckcompiler.orchestration import source_ref_authoring as cap,package_correspondence as audit,reconstruction_jobs as jobs,shared_render_qa as shared

NEW='pngtopptx-pr6-optional-paragraph-loader-v1'
REQUEST={'schemaVersion':'slide-image-dual-render.pptxgenjs-dependency-request.v1','profile':'pptxgenjs-4.0.1-paragraph-properties-v1'}
BASE=b'// Invented inert original CJS fixture; must never execute\n'
RESULT=b'// Invented inert reviewed-result fixture; must never execute\n'
sha=lambda b:hashlib.sha256(b).hexdigest()

class OptionalParagraphDependencyTests(unittest.TestCase):
 def setUp(self):self.dep=importlib.import_module('presentation_agent.deckcompiler.orchestration.pptxgenjs_dependency')
 def install(self,root,skill,patched=True,actual=None):
  project=root/'pngtopptx-project'; hashes={};bundle_id=getattr(self,'bundle_id',NEW)
  for name,relative in self.dep.MODULE_PATHS.items():
   path=skill.parent/relative;path.parent.mkdir(parents=True,exist_ok=True)
   raw=(actual['skill_root']/relative).read_bytes() if actual else (path.read_bytes() if name=='slide_pipeline.js' and path.exists() else f'// Inert synthetic dependency fixture: {name}\n'.encode())
   path.write_bytes(raw);hashes[name]=sha(raw)
  if not actual:
   for key,value in [('BASE_SHA',sha(BASE)),('RESULT_SHA',sha(RESULT)),('PATCH_SHA',hashes['patches/pptxgenjs-4.0.1-paragraph-properties.patch']),('LICENSE_SHA',hashes['patches/PptxGenJS-LICENSE'])]:
    guard=patch.object(self.dep,key,value);guard.start();self.addCleanup(guard.stop)
  # Both production registries use the same explicit synthetic whole bundle.
  guard=patch.object(cap,'REVIEWED_BUNDLES',{bundle_id:hashes});guard.start();self.addCleanup(guard.stop)
  guard=patch.object(self.dep,'REVIEWED_BUNDLES',{bundle_id:hashes});guard.start();self.addCleanup(guard.stop)
  original=project/self.dep.ORIGINAL_REL;original.parent.mkdir(parents=True,exist_ok=True);original.write_bytes(BASE if not actual else actual['base_bytes'])
  request=project/self.dep.REQUEST_REL;request.parent.mkdir(parents=True,exist_ok=True)
  if patched:write_json(request,REQUEST)
  return project,hashes
 def fixture(self,patched=True):
  f=authoring.SourceRefAuthoringTests();f.setUp();self.addCleanup(f.doCleanups);project,hashes=self.install(f.root,f.skill,patched)
  write_json(f.path,authoring.REQUEST);write_json(f.work/audit.REQUEST_NAME,geometry.REQUEST)
  return f,project,hashes
 def test_registry_has_all_nine_required_members_and_old_bundles_unchanged(self):
  self.assertEqual(cap.REVIEWED_BUNDLES[NEW],self.dep.REVIEWED_MODULES)
  self.assertEqual(len(self.dep.REVIEWED_MODULES),9)
  self.assertEqual(audit.PROFILE_PRODUCERS[audit.PROFILE],(audit.PRODUCER,))
  self.assertIn(NEW,audit.PROFILE_PRODUCERS[audit.GEOMETRY_PROFILE])
  self.assertEqual(len(cap.REVIEWED_BUNDLES['pngtopptx-pr6-text-preservation-v1']),4)
 def test_preparation_binds_expected_identity_without_creating_cache(self):
  f,p,hashes=self.fixture();before=sorted(str(x.relative_to(p)) for x in p.rglob('*'));row=f.build();d=row['job']['source_ref_authoring']['renderer_capability']['pptxgenjs_dependency']
  self.assertEqual(d['mode'],'PATCHED_EXACT_CJS');self.assertEqual(d['original_entry']['path'],str(p/self.dep.ORIGINAL_REL));self.assertEqual(d['original_entry']['sha256'],sha(BASE))
  self.assertEqual(d['expected_entry']['sha256'],sha(RESULT));self.assertEqual(d['validator']['sha256'],sha(self.dep.VALIDATOR_PATH.read_bytes()))
  self.assertEqual(set(row['job']['source_ref_authoring']['renderer_capability']['modules']),set(hashes));self.assertEqual(row,f.build());self.assertEqual(before,sorted(str(x.relative_to(p)) for x in p.rglob('*')))
 def test_unpatched_mode_and_request_transition_invalidate_job_identity(self):
  f,p,_=self.fixture(False);a=f.build();d=a['job']['source_ref_authoring']['renderer_capability']['pptxgenjs_dependency'];self.assertEqual(d['mode'],'UNPATCHED_DEFAULT');self.assertEqual(d['expected_entry'],d['original_entry'])
  write_json(p/self.dep.REQUEST_REL,REQUEST);b=f.build();self.assertNotEqual(a['job']['content_hash'],b['job']['content_hash']);(p/self.dep.REQUEST_REL).unlink();self.assertEqual(f.build(),a)
 def test_request_and_declared_original_invalid_paths_fail_before_binding(self):
  f,p,_=self.fixture();request=p/self.dep.REQUEST_REL;original=request.read_bytes()
  for value in (None,{},dict(REQUEST,path='/arbitrary/module'),dict(REQUEST,profile='4.0.1')):
   write_json(request,value)
   with self.subTest(value=value),self.assertRaises(DeckCompilerError):f.build()
  request.write_bytes(original);base=p/self.dep.ORIGINAL_REL;raw=base.read_bytes();base.write_bytes(b'wrong')
  with self.assertRaisesRegex(DeckCompilerError,'identity|sha256'):f.build()
  base.unlink();base.symlink_to(request)
  with self.assertRaisesRegex(DeckCompilerError,'symlink'):f.build()
  base.unlink();os.mkfifo(base)
  with self.assertRaisesRegex(DeckCompilerError,'regular'):f.build()
  base.unlink();base.write_bytes(raw)
 def test_source_and_validator_bytes_and_existing_bad_cache_invalidate(self):
  f,p,_=self.fixture();row=f.build()
  for name,module in row['job']['source_ref_authoring']['renderer_capability']['modules'].items():
   path=Path(module['path']);old=path.read_bytes();path.write_bytes(old+b'\n')
   with self.subTest(name=name),self.assertRaises(DeckCompilerError):f.build()
   path.write_bytes(old)
  validator=f.root/'synthetic-validator.py';validator.write_bytes(self.dep.VALIDATOR_PATH.read_bytes())
  with patch.object(self.dep,'VALIDATOR_PATH',validator):
   a=f.build();validator.write_bytes(validator.read_bytes()+b'\n');self.assertNotEqual(a['job']['content_hash'],f.build()['job']['content_hash'])
  cache=Path(row['job']['source_ref_authoring']['renderer_capability']['pptxgenjs_dependency']['expected_entry']['path']);cache.parent.mkdir(parents=True);cache.write_bytes(b'wrong')
  with self.assertRaisesRegex(DeckCompilerError,'identity|sha256'):f.build()
 def public_fixture(self,patched=True,package_audit=True,actual=None):
  f=geometry.EmitterGeometryCorrespondenceTests();f.setUp();self.addCleanup(f.doCleanups);root,project,work,oldjob=f.public_fixture()
  skill=Path(oldjob['source_ref_authoring']['renderer_capability']['skill']['path']);self.install(root,skill,patched,actual)
  if not package_audit:(work/audit.REQUEST_NAME).unlink()
  jobs.prepare_reconstruction_jobs(root);job=read_json(work/'reconstruction_job.json');bound=job['source_ref_authoring']['renderer_capability'];d=bound['pptxgenjs_dependency']
  native_path=project/'out/native_object_manifest.json';native=read_json(native_path);trace_path=project/'out/render_trace.json';trace=read_json(trace_path);build=trace.pop('build')
  for obj in native['slides']['1']['objects']:obj['sourceRefs']['bindings']['jobContentHash']=job['content_hash']
  if patched:
   result=RESULT if actual is None else actual['result_bytes']
   cache=Path(d['expected_entry']['path']);cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(result)
   Path(d['cache_license']['path']).write_bytes(Path(bound['modules']['patches/PptxGenJS-LICENSE']['path']).read_bytes())
   descriptor=self.dep.expected_descriptor(bound)
   for target in (native,trace,build):target['pptxgenjsDependency']=copy.deepcopy(descriptor)
  build['buildJs']=bound['modules']['build.js']['path'];build['projectRoot']=str(project)
  trace['hashes'].update(atomsPptx=bound['modules']['atoms_pptx.js']['sha256'],atomsHtml=bound['modules']['atoms_html.js']['sha256'],buildJs=bound['modules']['build.js']['sha256'])
  trace['nodePathUsed']=str(project/'node_modules')
  write_json(native_path,native);trace['nativeObjectManifestHash']=authoring.sha(native_path);write_json(trace_path,trace);write_json(project/'out/build_trace.json',build)
  return root,project,work,job
 def test_public_finalize_completion_and_build_trace_receipt_binding(self):
  root,p,w,job=self.public_fixture();result=audit.audit_job_package(root,job,w);self.assertEqual(result['status'],'CORRESPONDENCE_VERIFIED');self.assertIn('dependency_selection_sha256',result['bindings']);self.assertIn('build_trace_sha256',result['bindings'])
  shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json');self.assertTrue(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
 def test_dependency_check_is_mandatory_even_without_package_audit(self):
  root,p,w,job=self.public_fixture(package_audit=False);self.assertIsNone(audit.audit_job_package(root,job,w));shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json')
  receipt=(w/'worker_receipt.json').read_bytes();(p/'out/build_trace.json').unlink()
  with self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
  self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
  with self.assertRaises(DeckCompilerError):shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json')
  self.assertEqual((w/'worker_receipt.json').read_bytes(),receipt)
 def test_all_descriptor_locations_and_cache_license_revalidate_before_public_success(self):
  root,p,w,job=self.public_fixture();shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json');receipt=(w/'worker_receipt.json').read_bytes()
  targets=[p/'out/build_trace.json',p/'out/render_trace.json',p/'out/native_object_manifest.json']
  for target in targets:
   original=target.read_bytes();obj=json.loads(original);obj['pptxgenjsDependency']['resultSha256']='0'*64;write_json(target,obj)
   with self.subTest(target=target.name),self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
   self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid']);target.write_bytes(original)
  d=job['source_ref_authoring']['renderer_capability']['pptxgenjs_dependency']
  for target in [Path(d['expected_entry']['path']),Path(d['cache_license']['path']),Path(d['original_entry']['path']),Path(d['request']['path'])]:
   original=target.read_bytes();target.write_bytes(original+b'\n')
   with self.subTest(target=target.name),self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
   with self.assertRaises(DeckCompilerError):shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json')
   self.assertEqual((w/'worker_receipt.json').read_bytes(),receipt);target.write_bytes(original)
 def test_unpatched_public_path_cannot_claim_patch_and_old_default_is_unchanged(self):
  root,p,w,job=self.public_fixture(False);self.assertEqual(audit.audit_job_package(root,job,w)['status'],'CORRESPONDENCE_VERIFIED')
  file=p/'out/native_object_manifest.json';native=read_json(file);native['pptxgenjsDependency']=None;write_json(file,native)
  with self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
  f=authoring.SourceRefAuthoringTests();f.setUp();self.addCleanup(f.doCleanups);self.assertEqual(f.build(),f.default)
 def test_current_supported_geometry_and_strict_text_rules_are_not_relaxed(self):
  root,p,w,job=self.public_fixture();file=p/'out/native_object_manifest.json';native=read_json(file);native['slides']['1']['objects'][0]['emitterGeometry']['transform']['flipH']=True;write_json(file,native)
  trace=read_json(p/'out/render_trace.json');trace['nativeObjectManifestHash']=authoring.sha(file);write_json(p/'out/render_trace.json',trace)
  with self.assertRaisesRegex(DeckCompilerError,'UNSUPPORTED_PROFILE'):audit.audit_job_package(root,job,w)

 def test_validator_edit_cannot_leave_prepared_public_job_valid(self):
  import tempfile
  with tempfile.TemporaryDirectory() as temp:
   validator=Path(temp)/'validator.py';validator.write_bytes(self.dep.VALIDATOR_PATH.read_bytes())
   with patch.object(self.dep,'VALIDATOR_PATH',validator):
    root,p,w,job=self.public_fixture();shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json');receipt=(w/'worker_receipt.json').read_bytes()
    validator.write_bytes(validator.read_bytes()+b'\n')
    self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
    with self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
    with self.assertRaises(DeckCompilerError):shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json')
    self.assertEqual((w/'worker_receipt.json').read_bytes(),receipt)
 def test_missing_postload_cache_and_unsafe_absent_cache_ancestor_fail(self):
  root,p,w,job=self.public_fixture();d=job['source_ref_authoring']['renderer_capability']['pptxgenjs_dependency'];entry=Path(d['expected_entry']['path']);raw=entry.read_bytes();entry.unlink()
  # Preparing the same expectation still works; completion requires the result.
  with self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
  entry.write_bytes(raw);license=Path(d['cache_license']['path']);license.unlink()
  with self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
  f,p,_=self.fixture();outside=f.root/'empty-external-cache';outside.mkdir();(p/'.cache').symlink_to(outside,target_is_directory=True)
  with self.assertRaisesRegex(DeckCompilerError,'symlink'):f.build()

 def test_present_nondirectory_ancestors_reject_before_absence_or_read(self):
  # An absent leaf cannot make a present-invalid ancestor count as absent.
  for relative in ('.cache', '.cache/pptxgenjs', '.cache/pptxgenjs/{result}', 'analysis'):
   for kind in ('regular', 'fifo'):
    with self.subTest(relative=relative,kind=kind):
     f,p,_=self.fixture();target=p/relative.format(result=self.dep.RESULT_SHA)
     if target.exists():target.rename(target.with_name(target.name+'-preserved'))
     target.parent.mkdir(parents=True,exist_ok=True)
     if kind=='regular':target.write_bytes(b'Invented invalid directory entry')
     else:os.mkfifo(target)
     # No read may reach a FIFO, including when it is only an ancestor.
     with self.assertRaisesRegex(DeckCompilerError,'ancestor.*directory'):
      f.build()
 def test_genuinely_absent_request_and_cache_directories_remain_allowed(self):
  f,p,_=self.fixture(False);expected=f.build();analysis=p/'analysis';analysis.rename(p/'analysis-preserved')
  self.assertFalse(analysis.exists());self.assertEqual(f.build(),expected)
  g,q,_=self.fixture();expected=g.build();self.assertFalse((q/'.cache').exists())
  (q/'.cache/pptxgenjs').mkdir(parents=True)
  self.assertEqual(g.build(),expected)

 def test_request_ancestor_errors_are_structured_on_absent_optin_public_paths(self):
  for kind in ('regular','fifo'):
   with self.subTest(kind=kind):
    f=authoring.SourceRefAuthoringTests();f.setUp();self.addCleanup(f.doCleanups)
    project=f.root/'pngtopptx-project';project.mkdir(exist_ok=True);analysis=project/'analysis'
    if analysis.exists():analysis.rename(project/'analysis-preserved')
    if kind=='regular':analysis.write_bytes(b'Invented invalid directory entry')
    else:os.mkfifo(analysis)
    for call in (f.build,lambda:audit.audit_job_package(f.root,f.default['job'],f.work)):
     with self.assertRaisesRegex(DeckCompilerError,'ancestor.*directory'):call()
