"""Validate portable catalog contracts and the Git payload without running a GPU job."""
import json, re, subprocess, sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'app'))
sys.path.insert(0,str(root))
from model_library import FOLDERS, SUFFIXES
from studio_workflow.preset_adapter import SOURCE_KEYS, missing_source_key
catalog=json.loads((root/'presets/catalog.json').read_text(encoding='utf-8'))['presets']
assert len({p['id'] for p in catalog})==len(catalog), 'Duplicate preset IDs'
fields=['positive','negative','width','height','seed','steps','cfg','denoise','lora','reference','last_reference','frames','fps','style_weight','pose_strength','depth_cut','sampler','scheduler','lora_name','lora2','lora2_name','lora3','lora3_name','lora4','lora4_name','lora5','lora5_name','lora6','lora6_name']
bound={};named_loras=[]
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
    # The RGBA-mask guard in app/server.py refuses a queue without that upload, so the flag needs the slot.
    if preset.get('requires_rgba_mask'): assert preset.get('reference'), (preset['id'],'requires_rgba_mask without a reference binding')
    # A graph that loads a picture must say so with a source key: `studio_workflow.guidance.project` and the
    # browser's reference staging read those keys alone, so an image input declared under none of them is invisible
    # to them and the authored example gets bound in place of the user's picture (#600). `canonical_graph` is a
    # second API graph the same preset owns (app/i2v_diagnostics.py loads it), so it is swept on the same terms.
    graphs=[(preset['graph'],graph)]
    if preset.get('canonical_graph'):
        canonical_path=(root/preset['canonical_graph']).resolve()
        assert canonical_path.is_relative_to(root/'workflows/api'), (preset['id'],'canonical_graph outside workflow directory')
        graphs.append((preset['canonical_graph'],json.loads(canonical_path.read_text(encoding='utf-8'))))
    for where,body in graphs:
        loaders=missing_source_key(preset,body)
        assert not loaders, (preset['id'],where,loaders,'graph loads a picture but the preset declares none of '+repr(SOURCE_KEYS))
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
        for key in ('sampler','scheduler'):
            if key in variant.get('controls',{}):assert variant['controls'][key] in preset.get('choices',{}).get(key,[]), (preset['id'],variant['name'],key)
        for key,value in variant.get('controls',{}).items():
            if key.endswith('_name'):named_loras.append((preset['id']+' variant '+variant['name'],value))
        limits=preset.get('dimension_limits',[64,1536]);multiple=preset.get('dimension_multiple',8)
        for key in ('width','height'):
            if key in variant.get('controls',{}):
                value=variant['controls'][key];assert isinstance(value,int) and limits[0]<=value<=limits[1] and value%multiple==0, (preset['id'],variant['name'],key,value,'outside dimension_limits or off the dimension_multiple grid')
    if preset.get('verified'):
        note=preset.get('execution_note') or preset.get('execution_notes')
        assert isinstance(note,(str,list,dict)) and note, (preset['id'],'verified presets must carry an execution_note or execution_notes recording the run')
    for mode in preset.get('i2v_modes',[]):
        controls=mode.get('controls',{}) if isinstance(mode,dict) else {}
        assert set(controls) <= bound[preset['id']], (preset['id'],'i2v mode',mode.get('id'),'declares controls the preset does not bind',sorted(set(controls)-bound[preset['id']]))
        for key in ('sampler','scheduler'):
            if key in controls:assert controls[key] in preset.get('choices',{}).get(key,[]), (preset['id'],'i2v mode',mode.get('id'),key)
        limits=preset.get('dimension_limits',[64,1536]);multiple=preset.get('dimension_multiple',8)
        for key in ('width','height'):
            if key in controls:
                value=controls[key];assert isinstance(value,int) and limits[0]<=value<=limits[1] and value%multiple==0, (preset['id'],'i2v mode',mode.get('id'),key,value)
    for key in ('lora_name','lora2_name','lora3_name','lora4_name','lora5_name','lora6_name'):
        for node,field in ([preset[key]] if preset.get(key) else [])+preset.get('bindings_extra',{}).get(key,[]):
            authored=graph[node]['inputs'][field]
            assert isinstance(authored,str) and authored.endswith('.safetensors') and authored==Path(authored).name, (preset['id'],key,authored)
            named_loras.append((preset['id']+' authored '+key,authored))
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
        recipe_preset=next(p for p in catalog if p['id']==recipe['preset_id'])
        for key in ('sampler','scheduler'):
            if key in recipe.get('controls',{}):assert recipe['controls'][key] in recipe_preset.get('choices',{}).get(key,[]), (recipe['id'],key)
        for key,value in recipe.get('controls',{}).items():
            if key.endswith('_name'):named_loras.append(('recipe '+recipe['id'],value))
        limits=recipe_preset.get('dimension_limits',[64,1536]);multiple=recipe_preset.get('dimension_multiple',8)
        for key in ('width','height'):
            if key in recipe.get('controls',{}):
                value=recipe['controls'][key];assert isinstance(value,int) and limits[0]<=value<=limits[1] and value%multiple==0, (recipe['id'],key,value,'outside dimension_limits or off the dimension_multiple grid')
        assert recipe.get('status') in {'executed','unverified'}, (recipe['id'],recipe.get('status'))
        assert isinstance(recipe.get('sources',[]),list), recipe['id']
