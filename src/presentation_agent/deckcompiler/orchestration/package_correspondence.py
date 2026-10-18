"""Opt-in, bounded ordered PPTX correspondence for direct primitive calls only.

This is not an OOXML conformance/visual/semantic verifier. The profile recognizes
reviewed producer bytes, not authenticated provenance or runtime attestation.
It verifies text using XML-decoded paragraph/run/break serialization, not display
text. Styles, fonts, radius, line width and unselected-slide content are unproved.
No archive extraction, external entity resolution, network or renderer execution.
"""
from __future__ import annotations
import binascii
from fractions import Fraction
import hashlib
import io
import math
import os
import posixpath
import re
import stat
import struct
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile
import zlib

from ..errors import DeckCompilerError
from ..identity import content_sha256
from .region_classification_review import _exact, _json_object
from .source_ref_authoring import AUTHORITY, bind_source_ref_authoring

REQUEST_NAME = 'package_correspondence.json'
PROFILE = 'direct-text-shape-raster-v1'
PRODUCER = 'pngtopptx-pr1-pr6-source-refs-v1'
GEOMETRY_PROFILE = 'direct-text-shape-raster-lines-v2'
GEOMETRY_PRODUCER = 'pngtopptx-pr1-pr6-emitter-geometry-v1'
PROFILE_PRODUCERS = {PROFILE:PRODUCER, GEOMETRY_PROFILE:GEOMETRY_PRODUCER}
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_MEMBERS = 4096
MAX_XML_NODES = 200000
MAX_XML_DEPTH = 128
P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
NS={'p':P,'a':A,'r':R}


def _fail(state, message):
    raise DeckCompilerError(code='DC_PPTX_PACKAGE_'+state, stage='reconstruction_completion', message=message)


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _local(path, root, limit):
    # Reject every symlink component and nonregular file before opening (FIFO).
    root=root.resolve()
    if not path.is_absolute() or not path.is_relative_to(root) or not path.resolve().is_relative_to(root) or '..' in path.parts:
        raise ValueError('artifact must remain inside its local root')
    current=root
    for part in path.relative_to(root).parts:
        current=current/part
        if current.is_symlink():raise ValueError('symlink artifact is unsupported')
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode):raise ValueError('artifact must be a regular file')
    if info.st_size>limit:raise ValueError('artifact resource limit exceeded before read')
    flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
    with os.fdopen(os.open(path,flags),'rb') as stream:
        opened=os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino):
            raise ValueError('artifact changed or is not a regular file')
        raw=stream.read(limit+1)
    if len(raw)>limit or len(raw)!=info.st_size:raise ValueError('artifact size changed or resource limit exceeded')
    return raw


def bind_package_correspondence(root, job, work_dir):
    path=work_dir/REQUEST_NAME
    if not path.exists() and not path.is_symlink():return None
    try:
        raw=_local(path,root,65536);request=_json_object(raw)
        _exact(request,{'schema_name','schema_version','profile','enabled'},'package correspondence request')
        profile=request['profile']
        if (profile not in PROFILE_PRODUCERS
                or request!={'schema_name':'codex_package_correspondence_request','schema_version':'1.0.0','profile':profile,'enabled':True}
                or request['enabled'] is not True):
            raise ValueError('request schema/profile/enabled is invalid')
        authoring=job.get('source_ref_authoring',{})
        producer=PROFILE_PRODUCERS[profile]
        if authoring.get('renderer_capability',{}).get('bundle_id')!=producer:
            raise ValueError('package audit profile requires its exact recognized combined producer bundle')
        return {'schema_version':'1.0.0','profile':profile,'producer_bundle':producer,
                'request':{'path':path.relative_to(root).as_posix(),'sha256':_sha(raw)},'authority':AUTHORITY.copy()}
    except (OSError,ValueError,TypeError,KeyError) as exc:_fail('INVALID_INPUT',str(exc))


def _name(name, *, directory=False):
    value=name[:-1] if directory and name.endswith('/') else name
    if (not value or '\\' in value or '\x00' in value or value.startswith('/')
            or any(p in ('','.','..') for p in value.split('/')) or ':' in value):
        raise ValueError('unsafe or noncanonical ZIP member name')
    return value


