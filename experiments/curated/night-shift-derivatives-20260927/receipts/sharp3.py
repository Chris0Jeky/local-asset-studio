# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
"""MA-sharp attempt 3: whole-frame refine at 2K, then the same ESRGAN raw 4x and a supersampled Lanczos down to 3840x2160.
MA -> Lanczos 1920x1088 -> Z-Image Turbo img2img (denoise 0.3, the z2 anchor's own prompt, one full frame, no tiles)
-> RealESRGAN x4plus anime 6B raw 4x (7680x4352) -> Lanczos 3840x2160."""
import json, os, sys, time
from PIL import Image
import ns, sharp
drive = ns.drive
key, denoise, seed = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
MA = ns.OUTROOT + 'Research/nightshift-20260927/retro-anime-master/master/retro-anime-master--3840x2160--ma.png'
Z2 = json.load(open('C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio/experiments/curated/asset-kit-20260927/receipts/studio-jobs/retro-anime-master-z2/recipe.json', encoding='utf-8'))['controls']['positive']
name = 'ns-sharp-%s-2k.png' % key
Image.open(MA).convert('RGB').resize((1920, 1088), Image.LANCZOS).save(sharp.INPUT + name)
def post(g):
    r, p = drive.queue(); assert not r and not p
    code, reply = drive.comfy('/prompt', {'prompt': g, 'client_id': 'nightshift-sharp-0927'}); assert code == 200, reply; pid = reply['prompt_id']
    while True:
        h = (drive.comfy('/history/' + pid)[1] or {}).get(pid)
        if h: break
        time.sleep(1)
    assert h['status']['status_str'] == 'success', h['status']
    ts = {m[0]: m[1].get('timestamp') for m in h['status']['messages']}; o = list(h['outputs'].values())[0]['images'][0]
    return pid, (ts['execution_success'] - ts['execution_start']) / 1000, o['subfolder'] + '/' + o['filename']
c0 = drive.commit(); t0 = time.time()
g = sharp.graph(name, denoise, seed, 'Research/nightshift-20260927/sharp/%s-2k' % key); g['4']['inputs']['text'] = Z2
pid1, s1, out1 = post(g)
e = json.load(open('C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio/workflows/api/anime-esrgan-api.json', encoding='utf-8'))
os.makedirs(sharp.INPUT, exist_ok=True); import shutil; shutil.copyfile(ns.OUTROOT + out1, sharp.INPUT + 'ns-sharp-%s-2k-refined.png' % key)
e['1']['inputs']['image'] = 'ns-sharp-%s-2k-refined.png' % key; e['4']['inputs']['scale_by'] = 1.0; e['5']['inputs']['filename_prefix'] = 'Research/nightshift-20260927/sharp/%s-raw4x' % key
pid2, s2, out2 = post(e)
big = Image.open(ns.OUTROOT + out2).convert('RGB')
d = ns.OUTROOT + 'Research/nightshift-20260927/retro-anime-master/candidates/'; dst = d + 'retro-anime-master--3840x2160--%s.png' % key
big.resize((3840, 2160), Image.LANCZOS).save(dst, optimize=True)
ns.log({'key': key, 'route': 'direct-comfyui: z-image img2img full frame 1920x1088 + ESRGAN raw 4x + Lanczos', 'source_sha256': ns.sha(MA), 'denoise': denoise, 'seed': seed,
        'prompt': Z2, 'refine': {'prompt_id': pid1, 'exec_s': s1, 'output': out1}, 'upscale': {'prompt_id': pid2, 'exec_s': s2, 'output': out2, 'size': big.size},
        'wall_seconds': round(time.time() - t0, 1), 'commit_before': c0, 'commit_after': drive.commit(), 'output': dst, 'sha256': ns.sha(dst), 'size': [3840, 2160]})
print(key, pid1, s1, pid2, s2)
