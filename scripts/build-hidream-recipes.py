"""Build isolated HiDream T2I and reference-edit recipes; never submit a job."""
import copy
import importlib.util
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]

def build(info):
    spec=importlib.util.spec_from_file_location('expansion_builder',ROOT/'scripts/build-expansion.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    catalog=json.loads((ROOT/'presets/catalog.json').read_text(encoding='utf-8'))
    old={p['id']:p for p in catalog['presets']};added=[]
    base=json.loads((ROOT/'workflows/experimental/hidream-o1-fp8-api.json').read_text(encoding='utf-8'))
    files=['model.safetensors','config.json','generation_config.json','preprocessor_config.json','tokenizer.json','tokenizer_config.json','chat_template.json','merges.txt','vocab.json']
    for mode in ('concept','edit'):
        graph=copy.deepcopy(base);identifier='hidream-o1-'+mode
        graph['3']['inputs'].update(width=2048,height=2048,steps=8,seed=2026091131,force_offload=True)
        graph['4']['inputs']['filename_prefix']='Studio/'+identifier
        graph['2']['inputs']['prompt']='Original anime key visual: an adult silver-haired explorer in a dark travelling coat, holding a brass compass in a rainy Japanese mountain village at blue hour. Clean expressive linework, layered cel shading, teal lantern light, restrained vermilion accents, cinematic composition. No typography.'
        if mode=='edit':
            graph['3']['inputs'].update(image='1',keep_image1_aspect=True)
            graph['3']['inputs']['image.image_1']=['5',0]
            graph['5']={'class_type':'LoadImage','inputs':{'image':'studio-lantern-cutout.png'}}
            graph['2']['inputs']['prompt']='Restyle the reference as a premium anime game prop illustration. Preserve the lantern silhouette, brass frame and warm inner light. Use crisp ink contours, teal shadows and painterly enamel highlights on a plain dark background.'
        title='HiDream O1 - '+('2K Anime Concept' if mode=='concept' else 'Reference Restyle')
        api=f'workflows/api/{identifier}-api.json';visual=f'workflows/comfyui/{53+len(added)} - {title}.json'
        raw=json.dumps(graph,indent=2)+'\n';path=ROOT/api
        unchanged=path.exists() and path.read_text(encoding='utf-8')==raw
        path.write_text(raw,encoding='utf-8');(ROOT/visual).write_text(json.dumps(builder.visual(graph,title,info),indent=2)+'\n',encoding='utf-8')
        entry=dict(id=identifier,name=title,category='HiDream studio',collection='production-workspace',family='HiDream O1',backend_id='hidream',modality='image',graph=api,visual=visual,
                   positive=['2','prompt'],negative=['2','negative_prompt'],seed=['3','seed'],steps=['3','steps'],cfg=['3','guidance_scale'],
                   description='Native 2K concept synthesis in the isolated environment.' if mode=='concept' else 'Whole-image reference restyling at the source aspect ratio, capped by the model at 2K. Unrequested details can change.',
                   stages=['HiDream full FP8','Unified pixels and text','SDPA sampling','PNG'],verified=old.get(identifier,{}).get('verified',False) if unchanged else False,
                   model_files=['diffusion_models/HiDream-O1-Image-fp8/'+name for name in files],
                   source='https://huggingface.co/HiDream-ai/HiDream-O1-Image',
                   commercial_note='Upstream model MIT; FP8 conversion by drbaph. Isolated experimental runtime: upstream advises against Torch 2.9.x, which this Radeon build currently uses. Eight steps is a fast study; official full-model guidance is 50.',
                   variants=[{'name':'8-step study','controls':{'steps':8}},{'name':'20-step study','controls':{'steps':20}},{'name':'50-step full model','controls':{'steps':50}}])
        if mode=='concept':
            entry.update(width=['3','width'],height=['3','height'],dimension_limits=[1312,3104],dimension_multiple=32,
                         resolution_choices=[[2048,2048],[2304,1728],[1728,2304],[2560,1440],[1440,2560],[2496,1664],[1664,2496],[3104,1312],[1312,3104],[2304,1792],[1792,2304]])
            entry['variants'] += [{'name':'Portrait 1728 × 2304','controls':{'width':1728,'height':2304}},{'name':'Wide 2560 × 1440','controls':{'width':2560,'height':1440}}]
        else:entry['reference']=['5','image']
        if unchanged and old.get(identifier,{}).get('execution_note'):entry['execution_note']=old[identifier]['execution_note']
        added.append(entry)
    catalog['presets']=[p for p in catalog['presets'] if p['id'] not in {p['id'] for p in added}]+added
    (ROOT/'presets/catalog.json').write_text(json.dumps(catalog,indent=2)+'\n',encoding='utf-8')
    return added

if __name__=='__main__':
    print('Built',len(build(json.load(urlopen('http://127.0.0.1:8192/object_info',timeout=20)))),'HiDream API/visual pairs. Nothing submitted.')