def _inflate(raw, info, end):
    """Count actual inflated bytes; ZipExtFile alone truncates to central size."""
    offset=info.header_offset
    if offset<0 or offset+30>len(raw) or raw[offset:offset+4]!=b'PK\x03\x04':raise ValueError('invalid local ZIP header')
    if raw[offset+4]>20:_fail('UNSUPPORTED_PROFILE','unsupported local ZIP extraction version')
    flags,method=struct.unpack_from('<HH',raw,offset+6)
    crc,compressed,expanded=struct.unpack_from('<III',raw,offset+14)
    nlen,xlen=struct.unpack_from('<HH',raw,offset+26)
    start=offset+30+nlen+xlen;stop=start+info.compress_size
    if stop>end or start>stop:raise ValueError('overlapping or out-of-bounds ZIP member')
    name=raw[offset+30:offset+30+nlen].decode('utf-8' if flags&0x800 else 'cp437')
    if name!=info.orig_filename or flags!=info.flag_bits or method!=info.compress_type:raise ValueError('local/central ZIP metadata mismatch')
    if not flags&8 and (crc,compressed,expanded)!=(info.CRC,info.compress_size,info.file_size):raise ValueError('local/central ZIP sizes mismatch')
    chunks=[];size=0;check=0;decoder=zlib.decompressobj(-15) if method==8 else None
    for position in range(start,stop,65536):
        block=raw[position:min(position+65536,stop)]
        data=decoder.decompress(block,info.file_size-size+1) if decoder else block
        size+=len(data)
        if size>info.file_size or size>MAX_MEMBER_BYTES:raise ValueError('actual inflated size exceeds declared size or resource limit')
        if decoder and (decoder.unconsumed_tail or decoder.unused_data):raise ValueError('unconsumed/trailing compressed bytes')
        check=binascii.crc32(data,check);chunks.append(data)
    if decoder and not decoder.eof:raise ValueError('truncated deflate stream')
    if size!=info.file_size or check!=info.CRC:raise ValueError('actual inflated size/CRC mismatch')
    return b''.join(chunks)


def _xml(raw):
    # UTF-8 only makes the preparse entity/DTD rejection unambiguous; UTF-16 and
    # alternative encodings are outside this bounded producer profile.
    text=raw.decode('utf-8-sig')
    if '\x00' in text or re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b',text,re.I):raise ValueError('DTD/entity or non-UTF8 XML rejected before parse')
    declared=re.match(r'\s*<\?xml[^>]*encoding\s*=\s*[\'"]([^\'"]+)',text,re.I)
    if declared and declared[1].lower() not in ('utf-8','utf8'):raise ValueError('only UTF-8 XML is supported')
    depth=0;count=0
    parser=ET.iterparse(io.StringIO(text),events=('start','end'))
    for event,_ in parser:
        if event=='start':
            depth+=1;count+=1
            if depth>MAX_XML_DEPTH or count>MAX_XML_NODES:raise ValueError('XML structural resource limit exceeded')
        else:depth-=1
    return parser.root


def _owner(rels_name):
    if rels_name=='_rels/.rels':return ''
    parent,filename=posixpath.split(rels_name)
    if posixpath.basename(parent)!='_rels' or not filename.endswith('.rels'):raise ValueError('invalid relationship part path')
    return posixpath.join(posixpath.dirname(parent),filename[:-5])


def _target(owner, target):
    parsed=urlsplit(target)
    if (not target or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or '\\' in target or '\x00' in target or target.startswith('/')):raise ValueError('unsafe internal relationship target')
    decoded=unquote(target,errors='strict')
    if '\\' in decoded or '\x00' in decoded or decoded.startswith('/') or ':' in decoded:raise ValueError('unsafe encoded relationship target')
    name=posixpath.normpath(posixpath.join(posixpath.dirname(owner),decoded))
    return _name(name)


