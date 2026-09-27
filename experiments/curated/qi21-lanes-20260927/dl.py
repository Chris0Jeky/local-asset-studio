# As-run download script (27 Sep 2026), kept as a receipt; hardcodes local paths.
"""#1028 lane downloads (owner authorised 27 Sep 2026): resumable curl -C -, sha256 against the HF LFS oid, then rename into place."""
import hashlib, json, os, subprocess, time
M = 'C:/AI/experiments/qwen-image-21/ComfyUI/models/'
FILES = [
 ('https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/main/text_encoders/qwen3vl_8b_w4a8.safetensors', M + 'text_encoders/qwen3vl_8b_w4a8.safetensors', 6312105364, '7754425e55e7bea2bfde4dde59a4cc236cb44e5ee9c215ea66ef8d47012824eb'),
 ('https://huggingface.co/unsloth/Qwen-Image-2.1-GGUF/resolve/main/qwen-image-2.1-Q4_K_M.gguf', M + 'diffusion_models/qwen-image-2.1-Q4_K_M.gguf', 4199565024, '631d532e7ca71e8d90a87c71d3699761a812039d22e3370e87498d87754660fe'),
 ('https://huggingface.co/realrebelai/Qwen-Image-2.1_GGUFs/resolve/main/Qwen-Image-2.1-Q4.gguf', M + 'diffusion_models/Qwen-Image-2.1-Q4-realrebelai.gguf', 5959127264, '51998ad7c068ce7d68e233237537900ffe874ab4d5c72e20758f5f18ceb15b8a'),
 ('https://huggingface.co/unsloth/Qwen-Image-2.1-FP8/resolve/main/Qwen-Image-2.1-FP8.safetensors', M + 'diffusion_models/Qwen-Image-2.1-FP8.safetensors', 7122877560, '70e151cfbedd37de7f4a11bda8f58180965c85f4960584c3d10acff599fcd205'),
 ('https://huggingface.co/unsloth/Qwen-Image-2.1-FP8/resolve/main/Qwen-Image-2.1-text_encoder-FP8.safetensors', M + 'text_encoders/Qwen-Image-2.1-text_encoder-FP8.safetensors', 9394530592, '0a1e217ea5a327c77cf4c58ee2ec4b15dabdd55cc4ffa6d999085865e70db3df'),
]
import sys
sel = [int(a) for a in sys.argv[1:]] or range(len(FILES))
out = []
for url, dst, size, sha in [FILES[i] for i in sel]:
    if os.path.exists(dst) and os.path.getsize(dst) == size: print('present', dst, flush=True); out.append({'url': url, 'dest': dst, 'bytes': size, 'sha256': sha, 'status': 'already present'}); continue
    part = dst + '.part'; t0 = time.time()
    for attempt in range(500):
        r = subprocess.run(['curl', '-L', '-C', '-', '--fail', '--retry', '3', '-sS', '-o', part, url])
        if os.path.exists(part) and os.path.getsize(part) >= size: break
        time.sleep(5)
    h = hashlib.sha256()
    with open(part, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''): h.update(b)
    ok = h.hexdigest() == sha and os.path.getsize(part) == size
    if ok: os.replace(part, dst)
    rec = {'url': url, 'dest': dst, 'bytes': os.path.getsize(dst if ok else part), 'expected_sha256': sha, 'sha256': h.hexdigest(), 'verified': ok, 'seconds': round(time.time() - t0, 1), 'fetched': time.strftime('%Y-%m-%dT%H:%M:%S')}
    out.append(rec); print(json.dumps(rec), flush=True)
    json.dump(out, open('receipts-%s.json' % '-'.join(map(str, sel)), 'w'), indent=1)
json.dump(out, open('receipts-%s.json' % '-'.join(map(str, sel)), 'w'), indent=1); print('DONE', flush=True)
