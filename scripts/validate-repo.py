"""Validate portable catalog contracts and the Git payload without running a GPU job."""
import json, re, subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
catalog=json.loads((root/'presets/catalog.json').read_text(encoding='utf-8'))['presets']
assert len({p['id'] for p in catalog})==len(catalog), 'Duplicate preset IDs'
fields=['positive','negative','width','height','seed','steps','cfg','denoise','lora','reference','last_reference','frames','fps','sampler','scheduler','lora_name','lora2','lora2_name','lora3','lora3_name','lora4','lora4_name']
bound={}
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
    for slot in preset.get('reference_slots',[]):
        node,field=slot['binding']
        assert field in graph[node]['inputs'], (preset['id'],'reference',slot)
        assert slot['role'] in {'identity','pose','style','costume','composition','geometry','motion','mask'}
    assert preset.get('modality','image') in {'image','video','3d'}
    if preset.get('visual'):
        visual_path=(root/preset['visual']).resolve()
        assert visual_path.is_relative_to(root/'workflows/comfyui')
        visual=json.loads(visual_path.read_text(encoding='utf-8'))
        ids={n['id'] for n in visual['nodes']}
        for link in visual['links']:
            assert link[1] in ids and link[3] in ids, (preset['id'],link)
    bound[preset['id']]={k for k in fields if preset.get(k) or preset.get('bindings_extra',{}).get(k)}
    for variant in preset.get('variants',[]):
        assert set(variant.get('controls',{})) <= bound[preset['id']], (preset['id'],variant)
    for key in ('lora_name','lora2_name','lora3_name','lora4_name'):
        for node,field in ([preset[key]] if preset.get(key) else [])+preset.get('bindings_extra',{}).get(key,[]):
            authored=graph[node]['inputs'][field]
            assert isinstance(authored,str) and authored.endswith('.safetensors') and authored==Path(authored).name, (preset['id'],key,authored)
kb_path=root/'presets/settings-kb.json'
if kb_path.is_file():
    kb=json.loads(kb_path.read_text(encoding='utf-8'))
    assert isinstance(kb.get('families'),dict) and isinstance(kb.get('loras'),dict), 'settings-kb.json needs families and loras objects'
    axis_controls=set(fields)|{'steps','cfg','width','height'}
    for name,family in kb['families'].items():
        assert isinstance(family,dict), name
        assert isinstance(family.get('defaults',{}),dict) and isinstance(family.get('sources',[]),list), name
        for axis in family.get('axes',[]):
            assert axis.get('control') in axis_controls, (name,axis.get('id'),axis.get('control'))
            assert isinstance(axis.get('values'),list) and axis['values'], (name,axis.get('id'))
            assert isinstance(axis.get('sources',[]),list), (name,axis.get('id'))
    for file,entry in kb['loras'].items():
        assert file.endswith('.safetensors') and file==Path(file).name, file
        assert isinstance(entry,dict) and entry.get('family') in kb['families'], file
        assert entry.get('sha256')=='unpinned' or re.fullmatch('[a-f0-9]{64}',entry.get('sha256',''),re.I), file
recipe_path=root/'presets/recipes.json'
if recipe_path.is_file():
    recipes=json.loads(recipe_path.read_text(encoding='utf-8'))['recipes']
    assert len({r['id'] for r in recipes})==len(recipes), 'Duplicate recipe IDs'
    for recipe in recipes:
        assert re.fullmatch('[a-z0-9]+(-[a-z0-9]+)*',recipe['id']), recipe['id']
        assert recipe['preset_id'] in bound, (recipe['id'],recipe['preset_id'])
        assert set(recipe.get('controls',{})) <= bound[recipe['preset_id']], (recipe['id'],sorted(set(recipe.get('controls',{}))-bound[recipe['preset_id']]))
        assert recipe.get('status') in {'executed','unverified'}, (recipe['id'],recipe.get('status'))
        assert isinstance(recipe.get('sources',[]),list), recipe['id']
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
    assert not name.startswith(('experiments/runs/','experiments/uploads/','experiments/workspace/','experiments/projects/','.runtime/')), 'Operational output in Git: '+name
    assert name!='config/local.json' and not path.name.startswith('.env'), 'Local config/secret file in Git'
print(f'PASS: {len(catalog)} preset graphs/bindings; {len(library["assets"])} pinned assets; {len(list(filter(None,files)))} tracked paths checked.')