def _central_directory(raw, offset, size, declared_count):
    """Bound the actual raw records before ZipFile/ZipInfo allocation.

    EOCD counts alone are insufficient: Python walks the central byte range.
    Do not instantiate a ZipFile until the same range has been bounded here.
    """
    end=offset+size;cursor=offset;count=0;expanded_total=0
    while cursor<end:
        if count>=MAX_MEMBERS:raise ValueError('actual central member count resource limit exceeded')
        if cursor+46>end or raw[cursor:cursor+4]!=b'PK\x01\x02':raise ValueError('invalid central directory record bounds/signature')
        if raw[cursor+6]>20:_fail('UNSUPPORTED_PROFILE','ZIP extraction versions above 2.0 are outside this profile')
        compressed,expanded=struct.unpack_from('<II',raw,cursor+20)
        name_len,extra_len,comment_len,disk=struct.unpack_from('<4H',raw,cursor+28)
        local_offset=struct.unpack_from('<I',raw,cursor+42)[0]
        if disk:_fail('UNSUPPORTED_PROFILE','multi-disk central record is unsupported')
        if 0xffffffff in (compressed,expanded,local_offset):_fail('UNSUPPORTED_PROFILE','ZIP64 central record is unsupported')
        if local_offset>=offset:raise ValueError('local record overlaps central directory')
        length=46+name_len+extra_len+comment_len
        if not name_len or cursor+length>end:raise ValueError('central variable fields exceed record bounds')
        expanded_total+=expanded
        if expanded>MAX_MEMBER_BYTES or expanded_total>MAX_EXPANDED_BYTES:raise ValueError('central expanded resource limit exceeded')
        cursor+=length;count+=1
    if cursor!=end or count!=declared_count:raise ValueError('actual/declared central record count mismatch')


def _package(raw):
    if len(raw)>MAX_ARCHIVE_BYTES:raise ValueError('archive resource limit exceeded')
    # Check EOCD counts before ZipFile allocates one object per central entry.
    eocd=raw.rfind(b'PK\x05\x06',max(0,len(raw)-65557))
    if eocd<0 or eocd+22>len(raw):raise ValueError('missing ZIP end record')
    disk,start_disk,on_disk,count,size,offset,comment=struct.unpack_from('<4H2IH',raw,eocd+4)
    if disk or start_disk or on_disk!=count:_fail('UNSUPPORTED_PROFILE','multi-disk ZIP is unsupported')
    if count==65535 or size==0xffffffff or offset==0xffffffff:_fail('UNSUPPORTED_PROFILE','ZIP64 is outside bounded profile')
    if count>MAX_MEMBERS:raise ValueError('ZIP member count resource limit exceeded before central read')
    if eocd+22+comment!=len(raw) or offset+size!=eocd:raise ValueError('invalid ZIP central directory bounds')
    _central_directory(raw,offset,size,count)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if len(infos)!=count:raise ValueError('ZIP central count mismatch')
        if len(infos)>MAX_MEMBERS:raise ValueError('ZIP member count resource limit exceeded')
        names=set();total=0
        for info in infos:
            name=_name(info.orig_filename,directory=info.is_dir())
            if info.orig_filename!=info.filename or name in names:raise ValueError('duplicate/canonical ZIP paths')
            names.add(name)
            if info.flag_bits & ~0x80e:_fail('UNSUPPORTED_PROFILE','encrypted/reserved ZIP flags are unsupported')
            if info.compress_type not in (0,8):_fail('UNSUPPORTED_PROFILE','only stored/deflate ZIP members are supported')
            total+=info.file_size
            if info.file_size>MAX_MEMBER_BYTES or total>MAX_EXPANDED_BYTES:raise ValueError('expanded ZIP resource limit exceeded before inflation')
        ordered=sorted(infos,key=lambda i:i.header_offset)
        parts={}
        for index,info in enumerate(ordered):
            end=ordered[index+1].header_offset if index+1<len(ordered) else z.start_dir
            data=_inflate(raw,info,end)
            if not info.is_dir():parts[info.filename]=data
            elif data:raise ValueError('nonempty ZIP directory')
    xml={name:_xml(data) for name,data in parts.items() if name.endswith(('.xml','.rels'))}
    if '[Content_Types].xml' not in xml:raise ValueError('missing content types part')
    relationships={}
    for name,tree in xml.items():
        if not name.endswith('.rels'):continue
        owner=_owner(name)
        if owner and owner not in parts:raise ValueError('relationship owner is missing')
        if tree.tag!='{'+REL+'}Relationships':raise ValueError('invalid relationships root')
        rows={}
        for rel in tree:
            if rel.tag!='{'+REL+'}Relationship':raise ValueError('invalid relationship row')
            ident,kind,target=rel.get('Id'),rel.get('Type'),rel.get('Target')
            if not ident or ident in rows or not kind or not target:raise ValueError('missing/duplicate relationship identity')
            mode=rel.get('TargetMode','Internal')
            if mode=='External':_fail('UNSUPPORTED_PROFILE','external relationship (including hyperlink) is unsupported')
            if mode!='Internal':raise ValueError('invalid relationship TargetMode')
            resolved=_target(owner,target)
            if resolved not in parts:raise ValueError('relationship target is missing')
            rows[ident]=(kind,resolved)
        relationships[owner]=rows
    return parts,xml,relationships


