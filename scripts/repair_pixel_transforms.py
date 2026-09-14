"""Explicit offline raster transforms; legacy character-edit packets are unchanged.

The kernels consume decoded normalized buffers, not a model request. They prove
sample preservation, not candidate registration, artistic quality or permission.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from io import BytesIO
import json
from math import ceil
from pathlib import Path
import sys

from PIL import Image, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from scripts.character_edit import check_plan, digest
from scripts.character_edit_pixels import changed_mask, validate_coverage, verify_references
from scripts.repair_proposal import transform
from scripts import repair_source as rs
from scripts.character_study import artifact, canonical, inside, keys, relative, sha

VERSION = 'straight-rgba-bilinear-v1'
MAX_PIXELS = 24_000_000
REQUEST_SCHEMA = 'studio.repair-transform-request/v1'
BUNDLE_SCHEMA = 'studio.repair-transform-bundle/v1'
RESULT_SCHEMA = 'studio.repair-transform-result/v1'
PREPARED_FILES = {'context': 'context.png', 'work_write': 'work-write.png',
                  'work_protect': 'work-protect.png', 'authored_write': 'authored-write.png',
                  'effective_write': 'effective-write.png', 'source_protect': 'source-protect.png'}


def require(condition, message):
    if not condition: raise ValueError(message)


def compile_transform(source_size, spec):
    require(type(spec) is dict and set(spec) == {'version', 'box', 'scale', 'padding', 'alignment'},
            'Declare the exact raster transform fields')
    require(spec['version'] == VERSION, 'Unsupported raster transform version')
    # The existing declaration checker owns rational coordinate arithmetic. This
    # call alone performs no raster operation and never makes v0 proposals jobs.
    geometry = transform(source_size, {key: spec[key] for key in ('box', 'scale', 'padding', 'alignment')})
    require(source_size[0] * source_size[1] <= MAX_PIXELS, 'Source exceeds raster pixel limit')
    require(geometry['work_size'][0] * geometry['work_size'][1] <= MAX_PIXELS,
            'Working canvas exceeds raster pixel limit')
    require(Fraction(1, 4) <= Fraction(*spec['scale']) <= 4, 'Supported raster scale is one quarter through four')
    return {**geometry, 'version': VERSION, 'source_size': list(source_size),
            'context_box': list(spec['box']), 'requested_scale': list(spec['scale']),
            'image_filter': 'bilinear-per-straight-RGBA-channel', 'coverage_filter': 'bilinear',
            'blend': 'Pillow-encoded-sample-L-coverage', 'coverage_operations': 'forward-then-inverse; no dilation or feather',
            'protection_projection': 'conservative-square-max-before-nearest',
            'pillow_version': Image.__version__}


def _resize_rgba(image, size):
    # Resizing RGBA as a single Pillow image premultiplies alpha. Separate L
    # channels make the chosen straight-sample policy explicit, including RGB
    # samples hidden under zero alpha. This is not colour-space conversion.
    return Image.merge('RGBA', tuple(channel.resize(size, Image.Resampling.BILINEAR)
                                    for channel in image.split()))


def _validate_inputs(source, write, protect, geometry):
    require(source.mode == 'RGBA' and list(source.size) == geometry['source_size'], 'Expected normalized RGBA source')
    require(not source.info.get('exif') and 'transparency' not in source.info,
            'Normalize orientation and transparency explicitly before raster preparation')
    require(write.mode == protect.mode == 'L' and write.size == protect.size == source.size,
            'Coverage and protection must be same-size grayscale L')
    require(sum(protect.histogram()[1:255]) == 0, 'Protection must be binary')
    _scope(write, protect, geometry)


def _scope(write, protect, geometry):
    support = write.point(lambda value: 255 if value else 0)
    bounds = support.getbbox()
    require(bounds is not None and write.histogram()[0] > 0, 'Local coverage must edit and preserve source pixels')
    x0, y0, x1, y1 = geometry['context_box']
    require(x0 <= bounds[0] < bounds[2] <= x1 and y0 <= bounds[1] < bounds[3] <= y1,
            'Effective write coverage extends beyond context')
    require(ImageChops.multiply(support, protect).getbbox() is None, 'Write coverage overlaps protection')


def _work_protection(protect, box, resized):
    cropped = protect.crop(box)
    if cropped.getbbox() is None: return Image.new('L', resized, 0)
    # A nearest sample is at most half a source/output cell from any source
    # sample in that cell. The extra whole pixel conservatively covers the
    # bilinear footprint and integer rounding; thin protection cannot vanish.
    # This intentionally overprotects, and does not claim minimal support.
    radius = ceil(max(1, cropped.width / resized[0], cropped.height / resized[1])) + 1
    expanded = cropped.filter(ImageFilter.MaxFilter(2 * radius + 1))
    return expanded.resize(resized, Image.Resampling.NEAREST)


def prepare_pixels(source, authored_write, protect, spec):
    geometry = compile_transform(list(source.size), spec)
    _validate_inputs(source, authored_write, protect, geometry)
    box = tuple(geometry['context_box']); resized = tuple(geometry['resized_size'])
    work_size = tuple(geometry['work_size']); left, top, _, _ = geometry['padding_ltrb']
    crop = source.crop(box)
    inner = _resize_rgba(crop, resized)
    context = Image.new('RGBA', work_size, (0, 0, 0, 0)); context.paste(inner, (left, top))
    context.info = source.info.copy()
    work_inner = authored_write.crop(box).resize(resized, Image.Resampling.BILINEAR)
    work_write = Image.new('L', work_size, 0); work_write.paste(work_inner, (left, top))
    effective = Image.new('L', source.size, 0)
    effective.paste(work_inner.resize(crop.size, Image.Resampling.BILINEAR), box[:2])
    _scope(effective, protect, geometry)
    inner_protect = _work_protection(protect, box, resized)
    require(ImageChops.multiply(work_inner.point(lambda value: 255 if value else 0), inner_protect).getbbox() is None,
            'Conservative work protection overlaps sampler coverage; revise scope or scale')
    work_protect = Image.new('L', work_size, 255); work_protect.paste(inner_protect, (left, top))
    return {'geometry': {**geometry, 'resampling_performed': True},
            'images': {'context': context, 'work_write': work_write, 'work_protect': work_protect,
                       'authored_write': authored_write.copy(), 'effective_write': effective,
                       'source_protect': protect.copy()}}


def render_pixels(source, authored_write, protect, spec, candidate):
    prepared = prepare_pixels(source, authored_write, protect, spec)
    geometry, images = prepared['geometry'], prepared['images']
    require(candidate.mode == 'RGBA' and list(candidate.size) == geometry['work_size'],
            'Candidate must have the exact prepared RGBA working canvas')
    require(candidate.info.get('icc_profile') == source.info.get('icc_profile'), 'Candidate/source colour profiles differ')
    require(not candidate.info.get('exif') and 'transparency' not in candidate.info, 'Candidate orientation/alpha is not normalized')
    left, top, _, _ = geometry['padding_ltrb']; width, height = geometry['resized_size']
    inner_box = (left, top, left + width, top + height)
    candidate_inner = candidate.crop(inner_box)
    no_op = candidate_inner.tobytes() == images['context'].crop(inner_box).tobytes()
    result = source.copy(); box = tuple(geometry['context_box'])
    if not no_op:
        # Padding never participates in inverse resampling. The original full
        # source remains the destination; only the recorded final coverage blends.
        mapped = _resize_rgba(candidate_inner, (box[2] - box[0], box[3] - box[1]))
        repaired = Image.composite(mapped, source.crop(box), images['effective_write'].crop(box))
        result.paste(repaired, box[:2])
    delta = changed_mask(source, result)
    locked = images['effective_write'].point(lambda value: 0 if value else 255)
    outside = ImageChops.multiply(delta, locked).histogram()[255]
    protected = ImageChops.multiply(delta, protect).histogram()[255]
    require(outside == 0 and protected == 0, 'Pixel preservation invariant failed')
    return {'result': result, 'delta': delta, 'effective_write': images['effective_write'],
            'geometry': geometry, 'outside_changes': outside, 'protected_changes': protected,
            'no_op': delta.getbbox() is None, 'neural_inference': False, 'semantic_approval': False}


def _folder(root, name, *, new=False):
    relative(name); base = Path(root).resolve(strict=True); path = base / name
    require(path.parent.resolve().is_relative_to(base), 'Packet parent escapes workspace')
    if not new:
        require(path.resolve(strict=True).is_relative_to(base) and path.is_dir(), 'Expected packet directory inside workspace')
    return path


def _captured_artifact(root, record):
    artifact(record)
    data = rs.read_bounded(inside(root, record['path']), rs.MAX_OUTPUT_BYTES, reject_symlink=True)
    require(rs.digest(data) == record['sha256'], 'Changed artifact: ' + record['path'])
    return data


def _decode(data, *, mask=False, colours=None):
    chunks = rs.scan_png(data, grayscale=mask)
    allowed = (b'IHDR', b'IDAT', b'IEND') if mask else (*rs.COLOUR, b'IHDR', b'IDAT', b'IEND')
    require(all(kind in allowed for kind, _ in chunks), 'Undeclared PNG metadata; normalize explicitly')
    actual_colours = [(kind, value) for kind, value in chunks if kind in rs.COLOUR]
    if colours is not None: require(actual_colours == colours, 'Candidate/source colour chunks differ')
    with BytesIO(data) as buffer, Image.open(buffer) as image:
        require(image.format == 'PNG' and image.mode == ('L' if mask else 'RGBA'), 'Unexpected decoded PNG mode')
        image.load(); return image.copy(), actual_colours


def _encode(image, colours=()):
    if image.mode == 'RGBA': return rs.encode_rgba(image, colours)
    with BytesIO() as buffer, Image.frombytes('L', image.size, image.tobytes()) as clean:
        clean.save(buffer, format='PNG'); return buffer.getvalue()


def _facts(data, image):
    return {'sha256': rs.digest(data), 'bytes': len(data), 'size': list(image.size),
            'mode': image.mode, 'pixel_sha256': rs.digest(image.tobytes())}


def _prepare(root, plan, request):
    check_plan(plan)
    keys(request, {'schema', 'plan_sha256', 'source_packet', 'authored_write', 'protection', 'transform'})
    require(request['schema'] == REQUEST_SCHEMA and request['plan_sha256'] == plan['plan_sha256'],
            'Transform request belongs to another plan or version')
    binding = request['source_packet']; keys(binding, {'path', 'receipt_sha256', 'normalized_sha256'})
    digest(binding['receipt_sha256']); digest(binding['normalized_sha256'])
    require(canonical(request['authored_write']) == canonical(plan['intent']['edit_mask'])
            and canonical(request['protection']) == canonical(plan['intent']['protect_mask']),
            'Transform masks must match the checked edit plan')
    geometry = compile_transform(plan['document']['canvas'], request['transform'])
    require(geometry['context_box'] == plan['intent']['context_box'], 'Transform context differs from checked plan')
    folder = _folder(root, binding['path'])
    normalized, source_receipt, raw_receipt = rs.load_packet(folder)
    require(rs.digest(raw_receipt) == binding['receipt_sha256'], 'Source packet receipt changed')
    require(rs.digest(normalized) == binding['normalized_sha256'] == plan['document']['source']['sha256'],
            'Normalized source differs from request or plan')
    # Resolve identity without reopening the normalized file after verification:
    # the captured bytes above are the exact buffer decoded and used below.
    require(inside(root, plan['document']['source']['path']) == (folder / 'normalized.png').resolve(strict=True),
            'Plan source must name this normalized packet member')
    source, colours = _decode(normalized)
    require(list(source.size) == plan['document']['canvas'], 'Normalized source dimensions differ from plan')
    verify_references(root, plan)
    write, _ = _decode(_captured_artifact(root, request['authored_write']), mask=True)
    protect = Image.new('L', source.size, 0)
    if request['protection'] is not None:
        protect, _ = _decode(_captured_artifact(root, request['protection']), mask=True)
    require(write.size == protect.size == source.size, 'Coverage and protection dimensions differ from source')
    require(sum(protect.histogram()[1:255]) == 0, 'Protection must be binary')
    validate_coverage(plan, write, protect)
    prepared = prepare_pixels(source, write, protect, request['transform'])
    validate_coverage(plan, prepared['images']['effective_write'], protect)
    artifacts, files = {}, {}
    for key, name in PREPARED_FILES.items():
        image = prepared['images'][key]; data = _encode(image, colours)
        artifacts[name] = data; files[name] = _facts(data, image)
    receipt = {'schema': BUNDLE_SCHEMA, 'request_sha256': sha(request), 'request': request,
               'source_normalization': source_receipt['normalization'], 'geometry': prepared['geometry'],
               'files': files, 'mask_convention': 'write:0=preserve,1..255=coverage; protection:255=forbid',
               'neural_inference': False, 'semantic_approval': False, 'review_state': 'unreviewed',
               'candidate_registration': 'not_proven_by_matching_canvas'}
    return artifacts, receipt, (source, write, protect, colours)


def prepare(root, plan, request, output):
    """Publish explicit work images and reconstructed effective source coverage."""
    destination = _folder(root, output, new=True)
    artifacts, receipt, _ = _prepare(root, plan, request)
    return rs.publish_packet(destination, artifacts, receipt)


def verify_prepared(root, plan, request, bundle, *, expected_effective_write_sha256=None):
    """Read/reconstruct a prepared bundle; return captured buffers, never authority.

    Scope review has no accepted mask yet. Apply still requires its caller's
    explicit effective-mask pin. Both consumers use this same verification path.
    """
    if expected_effective_write_sha256 is not None: digest(expected_effective_write_sha256)
    expected_files, expected_receipt, inputs = _prepare(root, plan, request)
    if expected_effective_write_sha256 is not None:
        require(expected_effective_write_sha256 == expected_receipt['files']['effective-write.png']['sha256'],
                'Effective write coverage differs from the caller expected digest')
    folder = _folder(root, bundle)
    rs.check_packet_members(folder, {*expected_files, 'receipt.json'})
    raw_receipt = rs.read_bounded(folder / 'receipt.json', rs.MAX_METADATA_BYTES, reject_symlink=True)
    receipt = rs.strict_json(raw_receipt)
    require(canonical(receipt) == canonical(expected_receipt), 'Prepared receipt does not reconstruct from request')
    remaining = rs.MAX_OUTPUT_BYTES
    for name, expected in expected_files.items():
        actual = rs.read_bounded(folder / name, remaining, reject_symlink=True); remaining -= len(actual)
        require(actual == expected, 'Prepared artifact does not reconstruct: ' + name)
    return expected_files, receipt, inputs, raw_receipt


def apply(root, plan, request, bundle, candidate, output, *, expected_effective_write_sha256):
    """Reconstruct a packet from external authority, then compose a supplied image."""
    destination = _folder(root, output, new=True)
    digest(expected_effective_write_sha256)
    _, receipt, inputs, raw_receipt = verify_prepared(root, plan, request, bundle,
        expected_effective_write_sha256=expected_effective_write_sha256)
    source, write, protect, colours = inputs
    raw_candidate = _captured_artifact(root, candidate)
    patch, _ = _decode(raw_candidate, colours=colours)
    rendered = render_pixels(source, write, protect, request['transform'], patch)
    artifacts, files = {}, {}
    for name, image in (('result.png', rendered['result']), ('changed-pixels.png', rendered['delta'])):
        data = _encode(image, colours); artifacts[name] = data; files[name] = _facts(data, image)
    result = {'schema': RESULT_SCHEMA, 'request_sha256': sha(request), 'request': request,
              'expected_effective_write_sha256': expected_effective_write_sha256,
              'bundle_receipt_sha256': rs.digest(raw_receipt), 'source_normalization': receipt['source_normalization'],
              'candidate': {**candidate, **_facts(raw_candidate, patch)}, 'geometry': rendered['geometry'], 'files': files,
              'changed_pixels': rendered['delta'].histogram()[255],
              'outside_mask_changed_pixels': rendered['outside_changes'], 'protected_changed_pixels': rendered['protected_changes'],
              'exactly_preserved_pixels': source.width * source.height - rendered['delta'].histogram()[255],
              'effective_write': receipt['files']['effective-write.png'], 'no_op': rendered['no_op'],
              'neural_inference': False, 'semantic_approval': False, 'review_state': 'unreviewed',
              'candidate_origin': 'supplied_separately_not_verified_by_this_command',
              'candidate_registration': 'not_proven_by_matching_canvas',
              'warnings': ['No pixel change detected; do not call this a successful correction'] if rendered['no_op'] else []}
    return rs.publish_packet(destination, artifacts, result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'apply'):
        sub = commands.add_parser(command)
        sub.add_argument('--workspace', type=Path, required=True)
        sub.add_argument('--plan', type=Path, required=True)
        sub.add_argument('--request', type=Path, required=True)
        sub.add_argument('--request-sha256', required=True)
        sub.add_argument('--out', required=True)
        if command == 'apply':
            sub.add_argument('--bundle', required=True)
            sub.add_argument('--candidate', required=True)
            sub.add_argument('--candidate-sha256', required=True)
            sub.add_argument('--expected-effective-write-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        digest(args.request_sha256)
        raw_request = rs.read_bounded(args.request, rs.MAX_METADATA_BYTES)
        require(rs.digest(raw_request) == args.request_sha256, 'External request file changed')
        request = rs.strict_json(raw_request)
        plan = rs.strict_json(rs.read_bounded(args.plan, 4 * rs.MAX_METADATA_BYTES))
        if args.command == 'prepare': result = prepare(args.workspace, plan, request, args.out)
        else: result = apply(args.workspace, plan, request, args.bundle,
                             {'path': args.candidate, 'sha256': args.candidate_sha256}, args.out,
                             expected_effective_write_sha256=args.expected_effective_write_sha256)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2)); return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({'error': str(exc), 'neural_inference': False, 'semantic_approval': False})); return 2


if __name__ == '__main__': raise SystemExit(main())
