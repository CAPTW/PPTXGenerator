"""Default-off author guidance for exact reviewed sourceRefs-capable modules.

The local request and byte-bundle registry establish compatibility only, not
signed provenance, permission, semantic truth or runtime attestation. Files are
rechecked when public job validation rebuilds the expected row. A later renderer
process can still load changed files: this is not a runtime TOCTOU guarantee.
No JavaScript is parsed, imported or executed to discover the capability.
"""
from __future__ import annotations
import hashlib
import json
import stat
from pathlib import Path

from ..errors import DeckCompilerError
from .region_classification_review import _exact, _json_object

REQUEST_NAME = 'source_ref_authoring.json'
RECOGNITION_VERSION = 'reviewed-source-refs-bundles-v1'
# Whole bundles, never independent per-file allowlists. These are reviewed
# draft compatibility identities, not canonical renderer pins or signatures.
# PR6 069c4d208fda516dfe034a589db65a72773b7af3 and the reviewed PR1+PR6 merge.
REVIEWED_BUNDLES = {
    'pngtopptx-pr6-source-refs-v1': {
        'object_manifest.js':'63e5066cc9c9a7fb8c4875f1ab53f171de5e3e1b79f914587b993846131fd95a',
        'atoms_pptx.js':'78e42fd2f4a5c521f84be0f61bb2cf906d0b10cb87048012a17b1c447b2b42c6',
        'atoms_html.js':'b487d59a25c14a872eb803c3d0a6e0e801135f05be2fdd40cd38c59b26b32acb',
    },
    'pngtopptx-pr1-pr6-source-refs-v1': {
        'object_manifest.js':'21c5cbef12d34410bfa2acf2d24760329b83524273f9e239bf9ae9fcbfa2f08e',
        'atoms_pptx.js':'a01757a582fede4540116940316c171518246f13499f84f0de595e9068ab28da',
        'atoms_html.js':'b487d59a25c14a872eb803c3d0a6e0e801135f05be2fdd40cd38c59b26b32acb',
    },
    # Independently reviewed emitter-geometry v1 compatibility bundle. The
    # versioned package profile qualifies its evidence separately; this is not
    # a canonical renderer pin, signature or later runtime attestation.
    'pngtopptx-pr1-pr6-emitter-geometry-v1': {
        'object_manifest.js':'f850cb73728cd1d3808a65506f4f00a9354d6f4897962b07895f6772b192a4a5',
        'atoms_pptx.js':'3262e57a847ae4c6fc30e52582bf004975af048c33feb0f512cf41f6623d9ad7',
        'atoms_html.js':'b487d59a25c14a872eb803c3d0a6e0e801135f05be2fdd40cd38c59b26b32acb',
    },
}
MODULE_NAMES = ('object_manifest.js', 'atoms_pptx.js', 'atoms_html.js')
AUTHORITY = {k: False for k in ('semantic_truth', 'text_removal', 'native_admission', 'vector_eligibility', 'quality_accepted')}


def _regular_bytes(path: Path, anchor: Path) -> bytes:
    if not path.is_absolute() or not anchor.is_absolute():
        raise ValueError('capability paths must be absolute')
    if anchor.is_symlink() or not path.resolve().is_relative_to(anchor.resolve()):
        raise ValueError('file must remain inside its local root without symlinks')
    relative = path.relative_to(anchor)
    current = anchor
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('file must remain inside its local root without symlinks')
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('file must be a regular file before reading')
    return path.read_bytes()


