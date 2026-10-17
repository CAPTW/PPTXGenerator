"""Reuse explicit reviewed VSC identities with canonical native measurements.

This adapter does not detect, approve content, or promote VSC sampling boxes.
The caller supplies an independently reviewed identity mapping. Artifact hashes
bind that assertion; they do not authenticate the reviewer. Only the preserved
contain-canvas format and text-block links are supported by this narrow adapter.
"""
from __future__ import annotations

import copy
import hashlib
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image

from ..manifest_io import read_json, write_json
from .semantic_geometry_binding import ASSOCIATION_NAME, _artifact, _error, _read_bound_artifact, _validate_bbox


def prepare_vsc_associations(root: Path, *, slide_number: int, review_path: Path) -> Path:
    """Write the existing association input after genuine preflight validation."""
    from .image_requests import REQUEST_MANIFEST_NAME, validate_image_request_bundle
    from .vector_preflight import slide_preflight_path, validate_vector_preflight_slide_bundle
    from .semantic_geometry_binding import bind_semantic_geometry

    root = root.resolve()
    for report in (validate_image_request_bundle(root), validate_vector_preflight_slide_bundle(root, slide_number)):
        if not report['valid']:
            raise _error('VSC associations require valid existing request and vector preflight: ' + '; '.join(report['issues']))
    manifest = read_json(root / 'image_requests' / REQUEST_MANIFEST_NAME)
    request = next(row for row in manifest['slides'] if row['slide_number'] == slide_number)
    vector = read_json(slide_preflight_path(root, slide_number))['slide']
    job = {
        'workflow_id': manifest['workflow_id'], 'slide_number': slide_number,
        'slide_id': request['slide_id'], 'request_lineage': {'request_id': request['request_id']},
        'source_png': vector['source_png'], 'semantic_sidecar': request['semantic_sidecar'],
        'vector_preflight': {'measurement_inventory': vector['measurement_inventory']},
    }
    review_ref = _artifact(root, review_path)
    review = _read_bound_artifact(root, review_ref, 'vsc_identity_review')
    links = review.get('links')
    if not isinstance(links, list) or not links:
        raise _error('no explicit reviewed links; association remains UNRESOLVED', review_path)
    bindings = [{key: row[key] for key in ('content_pointer', 'content_identity_pointer', 'measurement_collection', 'measurement_id') if key in row} for row in links]
    consume_vsc_review(root, job, review_ref, bindings)
    association = {
        'workflow_id': job['workflow_id'], 'slide_number': slide_number, 'slide_id': job['slide_id'],
        'request_id': request['request_id'], 'source_png_sha256': job['source_png']['sha256'],
        'semantic_sidecar_sha256': request['semantic_sidecar']['sha256'],
        'measurement_inventory_sha256': vector['measurement_inventory']['sha256'],
        'bindings': bindings, 'vsc_identity_review': review_ref,
    }
    work = root / 'pngtopptx-project' / 'work' / f'slide{slide_number:02d}'
    path = work / ASSOCIATION_NAME
    # Validate off the live path. Readers must never see a rejected candidate.
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vsc-association-check-", dir=work) as tmp:
        scratch = Path(tmp)
        write_json(scratch / ASSOCIATION_NAME, association)
        bind_semantic_geometry(root, job, scratch)
    return write_json(path, association)


