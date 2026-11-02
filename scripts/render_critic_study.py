"""Owned CPU pixel experiment: noise-floor suppression versus missed small defects.

    python scripts/render_critic_study.py --out-dir NEW_DIRECTORY

Uses the real render_critic pixel gate; never starts Blender or calls a model.
This is an adversarial synthetic study, not native renderer noise calibration.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import platform

import render_critic
import render_critic_policy

SIZES = (96, 256, 512)
FLOORS = (0, .001, .004)
CASES = (('clean', False), ('sublevel', False), ('sparse26', False), ('defect25', True),
         ('defect171', True), ('large-defect', True), ('alpha-loss', True), ('size-mismatch', True))


def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')


def _candidate(size, kind, view):
    from PIL import Image
    image = Image.new('RGBA', (size, size), (100, 100, 100, 255))
    if kind == 'sublevel': return Image.new('RGBA', image.size, (107, 100, 100, 255))
    if kind == 'sparse26':
        for i in range(26):
            if i % 4 == view: image.putpixel(((i * 37 + 13) % size, (i * 53 + 7) % size), (255, 100, 100, 255))
    if view == 0:
        if kind in ('defect25', 'defect171'):
            count = 25 if kind == 'defect25' else 171
            for i in range(count): image.putpixel((size // 2 + i % 19, size // 2 + i // 19), (255, 100, 100, 255))
        if kind == 'large-defect': image.paste((255, 100, 100, 255), (size // 3, size // 3, size // 3 + size // 5, size // 3 + size // 5))
        if kind == 'alpha-loss': image.putalpha(0)
        if kind == 'size-mismatch': return image.crop((0, 0, size - 1, size))
    return image


def run(out_dir, sizes=SIZES):
    """Bounded (at most three allowed resolutions), new directory only, deterministic artifacts."""
    if (not sizes or len(sizes) > 3 or any(type(n) is not int or n not in SIZES for n in sizes)
            or len(set(sizes)) != len(sizes)): raise ValueError('sizes must be a unique subset of 96, 256, 512')
    from PIL import Image, __version__ as pillow_version
    root = Path(out_dir); root.mkdir(parents=True, exist_ok=False)
    records = []; html_rows = []
    for size in sizes:
        ref = root / f'{size}-reference'; ref.mkdir()
        refs = [ref / f'view_{v}.png' for v in render_critic.VIEWS]
        for p in refs: Image.new('RGBA', (size, size), (100, 100, 100, 255)).save(p)
        for kind, truth in CASES:
            case_id = f'{size}-{kind}'; folder = root / case_id; folder.mkdir()
            images = [folder / f'view_{v}.png' for v in render_critic.VIEWS]
            for i, p in enumerate(images): _candidate(size, kind, i).save(p)
            receipt = render_critic.check(images, reference=refs, diff_only=True)
            # JSON-normalise tuples so in-memory and retained receipts are identical.
            receipt = json.loads(json.dumps(receipt))
            hypotheses = {str(f): render_critic_policy.decide(receipt, f) for f in FLOORS}
            _write(folder / 'receipt.json', receipt); _write(folder / 'hypotheses.json', hypotheses)
            records.append({'id': case_id, 'synthetic_requires_review': truth, 'receipt': receipt,
                            'receipt_path': f'{case_id}/receipt.json', 'hypotheses': hypotheses})
            maximum = max(v['changed_fraction'] for v in hypotheses['0']['views'].values())
            labels = ', '.join(f'{f}: {r["status"]}' for f, r in hypotheses.items())
            html_rows.append(f'<tr><td>{case_id}<br>synthetic review: {truth}</td>'
                             f'<td><img width="192" height="192" src="{size}-reference/view_front.png" alt="Reference" /></td>'
                             f'<td><img width="192" height="192" src="{case_id}/view_front.png" alt="Candidate" /></td>'
                             f'<td>raw changed: {receipt["changed"]}<br>max view fraction: {maximum:.6f}<br>'
                             f'{html.escape(labels)}<br><a href="{case_id}/receipt.json">Raw receipt</a></td></tr>')
    summary = {}
    for floor in FLOORS:
        stats = dict(tp=0, fp=0, tn=0, fn=0, incomplete=0)
        for row in records:
            r = row['hypotheses'][str(floor)]
            if r['status'] == 'incomplete': stats['incomplete'] += 1; continue
            pred, truth = r['requires_review'], row['synthetic_requires_review']
            stats['tp' if pred and truth else 'fp' if pred else 'fn' if truth else 'tn'] += 1
        summary[str(floor)] = stats
    (root / 'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Render critic policy study</title>'
        '<h1>Owned pixel study — not native Blender calibration</h1>'
        '<p>Sparse26 is labelled nuisance by construction, not by measured renderer behaviour. Small patches are labelled defects. '
        'A threshold that removes both is not a successful repair. These 24 related synthetic variants are not independent production trials. '
        'Preview shows the front view; raw receipts cover all four views. Alpha differences may be invisible against a matching background. '
        'Images are displayed at 192px; use the original files for pixel inspection. No policy is promoted.</p>'
        '<table><thead><tr><th>Case</th><th>Reference</th><th>Candidate</th><th>Hypotheses</th></tr></thead><tbody>'
        + ''.join(html_rows) + '</tbody></table></html>', encoding='utf-8')
    sources = {Path(module.__file__).name: _sha(Path(module.__file__))
               for module in (render_critic, render_critic_policy)}
    sources[Path(__file__).name] = _sha(Path(__file__))
    result = {'schema': 'las.render-critic-owned-study.v1', 'native_calibration': False, 'default_policy_changed': False,
              'python': platform.python_version(), 'pillow': pillow_version, 'source_sha256': sources,
              'synthetic_confusion': summary, 'cases': records,
              'artifacts': [{'path': p.relative_to(root).as_posix(), 'sha256': _sha(p)} for p in sorted(root.rglob('*')) if p.is_file()]}
    _write(root / 'summary.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out-dir', required=True)
    args = parser.parse_args(argv)
    result = run(args.out_dir)
    print(json.dumps(result['synthetic_confusion'], indent=2))


if __name__ == '__main__': main()