def bind_source_ref_authoring(root: Path, job: dict, work_dir: Path, renderer: dict) -> dict | None:
    path = work_dir / REQUEST_NAME
    if not path.exists() and not path.is_symlink():
        return None
    try:
        raw = _regular_bytes(path, root.resolve())
        request = _json_object(raw)
        _exact(request, {'schema_name', 'schema_version', 'enabled'}, 'source-ref authoring request')
        if (request['schema_name'] != 'codex_source_ref_authoring_request'
                or request['schema_version'] != '1.0.0' or request['enabled'] is not True):
            raise ValueError('request requires the supported schema and enabled true')
        review = job.get('region_classification_review')
        if not isinstance(review, dict) or review.get('status') != 'STRUCTURALLY_BOUND_REVIEW':
            raise ValueError('source-ref authoring requires the validated PR21 review')
        if review['coverage']['observation_count'] == 0:
            raise ValueError('empty observation scope is unsupported; do not fabricate objects to enable it')
        skill = Path(renderer['skill_path'])
        base = skill.parent
        skill_sha = hashlib.sha256(_regular_bytes(skill, base)).hexdigest()
        if renderer.get('sha256') != skill_sha:
            raise ValueError('renderer Skill digest does not match the execution plan')
        modules = {}
        for name in MODULE_NAMES:
            module = base / 'scripts' / 'lib' / name
            modules[name] = {'path': module.as_posix(), 'sha256': hashlib.sha256(_regular_bytes(module, base)).hexdigest()}
        observed = {name: data['sha256'] for name, data in modules.items()}
        recognized = next((name for name, hashes in REVIEWED_BUNDLES.items() if observed == hashes), None)
        if recognized is None:
            raise ValueError('installed renderer does not match a whole reviewed sourceRefs bundle')
        return {
            'schema_version':'1.0.0', 'request':{'path':path.relative_to(root.resolve()).as_posix(), 'sha256':hashlib.sha256(raw).hexdigest()},
            'renderer_capability':{'recognition_version':RECOGNITION_VERSION, 'bundle_id':recognized,
                'meaning':'reviewed-byte-compatibility-not-signed-or-runtime-attestation',
                'skill':{'path':skill.as_posix(), 'sha256':skill_sha}, 'modules':modules},
            'post_render_requirement':'at_least_one_valid_tagged_surface_row',
            'empty_observation_scope':'unsupported', 'authority':AUTHORITY.copy(),
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise DeckCompilerError(code='DC_SOURCE_REF_AUTHORING_INVALID', stage='reconstruction_job_preparation',
            message=f'source-ref authoring request is invalid: {exc}', artifact_path=path.as_posix()) from exc


def source_ref_authoring_prompt(job: dict) -> str:
    if 'source_ref_authoring' not in job:
        return ''
    review = job['region_classification_review']
    metadata = {
        'schemaVersion':'slide-image-dual-render.source-refs.v1', 'slide':job['slide_number'],
        'bindings':{'jobContentHash':job['content_hash'], 'sourcePngSha256':job['source_png']['sha256'],
            'measurementInventorySha256':job['vector_preflight']['measurement_inventory']['sha256'],
            'reviewArtifactSha256':review['review_artifact']['sha256']},
        'claim':{'kind':'extra', 'groupId':'replace-with-explicit-unresolved-group', 'purpose':'unresolved'},
        'authority':AUTHORITY.copy(),
    }
    identities = {
        'recorded_claims':[{k:row[k] for k in ('collection','observation_id','role')}
            for row in review['decisions'] if row['review_status']=='recorded' and row['role'] in ('text','graphic')],
        'unresolved_observations':review['coverage']['needs_review'],
    }
    return f'''
This job explicitly opts into source-reference provenance. Its installed surface
module bundle matched reviewed bytes during preparation and job validation.
This is capability compatibility, not signed provenance or later runtime
attestation. Use the same official `s.withSourceRefs(metadata)` surface for both
backends; never branch by backend or put provenance fields in drawing options.
Only call the existing img/rrect/ell/chev/ln/txt primitives or existing helpers
with the tagged receiver. The following complete metadata example is an
UNRESOLVED extra, not a drawing instruction or permission to admit an object.
Keep all common fields exactly as shown; replace its claim with the explicit
source/group claim appropriate to an actually authored call:

```json
{json.dumps(metadata, indent=2)}
```

For a source claim, use exactly kind `observation`, a nonempty unique groupId,
source {{collection, observation_id}}, glyphMembers [], and disposition
`linked`, `unresolved`, or `deferred`. These are the exact namespaced IDs:

```json
{json.dumps(identities, indent=2)}
```

Recorded roles above remain advisory, not semantic truth or native/vector
admission. A linked claim still needs the existing independent classification
and authoring requirements. Unknown, disputed and unreviewed observations must
use unresolved/deferred; this is not permission to remove protected OCR.
Do not infer glyph grouping from overlap, array order or text similarity. Only
explicitly justified reviewed text candidates may be listed as glyphMembers
of one protected text primary; each namespace+ID has a single group owner.
Use that same claim on each call of a multi-call helper; each call remains a
separate manifest row. Do not create duplicate owners or collapse several
emitted calls into one. An explicit extra claim needs exactly kind `extra`, a
unique groupId and purpose `decorative`, `background` or `unresolved`.
Keep unresolved relationships explicit; do not tag unrelated outputs as the
missing observation. Observations with no authored call remain unresolved.
The opt-in post-render consumer requires at least one valid tagged surface row.
No objects may be invented to satisfy that requirement. If no legitimate
representation can be authored under existing gates, report the blocker.
Partial tagging is incomplete accounting/representation, not full preservation.
All authority fields remain false; these annotations alone establish neither
serialized PPTX identity nor rendered quality. Do not manually repair the ledger
or alter immutable source measurements/review to obtain acceptance.
'''