library=json.loads((root/'models/library.json').read_text(encoding='utf-8'))
assert len({a['id'] for a in library['assets']})==len(library['assets'])
for asset in library['assets']:
    assert re.fullmatch('[a-z0-9-]+',asset['id'])
    assert re.fullmatch('[a-f0-9]{64}',asset['sha256'])
    assert isinstance(asset['bytes'],int) and asset['bytes']>0
    relative=Path(asset['file'])
    assert not relative.is_absolute() and '..' not in relative.parts
    # Every pin must be a weight kind the Models view knows, in a folder ModelLibrary.locate accepts:
    # an entry outside FOLDERS makes the whole snapshot raise instead of listing the library.
    assert relative.suffix.lower() in SUFFIXES, (asset['id'],relative.suffix)
    assert relative.parts[0] in FOLDERS, (asset['id'],relative.parts[0])
    # A pin records where the bytes came from; only safetensors are ever fetched from it. A pin with no
    # curated origin at all (a GitHub release, an unrecorded copy) must say so in terms rather than guess.
    curated=asset['url'].startswith(('https://huggingface.co/','https://civitai.com/','https://civitai.red/'))
    assert curated or asset['url']=='', (asset['id'],'url must be a curated source or empty')
    assert curated or asset.get('terms'), (asset['id'],'an unsourced pin must say so in terms')
files=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
for name in filter(None,files):
    path=root/name
    assert path.stat().st_size<=10*1024*1024, 'Tracked file exceeds 10 MiB: '+name
    assert path.suffix.lower() not in {'.safetensors','.gguf','.ckpt','.onnx','.pt','.pth','.bin','.exe','.dll','.zip'}, 'Dependency/weight in Git: '+name
    assert not name.startswith(('experiments/runs/','experiments/uploads/','experiments/workspace/','experiments/projects/','.runtime/')), 'Operational output in Git: '+name
    assert name!='config/local.json' and not path.name.startswith('.env'), 'Local config/secret file in Git'
print(f'PASS: {len(catalog)} preset graphs/bindings; {len(library["assets"])} pinned assets; {len(list(filter(None,files)))} tracked paths checked.')
# Every LoRA a preset, variant or recipe names must be a known, installed adapter (KB entry not marked uninstalled, or a pinned library file).
known={a['file'].split('/')[-1] for a in library['assets']}
kb_loras=(json.loads(kb_path.read_text(encoding='utf-8'))['loras'] if kb_path.is_file() else {})
for where,name in named_loras:
    entry=kb_loras.get(name)
    assert name in known or entry is not None, (where,name)
    assert not (entry and entry.get('installed') is False), (where,name,'marked uninstalled in settings-kb.json')
print('LoRA names checked:',len(named_loras))
