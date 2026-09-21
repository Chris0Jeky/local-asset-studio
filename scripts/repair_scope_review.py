"""Offline scope review and explicit inverse-alpha mask handoff.

A diagnostic preview is not acceptance. A mask export is not a generation graph.
Prepared inputs are reconstructed from the external plan/request before use.
"""
from __future__ import annotations

import argparse
import base64
from html import escape
from io import BytesIO
import json
from pathlib import Path
import sys

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

SCHEMA = 'studio.repair-scope-review/v1'
MASK_ADAPTER = 'comfy.LoadImage.MASK-inverse-alpha/v1'
MAX_PIXELS = 24_000_000
VIEW_NAMES = ('source-effective.png', 'scope-change.png', 'work-scope.png')


def require(condition, message):
    if not condition: raise ValueError(message)


def _vector(value, length, minimum=0):
    require(type(value) is list and len(value) == length
            and all(type(v) is int and minimum <= v <= MAX_PIXELS for v in value), 'Invalid geometry vector')
    return value


def _size(value):
    value = _vector(value, 2, 1)
    require(value[0] * value[1] <= MAX_PIXELS, 'Review canvas exceeds pixel bound')
    return tuple(value)


def _mask(image, size, *, binary=False):
    require(image.mode == 'L' and image.size == size and not image.info,
            'Use metadata-free same-size L coverage, not source transparency')
    if binary: require(sum(image.histogram()[1:255]) == 0, 'Protection must be binary')


def _support(image):
    return image.point(lambda v: 255 if v else 0)


def _disjoint(mask, protection):
    with _support(mask) as support, ImageChops.multiply(support, protection) as overlap:
        require(overlap.getbbox() is None, 'Write coverage overlaps protection')


def inverse_alpha(mask, protect):
    """Separate RGBA mask carrier: alpha=255-coverage, RGB=0.

    Comfy LoadImage's MASK output inverts normalized alpha. Never substitute this
    carrier for the context image, or interpret source-image alpha as coverage.
    """
    _size(list(mask.size)); _mask(mask, mask.size); _mask(protect, mask.size, binary=True)
    _disjoint(mask, protect)
    result = Image.new('RGBA', mask.size, (0, 0, 0, 255))
    with ImageChops.invert(mask) as alpha: result.putalpha(alpha)
    return result


def _stats(mask):
    histogram = mask.histogram()
    return {'size': list(mask.size), 'bounds': list(mask.getbbox()) if mask.getbbox() else None,
            'support_pixels': mask.width * mask.height - histogram[0],
            'full_coverage_pixels': histogram[255], 'fractional_pixels': sum(histogram[1:255]),
            'coverage_sum_255': sum(i * count for i, count in enumerate(histogram))}


def _png(image):
    with BytesIO() as out:
        image.save(out, format='PNG'); return out.getvalue()