def _one(parent,path):
    found=parent.findall(path,NS)
    if len(found)!=1:raise ValueError('expected exactly one '+path)
    return found[0]


def _integer(value):
    if not isinstance(value,str) or not re.fullmatch(r'0|[1-9][0-9]*',value):raise ValueError('invalid nonnegative OOXML integer')
    return int(value)


def _emu(value, extent, pixels):
    # Same binary operations as ix/iy, followed by ECMAScript positive toFixed(3)
    # (ties choose larger) and PptxGenJS Math.round(inches*914400).
    scaled=float(value)*extent/pixels
    thousandths=math.floor(Fraction.from_float(scaled)*1000+Fraction(1,2))
    return math.floor((thousandths/1000)*914400+0.5)


def _qualified_geometry(obj, slide):
    """Exact producer projection only; diagnostic bboxes cannot recover it.

    The recognized renderer adds this field only to tagged primitives and
    records the numeric arguments actually passed to its 4.0.1 emitter. This
    validates consistency, not signed provenance or original line direction.
    In particular, safeLineGeom's existing zero-axis inflation is preserved.
    """
    category={
        'surface.txt':('text','none'), 'surface.img':('image','none'),
        'surface.rrect':('panel','none'), 'surface.ell':('shape','none'),
        'surface.chev':('shape','none'), 'surface.ln':('rule','safe-line-geom-v1'),
    }.get(obj.get('source'))
    if category is None:_fail('UNSUPPORTED_PROFILE','unsupported geometry producer primitive')
    if obj.get('type')!=category[0]:raise ValueError('primitive native category does not match producer')
    refs=obj.get('sourceRefs')
    if (not isinstance(refs,dict) or refs.get('schemaVersion')!='slide-image-dual-render.source-refs.v1'
            or type(refs.get('slide')) is not int or refs['slide']!=slide):
        raise ValueError('qualified geometry requires the producer sourceRefs slide/schema')
    # These fields remain diagnostic, not a projection input or direction test.
    if any(type(obj.get(k)) not in (int,float) or not math.isfinite(obj[k]) for k in ('x','y','w','h')):
        raise ValueError('invalid diagnostic source geometry')
    evidence=obj.get('emitterGeometry')
    _exact(evidence,{'schemaVersion','emitterVersion','units','status','reason','sourceNormalization','transform'},'emitter geometry')
    if (any(type(evidence[k]) is not str for k in ('schemaVersion','units','status','sourceNormalization'))
            or (evidence['emitterVersion'] is not None and type(evidence['emitterVersion']) is not str)
            or (evidence['reason'] is not None and type(evidence['reason']) is not str)):
        raise ValueError('invalid emitter geometry qualifier types')
    if (evidence['schemaVersion']!='slide-image-dual-render.emitter-geometry.v1'
            or evidence['emitterVersion']!='4.0.1'):
        _fail('UNSUPPORTED_PROFILE','unqualified emitter geometry schema/version')
    if evidence['units']!='EMU' or evidence['sourceNormalization']!=category[1]:
        raise ValueError('emitter geometry units/normalization does not match producer')
    if evidence['status']=='UNSUPPORTED':_fail('UNSUPPORTED_PROFILE','producer geometry is unsupported')
    if evidence['status']!='PROJECTED' or evidence['reason'] is not None:
        raise ValueError('invalid qualified emitter geometry status/reason')
    transform=evidence['transform']
    _exact(transform,{'x','y','cx','cy','flipH','flipV','rotation'},'emitter transform')
    # The exact producer excludes >=100-inch numeric inputs, but rounding a
    # value just below that bound can legitimately produce exactly 91440000 EMU.
    # bool is an int subclass in Python; accept JSON integers only, never bool
    # or integral floats, and never round purported expected coordinates.
    if (any(type(transform[k]) is not int or not 0<=transform[k]<=91440000 for k in ('x','y','cx','cy'))
            or transform['cx']==0 or transform['cy']==0
            or type(transform['flipH']) is not bool or type(transform['flipV']) is not bool
            or type(transform['rotation']) is not int):
        raise ValueError('invalid exact integer EMU geometry or transform flag types')
    if transform['flipH'] or transform['flipV'] or transform['rotation']!=0:
        _fail('UNSUPPORTED_PROFILE','flipped/rotated geometry is not qualified by this producer')
    return [transform[k] for k in ('x','y','cx','cy')]


