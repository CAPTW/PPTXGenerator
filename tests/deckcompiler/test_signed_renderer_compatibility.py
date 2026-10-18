"""Synthetic registry/public-audit controls; no JavaScript or rendered deck.

Actual reviewed module bytes are a separately verified local integration input;
these public unit fixtures use invented inert module text and declared test QA.
"""
import copy,json,unittest
from unittest.mock import patch
from pathlib import Path
import test_emitter_geometry_correspondence as geometry
import test_source_ref_authoring as authoring
from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json,write_json
from presentation_agent.deckcompiler.orchestration import package_correspondence as api,source_ref_authoring as capability,reconstruction_jobs as jobs,shared_render_qa as shared

NEW='pngtopptx-pr6-signed-line-renderer-v1'
HASHES={'object_manifest.js':'f850cb73728cd1d3808a65506f4f00a9354d6f4897962b07895f6772b192a4a5',
 'atoms_pptx.js':'5e795a64a18b6fee1edf89320634d82c9ff40faee276a20971a59107ad9693fb',
 'atoms_html.js':'2e5179b6856303f5c77ba9aee5ea547125bd7b3d9cf28255533c2a4834dd0a3f'}

class SignedRendererCompatibilityTests(unittest.TestCase):
 def test_exact_new_bundle_and_explicit_two_bundle_v2_membership(self):
  self.assertEqual(capability.REVIEWED_BUNDLES.get(NEW),HASHES)
  self.assertEqual(api.PROFILE_PRODUCERS[api.PROFILE],(api.PRODUCER,))
  self.assertEqual(api.PROFILE_PRODUCERS[api.GEOMETRY_PROFILE],(api.GEOMETRY_PRODUCER,NEW))
 def test_pure_v2_accepts_projected_nonflipped_only_and_cross_version_rejects(self):
  p,m=geometry.fixture()
  result=api.inspect_package(geometry.base.package(p),m,slide=1,physical_index=1,canvas=(100,100),profile=api.GEOMETRY_PROFILE,producer_bundle=NEW)
  self.assertEqual(result['status'],'CORRESPONDENCE_VERIFIED');self.assertEqual(result['representation_status'],'NOT_ESTABLISHED');self.assertTrue(all(v is False for v in result['authority'].values()))
  for profile,producer in [(api.PROFILE,NEW),(api.GEOMETRY_PROFILE,api.PRODUCER),(api.GEOMETRY_PROFILE,'unknown')]:
   with self.subTest(profile=profile,producer=producer),self.assertRaisesRegex(DeckCompilerError,'UNSUPPORTED_PROFILE'):
    api.inspect_package(geometry.base.package(p),m,slide=1,physical_index=1,canvas=(100,100),profile=profile,producer_bundle=producer)
 def test_absent_requests_keep_exact_default_row_and_prompt(self):
  f=authoring.SourceRefAuthoringTests();f.setUp();self.addCleanup(f.doCleanups)
  before=f.build()
  with patch.object(capability,'REVIEWED_BUNDLES',{NEW:f.bundles['synthetic-a']}):self.assertEqual(f.build(),before)
 def test_public_job_binds_actual_compatible_id_and_rejects_mixed_modules(self):
  f=authoring.SourceRefAuthoringTests();f.setUp();self.addCleanup(f.doCleanups);write_json(f.path,authoring.REQUEST);write_json(f.work/api.REQUEST_NAME,geometry.REQUEST)
  with patch.object(capability,'REVIEWED_BUNDLES',{NEW:f.bundles['synthetic-a'],api.GEOMETRY_PRODUCER:f.bundles['synthetic-b']}):
   row=f.build();self.assertEqual(row['job']['package_correspondence']['producer_bundle'],NEW)
   self.assertEqual(row['job']['source_ref_authoring']['renderer_capability']['bundle_id'],NEW)
   (f.skill.parent/'scripts/lib/atoms_pptx.js').write_text('// Invented inert fixture synthetic-b atoms_pptx.js; must never execute\n')
   with self.assertRaisesRegex(DeckCompilerError,'whole reviewed'):f.build()
 def public_fixture(self,actual_library=None):
  original_registry=copy.deepcopy(capability.REVIEWED_BUNDLES)
  f=geometry.EmitterGeometryCorrespondenceTests();f.setUp();self.addCleanup(f.doCleanups)
  root,project,work,oldjob=f.public_fixture()
  skill=Path(oldjob['source_ref_authoring']['renderer_capability']['skill']['path']);lib=skill.parent/'scripts/lib'
  if actual_library:
   for name in authoring.MODULES:(lib/name).write_bytes((actual_library/name).read_bytes())
   registry=original_registry
  else:registry={NEW:copy.deepcopy(capability.REVIEWED_BUNDLES[api.GEOMETRY_PRODUCER])}
  guard=patch.object(capability,'REVIEWED_BUNDLES',registry);guard.start();self.addCleanup(guard.stop)
  jobs.prepare_reconstruction_jobs(root);job=read_json(work/'reconstruction_job.json')
  native_path=project/'out/native_object_manifest.json';native=read_json(native_path)
  for row in native['slides']['1']['objects']:row['sourceRefs']['bindings']['jobContentHash']=job['content_hash']
  write_json(native_path,native);trace=read_json(project/'out/render_trace.json');trace['nativeObjectManifestHash']=geometry.base.sha(native_path.read_bytes())
  trace['hashes'].update(atomsPptx=authoring.sha(lib/'atoms_pptx.js'),atomsHtml=authoring.sha(lib/'atoms_html.js'));write_json(project/'out/render_trace.json',trace)
  return root,project,work,job
 def test_public_audit_and_completion_accept_ordinary_but_reject_signed_or_flip_records(self):
  root,project,work,job=self.public_fixture();summary=project/'out/visual_qa_summary_final.json'
  shared.finalize_shared_render_qa(root,summary_path=summary);receipt=(work/'worker_receipt.json').read_bytes()
  self.assertEqual(read_json(work/'worker_receipt.json')['packageCorrespondence']['bindings']['producer_bundle'],NEW)
  self.assertTrue(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
  native_path=project/'out/native_object_manifest.json';baseline=read_json(native_path)
  for change in ({'status':'UNSUPPORTED','reason':'UNSUPPORTED_LINE_DIRECTION'},{'flipH':True},{'flipV':True}):
   native=copy.deepcopy(baseline);obj=native['slides']['1']['objects'][0]
   obj.update(type='rule',source='surface.ln');obj['emitterGeometry']['sourceNormalization']='safe-line-geom-v1'
   if 'status' in change:obj['emitterGeometry'].update(change)
   else:obj['emitterGeometry']['transform'].update(change)
   write_json(native_path,native);trace=read_json(project/'out/render_trace.json');trace['nativeObjectManifestHash']=geometry.base.sha(native_path.read_bytes());write_json(project/'out/render_trace.json',trace)
   with self.subTest(change=change):
    with self.assertRaisesRegex(DeckCompilerError,'UNSUPPORTED_PROFILE'):api.audit_job_package(root,job,work)
    self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
    with self.assertRaises(DeckCompilerError):shared.finalize_shared_render_qa(root,summary_path=summary)
    self.assertEqual((work/'worker_receipt.json').read_bytes(),receipt)

if __name__=='__main__':unittest.main()