def _preview(image, layers):
    width, height = image.size
    scale = min(1, 1280 / max(width, height))
    size = (max(1, int(width * scale)), max(1, int(height * scale)))
    with image.resize(size, Image.Resampling.NEAREST) as small:
        background = Image.new('RGBA', size, (237, 237, 237, 255))
        draw = ImageDraw.Draw(background)
        for y in range(0, size[1], 16):
            for x in range(0, size[0], 16):
                if (x // 16 + y // 16) % 2: draw.rectangle((x, y, x+15, y+15), fill=(211, 211, 211, 255))
        base = Image.alpha_composite(background, small).convert('RGB'); background.close()
    try:
        for mask, colour in layers:
            with mask.resize(size, Image.Resampling.NEAREST) as displayed, \
                    displayed.point(lambda v: 120 if v else 0) as opacity, Image.new('RGB', size, colour) as tint:
                updated = Image.composite(tint, base, opacity)
            base.close(); base = updated
        return _png(base)
    finally: base.close()


def scope_views(source, images, geometry):
    """Compute full-resolution scope facts and bounded diagnostic PNG views."""
    require(set(images) == {'context', 'work_write', 'work_protect', 'authored_write',
                           'effective_write', 'source_protect'}, 'Unexpected prepared image set')
    size = _size(geometry['source_size']); work_size = _size(geometry['work_size'])
    require(source.mode == 'RGBA' and source.size == size, 'Expected normalized RGBA source')
    require(images['context'].mode == 'RGBA' and images['context'].size == work_size, 'Context dimensions/mode differ')
    x0, y0, x1, y1 = _vector(geometry['context_box'], 4)
    require(x0 < x1 <= size[0] and y0 < y1 <= size[1], 'Context is outside source')
    left, top, right, bottom = _vector(geometry['padding_ltrb'], 4)
    rw, rh = _size(geometry['resized_size'])
    require((left + rw + right, top + rh + bottom) == work_size, 'Padding and working dimensions disagree')
    authored, effective, protect = (images[k] for k in ('authored_write', 'effective_write', 'source_protect'))
    _mask(protect, size, binary=True)
    for mask in (authored, effective):
        _mask(mask, size); _disjoint(mask, protect)
        bounds = mask.getbbox()
        require(bounds is not None and mask.histogram()[0] > 0, 'Local mask must write and preserve pixels')
        require(x0 <= bounds[0] < bounds[2] <= x1 and y0 <= bounds[1] < bounds[3] <= y1, 'Mask escapes context')
    work, work_protect = images['work_write'], images['work_protect']
    _mask(work, work_size); _mask(work_protect, work_size, binary=True); _disjoint(work, work_protect)
    padding = Image.new('L', work_size, 255); padding.paste(0, (left, top, left+rw, top+rh))
    with ImageChops.multiply(work, padding) as writable:
        require(writable.getbbox() is None, 'Padding cannot be writable')
    with ImageChops.invert(work_protect) as unlocked, ImageChops.multiply(unlocked, padding) as unsafe:
        require(unsafe.getbbox() is None, 'Padding must be protected')
    padding.close()
    with _support(authored) as a, _support(effective) as e, \
            ImageChops.subtract(e, a) as added, ImageChops.subtract(a, e) as removed, \
            ImageChops.difference(authored, effective) as difference:
        views = {
            'source-effective.png': _preview(source, [(effective, (230, 63, 62)), (protect, (48, 110, 190))]),
            'scope-change.png': _preview(source, [(added, (13, 164, 100)), (removed, (234, 170, 25))]),
            'work-scope.png': _preview(images['context'], [(work, (230, 63, 62)), (work_protect, (48, 110, 190))])}
        summary = {'authored': _stats(authored), 'effective': _stats(effective), 'work': _stats(work),
                   'added_support_pixels': added.histogram()[255], 'removed_support_pixels': removed.histogram()[255],
                   'coverage_changed_pixels': source.width * source.height - difference.histogram()[0],
                   'protected_pixels': protect.histogram()[255], 'work_protected_pixels': work_protect.histogram()[255],
                   'neural_inference': False, 'semantic_approval': False, 'review_state': 'unreviewed',
                   'candidate_registration': 'not_assessed', 'colour_managed': False}
    if 'coverage_policy' in geometry:
        summary['coverage_policy'] = dict(geometry['coverage_policy'])
    return views, summary


def render_html(views, summary, identities):
    cards = []
    for name, title, legend in (
        (VIEW_NAMES[0], 'Final write area on the source', 'Red: effective write support. Blue: protected pixels.'),
        (VIEW_NAMES[1], 'Support changed by resampling', 'Green: added support. Amber: removed support.'),
        (VIEW_NAMES[2], 'Working context and sampler mask', 'Red: sampler coverage. Blue: protection, including padding.')):
        if name == VIEW_NAMES[1] and 'coverage_policy' in summary:
            title = 'Support changed by mask processing and resampling'
        data = base64.b64encode(views[name]).decode('ascii')
        cards.append(f'<section><h2>{title}</h2><p>{legend}</p><img alt="{title}" src="data:image/png;base64,{data}"></section>')
    metrics = []
    for key, label, value in (
        ('effective_support', 'Pixels in final write area', summary['effective']['support_pixels']),
        ('added_support', 'Pixels added to the area', summary['added_support_pixels']),
        ('removed_support', 'Pixels removed from the area', summary['removed_support_pixels']),
        ('coverage_changed', 'Pixels with changed coverage', summary['coverage_changed_pixels'])):
        require(type(value) is int and value >= 0, 'Scope counts must be nonnegative integers')
        metrics.append(f'<div data-stat="{key}"><dt>{label}</dt><dd>{value:,}</dd></div>')
    payload = escape(json.dumps({'identities': identities, 'scope': summary}, indent=2, ensure_ascii=True, allow_nan=False))
    mask_pin = escape(str(identities.get('expected_effective_write_sha256', 'Not provided')))
    body = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Repair scope review</title><style>
*{box-sizing:border-box}body{font:16px/1.5 system-ui,sans-serif;margin:auto;padding:24px;max-width:1120px;background:#f6f7f8;color:#18222c}
h1{line-height:1.2;margin-bottom:8px}section,details{margin:0;padding:18px;background:white;border:1px solid #bac5ce;border-radius:8px}
.views{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:18px 0}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}
.metrics div{padding:12px;background:#e8edf2;border-radius:8px}dt{font-size:14px}dd{margin:4px 0 0;font-weight:700;font-size:24px;font-variant-numeric:tabular-nums}
img{max-width:100%;height:auto;display:block}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}
code{overflow-wrap:anywhere}h2{font-size:19px;margin:0 0 8px}p{max-width:90ch}summary{cursor:pointer;font-weight:600}
textarea{display:block;width:100%;resize:vertical;padding:10px;font:14px/1.5 ui-monospace,monospace;margin-top:8px;border:1px solid #8798a8;border-radius:4px}
textarea:focus,summary:focus{outline:3px solid #2165aa;outline-offset:3px}.handoff{margin:18px 0}.status{font-size:14px;font-weight:600}
@media(max-width:650px){body{padding:12px}.views{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}section,details{padding:12px}}
</style><h1>Repair scope review</h1>
<p class="status">Review required · No generation submitted</p>
<p>Check the proposed write area and any changes introduced by scaling. Red marks where edits may be written; it does not mean those pixels are already repaired.</p>
'''
    limits = '''<p>These are diagnostic previews, not accepted artwork. Thumbnails are not colour managed and can hide thin regions. The full-resolution L masks are included; their exact counts are shown above.</p>
<details><summary>ComfyUI mask handoff: keep context and mask separate</summary>
<p><code>context.png</code> is the image context. <code>comfy-mask.png</code> is a separate mask carrier: use only its LoadImage <strong>MASK</strong> output. Never use its black RGB output as the context, and never use the context's transparent background as editing permission. Do not invert the exported MASK a second time.</p>
<p>Matching a mask or canvas does not prove anatomy, identity, candidate alignment or native-model compatibility. A model route still needs its own qualification and explicit Start.</p></details>
'''
    if 'coverage_policy' in summary:
        policy = summary['coverage_policy']
        body = body.replace('introduced by scaling', 'introduced by mask processing and resampling')
        body += '<p>' + escape(f"Dilation: {policy['dilate_px']} source pixels; feather: {policy['feather_px']} source pixels.") + '</p>'
    handoff = '<section class="handoff"><h2>Retain the reviewed mask identity</h2><p>After reviewing the full-resolution masks, use this exact value for the separate Apply step. This page does not approve or apply a result.</p><label for="effective-mask-digest">Effective write-mask SHA-256</label><textarea id="effective-mask-digest" readonly rows="2" spellcheck="false">' + mask_pin + '</textarea></section>'
    return (body + '<dl class="metrics">' + ''.join(metrics) + '</dl><div class="views">' + ''.join(cards)
            + '</div>' + limits + handoff + '<details id="raw-evidence"><summary>Technical evidence and file identities</summary><pre>'
            + payload + '</pre></details></html>').encode('utf-8')


def _build(root, plan, request, bundle):
    # Lazy import leaves the pure PIL mask/view helpers usable without a model or
    # the server. The actual packet path always uses existing plan verification.
    from scripts import repair_pixel_transforms as rp
    artifacts, prepared, inputs, raw_receipt = rp.verify_prepared(root, plan, request, bundle)
    original = inputs[0]; images = {}
    try:
        for key, name in rp.PREPARED_FILES.items():
            images[key], _ = rp._decode(artifacts[name], mask=key != 'context')
        views, summary = scope_views(original, images, prepared['geometry'])
        identities = {'request_sha256': prepared['request_sha256'], 'plan_sha256': plan['plan_sha256'],
                      'source_normalized_sha256': request['source_packet']['normalized_sha256'],
                      'bundle_receipt_sha256': rp.rs.digest(raw_receipt),
                      'expected_effective_write_sha256': prepared['files']['effective-write.png']['sha256'],
                      'work_write_sha256': prepared['files']['work-write.png']['sha256']}
        with inverse_alpha(images['work_write'], images['work_protect']) as carrier:
            exported = _png(carrier)
        files = {**artifacts, **views, 'comfy-mask.png': exported,
                 'scope-review.html': render_html(views, summary, identities)}
        report = {'schema': SCHEMA, 'renderer_version': 'scope-diagnostic/v2', **identities, 'scope': summary, 'geometry': prepared['geometry'],
                  'mask_adapter': MASK_ADAPTER, 'mask_polarity': 'alpha=255-work-write; LoadImage MASK=1-alpha/255',
                  'model_compatibility': 'not_qualified', 'neural_inference': False, 'semantic_approval': False,
                  'review_state': 'unreviewed', 'files': {name: {'sha256': rp.rs.digest(raw), 'bytes': len(raw)} for name, raw in files.items()}}
        return files, report
    finally:
        for image in images.values(): image.close()
        for image in inputs[:3]: image.close()


def create_review(root, plan, request, bundle, output):
    """Publish a new diagnostic review; no generation or approval is performed."""
    from scripts import repair_pixel_transforms as rp
    destination = rp._folder(root, output, new=True)
    files, report = _build(root, plan, request, bundle)
    return rp.rs.publish_packet(destination, files, report)


def verify_review(root, plan, request, bundle, review):
    """Reconstruct all review artifacts from the external inputs, read-only."""
    from scripts import repair_pixel_transforms as rp
    folder = rp._folder(root, review)
    expected_files, expected_report = _build(root, plan, request, bundle)
    rp.rs.check_packet_members(folder, {*expected_files, 'receipt.json'})
    report = rp.rs.strict_json(rp.rs.read_bounded(folder/'receipt.json', rp.rs.MAX_METADATA_BYTES, reject_symlink=True))
    require(rp.canonical(report) == rp.canonical(expected_report), 'Review receipt does not reconstruct from external inputs')
    remaining = rp.rs.MAX_OUTPUT_BYTES
    for name, expected in expected_files.items():
        actual = rp.rs.read_bounded(folder/name, remaining, reject_symlink=True); remaining -= len(actual)
        require(actual == expected, 'Review artifact does not reconstruct: ' + name)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='command', required=True)
    for command in ('preview', 'verify'):
        sub = commands.add_parser(command)
        sub.add_argument('--workspace', type=Path, required=True); sub.add_argument('--plan', type=Path, required=True)
        sub.add_argument('--request', type=Path, required=True); sub.add_argument('--request-sha256', required=True)
        sub.add_argument('--bundle', required=True)
        sub.add_argument('--out' if command == 'preview' else '--review', required=True)
    args = parser.parse_args(argv)
    try:
        from scripts import repair_pixel_transforms as rp
        rp.digest(args.request_sha256)
        raw_request = rp.rs.read_bounded(args.request, rp.rs.MAX_METADATA_BYTES)
        require(rp.rs.digest(raw_request) == args.request_sha256, 'External request file changed')
        request = rp.rs.strict_json(raw_request)
        plan = rp.rs.strict_json(rp.rs.read_bounded(args.plan, 4 * rp.rs.MAX_METADATA_BYTES))
        if args.command == 'preview': result = create_review(args.workspace, plan, request, args.bundle, args.out)
        else: result = verify_review(args.workspace, plan, request, args.bundle, args.review)
        print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False)); return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({'error': str(exc), 'neural_inference': False, 'semantic_approval': False}, ensure_ascii=True)); return 2


if __name__ == '__main__': raise SystemExit(main())
