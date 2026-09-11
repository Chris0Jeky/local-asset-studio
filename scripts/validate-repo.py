"""Validate portable catalog contracts and the Git payload without running a GPU job."""
import json, re, subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
catalog=json.loads((root/'presets/catalog.json').read_text(encoding='utf-8'))['presets']
assert len({p['id'] for p in catalog})==len(catalog), 'Duplicate preset IDs'
fields=['positive','negative','width','height','seed','steps','cfg','denoise','lora','reference','last_reference','frames','fps','sampler','scheduler']
for preset in catalog:
    path=(root/preset['graph']).resolve()
    assert path.is_relative_to(root/'workflows/api'), 'Graph outside workflow directory'
    graph=json.loads(path.read_text(encoding='utf-8'))
    for key in fields:
        bindings=([preset[key]] if preset.get(key) else [])+preset.get('bindings_extra',{}).get(key,[])
        for node,field in bindings:
            assert field in graph[node]['inputs'], (preset['id'],key,node,field)
    for node in graph.values():
        assert 'class_type' in node and isinstance(node['inputs'],dict)
        for value in node['inputs'].values():
            if isinstance(value,list):
                assert len(value)==2 and value[0] in graph and isinstance(value[1],int), (preset['id'],value)
    assert preset.get('modality','image') in {'image','video','3d'}
    if preset.get('visual'):
        visual_path=(root/preset['visual']).resolve()
        assert visual_path.is_relative_to(root/'workflows/comfyui')
        visual=json.loads(visual_path.read_text(encoding='utf-8'))
        ids={n['id'] for n in visual['nodes']}
        for link in visual['links']:
            assert link[1] in ids and link[3] in ids, (preset['id'],link)
    for variant in preset.get('variants',[]):
        assert set(variant.get('controls',{})) <= {k for k in fields if preset.get(k) or preset.get('bindings_extra',{}).get(k)}, (preset['id'],variant)
library=json.loads((root/'models/library.json').read_text(encoding='utf-8'))
assert len({a['id'] for a in library['assets']})==len(library['assets'])
for asset in library['assets']:
    assert re.fullmatch('[a-z0-9-]+',asset['id'])
    assert re.fullmatch('[a-f0-9]{64}',asset['sha256'])
    assert isinstance(asset['bytes'],int) and asset['bytes']>0
    assert not Path(asset['file']).is_absolute() and '..' not in Path(asset['file']).parts
    assert asset['file'].endswith('.safetensors')
    assert asset['url'].startswith(('https://huggingface.co/','https://civitai.com/','https://civitai.red/'))
files=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
for name in filter(None,files):
    path=root/name
    assert path.stat().st_size<=10*1024*1024, 'Tracked file exceeds 10 MiB: '+name
    assert path.suffix.lower() not in {'.safetensors','.gguf','.ckpt','.onnx','.pt','.pth','.bin','.exe','.dll','.zip'}, 'Dependency/weight in Git: '+name
    assert not name.startswith(('experiments/runs/','experiments/uploads/','.runtime/')), 'Operational output in Git: '+name
    assert name!='config/local.json' and not path.name.startswith('.env'), 'Local config/secret file in Git'
print(f'PASS: {len(catalog)} preset graphs/bindings; {len(library["assets"])} pinned assets; {len(list(filter(None,files)))} tracked paths checked.')
