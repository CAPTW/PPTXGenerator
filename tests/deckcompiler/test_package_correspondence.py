"""Invented OPC/XML safety and public-gate tests, never a rendered deck claim."""
import copy
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import warnings
from unittest.mock import patch
import zipfile

from presentation_agent.deckcompiler.errors import DeckCompilerError
from presentation_agent.deckcompiler.manifest_io import read_json, write_json

P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
PROFILE='direct-text-shape-raster-v1'
REQUEST={'schema_name':'codex_package_correspondence_request','schema_version':'1.0.0','profile':PROFILE,'enabled':True}
NAME='package_correspondence.json'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def rels(rows):
    return ('<Relationships xmlns="'+REL+'">'+''.join('<Relationship Id="%s" Type="%s" Target="%s" %s/>'%r for r in rows)+'</Relationships>').encode()
def package(parts):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for key,value in parts.items():z.writestr(key,value)
    return out.getvalue()
def fixture(text='A &amp; B', *, width=100,height=100):
    # Full-frame geometry has the same result under all supported source canvases.
    geometry='<a:xfrm><a:off x="0" y="0"/><a:ext cx="12191695" cy="6858000"/></a:xfrm>'
    parts={
      '[Content_Types].xml':b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
      '_rels/.rels':rels([('root',R+'/officeDocument','ppt/presentation.xml','')]),
      'ppt/presentation.xml':f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst><p:sldId id="256" r:id="s1"/></p:sldIdLst><p:sldSz cx="12191695" cy="6858000"/></p:presentation>'.encode(),
      'ppt/_rels/presentation.xml.rels':rels([('s1',R+'/slide','slides/slide1.xml','')]),
      'ppt/slides/slide1.xml':f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/><p:sp><p:spPr>{geometry}</p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'.encode(),
      'ppt/slides/_rels/slide1.xml.rels':rels([]),
    }
    obj={'type':'text','source':'surface.txt','x':0,'y':0,'w':width,'h':height,
      'representation':'native-text','contentEditable':True,'textContentSerialization':'pptxgenjs-paragraph-text-v1',
      'textContentEmitterVersion':'4.0.1','textContentIdentityError':None,'textContentSha256':sha(b'A & B')}
    return parts,{'slides':{'1':{'objects':[obj]}}}

