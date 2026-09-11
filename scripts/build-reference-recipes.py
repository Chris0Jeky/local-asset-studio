"""Promote the merged Qwen reference factory into native Studio recipes.

Only these three recipes are rewritten. Existing execution badges are preserved
when their graph bytes are unchanged. This command never submits a GPU job.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def build(info):
    spec = importlib.util.spec_from_file_location('expansion_builder', ROOT/'scripts/build-expansion.py')
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    catalog = json.loads((ROOT/'presets/catalog.json').read_text(encoding='utf-8'))
    originals = {p['id']:p for p in catalog['presets']}
    roles = [
        {'role':'identity','contribution':'Face, hair, proportions, distinctive costume and accessories','avoid':'Unrequested changes to identity or costume'},
        {'role':'pose','contribution':'Body position, viewing angle, hand and prop contact','avoid':'The reference person, costume and rendering style'},
        {'role':'style','contribution':'Linework, shading, medium and palette','avoid':'The reference subject and composition'},
    ]
    added=[]
    for count in (1,2,3):
        source = ROOT/f'research/game-assets/workflows/qwen-{count}ref-api.json'
        graph = json.loads(source.read_text(encoding='utf-8'))
        # Native ImageScale computes height from the input aspect when height=0.
        graph['5']['inputs'].update(width=512,height=0,crop='disabled')
        graph['4']['inputs']['image']='studio-lantern-cutout.png'
        for node in ('16','17'):
            if node in graph: graph[node]['inputs']['image']='studio-lantern-cutout.png'
        graph['13']['inputs']['filename_prefix']=f'Studio/Qwen-{count}ref'
        title=f'Qwen Atelier - {count} Reference'+('s' if count>1 else '')
        identifier=f'qwen-{count}ref'
        api_path=f'workflows/api/{identifier}-api.json'
        visual_path=f'workflows/comfyui/{49+count} - {title}.json'
        raw=json.dumps(graph,indent=2)+'\n'
        path=ROOT/api_path
        unchanged=path.exists() and path.read_text(encoding='utf-8')==raw
        path.write_text(raw,encoding='utf-8')
        (ROOT/visual_path).write_text(json.dumps(builder.visual(graph,title,info),indent=2)+'\n',encoding='utf-8')
        entry={'id':identifier,'name':title,'category':'Reference atelier','collection':'production-workspace',
               'family':'Qwen Image Edit 2511','modality':'image','graph':api_path,'visual':visual_path,
               'positive':['6','prompt'],'negative':['7','prompt'],'seed':['11','seed'],
               'width':['5','width'],'steps':['11','steps'],'cfg':['11','cfg'],
               'reference':['4','image'], 'verified': originals.get(identifier,{}).get('verified',False) if unchanged else False,
               'description':'Assign identity, pose and style separately. Images retain their aspect ratio; role guidance is compiled into the editable brief. Semantic guidance does not guarantee exact pose or protected pixels.',
               'reference_slots':[dict(roles[i],binding=[('4','16','17')[i],'image']) for i in range(count)],
               'reference_policy':{'primary':'fit-width-preserve-aspect','secondary':'native Qwen encoder preprocessing','vae':'center-crop to multiple of 8'},
               'max_reference_pixels':1024*1024,
               'stages':['Role-assigned references','Aspect-preserving resize','Qwen edit + matching Lightning','4-step sampling','Tiled decode'],
               'source':'https://huggingface.co/Qwen/Qwen-Image-Edit-2511',
               'commercial_note':'Review exact Qwen model and adapter terms. Creative selection is recorded separately.',
               'variants':[{'name':'Quick reference study','controls':{'width':384}},{'name':'Detailed reference study','controls':{'width':768}}],
               'source_graph_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
        if unchanged and originals.get(identifier,{}).get('execution_note'): entry['execution_note']=originals[identifier]['execution_note']
        added.append(entry)
    catalog['presets']=[p for p in catalog['presets'] if p['id'] not in {p['id'] for p in added}]+added
    (ROOT/'presets/catalog.json').write_text(json.dumps(catalog,indent=2)+'\n',encoding='utf-8')
    return added


if __name__=='__main__':
    info=json.load(urlopen('http://127.0.0.1:8188/object_info',timeout=20))
    print('Built '+str(len(build(info)))+' Qwen reference API/visual pairs; no jobs submitted.')
