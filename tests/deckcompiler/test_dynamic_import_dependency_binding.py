"""Invented local fixture controls; no JS, package emission or runtime attestation."""
import copy,hashlib,json,unittest
from pathlib import Path
from unittest.mock import patch
import test_optional_paragraph_dependency as prior
from presentation_agent.deckcompiler.orchestration import pptxgenjs_dependency as dep,source_ref_authoring as cap,package_correspondence as audit,reconstruction_jobs as jobs,shared_render_qa as shared
from presentation_agent.deckcompiler.manifest_io import read_json,write_json
from presentation_agent.deckcompiler.errors import DeckCompilerError
NEW='pngtopptx-pr6-optional-paragraph-builtin-import-v1'
LOADER='0f15a0de0dead168308511d376e7c2d04a69eb7b9932f21e40c7f98311671ca8'
sha=lambda raw:hashlib.sha256(raw).hexdigest()

class DynamicImportDependencyBindingTests(unittest.TestCase):
 def fixture(self,patched=True,package_audit=True):
  f=prior.OptionalParagraphDependencyTests();f.setUp();f.bundle_id=NEW;self.addCleanup(f.doCleanups)
  return f,f.public_fixture(patched=patched,package_audit=package_audit)
 def test_exact_registry_and_unchanged_previous_bundle(self):
  self.assertIn(NEW,dep.REVIEWED_BUNDLES);self.assertEqual(set(dep.REVIEWED_BUNDLES[NEW]),set(dep.REVIEWED_MODULES));self.assertEqual(dep.REVIEWED_BUNDLES[dep.BUNDLE],dep.REVIEWED_MODULES)
  changed=[k for k,v in dep.REVIEWED_BUNDLES[NEW].items() if v!=dep.REVIEWED_MODULES[k]];self.assertEqual(changed,['pptxgenjs_dependency.js']);self.assertEqual(dep.REVIEWED_BUNDLES[NEW][changed[0]],LOADER)
  self.assertEqual(cap.REVIEWED_BUNDLES[NEW],dep.REVIEWED_BUNDLES[NEW]);self.assertIn(NEW,audit.PROFILE_PRODUCERS[audit.GEOMETRY_PROFILE]);self.assertEqual(audit.PROFILE_PRODUCERS[audit.PROFILE],(audit.PRODUCER,))
 def test_new_bundle_patched_and_default_public_paths_and_no_audit_hook(self):
  for patched,package in [(True,True),(False,True),(True,False)]:
   with self.subTest(patched=patched,package=package):
    f,(root,p,w,job)=self.fixture(patched,package);bound=job['source_ref_authoring']['renderer_capability'];self.assertEqual(bound['bundle_id'],NEW)
    self.assertEqual(bound['pptxgenjs_dependency']['mode'],'PATCHED_EXACT_CJS' if patched else 'UNPATCHED_DEFAULT')
    result=audit.audit_job_package(root,job,w);self.assertEqual(result is None,not package)
    shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json');self.assertTrue(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
    (p/'out/build_trace.json').unlink();self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
 def test_descriptor_uses_bundle_key_and_rejects_wrong_or_unknown_identity(self):
  f,(root,p,w,job)=self.fixture();bound=job['source_ref_authoring']['renderer_capability'];descriptor=dep.expected_descriptor(bound)
  self.assertEqual(descriptor['loaderSha256'],bound['modules']['pptxgenjs_dependency.js']['sha256'])
  for mutation in ('old-label','wrong-loader','extra-member','unknown-label'):
   value=copy.deepcopy(bound)
   if mutation=='old-label':value['bundle_id']=dep.BUNDLE
   elif mutation=='unknown-label':value['bundle_id']='unrecognized'
   elif mutation=='wrong-loader':value['modules']['pptxgenjs_dependency.js']['sha256']='0'*64
   else:value['modules']['unexpected.js']={'path':'untrusted','sha256':'0'*64}
   with self.subTest(mutation=mutation),self.assertRaises(ValueError):dep.expected_descriptor(value)
 def test_old_complete_bundle_swap_requires_fresh_job_not_stale_receipt(self):
  f,(root,p,w,job)=self.fixture();shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json');receipt=(w/'worker_receipt.json').read_bytes();bound=job['source_ref_authoring']['renderer_capability']
  current={k:v['sha256'] for k,v in bound['modules'].items()};old=dict(current);replacement=b'// Invented previous loader fixture\n';old['pptxgenjs_dependency.js']=sha(replacement)
  # Real old/new bundles differ only in this loader; this is a complete valid
  # old bundle, not an invalid mix of their eight identical shared modules.
  with patch.object(dep,'REVIEWED_BUNDLES',{NEW:current,dep.BUNDLE:old}),patch.object(cap,'REVIEWED_BUNDLES',{NEW:current,dep.BUNDLE:old}):
   Path(bound['modules']['pptxgenjs_dependency.js']['path']).write_bytes(replacement)
   fresh=cap.bind_source_ref_authoring(root,job,w,{'skill_path':bound['skill']['path'],'sha256':bound['skill']['sha256']});self.assertEqual(fresh['renderer_capability']['bundle_id'],dep.BUNDLE)
   self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
   with self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
   with self.assertRaises(DeckCompilerError):shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json')
   self.assertEqual((w/'worker_receipt.json').read_bytes(),receipt)
 def test_request_result_validator_and_loader_mutations_invalidate(self):
  f,(root,p,w,job)=self.fixture();shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json');receipt=(w/'worker_receipt.json').read_bytes();bound=job['source_ref_authoring']['renderer_capability'];d=bound['pptxgenjs_dependency']
  for item in [bound['modules']['pptxgenjs_dependency.js'],d['request'],d['original_entry'],d['expected_entry'],d['cache_license']]:
   path=Path(item['path']);before=path.read_bytes();path.write_bytes(before+b'\n')
   with self.subTest(path=path.name),self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
   self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid']);path.write_bytes(before)
  self.assertEqual((w/'worker_receipt.json').read_bytes(),receipt)
 def test_three_descriptors_reject_missing_or_resealed_runtime_claims(self):
  f,(root,p,w,job)=self.fixture();shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json');receipt=(w/'worker_receipt.json').read_bytes()
  files=[p/'out/build_trace.json',p/'out/render_trace.json',p/'out/native_object_manifest.json'];saved={p:p.read_bytes() for p in files}
  for change in ({'nodeVersion':'24.19.0'},{'dynamicImportCapability':True},{'dynamicImportCapability':False},{'securitySandbox':True},{'loaderSha256':'0'*64},None):
   for path in files:
    value=json.loads(saved[path])
    if change is None:value.pop('pptxgenjsDependency')
    else:value['pptxgenjsDependency'].update(change)
    write_json(path,value)
   trace=read_json(files[1]);trace['nativeObjectManifestHash']=sha(files[2].read_bytes());write_json(files[1],trace)
   with self.subTest(change=change),self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
   self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
   with self.assertRaises(DeckCompilerError):shared.finalize_shared_render_qa(root,summary_path=p/'out/visual_qa_summary_final.json')
   self.assertEqual((w/'worker_receipt.json').read_bytes(),receipt)
   for path,raw in saved.items():path.write_bytes(raw)
 def test_signed_profile_and_mixed_older_member_still_reject(self):
  f,(root,p,w,job)=self.fixture();path=p/'out/native_object_manifest.json';value=read_json(path);value['slides']['1']['objects'][0]['emitterGeometry']['transform']['flipH']=True;write_json(path,value);trace=read_json(p/'out/render_trace.json');trace['nativeObjectManifestHash']=sha(path.read_bytes());write_json(p/'out/render_trace.json',trace)
  with self.assertRaisesRegex(DeckCompilerError,'UNSUPPORTED_PROFILE'):audit.audit_job_package(root,job,w)
  member=Path(job['source_ref_authoring']['renderer_capability']['modules']['object_manifest.js']['path']);member.write_bytes(b'// Invented incompatible earlier manifest\n')
  with self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,w)
