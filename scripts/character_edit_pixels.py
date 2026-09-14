"""Prepare editable context bundles and apply hash-bound candidate patches offline.

0 in edit-mask preserves source; 255 permits replacement. In protection masks,
255 forbids editing. No network, model execution, scaling, or automatic approval.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image, ImageChops
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.character_study import (canonical, file_sha, inside, keys, read_json,
    relative, require, sha, verify_artifact, write_json)
from scripts.character_edit import check_plan, digest


def png(path: Path) -> Image.Image:
    with Image.open(path) as im:
        require(im.format == 'PNG' and im.width * im.height <= 24000000, 'Expected PNG up to 24 million pixels')
        require(getattr(im, 'n_frames', 1) == 1, 'Animated PNG unsupported')
        require(im.info.get('exif') is None, 'Normalize EXIF orientation explicitly before editing')
        im.load(); return im.copy()


def changed_mask(a: Image.Image, b: Image.Image) -> Image.Image:
    require(a.size == b.size, 'Cannot compare differing dimensions')
    # RGBA.getbbox() defaults to alpha-only in some Pillow versions. Compare ALL
    # channels, including invisible RGB, to prove decoded-pixel preservation.
    diff = ImageChops.difference(a.convert('RGBA'), b.convert('RGBA'))
    maximum = Image.new('L', a.size, 0)
    for channel in diff.split(): maximum = ImageChops.lighter(maximum, channel)
    return maximum.point(lambda x: 255 if x else 0)


def verify_references(root: Path, plan: dict) -> None:
    """Check the current dependencies of an already checked edit plan."""
    for actor in plan['document']['actors']:
        verify_artifact(root, actor['canon'])
        for reference in actor['references']: verify_artifact(root, reference['image'])
    request = plan['intent']
    if request['layout'] is not None:
        for actor in request['layout']['actors']:
            if actor['pose_reference'] is not None: verify_artifact(root, actor['pose_reference'])


def _inputs(root: Path, plan: dict) -> tuple[Image.Image, Image.Image, Image.Image]:
    check_plan(plan); doc = plan['document']; request = plan['intent']
    source = png(verify_artifact(root, doc['source']))
    require(list(source.size) == doc['canvas'] and source.mode in {'RGB', 'RGBA'}, 'Source dimensions/mode changed')
    verify_references(root, plan)
    mask = png(verify_artifact(root, request['edit_mask']))
    require(mask.mode == 'L' and mask.size == source.size, 'Edit mask must be same-size grayscale L')
    protect = Image.new('L', source.size, 0)
    if request['protect_mask'] is not None:
        protect = png(verify_artifact(root, request['protect_mask']))
        require(protect.mode == 'L' and protect.size == source.size, 'Protection mask must be same-size grayscale L')
        require(sum(protect.histogram()[1:255]) == 0, 'Protection mask is binary: white forbids editing')
    validate_coverage(plan, mask, protect)
    return source, mask, protect


def validate_coverage(plan: dict, mask: Image.Image, protect: Image.Image) -> None:
    """Apply the existing plan exclusions to authored or derived L coverage."""
    doc = plan['document']; request = plan['intent']
    support = mask.point(lambda x: 255 if x else 0)
    require(support.getbbox() is not None, 'Empty edit mask')
    if request['operation'] != 'scenario':
        require(mask.histogram()[0] > 0, 'Local changes must preserve some pixels')
    require(ImageChops.multiply(support, protect).getbbox() is None, 'Edit mask overlaps a protected region')
    x0, y0, x1, y1 = request['context_box']; sx0, sy0, sx1, sy1 = support.getbbox()
    require(x0 <= sx0 < sx1 <= x1 and y0 <= sy0 < sy1 <= y1, 'Edit mask extends beyond context box')
    if request['layout'] is not None:
        for contact in request['layout']['contact_regions']:
            cx0, cy0, cx1, cy1 = contact['bounds']
            require(x0 <= cx0 < cx1 <= x1 and y0 <= cy0 < cy1 <= y1, 'Contact region outside context')
            require(support.crop(tuple(contact['bounds'])).getbbox() is not None, 'Contact region has no editable pixels')
    # Conservative envelopes. For crossing limbs, choose a joint interaction
    # or improve the document's reviewed envelopes, never silently weaken them.
    for actor in doc['actors']:
        if actor['id'] not in plan['targets']:
            require(support.crop(tuple(actor['bounds'])).getbbox() is None,
                    'Edit overlaps non-target actor: ' + actor['id'])


def _patches(source: Image.Image, mask: Image.Image, plan: dict) -> tuple[dict, dict]:
    request = plan['intent']; box = tuple(request['context_box'])
    crop = source.crop(box)
    # PNG tRNS is metadata on RGB images. Materialize it before pasting onto a
    # fresh canvas, otherwise transparent pixels become opaque in model context.
    # Leave ordinary RGB/RGBA contexts unchanged for existing bundle compatibility.
    if crop.mode == 'RGB' and 'transparency' in crop.info: crop = crop.convert('RGBA')
    edit = mask.crop(box); width, height = crop.size
    align = request['patch_alignment']; pw = (-width) % align; ph = (-height) % align
    require((width + pw) * (height + ph) <= 24000000, 'Padded patch exceeds pixel budget')
    context = Image.new(crop.mode, (width + pw, height + ph), 0); context.paste(crop, (0, 0))
    padded = Image.new('L', context.size, 0); padded.paste(edit, (0, 0))
    # Context padding is explicitly black/transparent, not a resizing operation.
    if 'icc_profile' in source.info: context.info['icc_profile'] = source.info['icc_profile']
    meta = {'context_box': list(box), 'unpadded_size': [width, height],
            'model_size': list(context.size), 'padding_ltrb': [0, 0, pw, ph],
            'padding_policy': 'zero-fill; edit mask zero in padding; no resampling',
            'mask_convention': 'edit:0=preserve,255=replace; protection:255=forbid'}
    return {'context.png': context, 'edit-mask.png': padded}, meta


@contextmanager
def _new_output(root: Path, name: str):
    """Single trusted local writer, as the repository requires; not a sandbox."""
    relative(name); base = root.resolve(strict=True); dest = base / name
    require(not dest.exists() and not dest.is_symlink(), 'Output exists; choose a new revision folder')
    require(dest.parent.resolve().is_relative_to(base), 'Output parent escapes workspace')
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.edit-', dir=dest.parent))
    try:
        yield stage
        require(not dest.exists() and not dest.is_symlink(), 'Output appeared during processing')
        stage.rename(dest)
    finally:
        if stage.exists(): shutil.rmtree(stage)


def _save(im: Image.Image, path: Path) -> None:
    options = {'icc_profile': im.info['icc_profile']} if 'icc_profile' in im.info else {}
    with path.open('xb') as stream: im.save(stream, format='PNG', **options)


def prepare(root: Path, plan: dict, output: str) -> dict:
    source, mask, _ = _inputs(root, plan); patches, transform = _patches(source, mask, plan)
    with _new_output(root, output) as stage:
        files = {}
        for name, im in patches.items():
            _save(im, stage / name); files[name] = {'path': name, 'sha256': file_sha(stage / name)}
        receipt = {'schema_version': 1, 'kind': 'character_edit_bundle', 'plan_sha256': plan['plan_sha256'],
                   'source': plan['document']['source'], 'transform': transform, 'files': files,
                   'pillow_version': Image.__version__, 'neural_inference': False, 'semantic_approval': False}
        receipt['bundle_sha256'] = sha(receipt); write_json(stage / 'bundle.json', receipt)
    return receipt


def _verify_bundle(root: Path, plan: dict, folder: str, patches: dict, transform: dict) -> dict:
    relative(folder); receipt_path = inside(root, folder + '/bundle.json'); bundle = read_json(receipt_path)
    keys(bundle, {'schema_version', 'kind', 'plan_sha256', 'source', 'transform', 'files',
                  'pillow_version', 'neural_inference', 'semantic_approval', 'bundle_sha256'})
    require(type(bundle['schema_version']) is int and bundle['schema_version'] == 1
            and bundle['kind'] == 'character_edit_bundle', 'Invalid bundle version')
    require(bundle['neural_inference'] is False and bundle['semantic_approval'] is False, 'Invalid bundle claims')
    digest(bundle['bundle_sha256'])
    require(sha({k: v for k, v in bundle.items() if k != 'bundle_sha256'}) == bundle['bundle_sha256'], 'Bundle hash mismatch')
    require(bundle['plan_sha256'] == plan['plan_sha256'], 'Bundle belongs to a different edit plan')
    require(canonical(bundle['source']) == canonical(plan['document']['source'])
            and canonical(bundle['transform']) == canonical(transform), 'Bundle source/transform changed')
    keys(bundle['files'], set(patches))
    for name, expected in patches.items():
        record = bundle['files'][name]; require(record.get('path') == name, 'Unexpected bundle member path')
        actual = png(verify_artifact(receipt_path.parent, record))
        require(actual.mode == expected.mode and actual.size == expected.size
                and actual.tobytes() == expected.tobytes()
                and actual.convert('RGBA').tobytes() == expected.convert('RGBA').tobytes()
                and actual.info.get('icc_profile') == expected.info.get('icc_profile'), 'Bundle pixels/profile changed')
    return bundle


def render(root: Path, plan: dict, bundle_folder: str, candidate: dict) -> dict:
    """Recheck all dependencies and compute the protected result without publishing."""
    source, mask, protect = _inputs(root, plan); patches, transform = _patches(source, mask, plan)
    bundle = _verify_bundle(root, plan, bundle_folder, patches, transform)
    patch = png(verify_artifact(root, candidate))
    require(patch.mode in {'RGB', 'RGBA'} and list(patch.size) == transform['model_size'],
            'Candidate must match the recorded padded context dimensions; no silent resize')
    require(patch.info.get('icc_profile') == source.info.get('icc_profile'), 'Candidate/source ICC profiles differ')
    box = tuple(plan['intent']['context_box']); width, height = transform['unpadded_size']
    original = source.convert('RGBA'); result = original.copy()
    repaired_crop = Image.composite(patch.crop((0, 0, width, height)).convert('RGBA'), original.crop(box), mask.crop(box))
    result.paste(repaired_crop, (box[0], box[1]))
    if 'icc_profile' in source.info: result.info['icc_profile'] = source.info['icc_profile']
    delta = changed_mask(original, result); locked = mask.point(lambda x: 255 if x == 0 else 0)
    outside_changes = ImageChops.multiply(delta, locked).histogram()[255]
    protected_changes = ImageChops.multiply(delta, protect).histogram()[255]
    require(outside_changes == 0 and protected_changes == 0, 'Pixel preservation invariant failed')
    return {'source': source, 'mask': mask, 'protect': protect, 'bundle': bundle,
            'transform': transform, 'result': result, 'delta': delta,
            'outside_changes': outside_changes, 'protected_changes': protected_changes}


def apply(root: Path, plan: dict, bundle_folder: str, candidate: dict, output: str) -> dict:
    """Publish a new decoded-pixel-preserving composite, never 'approve' the art."""
    rendered = render(root, plan, bundle_folder, candidate)
    result, delta, mask = (rendered[k] for k in ('result', 'delta', 'mask'))
    bundle, transform = rendered['bundle'], rendered['transform']
    outside_changes, protected_changes = rendered['outside_changes'], rendered['protected_changes']
    with _new_output(root, output) as stage:
        _save(result, stage / 'result.png'); _save(delta, stage / 'changed-pixels.png')
        receipt = {'schema_version': 1, 'kind': 'character_edit_result', 'plan_sha256': plan['plan_sha256'],
                   'bundle_sha256': bundle['bundle_sha256'], 'budget_owner': plan['budget_owner'],
                   'source': plan['document']['source'], 'candidate': candidate,
                   'output': {'path': output + '/result.png', 'sha256': file_sha(stage/'result.png')},
                   'transform': transform, 'changed_pixels': delta.histogram()[255],
                   'outside_mask_changed_pixels': outside_changes, 'protected_changed_pixels': protected_changes,
                   'exactly_preserved_pixels': mask.histogram()[0], 'pillow_version': Image.__version__,
                   'neural_inference': False, 'candidate_origin': 'supplied_separately_not_verified_by_this_command',
                   'review_state': 'unreviewed', 'semantic_approval': False,
                   'warnings': ['No pixel change detected; do not call this a successful correction'] if delta.getbbox() is None else []}
        receipt['receipt_sha256'] = sha(receipt); write_json(stage/'result.json', receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'apply'):
        p = sub.add_parser(command)
        p.add_argument('--workspace', type=Path, required=True); p.add_argument('--plan', type=Path, required=True)
        p.add_argument('--out', required=True, help='New workspace-relative directory')
        if command == 'apply':
            p.add_argument('--bundle', required=True); p.add_argument('--candidate', required=True)
            p.add_argument('--candidate-sha256', required=True)
    args = parser.parse_args()
    try:
        plan = read_json(args.plan)
        if args.command == 'prepare': result = prepare(args.workspace, plan, args.out)
        else: result = apply(args.workspace, plan, args.bundle, {'path': args.candidate, 'sha256': args.candidate_sha256}, args.out)
        print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
    except (ValueError, KeyError, TypeError, OSError) as exc: parser.exit(2, f'character-edit-pixels: {exc}\n')

if __name__ == '__main__': raise SystemExit(main())