def _paragraph_text(body):
    """Only direct a:p / a:r / a:t and direct a:br produce text in v1.

    Never count arbitrary descendant text in properties/extensions. Unsupported
    text-bearing structures fail closed instead of being skipped or interpreted.
    """
    prefix='{'+A+'}';paragraphs=[];consumed=set()
    permitted_body={prefix+n for n in ('bodyPr','lstStyle','p')}
    if any(child.tag not in permitted_body for child in body):_fail('UNSUPPORTED_PROFILE','unsupported text-body structure')
    _one(body,'a:bodyPr')
    if len(body.findall('a:lstStyle',NS))>1:raise ValueError('duplicate text list style')
    for paragraph in body.findall('a:p',NS):
        consumed.add(id(paragraph));fragments=[]
        for name in ('pPr','endParaRPr'):
            if len(paragraph.findall('a:'+name,NS))>1:raise ValueError('duplicate paragraph property')
        for child in paragraph:
            if child.tag==prefix+'r':
                if (any(c.tag not in (prefix+'rPr',prefix+'t') for c in child)
                        or len(child.findall('a:rPr',NS))>1):_fail('UNSUPPORTED_PROFILE','unsupported text run structure')
                text=_one(child,'a:t')
                if list(text):_fail('UNSUPPORTED_PROFILE','nested text markup is unsupported')
                consumed.add(id(text));fragments.append(text.text or '')
            elif child.tag==prefix+'br':
                if any(c.tag!=prefix+'rPr' for c in child) or len(child)>1:_fail('UNSUPPORTED_PROFILE','unsupported line break structure')
                consumed.add(id(child));fragments.append('\n')
            elif child.tag not in (prefix+'pPr',prefix+'endParaRPr'):
                _fail('UNSUPPORTED_PROFILE','unsupported paragraph text structure')
        paragraphs.append(''.join(fragments))
    for element in body.iter():
        if element.tag in (prefix+'t',prefix+'br',prefix+'p') and id(element) not in consumed:
            _fail('UNSUPPORTED_PROFILE','text in properties/extensions cannot impersonate emitted content')
        if element.tag==prefix+'fld':_fail('UNSUPPORTED_PROFILE','dynamic text fields are unsupported')
    return '\n'.join(paragraphs)


