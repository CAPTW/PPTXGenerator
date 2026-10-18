"""Synthetic four-member capability/public-gate controls, without JS execution.

Exact reviewed renderer bytes and saved XML are separate local integration
inputs; these portable tests use explicitly inert synthetic modules and QA.
"""
import copy,hashlib,unittest
from pathlib import Path
from unittest.mock import patch
import test_source_ref_authoring as authoring
import test_emitter_geometry_correspondence as geometry
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json,write_json
from presentation_agent.deckcompiler.orchestration import source_ref_authoring as cap,package_correspondence as audit,reconstruction_jobs as jobs,shared_render_qa as shared

NEW='pngtopptx-pr6-text-preservation-v1'
OLD='pngtopptx-pr6-signed-line-renderer-v1'
HASHES={'object_manifest.js':'f850cb73728cd1d3808a65506f4f00a9354d6f4897962b07895f6772b192a4a5',
 'atoms_pptx.js':'666082f0949ad93c4052f2e26d8eea73de64ae5b22632b918069d681150a5b2e',
 'atoms_html.js':'f8f5ff1f5d05cc13af0218635a9cbb8af738c2b2195741a68322235f9242fa66',
 'text_content.js':'2637a8b0a6b70aaafd1e909486cd1eaa4e43d803697e773257e6973e0e20dd98'}

def install(lib):
 hashes={}
 for name in HASHES:
  raw=f'// Synthetic four-member text fixture {name}; never execute\n'.encode()
  (lib/name).write_bytes(raw);hashes[name]=hashlib.sha256(raw).hexdigest()
 return hashes