def consume_vsc_review(root: Path, job: dict[str, Any], review_ref: dict[str, Any], bindings: list[dict[str, Any]]) -> dict[str, Any]:
    """Recheck every provenance link when the actual reconstruction job builds."""
    review = _read_bound_artifact(root, review_ref, 'vsc_identity_review')
    if review.get('status') != 'REVIEWED_IDENTITY_LINKS' or review.get('scope') != 'content_identity_only':
        raise _error('VSC review must explicitly review identity links only')
    if review.get('method') != 'independent_source_and_crop_visual_review' or not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        raise _error('VSC identity links require an explicit independent image/crop reviewer')
    for key, value in {
        'source_png_sha256': job['source_png']['sha256'],
        'semantic_sidecar_sha256': job['semantic_sidecar']['sha256'],
        'measurement_inventory_sha256': job['vector_preflight']['measurement_inventory']['sha256'],
    }.items():
        if review.get(key) != value:
            raise _error(f'VSC review {key} mismatch')
    artifacts = review.get('artifacts')
    if not isinstance(artifacts, dict) or set(artifacts) != {'vsc_inventory', 'canvas_receipt', 'canvas_png', 'reviewed_crops'}:
        raise _error('VSC review requires exact inventory, receipt, canvas, and crop artifact references')
    vsc = _read_bound_artifact(root, artifacts['vsc_inventory'], 'vsc_inventory')
    receipt = _read_bound_artifact(root, artifacts['canvas_receipt'], 'canvas_receipt')
    _read_bound_artifact(root, artifacts['canvas_png'], 'canvas_png', json_object=False)
    crops = artifacts['reviewed_crops']
    if not isinstance(crops, list) or not crops:
        raise _error('VSC review requires inspected crop references')
    for crop in crops:
        _read_bound_artifact(root, crop, 'reviewed_crop', json_object=False)
    if vsc.get('capability') != 'reviewed_observations_core_inventory_v1':
        raise _error('unsupported VSC inventory capability; retain UNRESOLVED')
    transform = _verified_transform(root, job, artifacts['canvas_png'], receipt)
    width, height = receipt['canvas']['size_px']
    if vsc.get('source') != {'canvas_px': {'w': width, 'h': height}, 'canvas_rgb_sha256': receipt['canvas']['rgb_sha256'], 'source_sha256': job['source_png']['sha256']}:
        raise _error('VSC inventory source/canvas identity mismatch')
    if vsc.get('inventory', {}).get('canvas_px') != {'w': width, 'h': height}:
        raise _error('VSC inventory canvas frame mismatch')
    inventory = _read_bound_artifact(root, job['vector_preflight']['measurement_inventory'], 'measurement_inventory')
    if inventory.get('canvas_px') != {'w': job['source_png']['width'], 'h': job['source_png']['height']}:
        raise _error('canonical measurement inventory native frame mismatch')
    links = review.get('links')
    if not isinstance(links, list) or not links or len(links) != len(bindings):
        raise _error('VSC review links must cover exactly the supplied associations')
    rows = vsc.get('block_observation_links', [])
    native_rows = inventory.get('text_blocks', [])
    used = set(); used_measurements = set(); results = []
    for link, binding in zip(links, bindings):
        if not isinstance(link, dict) or any(link.get(key) != binding.get(key) for key in ('content_pointer','content_identity_pointer','measurement_collection','measurement_id')):
            raise _error('VSC review does not match association content/measurement identities')
        if binding['measurement_collection'] != 'text_blocks':
            raise _error('only explicit VSC text-block identity links are supported')
        if not isinstance(link.get('visual_reason'), str) or not link['visual_reason'].strip():
            raise _error('each VSC identity link requires the independent visual review reason')
        if any(not isinstance(link.get(key), str) or not link[key] for key in ('block_id','observation_id','region_id')):
            raise _error('explicit VSC block/observation/region IDs are required')
        matches = [row for row in rows if all(row.get(key) == link.get(key) for key in ('block_id','observation_id','region_id'))]
        if len(matches) != 1 or matches[0]['block_id'] in used:
            raise _error('VSC block/observation/region identity must uniquely identify an unused existing observation')
        observation = matches[0]
        blocks = [row for row in vsc['inventory'].get('text_blocks', []) if row.get('id') == observation['block_id']]
        if len(blocks) != 1 or not any(member.get('observation_id') == observation['observation_id'] for member in blocks[0].get('members', [])):
            raise _error('VSC block/member identity closure mismatch')
        measured = [row for row in native_rows if row.get('id') == binding['measurement_id']]
        if len(measured) != 1 or binding['measurement_id'] in used_measurements:
            raise _error('review must select one unused existing canonical measured text ID')
        _validate_bbox(measured[0].get('bbox_px'), job['source_png']['width'], job['source_png']['height'], root)
        _validate_bbox(observation.get('sampling_bbox_px'), width, height, root)
        # Consistency only. Never copy this envelope into canonical geometry.
        bbox = measured[0]['bbox_px']; envelope = observation['sampling_bbox_px']
        sx, sy, left, top = transform
        edges = (Fraction(bbox['x'])*sx+left, Fraction(bbox['y'])*sy+top,
                 Fraction(bbox['x']+bbox['w'])*sx+left, Fraction(bbox['y']+bbox['h'])*sy+top)
        if not (envelope['x'] <= edges[0] < edges[2] <= envelope['x']+envelope['w'] and envelope['y'] <= edges[1] < edges[3] <= envelope['y']+envelope['h']):
            raise _error('reviewed native measurement is outside the linked VSC sampling envelope; retain UNRESOLVED')
        used.add(observation['block_id']); used_measurements.add(binding['measurement_id'])
        results.append({**copy.deepcopy(link), 'source_native_id': observation.get('source_native_id'),
                        'source_native_member_id': observation.get('source_native_member_id'),
                        'sampling_geometry_status': observation.get('geometry_status'),
                        'mapped_native_edges_canvas_rational': [[v.numerator,v.denominator] for v in edges]})
    return {
        'status':'REVIEWED_IDENTITY_LINKS_BOUND', 'review_artifact':copy.deepcopy(review_ref),
        'artifacts':copy.deepcopy(artifacts), 'links':results,
        'unbound_vsc_observation_ids':[row.get('observation_id') for row in rows if row.get('block_id') not in used],
        'unbound_measured_text_ids':[row.get('id') for row in native_rows if row.get('id') not in used_measurements],
        'unbound_status':'UNRESOLVED_NOT_SEMANTICALLY_ADMITTED',
        'authority':{'identity_link_only':True,'vsc_sampling_geometry_promoted':False,'erase':False,'style':False,'native_admission':False,'rendered_quality':False},
    }