def inspect_package(raw, manifest, *, slide, physical_index, canvas, profile=PROFILE, producer_bundle=None):
    """Pure bounded verifier; ordinal correspondence only, no geometry search."""
    try:
        if profile not in PROFILE_PRODUCERS:_fail('UNSUPPORTED_PROFILE','unknown package correspondence profile')
        # Legacy pure callers may omit the v1 producer. V2 must explicitly
        # name its qualified bundle; the public job boundary rehashes the actual
        # whole bundle before calling this pure parser. A field alone is not it.
        if ((profile==GEOMETRY_PROFILE or producer_bundle is not None)
                and producer_bundle!=PROFILE_PRODUCERS[profile]):
            _fail('UNSUPPORTED_PROFILE','package profile does not match its qualified producer bundle')
        if (type(slide) is not int or slide<=0 or type(physical_index) is not int or physical_index<=0
                or len(canvas)!=2 or any(type(v) is not int or not 0<v<=2**31-1 for v in canvas)):
            raise ValueError('invalid source/physical slide or canvas')
        parts,xml,rels=_package(raw)
        roots=[target for kind,target in rels.get('',{}).values() if kind==R+'/officeDocument']
        if len(roots)!=1:raise ValueError('exactly one officeDocument relationship is required')
        presentation=xml[roots[0]]
        if presentation.tag!='{'+P+'}presentation':raise ValueError('invalid presentation root')
        size=_one(presentation,'p:sldSz')
        if (size.get('cx'),size.get('cy'))!=('12191695','6858000'):_fail('UNSUPPORTED_PROFILE','only reviewed 13.333 by 7.5 inch layout is supported')
        slide_ids=_one(presentation,'p:sldIdLst')
        targets=[];ids=set()
        for item in slide_ids:
            ident=item.get('id');rid=item.get('{'+R+'}id')
            if item.tag!='{'+P+'}sldId' or not ident or ident in ids:raise ValueError('invalid/duplicate presentation slide identity')
            ids.add(ident);kind,target=rels[roots[0]][rid]
            if kind!=R+'/slide' or target in targets:raise ValueError('invalid/duplicate slide relationship')
            targets.append(target)
        rows=manifest['slides']
        if not isinstance(rows,dict) or any(not re.fullmatch(r'[1-9][0-9]*',k) for k in rows):raise ValueError('invalid source slide mapping')
        order=sorted(map(int,rows))
        if len(order)!=len(targets) or slide not in order or order.index(slide)+1!=physical_index:raise ValueError('source/physical slide mapping mismatch')
        part=targets[physical_index-1]
        if xml[part].tag!='{'+P+'}sld':raise ValueError('invalid selected slide root')
        tree=_one(xml[part],'p:cSld/p:spTree')
        allowed={'{'+P+'}'+n for n in ('nvGrpSpPr','grpSpPr','sp','pic')}
        if any(c.tag not in allowed for c in tree):_fail('UNSUPPORTED_PROFILE','unsupported top-level drawable in selected slide')
        group=_one(tree,'p:grpSpPr')
        if list(group):
            transform=_one(group,'a:xfrm')
            zero={'off':{'x':'0','y':'0'},'ext':{'cx':'0','cy':'0'},'chOff':{'x':'0','y':'0'},'chExt':{'cx':'0','cy':'0'}}
            if (len(group)!=1 or transform.attrib or len(transform)!=4
                    or any(_one(transform,'a:'+key).attrib!=value for key,value in zero.items())):
                _fail('UNSUPPORTED_PROFILE','transformed slide shape tree is unsupported')
        _one(tree,'p:nvGrpSpPr')
        shapes=[c for c in tree if c.tag in ('{'+P+'}sp','{'+P+'}pic')]
        expected=rows[str(slide)]['objects']
        if not isinstance(expected,list):raise ValueError('manifest objects must be an array')
        if len(shapes)!=len(expected):_fail('CORRESPONDENCE_MISMATCH','ordered object count mismatch')
        result=[]
        for index,(obj,shape) in enumerate(zip(expected,shapes)):
            if not isinstance(obj,dict):raise ValueError('manifest object must be an object')
            if profile==GEOMETRY_PROFILE:
                geometry=_qualified_geometry(obj,slide)
            else:
                box=[obj[k] for k in ('x','y','w','h')]
                if (any(type(v) not in (int,float) or not math.isfinite(v) or v<0 or int(v)!=v or v>2**31-1 for v in box)
                        or obj.get('source')=='surface.ln'):_fail('UNSUPPORTED_PROFILE','v1 requires nonnegative integer non-line boxes')
                if box[2]<=0 or box[3]<=0:_fail('UNSUPPORTED_PROFILE','zero-extent boxes are unsupported')
                geometry=[_emu(v,13.333 if i%2==0 else 7.5,canvas[i%2]) for i,v in enumerate(box)]
            transform=_one(shape,'p:spPr/a:xfrm')
            if transform.attrib:_fail('UNSUPPORTED_PROFILE','rotated/flipped/transformed primitive is unsupported')
            off=_one(transform,'a:off');ext=_one(transform,'a:ext')
            actual=[_integer(off.get(k)) for k in ('x','y')]+[_integer(ext.get(k)) for k in ('cx','cy')]
            if geometry!=actual:_fail('CORRESPONDENCE_MISMATCH',f'geometry mismatch at ordinal {index}')
            body=shape.find('p:txBody',NS)
            if body is not None:body=_one(shape,'p:txBody')
            if obj.get('type') not in (('text','shape','panel','image','rule') if profile==GEOMETRY_PROFILE else ('text','shape','panel','image','icon')):_fail('UNSUPPORTED_PROFILE','unsupported manifest object type')
            kind='image' if shape.tag=='{'+P+'}pic' else 'text' if body is not None else 'shape'
            expected_kind='image' if obj['type'] in ('image','icon') else 'text' if obj['type']=='text' else 'shape'
            if kind!=expected_kind:_fail('CORRESPONDENCE_MISMATCH',f'native kind mismatch at ordinal {index}')
            content=None
            if kind=='text':
                if (obj.get('source')!='surface.txt' or obj.get('representation')!='native-text' or obj.get('contentEditable') is not True
                        or obj.get('textContentSerialization')!='pptxgenjs-paragraph-text-v1' or obj.get('textContentEmitterVersion')!='4.0.1'
                        or obj.get('textContentIdentityError') is not None):_fail('UNSUPPORTED_PROFILE','unqualified emitted text identity')
                text=_paragraph_text(body)
                content=_sha(text.encode('utf-8'))
                if obj.get('textContentSha256')!=content:_fail('CORRESPONDENCE_MISMATCH',f'text content mismatch at ordinal {index}')
            elif kind=='image':
                if obj.get('source')!='surface.img' or obj.get('representation')!='raster-image' or obj.get('contentEditable') is not False or obj.get('imageIdentityError') is not None:_fail('UNSUPPORTED_PROFILE','unqualified raster identity')
                blip=_one(shape,'p:blipFill/a:blip')
                if list(blip) or set(blip.attrib)!={'{'+R+'}embed'}:_fail('UNSUPPORTED_PROFILE','linked/extended image is unsupported')
                image_kind,media=rels[part][blip.attrib['{'+R+'}embed']]
                if image_kind!=R+'/image':raise ValueError('invalid image relationship type')
                if posixpath.splitext(media)[1].lower() not in ('.png','.jpg','.jpeg','.gif','.bmp','.tif','.tiff'):_fail('UNSUPPORTED_PROFILE','non-raster or unsupported image media')
                content=_sha(parts[media])
                if obj.get('imageFileSha256')!=content:_fail('CORRESPONDENCE_MISMATCH',f'image content mismatch at ordinal {index}')
            else:
                presets={'surface.ell':'ellipse','surface.chev':'chevron','surface.rrect':'roundRect'}
                if profile==GEOMETRY_PROFILE:presets['surface.ln']='line'
                preset=presets.get(obj.get('source'))
                if preset is None:_fail('UNSUPPORTED_PROFILE','unsupported native shape source')
                if _one(shape,'p:spPr/a:prstGeom').get('prst')!=preset:_fail('CORRESPONDENCE_MISMATCH',f'shape preset mismatch at ordinal {index}')
            result.append({'manifest_pointer':f'/slides/{slide}/objects/{index}','manifest_row_sha256':content_sha256(obj),
                'package_ordinal':index,'kind':kind,'geometry_emu':actual,**({'content_sha256':content} if content is not None else {})})
        return {'schema_version':'1.0.0','profile':profile,'status':'CORRESPONDENCE_VERIFIED','representation_status':'NOT_ESTABLISHED',
            'authority':AUTHORITY.copy(),'source_slide_order':order,'source_slide':slide,'physical_slide_index':physical_index,'slide_part':part,
            'object_count':len(result),'objects':result}
    except DeckCompilerError:raise
    except NotImplementedError as exc:_fail('UNSUPPORTED_PROFILE',f'unsupported ZIP feature: {exc}')
    except (OSError,ValueError,TypeError,KeyError,IndexError,OverflowError,ET.ParseError,zipfile.BadZipFile,zlib.error,struct.error) as exc:_fail('INVALID_INPUT',str(exc))