class TextPreservationCompatibilityTests(unittest.TestCase):
 def fixture(self):
  f=authoring.SourceRefAuthoringTests();f.setUp();self.addCleanup(f.doCleanups)
  lib=f.skill.parent/'scripts/lib';hashes=install(lib)
  guard=patch.object(cap,'REVIEWED_BUNDLES',{NEW:hashes});guard.start();self.addCleanup(guard.stop)
  write_json(f.path,authoring.REQUEST);write_json(f.work/audit.REQUEST_NAME,geometry.REQUEST)
  return f,lib,hashes
 def test_versioned_four_member_registry_and_v2_only_tuple(self):
  self.assertEqual(cap.REVIEWED_BUNDLES.get(NEW),HASHES)
  self.assertEqual(audit.PROFILE_PRODUCERS[audit.PROFILE],(audit.PRODUCER,))
  self.assertEqual(audit.PROFILE_PRODUCERS[audit.GEOMETRY_PROFILE],(audit.GEOMETRY_PRODUCER,OLD,NEW))
 def test_four_member_job_binding_and_repeat_identity(self):
  f,lib,hashes=self.fixture();row=f.build();bound=row['job']['source_ref_authoring']['renderer_capability']
  self.assertEqual(bound['bundle_id'],NEW);self.assertEqual(set(bound['modules']),set(HASHES))
  self.assertEqual(bound['modules'],{k:{'path':str(lib/k),'sha256':v} for k,v in hashes.items()})
  self.assertEqual(row['job']['package_correspondence']['producer_bundle'],NEW)
  self.assertEqual(row,f.build());self.assertTrue(all(v is False for v in row['job']['source_ref_authoring']['authority'].values()))
 def test_missing_changed_symlink_and_nonregular_helper_fail_closed(self):
  f,lib,_=self.fixture();f.build();helper=lib/'text_content.js';original=helper.read_bytes()
  helper.unlink()
  with self.assertRaises(DeckCompilerError):f.build()
  helper.write_bytes(original+b'// changed\n')
  with self.assertRaisesRegex(DeckCompilerError,'whole reviewed'):f.build()
  helper.unlink();outside=f.root/'synthetic-external-helper';outside.write_bytes(original);helper.symlink_to(outside)
  with self.assertRaisesRegex(DeckCompilerError,'symlink|inside'):f.build()
  helper.unlink();helper.mkdir()
  with self.assertRaisesRegex(DeckCompilerError,'regular'):f.build()
 def test_mixed_core_and_helper_cannot_match_either_whole_bundle(self):
  f,lib,_=self.fixture();f.build()
  for name in HASHES:
   old=(lib/name).read_bytes();(lib/name).write_bytes(old+b'// other version\n')
   with self.subTest(name=name),self.assertRaisesRegex(DeckCompilerError,'whole reviewed'):f.build()
   (lib/name).write_bytes(old)
 def test_old_three_member_descriptor_ignores_unclaimed_helper_and_absence_is_exact(self):
  f=authoring.SourceRefAuthoringTests();f.setUp();self.addCleanup(f.doCleanups)
  before=f.build();lib=f.skill.parent/'scripts/lib';helper=lib/'text_content.js';helper.symlink_to(f.root/'missing-helper')
  self.assertEqual(f.build(),before)
  row=f.enable();descriptor=row['job']['source_ref_authoring']['renderer_capability']
  self.assertEqual(set(descriptor['modules']),set(authoring.MODULES));self.assertNotIn('text_content.js',descriptor['modules'])
  helper.unlink();helper.write_text('unrecognized extra helper is not attested\n');self.assertEqual(f.build(),row)
 def public_fixture(self,actual_library=None):
  registry=copy.deepcopy(cap.REVIEWED_BUNDLES)
  f=geometry.EmitterGeometryCorrespondenceTests();f.setUp();self.addCleanup(f.doCleanups)
  root,project,work,oldjob=f.public_fixture();lib=Path(oldjob['source_ref_authoring']['renderer_capability']['skill']['path']).parent/'scripts/lib'
  if actual_library:
   for name in HASHES:(lib/name).write_bytes((actual_library/name).read_bytes())
  else:registry={NEW:install(lib)}
  guard=patch.object(cap,'REVIEWED_BUNDLES',registry);guard.start();self.addCleanup(guard.stop)
  jobs.prepare_reconstruction_jobs(root);job=read_json(work/'reconstruction_job.json')
  native_path=project/'out/native_object_manifest.json';native=read_json(native_path)
  for row in native['slides']['1']['objects']:row['sourceRefs']['bindings']['jobContentHash']=job['content_hash']
  write_json(native_path,native);trace=read_json(project/'out/render_trace.json');trace['nativeObjectManifestHash']=authoring.sha(native_path)
  trace['hashes'].update(atomsPptx=authoring.sha(lib/'atoms_pptx.js'),atomsHtml=authoring.sha(lib/'atoms_html.js'));write_json(project/'out/render_trace.json',trace)
  return root,project,work,job
 def test_public_finalize_revalidation_rejects_changed_helper_and_keeps_receipt(self):
  root,project,work,job=self.public_fixture();summary=project/'out/visual_qa_summary_final.json'
  shared.finalize_shared_render_qa(root,summary_path=summary);receipt=(work/'worker_receipt.json').read_bytes()
  self.assertTrue(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
  self.assertEqual(read_json(work/'worker_receipt.json')['packageCorrespondence']['bindings']['producer_bundle'],NEW)
  helper=Path(job['source_ref_authoring']['renderer_capability']['modules']['text_content.js']['path']);raw=helper.read_bytes()
  for mutation in ('changed','missing','symlink'):
   helper.unlink()
   if mutation=='changed':helper.write_bytes(raw+b'\n')
   elif mutation=='symlink':
    target=helper.parent/'replacement';target.write_bytes(raw);helper.symlink_to(target)
   with self.subTest(mutation=mutation):
    self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
    with self.assertRaises(DeckCompilerError):audit.audit_job_package(root,job,work)
    with self.assertRaises(DeckCompilerError):shared.finalize_shared_render_qa(root,summary_path=summary)
    self.assertEqual((work/'worker_receipt.json').read_bytes(),receipt)
   if helper.exists() or helper.is_symlink():helper.unlink()
   helper.write_bytes(raw)
  self.assertTrue(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
 def test_public_audit_keeps_signed_flipped_records_unsupported(self):
  root,project,work,job=self.public_fixture();path=project/'out/native_object_manifest.json';native=read_json(path)
  self.assertEqual(audit.audit_job_package(root,job,work)['status'],'CORRESPONDENCE_VERIFIED')
  for change in ({'status':'UNSUPPORTED','reason':'UNSUPPORTED_LINE_DIRECTION'},{'flipH':True},{'flipV':True}):
   updated=copy.deepcopy(native);row=updated['slides']['1']['objects'][0]
   if 'status' in change:row['emitterGeometry'].update(change)
   else:row['emitterGeometry']['transform'].update(change)
   write_json(path,updated);trace=read_json(project/'out/render_trace.json');trace['nativeObjectManifestHash']=authoring.sha(path);write_json(project/'out/render_trace.json',trace)
   with self.subTest(change=change),self.assertRaisesRegex(DeckCompilerError,'UNSUPPORTED_PROFILE'):audit.audit_job_package(root,job,work)
 def test_projected_text_digest_does_not_normalize_wrong_old_emission_or_raw_input(self):
  for logical,wrong,raw in [('A\nB','A\n\nB','A\r\nB'),('A\nBC','A\nB\nC','A\nBC')]:
   p,m=geometry.fixture();obj=m['slides']['1']['objects'][0]
   obj.update(textInputSha256=geometry.base.sha(raw.encode()),textContentSha256=geometry.base.sha(logical.encode()))
   def payload(text):return p['ppt/slides/slide1.xml'].replace(b'A &amp; B',text.encode())
   good={**p,'ppt/slides/slide1.xml':payload(logical)};before=copy.deepcopy(m)
   result=audit.inspect_package(geometry.base.package(good),m,slide=1,physical_index=1,canvas=(100,100),profile=audit.GEOMETRY_PROFILE,producer_bundle=NEW)
   self.assertEqual(result['status'],'CORRESPONDENCE_VERIFIED');self.assertEqual(m,before)
   bad={**p,'ppt/slides/slide1.xml':payload(wrong)}
   with self.assertRaisesRegex(DeckCompilerError,'CORRESPONDENCE_MISMATCH'):
    audit.inspect_package(geometry.base.package(bad),m,slide=1,physical_index=1,canvas=(100,100),profile=audit.GEOMETRY_PROFILE,producer_bundle=NEW)
   with self.assertRaisesRegex(DeckCompilerError,'UNSUPPORTED_PROFILE'):
    audit.inspect_package(geometry.base.package(good),m,slide=1,physical_index=1,canvas=(100,100),profile=audit.PROFILE,producer_bundle=NEW)

if __name__=='__main__':unittest.main()