class PackageCorrespondenceTests(unittest.TestCase):
    def setUp(self):self.api=importlib.import_module('presentation_agent.deckcompiler.orchestration.package_correspondence')
    def inspect(self,parts=None,manifest=None,raw=None,**kw):
        p,m=fixture();return self.api.inspect_package(raw if raw is not None else package(parts or p),manifest or m,slide=1,physical_index=1,canvas=(100,100),**kw)
    def reject(self,status,**kw):
        with self.assertRaises(DeckCompilerError) as caught:self.inspect(**kw)
        self.assertEqual(caught.exception.code,'DC_PPTX_PACKAGE_'+status)
    def test_positive_exact_text_and_immutable_inputs(self):
        p,m=fixture();before=copy.deepcopy(m);result=self.inspect(p,m)
        self.assertEqual(result['status'],'CORRESPONDENCE_VERIFIED');self.assertEqual(result['object_count'],1)
        self.assertEqual(result['objects'][0]['content_sha256'],sha(b'A & B'));self.assertEqual(m,before)
        self.assertTrue(all(v is False for v in result['authority'].values()))
    def test_xml_paragraphs_breaks_and_entities_match_emitter_contract(self):
        p,m=fixture('A&amp;B</a:t></a:r><a:br/><a:r><a:t>C');p['ppt/slides/slide1.xml']=p['ppt/slides/slide1.xml'].replace(b'</a:p>',b'</a:p><a:p><a:r><a:t>D</a:t></a:r></a:p>',1)
        m['slides']['1']['objects'][0]['textContentSha256']=sha(b'A&B\nC\nD');self.inspect(p,m)
    def test_text_extensions_cannot_impersonate_direct_run_content(self):
        cases=[
            b'<a:pPr><a:extLst><a:ext uri="urn:synthetic"><a:t>A &amp; B</a:t></a:ext></a:extLst></a:pPr><a:r><a:t/></a:r>',
            b'<a:r><a:rPr><a:extLst><a:ext uri="urn:synthetic"><a:t>A &amp; B</a:t></a:ext></a:extLst></a:rPr><a:t/></a:r>',
            b'<a:r><a:extLst><a:ext uri="urn:synthetic"><a:t>A &amp; B</a:t></a:ext></a:extLst><a:t/></a:r>',
            b'<a:fld><a:t>A &amp; B</a:t></a:fld>',
            b'<a:t>A &amp; B</a:t>',
        ]
        for content in cases:
            p,m=fixture();p['ppt/slides/slide1.xml']=p['ppt/slides/slide1.xml'].replace(b'<a:r><a:t>A &amp; B</a:t></a:r>',content)
            with self.subTest(content=content):self.reject('UNSUPPORTED_PROFILE',parts=p,manifest=m)
        p,m=fixture();self.assertEqual(self.inspect(p,m)['objects'][0]['content_sha256'],sha(b'A & B'))

    def test_content_count_geometry_kind_mutations_fail(self):
        for mutate in ('text','count','geometry','kind'):
            with self.subTest(mutate=mutate):
                p,m=fixture()
                if mutate=='text':p['ppt/slides/slide1.xml']=p['ppt/slides/slide1.xml'].replace(b'A &amp; B',b'X &amp; Y')
                elif mutate=='count':m['slides']['1']['objects']=[]
                elif mutate=='geometry':p['ppt/slides/slide1.xml']=p['ppt/slides/slide1.xml'].replace(b'x="0"',b'x="1"',1)
                else:m['slides']['1']['objects'][0].update(type='shape',source='surface.ell')
                self.reject('CORRESPONDENCE_MISMATCH',parts=p,manifest=m)
    def test_unsupported_geometry_never_rounded(self):
        for key,value in [('x',.00001),('x',-1),('w',1.5),('source','surface.ln'),('x',True)]:
            p,m=fixture();m['slides']['1']['objects'][0][key]=value
            with self.subTest(key=key,value=value):self.reject('UNSUPPORTED_PROFILE',parts=p,manifest=m)
    def test_unsupported_top_level_drawables_and_rotation(self):
        for tag in ('grpSp','graphicFrame','cxnSp','contentPart','AlternateContent'):
            p,m=fixture();p['ppt/slides/slide1.xml']=p['ppt/slides/slide1.xml'].replace(b'</p:spTree>',f'<p:{tag}/></p:spTree>'.encode())
            with self.subTest(tag=tag):self.reject('UNSUPPORTED_PROFILE',parts=p,manifest=m)
        p,m=fixture();p['ppt/slides/slide1.xml']=p['ppt/slides/slide1.xml'].replace(b'<a:xfrm>',b'<a:xfrm rot="60000">');self.reject('UNSUPPORTED_PROFILE',parts=p,manifest=m)
    def test_zip_unsafe_duplicate_names_and_compression(self):
        for key in ('../evil','/root','a/../b','a//b','a\\b'):
            p,m=fixture();p[key]=b'x'
            with self.subTest(key=key):self.reject('INVALID_INPUT',parts=p,manifest=m)
        p,m=fixture();out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for k,v in p.items():z.writestr(k,v)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning);z.writestr('ppt/presentation.xml',p['ppt/presentation.xml'])
        self.reject('INVALID_INPUT',raw=out.getvalue())
        with zipfile.ZipFile(out:=io.BytesIO(),'w',zipfile.ZIP_BZIP2) as z:z.writestr('x',b'a')
        self.reject('UNSUPPORTED_PROFILE',raw=out.getvalue())
    def test_zip_budgets_precede_decompression(self):
        for field,limit in [('MAX_ARCHIVE_BYTES',1),('MAX_MEMBERS',1),('MAX_MEMBER_BYTES',1),('MAX_EXPANDED_BYTES',1)]:
            with self.subTest(field=field),patch.object(self.api,field,limit),patch.object(self.api,'_inflate',side_effect=AssertionError('must reject before inflate')):
                self.reject('INVALID_INPUT')
    def test_forged_eocd_count_rejects_before_zipinfo_allocation(self):
        raw=bytearray(package({f'item{i}':b'x' for i in range(5)}))
        end=raw.rfind(b'PK\x05\x06');struct.pack_into('<HH',raw,end+8,1,1)
        with patch.object(self.api,'MAX_MEMBERS',2),patch.object(self.api.zipfile,'ZipFile',side_effect=AssertionError('central allocation occurred')):
            self.reject('INVALID_INPUT',raw=bytes(raw))

    def test_unsupported_extraction_version_is_structured_before_zipfile(self):
        raw=bytearray(package({'item':b'x'}));central=raw.index(b'PK\x01\x02');struct.pack_into('<H',raw,central+6,99)
        with patch.object(self.api.zipfile,'ZipFile',side_effect=AssertionError('must reject before ZipFile')):
            self.reject('UNSUPPORTED_PROFILE',raw=bytes(raw))

    def test_actual_inflation_size_not_only_central_header(self):
        # Central/local declare a prefix and its CRC. A naive ZipExtFile truncates
        # to that length. The raw deflate stream still expands the full payload.
        raw=bytearray(package({'payload':b'abcd'}));local=raw.index(b'PK\x03\x04');central=raw.index(b'PK\x01\x02')
        import zlib
        crc=zlib.crc32(b'ab')
        struct.pack_into('<I',raw,local+14,crc);struct.pack_into('<I',raw,local+22,2)
        struct.pack_into('<I',raw,central+16,crc);struct.pack_into('<I',raw,central+24,2)
        self.reject('INVALID_INPUT',raw=bytes(raw))
    def test_dtd_entities_encoding_and_malformed_xml_reject(self):
        for raw in (b'<!DOCTYPE a [<!ENTITY x "xx">]><a>&x;</a>',b'<!ENTITY x SYSTEM "file:///x"><a/>',b'<bad', '<a/>'.encode('utf-16')):
            p,m=fixture();p['ppt/presentation.xml']=raw
            with self.subTest(raw=raw):self.reject('INVALID_INPUT',parts=p,manifest=m)
    def test_relationships_escape_external_missing_and_duplicate_id(self):
        for target,mode in [('../../../escape',''),('https://example.invalid/x','TargetMode="External"'),('missing.xml','')]:
            p,m=fixture();p['ppt/slides/_rels/slide1.xml.rels']=rels([('x',R+'/hyperlink',target,mode)])
            self.reject('UNSUPPORTED_PROFILE' if mode else 'INVALID_INPUT',parts=p,manifest=m)
        p,m=fixture();p['ppt/_rels/presentation.xml.rels']=rels([('s1',R+'/slide','slides/slide1.xml',''),('s1',R+'/slide','slides/slide1.xml','')]);self.reject('INVALID_INPUT',parts=p,manifest=m)
    def test_relationship_parent_and_shared_targets_are_valid(self):
        p,m=fixture();p['ppt/media/a.png']=b'invented';p['ppt/slides/_rels/slide1.xml.rels']=rels([('a',R+'/image','../media/a.png',''),('b',R+'/image','../media/a.png','')]);self.inspect(p,m)
    def test_native_shape_and_raster_hash_are_checked(self):
        p,m=fixture();xml=p['ppt/slides/slide1.xml'];start=xml.index(b'<p:txBody>');end=xml.index(b'</p:txBody>')+len(b'</p:txBody>')
        xml=xml[:start]+xml[end:];xml=xml.replace(b'</p:spPr>',b'<a:prstGeom prst="ellipse"/></p:spPr>')
        p['ppt/slides/slide1.xml']=xml;m['slides']['1']['objects'][0].update(type='shape',source='surface.ell')
        self.assertEqual(self.inspect(p,m)['objects'][0]['kind'],'shape')
        p['ppt/slides/slide1.xml']=xml.replace(b'prst="ellipse"',b'prst="rect"');self.reject('CORRESPONDENCE_MISMATCH',parts=p,manifest=m)
        p['ppt/slides/slide1.xml']=xml.replace(b'<p:sp>',b'<p:pic><p:blipFill><a:blip r:embed="img"/></p:blipFill>').replace(b'</p:sp>',b'</p:pic>')
        p['ppt/media/pixel.png']=b'Invented raster bytes for digest test'
        p['ppt/slides/_rels/slide1.xml.rels']=rels([('img',R+'/image','../media/pixel.png','')])
        m['slides']['1']['objects'][0].update(type='image',source='surface.img',representation='raster-image',contentEditable=False,imageIdentityError=None,imageFileSha256=sha(p['ppt/media/pixel.png']))
        self.assertEqual(self.inspect(p,m)['objects'][0]['kind'],'image')
        p['ppt/media/pixel.png']=b'Changed';self.reject('CORRESPONDENCE_MISMATCH',parts=p,manifest=m)

    def test_selected_slide_is_presentation_order_and_map_is_exact(self):
        p,m=fixture();p['ppt/_rels/presentation.xml.rels']=rels([('s1',R+'/slide','slides/renamed.xml','')]);p['ppt/slides/renamed.xml']=p.pop('ppt/slides/slide1.xml');p['ppt/slides/_rels/renamed.xml.rels']=p.pop('ppt/slides/_rels/slide1.xml.rels');self.inspect(p,m)
        m['slides']['2']=copy.deepcopy(m['slides']['1']);self.reject('INVALID_INPUT',parts=p,manifest=m)
    def test_fixed_request_default_parity_and_fail_closed(self):
        import test_source_ref_authoring as upstream
        f=upstream.SourceRefAuthoringTests();f.setUp();self.addCleanup(f.doCleanups)
        before=f.build();self.assertEqual(f.build(),before)
        path=f.work/NAME
        for value in (None,{},dict(REQUEST,enabled=1),dict(REQUEST,profile='arbitrary')):
            write_json(path,value)
            with self.assertRaises(DeckCompilerError):f.build()
        write_json(path,REQUEST)
        with self.assertRaisesRegex(DeckCompilerError,'combined'):f.build()
        f.path.write_text(json.dumps(upstream.REQUEST));f.api.REVIEWED_BUNDLES={self.api.PRODUCER:f.bundles['synthetic-a']}
        row=f.build();self.assertEqual(row['job']['package_correspondence']['request']['sha256'],sha(path.read_bytes()))
        path.unlink();os.mkfifo(path)
        with self.assertRaisesRegex(DeckCompilerError,'regular'):f.build()

    def test_local_input_rejects_symlink_escape_and_fifo_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'target';target.write_bytes(b'a')
            link=root/'link';link.symlink_to(target)
            with self.assertRaisesRegex(ValueError,'symlink'):self.api._local(link,root,100)
            with self.assertRaisesRegex(ValueError,'local root'):self.api._local(root/'..'/'outside',root,100)
            fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError,'regular'):self.api._local(fifo,root,100)
            # Replacement after lstat cannot turn the subsequent open into a
            # blocking FIFO read; the descriptor is checked before any read.
            original=self.api.os.open
            def replace(path,flags):
                target.unlink();os.mkfifo(target);return original(path,flags)
            with patch.object(self.api.os,'open',side_effect=replace):
                with self.assertRaisesRegex(ValueError,'regular'):self.api._local(target,root,100)

    def public_fixture(self):
        import test_source_ref_derivation as upstream
        import test_source_ref_authoring as authoring
        from presentation_agent.deckcompiler.orchestration import reconstruction_jobs as jobs
        from presentation_agent.deckcompiler.orchestration import source_ref_authoring as capability
        f=upstream.SourceRefDerivationTests();f.setUp();self.addCleanup(f.doCleanups)
        root,project,work,oldjob=f.public_fixture()
        skill=Path(oldjob['authoring_contract']['renderer_skill_path'])
        bundles=authoring.SourceRefAuthoringTests.install_modules(skill.parent)
        guard=patch.object(capability,'REVIEWED_BUNDLES',{self.api.PRODUCER:bundles['synthetic-a']});guard.start();self.addCleanup(guard.stop)
        write_json(work/authoring.NAME,authoring.REQUEST);write_json(work/NAME,REQUEST)
        jobs.prepare_reconstruction_jobs(root);job=read_json(work/'reconstruction_job.json')
        native=read_json(project/'out/native_object_manifest.json');tag=native['slides']['1']['objects'][0]['sourceRefs']
        tag['bindings']['jobContentHash']=job['content_hash']
        parts,m=fixture('Invented label',width=job['source_png']['width'],height=job['source_png']['height'])
        obj=m['slides']['1']['objects'][0];obj.update(textContentSha256=sha(b'Invented label'),textLength=14,editable=True)
        # Twelve synthetic text records retain ordinary gates without exemptions.
        single=parts['ppt/slides/slide1.xml'];start=single.index(b'<p:sp>');end=single.index(b'</p:sp>')+len(b'</p:sp>')
        parts['ppt/slides/slide1.xml']=single[:start]+single[start:end]*12+single[end:]
        objects=[copy.deepcopy(obj) for _ in range(12)];objects[0]['sourceRefs']=tag
        native['slides']['1'].update(objects=objects,counts={'text':12},editableObjectCount=12,editableTextLength=168)
        write_json(project/'out/native_object_manifest.json',native)
        metadata_path=work/'visual_qa/pptx_raster_metadata.json';metadata=read_json(metadata_path);pptx=Path(metadata['pptx'])
        pptx.write_bytes(package(parts));metadata.update(pptxSha256=sha(pptx.read_bytes()),physicalSlideIndex=1);write_json(metadata_path,metadata)
        trace_path=project/'out/render_trace.json';trace=read_json(trace_path)
        trace.update(pptxOut=str(pptx),generated={'pptx':str(pptx)},nativeObjectManifestHash=sha((project/'out/native_object_manifest.json').read_bytes()),
          build={'projectRoot':str(project),'nativeObjectManifest':str(project/'out/native_object_manifest.json'),
                 'outputs':{'pptx':str(pptx)},'slides':None,'htmlQaStaticMode':{'expectedSlideSize':{k:job['source_png'][k] for k in ('width','height')}}})
        trace['hashes'].update(atomsPptx=bundles['synthetic-a']['atoms_pptx.js'],atomsHtml=bundles['synthetic-a']['atoms_html.js'])
        write_json(trace_path,trace)
        return root,project,work,job,parts

    def test_public_finalize_and_completion_bind_and_recompute_package(self):
        from presentation_agent.deckcompiler.orchestration import reconstruction_jobs as jobs,shared_render_qa as shared
        root,project,work,job,parts=self.public_fixture()
        receipt_path=work/'worker_receipt.json';before=receipt_path.read_bytes()
        self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
        shared.finalize_shared_render_qa(root,summary_path=project/'out/visual_qa_summary_final.json')
        receipt=read_json(receipt_path);result=receipt['packageCorrespondence']
        self.assertEqual(result['status'],'CORRESPONDENCE_VERIFIED');self.assertEqual(result['object_count'],12)
        self.assertEqual(result['bindings']['job_content_hash'],job['content_hash'])
        self.assertTrue(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
        stable=receipt_path.read_bytes();shared.finalize_shared_render_qa(root,summary_path=project/'out/visual_qa_summary_final.json');self.assertEqual(stable,receipt_path.read_bytes())
        metadata_path=work/'visual_qa/pptx_raster_metadata.json';metadata=read_json(metadata_path);pptx=Path(metadata['pptx'])
        targets=[pptx,project/'out/native_object_manifest.json',work/NAME,metadata_path,project/'out/render_trace.json']
        for path in targets:
            raw=path.read_bytes();path.write_bytes(raw+b'\n')
            with self.subTest(changed=path.name):self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
            path.write_bytes(raw)
        # A resealed package mutation still fails the executable correspondence.
        parts['ppt/slides/slide1.xml']=parts['ppt/slides/slide1.xml'].replace(b'Invented label',b'Altered label!')
        pptx.write_bytes(package(parts));metadata['pptxSha256']=sha(pptx.read_bytes());write_json(metadata_path,metadata)
        self.assertFalse(jobs.validate_reconstruction_job_bundle(root,require_worker_outputs=True)['valid'])
        with self.assertRaisesRegex(DeckCompilerError,'CORRESPONDENCE_MISMATCH'):
            shared.finalize_shared_render_qa(root,summary_path=project/'out/visual_qa_summary_final.json')
        self.assertEqual(stable,receipt_path.read_bytes())

    def test_public_preflight_failure_writes_no_ledger_or_receipt(self):
        from presentation_agent.deckcompiler.orchestration import shared_render_qa as shared
        root,project,work,job,parts=self.public_fixture()
        metadata=read_json(work/'visual_qa/pptx_raster_metadata.json');path=Path(metadata['pptx'])
        parts['ppt/slides/slide1.xml']=parts['ppt/slides/slide1.xml'].replace(b'</p:spTree>',b'<p:graphicFrame/></p:spTree>')
        path.write_bytes(package(parts));metadata['pptxSha256']=sha(path.read_bytes());write_json(work/'visual_qa/pptx_raster_metadata.json',metadata)
        before={p:p.read_bytes() for p in work.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(DeckCompilerError,'UNSUPPORTED_PROFILE'):
            shared.finalize_shared_render_qa(root,summary_path=project/'out/visual_qa_summary_final.json')
        self.assertEqual(before,{p:p.read_bytes() for p in work.rglob('*') if p.is_file()})

if __name__=='__main__':unittest.main()