def audit_job_package(root, job, work_dir):
    """Recompute before receipt write and again at public completion. No writes."""
    requested=bind_package_correspondence(root,job,work_dir)
    if requested is None:
        if 'package_correspondence' in job:_fail('INVALID_INPUT','bound package audit request is missing')
        return None
    try:
        if content_sha256(requested)!=content_sha256(job.get('package_correspondence')):raise ValueError('stale package audit request binding')
        capability=job['source_ref_authoring']['renderer_capability'];skill=capability['skill']
        current=bind_source_ref_authoring(root,job,work_dir,{'skill_path':skill['path'],'sha256':skill['sha256']})
        if content_sha256(current)!=content_sha256(job['source_ref_authoring']):raise ValueError('stale producer capability')
        project=root/'pngtopptx-project';native_path=project/'out/native_object_manifest.json';trace_path=project/'out/render_trace.json'
        native_raw=_local(native_path,root,MAX_MEMBER_BYTES);trace_raw=_local(trace_path,root,MAX_MEMBER_BYTES)
        native,trace=_json_object(native_raw),_json_object(trace_raw)
        metadata_path=work_dir/'visual_qa/pptx_raster_metadata.json';metadata_raw=_local(metadata_path,root,MAX_MEMBER_BYTES);metadata=_json_object(metadata_raw)
        path=Path(metadata['pptx']);raw=_local(path,project,MAX_ARCHIVE_BYTES)
        if metadata['pptxSha256']!=_sha(raw) or metadata.get('diagnosticOnly') is not True or metadata.get('modifiedPptx') is not False:raise ValueError('invalid package metadata digest/diagnostic flags')
        source_slide=metadata.get('sourceSlideId',metadata.get('slide'))
        if type(source_slide) is not int or source_slide!=job['slide_number'] or metadata.get('mappingMode')!='source-slides-sequential':raise ValueError('invalid package source mapping')
        build=trace['build'];canvas=job['source_png']
        if (build['htmlQaStaticMode']['expectedSlideSize']!={'width':canvas['width'],'height':canvas['height']}
                or trace['projectRoot']!=str(project) or build['projectRoot']!=str(project)
                or trace['pptxOut']!=str(path) or trace['generated']['pptx']!=str(path) or build['outputs']['pptx']!=str(path)
                or trace['nativeObjectManifestHash']!=_sha(native_raw) or build['nativeObjectManifest']!=str(native_path)
                or native.get('source')!='actual-render-surface-calls'):raise ValueError('render trace does not bind package/manifest/canvas')
        for key,name in (('atomsPptx','atoms_pptx.js'),('atomsHtml','atoms_html.js')):
            if trace['hashes'][key]!=capability['modules'][name]['sha256']:raise ValueError('render trace producer mismatch')
        integrated=_local(project/'lib/slides.js',root,MAX_MEMBER_BYTES)
        if trace['hashes']['slidesJs']!=_sha(integrated):raise ValueError('render trace integrated source mismatch')
        selected=build.get('slides')
        if selected is not None:
            if not isinstance(selected,str) or not re.fullmatch(r'[1-9][0-9]*(?:,[1-9][0-9]*)*',selected):raise ValueError('invalid selected source slides')
            values=[int(x) for x in selected.split(',')]
            if len(values)!=len(set(values)) or sorted(values)!=sorted(map(int,native['slides'])):raise ValueError('selected source-slide set mismatch')
        result=inspect_package(raw,native,slide=job['slide_number'],physical_index=metadata['physicalSlideIndex'],canvas=(canvas['width'],canvas['height']),
                               profile=requested['profile'],producer_bundle=requested['producer_bundle'])
        result['bindings']={'job_content_hash':job['content_hash'],'request_sha256':requested['request']['sha256'],
            'producer_bundle':requested['producer_bundle'],'renderer_capability_sha256':content_sha256(capability),
            'package_path':path.relative_to(root).as_posix(),'package_sha256':_sha(raw),'native_manifest_sha256':_sha(native_raw),
            'render_trace_sha256':_sha(trace_raw),'raster_metadata_sha256':_sha(metadata_raw),'integrated_slides_sha256':_sha(integrated)}
        return result
    except DeckCompilerError:raise
    except (OSError,ValueError,TypeError,KeyError) as exc:_fail('INVALID_INPUT',str(exc))
