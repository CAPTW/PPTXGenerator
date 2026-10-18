"""Pure, default-off binding of the exact optional CJS paragraph profile.

Preparation declares a project-local original entry and expected selection;
Python never resolves or executes JavaScript, derives a cache or writes a request.
Post-build descriptors are claims checked against current bytes, not proof that
Node executed them. No transitive, browser, semantic or visual attestation.
"""
from __future__ import annotations
import hashlib
import os
import stat
from pathlib import Path
from ..identity import content_sha256
from ..errors import DeckCompilerError
from .region_classification_review import _exact, _json_object

BUNDLE = 'pngtopptx-pr6-optional-paragraph-loader-v1'
PROFILE = 'pptxgenjs-4.0.1-paragraph-properties-v1'
REQUEST_REL = Path('analysis/pptxgenjs_dependency.json')
ORIGINAL_REL = Path('node_modules/pptxgenjs/dist/pptxgen.cjs.js')
VALIDATOR_PATH = Path(__file__).resolve()
BASE_SHA = '873d182a8e2e1c0b5e522ef146117936b96b9b2024667bd4c1de59e2b031d27a'
RESULT_SHA = '9982d975f1e313be401af8472420e5d5af59f9d9b6707952bf9b879c2b3560e2'
PATCH_SHA = 'c45a7dd7cb18ef27ba931ccbfd1f877511b93fae81adc22ecea0100245bb8e92'
LICENSE_SHA = '7a2bfe96150786ed1908b8e63f98ebab88875c1e79e28faff6649e0f11f77e52'
REVIEWED_MODULES = {
 'object_manifest.js':'af17194a62254106b1f062aa514d4814905da3f2d8acba14a42872a97211b45c',
 'atoms_pptx.js':'666082f0949ad93c4052f2e26d8eea73de64ae5b22632b918069d681150a5b2e',
 'atoms_html.js':'f8f5ff1f5d05cc13af0218635a9cbb8af738c2b2195741a68322235f9242fa66',
 'text_content.js':'2637a8b0a6b70aaafd1e909486cd1eaa4e43d803697e773257e6973e0e20dd98',
 'pptxgenjs_dependency.js':'e0fb1a4d1e1ec37574d5fc2e6492a493668cfdc599abafe084fdb6088cca206e',
 'build.js':'1d3d48dc4f3a2b8928030415079e033e198f5576c6039cbead5b3da5b157df69',
 'slide_pipeline.js':'c5b03d3a4f56d441de7fcb64a9282548cdc98e24e75a551de86fc30bbfe8ad8a',
 'patches/pptxgenjs-4.0.1-paragraph-properties.patch':PATCH_SHA,
 'patches/PptxGenJS-LICENSE':LICENSE_SHA,
}
MODULE_PATHS = {name:('scripts/'+name if name in ('build.js','slide_pipeline.js') else 'scripts/lib/'+name) for name in REVIEWED_MODULES}


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _no_symlinks(path):
    for item in reversed((path,*path.parents)):
        try:info=item.lstat()
        except FileNotFoundError:continue
        if stat.S_ISLNK(info.st_mode):raise ValueError('dependency symlink is unsupported')
        if item!=path and not stat.S_ISDIR(info.st_mode):
            raise ValueError('dependency ancestor must be a directory')


def _read(path, anchor, limit):
    path,anchor=Path(path),Path(anchor)
    if not path.is_absolute() or not anchor.is_absolute() or not path.is_relative_to(anchor) or '..' in path.parts:
        raise ValueError('dependency path must remain inside its declared root')
    # Check every ancestor, including the root itself, before opening a regular file.
    _no_symlinks(path)
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode):raise ValueError('dependency file must be regular before reading')
    if info.st_size>limit:raise ValueError('dependency file exceeds byte limit')
    flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
    with os.fdopen(os.open(path,flags),'rb') as stream:
        opened=os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino):
            raise ValueError('dependency file changed before read')
        raw=stream.read(limit+1)
    if len(raw)>limit or len(raw)!=info.st_size:raise ValueError('dependency file size changed during read')
    return raw


def request_present(root):
    path=Path(root)/'pngtopptx-project'/REQUEST_REL
    try:
        _no_symlinks(path)
        return path.exists() or path.is_symlink()
    except (OSError,ValueError) as exc:
        raise DeckCompilerError(code='DC_SOURCE_REF_AUTHORING_INVALID',stage='reconstruction_job_preparation',
            message=f'dependency request path is invalid: {exc}',artifact_path=path.as_posix()) from exc


def _verified(path, anchor, limit, expected):
    digest=_sha(_read(path,anchor,limit))
    if digest!=expected:raise ValueError(f'dependency sha256 identity mismatch: {path.name}')
    return {'path':str(path),'sha256':digest}


