# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
"""Code-derive stage for the Night Shift pack (27 Sep 2026): quiet master at 3840x2160 on the master's exact crop box,
hero/poster/card crops and encodes of the upscaled master, byte-budgeted renditions, and one receipt per ID.
Every transformation is recorded; no pixel here is claimed as native model output."""
import hashlib, io, json, os, time
import numpy as np
from PIL import Image, ImageFilter
import ns

PK = ns.OUTROOT + 'Research/nightshift-20260927/'
runs = {json.loads(l)['key']: json.loads(l) for l in open(ns.HERE + 'runs.jsonl')}
MD = json.load(open(ns.HERE + 'master-derive.json'))
MASTER = MD['MA']['file']; CROP_V = MD['MA']['crop_box']   # [0, 17, 3840, 2177] of the 3840x2194 resize
rel = lambda p: os.path.relpath(p, PK).replace('\\', '/')

def fileinfo(p):
    im = Image.open(p)
    return {'relative_path': rel(p), 'sha256': ns.sha(p), 'bytes': os.path.getsize(p), 'width': im.size[0], 'height': im.size[1],
            'format': im.format, 'mode': im.mode, 'duration_seconds': None, 'codec': None}

def encode(im, dst, fmt, budget_kib, q0=90):
    """Highest quality (steps of 2) that fits the byte budget."""
    q = q0
    while True:
        buf = io.BytesIO(); im.save(buf, fmt, quality=q, method=6) if fmt == 'WEBP' else im.save(buf, fmt, quality=q)
        if buf.tell() <= budget_kib * 1024 or q <= 30: break
        q -= 2
    open(dst, 'wb').write(buf.getvalue()); return {'quality': q, 'budget_kib': budget_kib, 'within_budget': buf.tell() <= budget_kib * 1024}

def detail_split(im):
    """Mean edge magnitude in the left 60% versus the right 40% (brief: middle-left 60% low-detail)."""
    e = np.asarray(im.convert('L').resize((1344, 756)).filter(ImageFilter.FIND_EDGES), dtype=np.float64)
    return {'left60_mean_edge': round(float(e[:, :806].mean()), 2), 'right40_mean_edge': round(float(e[:, 806:].mean()), 2)}

def receipt(asset_id, method, tool_action, model, inputs, files, transformations, prompt_record=None, output_id=None, notes=None, unknowns=None):
    r = json.load(open('C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio/docs/adaptive-studio/assets/receipt-template.json', encoding='utf-8'))
    r.pop('file_entry_instructions', None)
    r.update(status='candidate-produced', requested_asset_id=asset_id, brief_revision='brief.py show %s @ origin/main ffe5b3f9' % asset_id)
    r['production'].update(method=method, provider='local ComfyUI 0.35.0 (primary, 127.0.0.1:8188) via Local Asset Studio' if model else 'local Python (Pillow 12.1.1, numpy)',
                           tool_action=tool_action, reported_model=model, output_id=output_id, produced_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                           prompt_record=prompt_record, input_anchors=inputs)
    r['source']['review_status'] = 'not-applicable: generated locally from the owner-chosen anchor'
    r['files'] = files; r['transformations'] = transformations
    r['art_review'] = {'status': 'not-reviewed', 'reviewer': None, 'notes': 'agent pre-review only (docs/quality/JUDGING-RUBRIC.md); owner art acceptance pending' + ('; ' + notes if notes else '')}
    r['rendition_review'] = {'status': 'agent-checked', 'checks': [f"{f['relative_path']}: {f['width']}x{f['height']} {f['format']} {f['bytes']} B" for f in files]}
    r['unknowns'] = unknowns or []
    d = PK + asset_id + '/receipt.json'; json.dump(r, open(d, 'w', encoding='utf-8'), indent=1); return d

ANCHOR_IN = {'id': 'retro-anime-master-z2', 'sha256': ns.ANCHOR_SHA, 'studio_job': 'c69e6e18-4739-458d-b546-1dd6e8174e19', 'prompt_id': 'adfc94c4-0de0-44af-ae72-72b3133742f0'}
master_im = Image.open(MASTER).convert('RGB')
master_in = {'id': 'retro-anime-master (3840x2160 MA)', 'sha256': ns.sha(MASTER)}
out = {}

# ---------- retro-anime-master: upscaled master + previews
d = PK + 'retro-anime-master/renditions/'; os.makedirs(d, exist_ok=True); files = [fileinfo(MASTER)]; enc = {}
for w, h in ((1280, 720), (960, 540)):
    im = master_im.resize((w, h), Image.LANCZOS)
    for fmt, ext in (('WEBP', 'webp'), ('AVIF', 'avif')):
        p = d + 'retro-anime-master--%dx%d--preview.%s' % (w, h, ext); enc[rel(p)] = encode(im, p, fmt, 300); files.append(fileinfo(p))
