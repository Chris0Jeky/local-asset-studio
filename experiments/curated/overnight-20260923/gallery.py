"""Local galleries and Git-safe sheets for an experiment folder (23 September 2026, overnight lab).

    python gallery.py <experiment-folder>          # writes <ComfyUI output>/Research/overnight-20260923/<slug>/index.html
    python gallery.py <experiment-folder> --sheet  # also writes examples/overnight-20260923/<slug>-sheet.jpg (git-safe images only)

The gallery (never in Git; the repo is public) shows every successful output as a thumbnail linking to the full-size
PNG, captioned with its configuration, suite case, prompt ID, time, verdict and worst defect. A judgement recorded on a
blind copy is matched to its original through key.sealed.json, so run this only after unblinding. Images judged
`skipped` are never thumbnailed. The sheet contains only suite cases marked `git_safe` (original characters, no fanservice).
"""
import html, json, sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labkit, suite  # noqa: E402

ROOT = labkit.OUTPUT / 'Research' / 'overnight-20260923'


def load(folder):
    records = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
    key = json.loads((folder / 'key.sealed.json').read_text(encoding='utf-8')) if (folder / 'key.sealed.json').exists() else {}
    judged = {}
    jf = folder / 'judgements.jsonl'
    if jf.exists():
        for line in jf.read_text(encoding='utf-8').splitlines():
            j = json.loads(line); name = Path(j['image']).name
            original = key.get(name, {}).get('file') if name in key else j['image']
            judged[str(Path(original)).lower()] = j
    return records, judged


def main(argv):
    folder = Path(argv[0]).resolve(); slug = folder.name; sheet = '--sheet' in argv
    records, judged = load(folder)
    out = ROOT / slug; thumbs = out / 'thumbs'; thumbs.mkdir(parents=True, exist_ok=True)
    cards, safe = [], []
    for r in records:
        if r.get('status') not in ('success', 'completed'): continue
        for o in r.get('outputs') or r.get('output_files') or []:
            path = Path(o['file'])
            if '/mask-' in str(path).replace('\\', '/') or not path.exists(): continue
            j = judged.get(str(path).lower())
            if j and j.get('verdict') == 'skipped': continue
            case = suite.by_id(r['case']) if r.get('case') else None
            thumb = thumbs / (path.stem + '.jpg')
            im = Image.open(path).convert('RGB'); im.thumbnail((360, 540)); im.save(thumb, quality=85)
            try: rel = path.relative_to(out).as_posix()
            except ValueError: rel = path.as_uri()
            cap = '<b>%s</b> · %s · seed %s<br>prompt %s · %s s' % (html.escape(str(r.get('config'))), html.escape(r.get('case') or ''),
                                                                 r.get('seed'), (r.get('prompt_id') or '')[:8],
                                                                 r.get('history_execution_seconds') or r.get('elapsed_seconds') or r.get('wall_seconds'))
            if j: cap += '<br>verdict <b>%s</b> %s<br><i>%s</i>' % (j['verdict'], html.escape(json.dumps(j['scores'])), html.escape(j['worst_defect']))
            cards.append('<figure><a href="%s"><img src="thumbs/%s"></a><figcaption>%s</figcaption></figure>' % (html.escape(rel), html.escape(thumb.name), cap))
            if case and case.get('git_safe') and not case.get('fanservice'): safe.append((r, path))
    page = ('<!doctype html><meta charset="utf-8"><title>%s</title><style>body{font:13px sans-serif;background:#111;color:#ddd}'
            'figure{display:inline-block;width:370px;vertical-align:top;margin:6px}img{max-width:360px}a{color:#9cf}</style>'
            '<h1>overnight-20260923 / %s</h1><p>Agent-judged, not accepted; configurations shown after unblinding. Evidence: '
            'experiments/curated/overnight-20260923/%s/ in the lab branch.</p>%s') % (slug, slug, slug, '\n'.join(cards))
    (out / 'index.html').write_text(page, encoding='utf-8'); print(out / 'index.html', len(cards), 'cards')
    if sheet and safe:
        tiles = []
        for r, path in safe:
            im = Image.open(path).convert('RGB'); im.thumbnail((256, 384)); tiles.append(im)
        w = 256 * min(4, len(tiles)); rows = (len(tiles) + 3) // 4
        canvas = Image.new('RGB', (w, 384 * rows), (24, 24, 24))
        for i, im in enumerate(tiles): canvas.paste(im, ((i % 4) * 256, (i // 4) * 384))
        dest = labkit.REPO / 'examples' / 'overnight-20260923' / (slug + '-sheet.jpg'); dest.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(dest, quality=80); print(dest, dest.stat().st_size, 'bytes')


if __name__ == '__main__':
    main(sys.argv[1:])
