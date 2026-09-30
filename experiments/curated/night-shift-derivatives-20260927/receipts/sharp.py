# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
"""MA-sharp attempts (27 Sep 2026): tiled low-denoise img2img over the accepted 3840x2160 master MA with the anchor's own model
(Z-Image Turbo fp8, graph workflows/api/zimage-fast-api.json with EmptySD3LatentImage replaced by LoadImage -> VAEEncode).
Tiles of 1024 px overlap by at least 128 px and are blended back with linear feathering. Each tile is one direct ComfyUI prompt.
Usage: python sharp.py <attempt-key> <denoise> <seed> [source-png]"""
import json, os, shutil, sys, time
import numpy as np
from PIL import Image
import ns
drive = ns.drive
INPUT = 'C:/AI/ComfyUI_windows_portable/ComfyUI/input/'
PROMPT = ('Hand-painted cel anime film background art, crisp clean line work, fine painterly texture on plaster and wood, '
          'soft lighting, detailed, no text, no people.')
T, OV = 1024, 128

def positions(total):
    n = int(np.ceil((total - OV) / (T - OV))); step = (total - T) / max(n - 1, 1)
    return [round(i * step) for i in range(n)]

def graph(tile_name, denoise, seed, prefix):
    g = json.load(open('C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio/workflows/api/zimage-fast-api.json', encoding='utf-8'))
    g['4']['inputs']['text'] = PROMPT
    del g['7']
    g['11'] = {'class_type': 'LoadImage', 'inputs': {'image': tile_name}}
    g['12'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': ['11', 0], 'vae': ['3', 0]}}
    g['8']['inputs'].update(latent_image=['12', 0], denoise=denoise, seed=seed)
    g['10']['inputs']['filename_prefix'] = prefix
    return g

def feather(w, h, x0, y0, W, H):
    m = np.ones((h, w), np.float32)
    ramp = np.linspace(0, 1, OV, dtype=np.float32)
    if x0 > 0: m[:, :OV] *= ramp[None, :]
    if x0 + w < W: m[:, -OV:] *= ramp[::-1][None, :]
    if y0 > 0: m[:OV, :] *= ramp[:, None]
    if y0 + h < H: m[-OV:, :] *= ramp[::-1][:, None]
    return m

def run(key, denoise, seed, src):
    im = Image.open(src).convert('RGB'); W, H = im.size
    acc = np.zeros((H, W, 3), np.float64); wsum = np.zeros((H, W), np.float64); tiles = []
    t0 = time.time(); c0 = drive.commit()
    for yi, y in enumerate(positions(H)):
        for xi, x in enumerate(positions(W)):
            name = 'ns-sharp-%s-%d-%d.png' % (key, yi, xi); im.crop((x, y, x + T, y + T)).save(INPUT + name)
            r, p = drive.queue(); assert not r and not p, 'queue busy'
            code, reply = drive.comfy('/prompt', {'prompt': graph(name, denoise, seed, 'Research/nightshift-20260927/sharp/%s-t%d%d' % (key, yi, xi)), 'client_id': 'nightshift-sharp-0927'})
            assert code == 200, reply; pid = reply['prompt_id']
            while True:
                h = (drive.comfy('/history/' + pid)[1] or {}).get(pid)
                if h: break
                time.sleep(0.5)
            assert h['status']['status_str'] == 'success', h['status']
            ts = {m[0]: m[1].get('timestamp') for m in h['status']['messages']}
            o = list(h['outputs'].values())[0]['images'][0]
            out = Image.open(ns.OUTROOT + o['subfolder'] + '/' + o['filename']).convert('RGB'); assert out.size == (T, T), out.size
            m = feather(T, T, x, y, W, H)
            acc[y:y + T, x:x + T] += np.asarray(out, np.float64) * m[..., None]; wsum[y:y + T, x:x + T] += m
            tiles.append({'tile': [x, y, x + T, y + T], 'prompt_id': pid, 'exec_s': (ts['execution_success'] - ts['execution_start']) / 1000, 'output': o['subfolder'] + '/' + o['filename']})
            print(key, yi, xi, pid[:8], tiles[-1]['exec_s'], flush=True)
    res = (acc / wsum[..., None]).clip(0, 255).round().astype(np.uint8)
    d = ns.OUTROOT + 'Research/nightshift-20260927/retro-anime-master/candidates/'; os.makedirs(d, exist_ok=True)
    dst = d + 'retro-anime-master--3840x2160--%s.png' % key; Image.fromarray(res).save(dst, optimize=True)
    rec = {'key': key, 'route': 'direct-comfyui tiles', 'model': 'z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors (graph zimage-fast-api.json, img2img)',
           'source': src, 'source_sha256': ns.sha(src), 'denoise': denoise, 'seed': seed, 'steps': 8, 'prompt': PROMPT, 'tile': T, 'overlap_min': OV,
           'tiles': tiles, 'wall_seconds': round(time.time() - t0, 1), 'commit_before': c0, 'commit_after': drive.commit(),
           'output': dst, 'sha256': ns.sha(dst), 'size': [W, H]}
    ns.log(rec); return rec

if __name__ == '__main__':
    MA = ns.OUTROOT + 'Research/nightshift-20260927/retro-anime-master/master/retro-anime-master--3840x2160--ma.png'
    run(sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else MA)