u1, u2 = runs['master-up-u1-studio2x'], runs['master-up-u2-raw4x']
out['retro-anime-master'] = receipt('retro-anime-master', 'derive (upscale of the owner-chosen anchor)', 'Studio upload + ComfyUI ImageUpscaleWithModel',
    'RealESRGAN_x4plus_anime_6B.pth (graph workflows/api/anime-esrgan-api.json with ImageScaleBy 0.5 -> 1.0)', [ANCHOR_IN], files,
    [{'step': 'upscale', 'detail': 'raw 4x ESRGAN, 1344x768 -> 5376x3072 (direct ComfyUI prompt %s; the model pass itself ran inside Studio job %s / prompt %s with identical input and was reused from ComfyUI cache)' % (u2['prompt_id'], u1['job_id'], u1['prompt_ids'][0])},
     {'step': 'resize', 'detail': 'Lanczos 5376x3072 -> 3840x2194 (x0.7143)'}, {'step': 'crop', 'detail': 'box %s (anchor px %s): 17 px off top and bottom for 16:9' % (CROP_V, MD['MA']['crop_box_anchor_px'])},
     {'step': 'encode', 'detail': enc}], output_id=u2['prompt_id'],
    notes='not a native 4K generation: an ESRGAN upscale of a 1344x768 original; the painterly wall grain is smoothed. Composition: focal point CRT screen at normalised (0.76, 0.61); text-safe wall x 0-0.55; detail split %s' % detail_split(master_im))

# ---------- retro-anime-quiet: 3840x2160 on the same crop box, poster, registration comparison
qsrc = runs['quiet-up-raw4x']['outputs'][0]['path']; q = Image.open(qsrc).convert('RGB')
q = q.resize((3840, round(q.size[1] * 3840 / q.size[0])), Image.LANCZOS).crop(tuple(CROP_V))
for sub in ('master', 'renditions', 'review'): os.makedirs(PK + 'retro-anime-quiet/' + sub, exist_ok=True)
qm = PK + 'retro-anime-quiet/master/retro-anime-quiet--3840x2160--r1-2.png'; q.save(qm, optimize=True)
qp = PK + 'retro-anime-quiet/renditions/retro-anime-quiet--1280x720--poster.webp'; qenc = encode(q.resize((1280, 720), Image.LANCZOS), qp, 'WEBP', 300)
# registration review: anchor-master edges (red) over the quiet master, and a 50 % crossfade frame, both 1280x720
import registration as R
A = np.asarray(master_im.convert('L').resize((1280, 720)).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float64)
Q = np.asarray(q.convert('L').resize((1280, 720)), dtype=np.float64) * 0.6; m = np.clip(A / 40, 0, 1)[..., None]
ov = np.stack([Q, Q, Q], -1) * (1 - m) + np.array([255, 40, 40]) * m
rp = PK + 'retro-anime-quiet/review/registration-edges-over-quiet--1280x720.png'; Image.fromarray(ov.astype(np.uint8)).save(rp)
xp = PK + 'retro-anime-quiet/review/crossfade-50--1280x720.png'; Image.blend(master_im.resize((1280, 720)), q.resize((1280, 720)), 0.5).save(xp)
qa = json.load(open(ns.HERE + 'align-quiet-r1-1-quiet-r1-2.json'))['quiet-r1-2']; r12 = runs['quiet-r1-2']; qup = runs['quiet-up-raw4x']
out['retro-anime-quiet'] = receipt('retro-anime-quiet', 'edit', 'Studio preset flux-edit (Change one thing, FLUX.2 Klein 4B), reference = anchor upload',
    'FLUX.2 Klein 4B (flux-edit preset graph workflows/api/flux-edit-api.json)', [ANCHOR_IN],
    [fileinfo(qm), fileinfo(qp), fileinfo(rp), fileinfo(xp)],
    [{'step': 'edit', 'detail': 'Studio job %s, prompt %s, seed 2026092782, 1344x768, refinement round 1 wording (r1-words.txt)' % (r12['job_id'], r12['prompt_ids'][0])},
     {'step': 'registration warp', 'detail': 'the edit came back ~0.7 %% larger and offset (patch-wise edge NCC, %d patches, mean |shift| %s px before -> %s after); affine x=%s, y=%s, bicubic, edge-replicated border (at most ~8 px at the right edge, 1344 scale)' % (qa['patches_used'], qa['mean_abs_shift_before'], qa['mean_abs_shift_after'], qa['affine_x'], qa['affine_y'])},
     {'step': 'upscale', 'detail': 'raw 4x ESRGAN (direct ComfyUI prompt %s, %.1f s exec), Lanczos to 3840x2194, crop %s: identical to the master path' % (qup['prompt_id'], qup['exec_seconds'], CROP_V)},
     {'step': 'encode', 'detail': {rel(qp): qenc}}], prompt_record=open(ns.HERE + 'r1-words.txt').read(), output_id=r12['prompt_ids'][0],
    notes='same camera by construction plus the recorded warp; the window view keeps the rail, train and poles in mist; monitor screen dark, lamp on')