def bind_dependency(root, modules):
    project=Path(root)/'pngtopptx-project'
    original=_verified(project/ORIGINAL_REL,project,1024*1024,BASE_SHA)
    validator={'path':str(VALIDATOR_PATH),'sha256':_sha(_read(VALIDATOR_PATH,VALIDATOR_PATH.parent,65536))}
    request_path=project/REQUEST_REL;request=None
    if request_present(root):
        raw=_read(request_path,project,4096);value=_json_object(raw)
        _exact(value,{'schemaVersion','profile'},'dependency profile request')
        if value!={'schemaVersion':'slide-image-dual-render.pptxgenjs-dependency-request.v1','profile':PROFILE}:
            raise ValueError('dependency request schema/profile is unsupported')
        request={'path':str(request_path),'sha256':_sha(raw)}
    for name,expected in [('patches/pptxgenjs-4.0.1-paragraph-properties.patch',PATCH_SHA),('patches/PptxGenJS-LICENSE',LICENSE_SHA)]:
        if modules[name]['sha256']!=expected:raise ValueError('dependency patch/license identity mismatch')
    cache=project/'.cache/pptxgenjs'/RESULT_SHA
    selected={'path':str(cache/'pptxgen.cjs.js'),'sha256':RESULT_SHA} if request else original.copy()
    license_cache={'path':str(cache/'LICENSE'),'sha256':LICENSE_SHA} if request else None
    # Absence is allowed before the loader runs, but present wrong bytes never are.
    if request:
        for item in (selected,license_cache):
            path=Path(item['path']);_no_symlinks(path)
            if path.exists() or path.is_symlink():_verified(path,project,1024*1024,item['sha256'])
    return {'schema_version':'1.0.0','mode':'PATCHED_EXACT_CJS' if request else 'UNPATCHED_DEFAULT',
        'profile':PROFILE if request else None,'project_path':str(project),'request':request,
        'original_entry':original,'expected_entry':selected,'cache_license':license_cache,'validator':validator,
        'meaning':'declared-exact-selection-not-runtime-attestation',
        'transitive_dependencies_attested':False,'semantic_authority':False,'visual_authority':False}


def expected_descriptor(capability):
    bound=capability['pptxgenjs_dependency'];modules=capability['modules']
    if bound['mode']!='PATCHED_EXACT_CJS':raise ValueError('unpatched default has no patched descriptor')
    return {'schemaVersion':'slide-image-dual-render.pptxgenjs-dependency.v1','profile':PROFILE,
        'qualification':'exact-cjs-bytes-only','projectRoot':bound['project_path'],
        'requestPath':bound['request']['path'],'requestSha256':bound['request']['sha256'],
        'loaderPath':modules['pptxgenjs_dependency.js']['path'],'loaderSha256':modules['pptxgenjs_dependency.js']['sha256'],
        'originalEntryPath':bound['original_entry']['path'],'originalEntrySha256':BASE_SHA,
        'patchPath':modules['patches/pptxgenjs-4.0.1-paragraph-properties.patch']['path'],'patchSha256':PATCH_SHA,
        'licensePath':modules['patches/PptxGenJS-LICENSE']['path'],'licenseSha256':LICENSE_SHA,
        'cacheEntryPath':bound['expected_entry']['path'],'cacheLicensePath':bound['cache_license']['path'],'resultSha256':RESULT_SHA,
        'dependencyResolution':'createRequire(originalEntryPath)',
        'transitiveDependenciesAttested':False,'securitySandbox':False,'semanticAuthority':False,'visualAuthority':False}


def validate_dependency_completion(root, capability):
    """Recheck bound local identity and all three receipts, without JS or writes."""
    bound=capability['pptxgenjs_dependency'];modules=capability['modules']
    current=bind_dependency(root,modules)
    if content_sha256(current)!=content_sha256(bound):raise ValueError('stale dependency selection binding')
    project=Path(root)/'pngtopptx-project'
    paths={'build':project/'out/build_trace.json','trace':project/'out/render_trace.json','native':project/'out/native_object_manifest.json'}
    raw={key:_read(path,project,16*1024*1024) for key,path in paths.items()}
    data={key:_json_object(value) for key,value in raw.items()}
    build,trace,native=data['build'],data['trace'],data['native']
    if (trace.get('projectRoot')!=str(project) or build.get('projectRoot')!=str(project)
            or trace.get('nodePathUsed')!=str(project/'node_modules')
            or build.get('buildJs')!=modules['build.js']['path']
            or trace.get('hashes',{}).get('buildJs')!=modules['build.js']['sha256']
            or trace.get('nativeObjectManifestHash')!=_sha(raw['native'])
            or build.get('nativeObjectManifest')!=str(paths['native'])):
        raise ValueError('dependency trace does not bind declared project, build and native manifest')
    if bound['mode']=='PATCHED_EXACT_CJS':
        for item in (bound['expected_entry'],bound['cache_license']):
            _verified(Path(item['path']),project,1024*1024,item['sha256'])
        expected=expected_descriptor(capability)
        for label,value in data.items():
            if 'pptxgenjsDependency' not in value or content_sha256(value['pptxgenjsDependency'])!=content_sha256(expected):
                raise ValueError(f'dependency descriptor missing or mismatched in {label}')
    else:
        if any('pptxgenjsDependency' in value for value in data.values()):
            raise ValueError('unpatched default must not claim a patched dependency descriptor')
    return {'build':build,'native':native,'trace':trace,'native_raw':raw['native'],'trace_raw':raw['trace'],
        'bindings':{'dependency_selection_sha256':content_sha256(bound),'build_trace_sha256':_sha(raw['build'])}}