def _verified_transform(root: Path, job: dict[str, Any], canvas_ref: dict[str, Any], receipt: dict[str, Any]) -> tuple[Fraction, Fraction, int, int]:
    if receipt.get('capability') != 'ordinary_rgb_canvas_preparation_v1' or receipt.get('version') != 1:
        raise _error('unsupported VSC canvas preparation receipt')
    for name, reference in (('source', job['source_png']), ('canvas', canvas_ref)):
        _read_bound_artifact(root, reference, name, json_object=False)
        with Image.open(root/reference['path']) as image:
            rgb=image.convert('RGB'); expected=receipt[name]
            if expected.get('file_sha256') != reference['sha256'] or expected.get('size_px') != list(rgb.size) or expected.get('rgb_sha256') != hashlib.sha256(rgb.tobytes()).hexdigest():
                raise _error(f'VSC preparation {name} hash/frame mismatch')
    sw,sh=receipt['source']['size_px']; cw,ch=receipt['canvas']['size_px']
    if [sw,sh] != [job['source_png']['width'],job['source_png']['height']]:
        raise _error('VSC preparation source native frame mismatch')
    t=receipt.get('transform', {})
    if t.get('policy') != 'contain' or t.get('edge_mapping') != 'canvas_edge = source_edge * effective_axis_scale + leading_padding':
        raise _error('unsupported VSC coordinate transform or units')
    try:
        pad=t['padding_ltrb']; resized=t['resized_px']
        if len(pad)!=4 or len(resized)!=2 or any(type(x) is not int or x<0 for x in pad) or any(type(x) is not int or x<=0 for x in resized):
            raise ValueError('invalid dimensions')
        scales=[]
        for axis in ('x','y'):
            scale=t['scale_'+axis]
            if any(type(scale[k]) is not int or scale[k]<=0 for k in ('numerator','denominator')): raise ValueError('invalid scale')
            scales.append(Fraction(scale['numerator'],scale['denominator']))
        sx,sy=scales
        if sx != Fraction(resized[0],sw) or sy != Fraction(resized[1],sh) or resized[0]+pad[0]+pad[2]!=cw or resized[1]+pad[1]+pad[3]!=ch:
            raise ValueError('inconsistent scale/padding')
    except (KeyError,TypeError,ValueError,ZeroDivisionError) as exc:
        raise _error('VSC exact rational transform/frame mismatch') from exc
    return sx,sy,pad[0],pad[1]