# ---------- retro-anime-hero: 3840x1600 wide crop, 1920x800 + 960x400
HB = (0, 360, 3840, 1960)
for sub in ('master', 'renditions', 'review'): os.makedirs(PK + 'retro-anime-hero/' + sub, exist_ok=True)
hero = master_im.crop(HB); hm = PK + 'retro-anime-hero/master/retro-anime-hero--3840x1600--wide.png'; hero.save(hm, optimize=True)
files = [fileinfo(hm)]; enc = {}
for w, h, b in ((1920, 800, 250), (960, 400, 250)):
    p = PK + 'retro-anime-hero/renditions/retro-anime-hero--%dx%d--wide.webp' % (w, h); enc[rel(p)] = encode(hero.resize((w, h), Image.LANCZOS), p, 'WEBP', b); files.append(fileinfo(p))
plan = {'portrait_crop_plan': 'narrow screens (390x844): take a 9:16 box of height 1600 from this hero master, x from 2350 to 3250 (normalised 0.61-0.85), centred on the lamp, CRT and lower window; the heading moves above the art. Not produced: the plan only, per the brief.',
        'focal_point_normalised': [0.76, 0.52], 'heading_zone': 'x 0-0.60 of the hero: plain wall, no detail', 'crop_box_in_master': HB}
json.dump(plan, open(PK + 'retro-anime-hero/review/composition.json', 'w'), indent=1)
out['retro-anime-hero'] = receipt('retro-anime-hero', 'derive', 'crop + Lanczos encode (Pillow)', None, [master_in, ANCHOR_IN], files,
    [{'step': 'crop', 'detail': 'master box %s (drops 360 px of upper window/sky and 200 px of floor)' % (HB,)}, {'step': 'encode', 'detail': enc}, {'step': 'plan', 'detail': plan}])

# ---------- retro-anime-poster: 1280x720 + 640x360 of the full 16:9 master
os.makedirs(PK + 'retro-anime-poster/renditions', exist_ok=True); files = []; enc = {}
for w, h, b in ((1280, 720, 220), (640, 360, 90)):
    p = PK + 'retro-anime-poster/renditions/retro-anime-poster--%dx%d--still.webp' % (w, h); enc[rel(p)] = encode(master_im.resize((w, h), Image.LANCZOS), p, 'WEBP', b); files.append(fileinfo(p))
out['retro-anime-poster'] = receipt('retro-anime-poster', 'derive', 'resize + encode (Pillow)', None, [master_in, ANCHOR_IN], files,
    [{'step': 'resize', 'detail': 'full 16:9 master, Lanczos, no crop, so a later loop from this still does not jump'}, {'step': 'encode', 'detail': enc}],
    notes='focal point (0.76, 0.61); source identity: the master sha256 in input_anchors')

# ---------- retro-anime-card: square crops, two framings
os.makedirs(PK + 'retro-anime-card/master', exist_ok=True); os.makedirs(PK + 'retro-anime-card/renditions', exist_ok=True); os.makedirs(PK + 'retro-anime-card/review', exist_ok=True)
CARDS = {'wide': (1680, 0, 3840, 2160), 'tight': (2240, 300, 3840, 1900)}
files = []; enc = {}
for name, box in CARDS.items():
    sq = master_im.crop(box).resize((1024, 1024), Image.LANCZOS); pm = PK + 'retro-anime-card/master/retro-anime-card--1024x1024--%s.png' % name; sq.save(pm, optimize=True); files.append(fileinfo(pm))
    for w, b in ((512, 80), (256, 30)):
        p = PK + 'retro-anime-card/renditions/retro-anime-card--%dx%d--%s.webp' % (w, w, name); enc[rel(p)] = encode(sq.resize((w, w), Image.LANCZOS), p, 'WEBP', b); files.append(fileinfo(p))
    sq.resize((96, 96), Image.LANCZOS).save(PK + 'retro-anime-card/review/at-96px--%s.png' % name)
out['retro-anime-card'] = receipt('retro-anime-card', 'derive', 'square crop + Lanczos encode (Pillow)', None, [master_in, ANCHOR_IN], files,
    [{'step': 'crop', 'detail': {k: {'box': v, 'normalised_x': [round(v[0] / 3840, 3), round(v[2] / 3840, 3)]} for k, v in CARDS.items()}}, {'step': 'encode', 'detail': enc}],
    notes='two framings offered; the 96 px check images are in review/')

json.dump(out, open(ns.HERE + 'derive-receipts.json', 'w'), indent=1)
manifest = {'pack': 'night-shift (Retro Anime pilot)', 'created': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'anchor': ANCHOR_IN,
            'status': 'candidate-produced; agent pre-review only; not art-accepted, not runtime-qualified',
            'assets': {}}
for aid in ('retro-anime-master', 'retro-anime-quiet', 'retro-anime-hero', 'retro-anime-poster', 'retro-anime-card'):
    r = json.load(open(PK + aid + '/receipt.json', encoding='utf-8'))
    manifest['assets'][aid] = [{k: f[k] for k in ('relative_path', 'sha256', 'bytes', 'width', 'height', 'format')} for f in r['files']]
json.dump(manifest, open(PK + 'pack-manifest.json', 'w'), indent=1)
for aid, fl in manifest['assets'].items():
    for f in fl: print(aid, f['relative_path'], f['width'], f['height'], f['format'], round(f['bytes'] / 1024, 1), 'KiB')
