"""Promote the merged Qwen reference factory into native Studio recipes.

Only these three recipes are rewritten. Existing execution badges are preserved
when their graph bytes are unchanged. This command never submits a GPU job.

`geometry()` is the shipped divergence from the research factory variants in
`research/game-assets/workflows/`: every reference is scaled to one megapixel and
the canvas is an explicit latent, not a VAE encode of the primary reference
(issue #21, pilot causes D1/D3/D4/D5). The research variants stay pinned to their
historical baseline; `source_graph_sha256` still names the bytes this derives from.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

# 832x1248 is in Qwen's own PREFERRED_KONTEXT_RESOLUTIONS: /16 divisible, 1.04 MP, non-square.
CANVAS = (832, 1248)
REFERENCE_MEGAPIXELS = 1.0
# One distinct starter per role; all three live in examples/references/.
DEFAULT_IMAGES = ('studio-lantern-cutout.png', 'passing-pose-guide.png', 'atelier-style-lab-foxes.jpg')
# TextEncodeQwenImageEditPlus injects "Picture {i+1}:" tokens, so the brief says Picture.
PROMPTS = {
    1: 'Use the character identity and costume from Picture 1. Create a non-explicit fantasy portrait. Preserve the approved character design.',
    2: 'Use the character identity and costume from Picture 1. Use only the pose from Picture 2, not its identity or clothes. Create a non-explicit fantasy portrait. Preserve the approved character design.',
    3: 'Use the character identity and costume from Picture 1. Use only the pose from Picture 2, not its identity or clothes. Use only the rendering style and palette from Picture 3. Create a non-explicit fantasy portrait. Preserve the approved character design.',
}
SLOTS = (('4', '5'), ('16', '18'), ('17', '19'))
LATENT_NODE = '20'


def geometry(graph, count):
    """Fixed canvas, one-megapixel references on every slot, Picture-N wording."""
    for index, (loader, scaler) in enumerate(SLOTS[:count]):
        graph[loader]['inputs']['image'] = DEFAULT_IMAGES[index]
        graph[scaler] = {'class_type': 'ImageScaleToTotalPixels',
                         'inputs': {'image': [loader, 0], 'upscale_method': 'lanczos',
                                    'megapixels': REFERENCE_MEGAPIXELS, 'resolution_steps': 1}}
        for encoder in ('6', '7'): graph[encoder]['inputs'][f'image{index+1}'] = [scaler, 0]
    graph[LATENT_NODE] = {'class_type': 'EmptySD3LatentImage',
                          'inputs': {'width': CANVAS[0], 'height': CANVAS[1], 'batch_size': 1}}
    graph['11']['inputs']['latent_image'] = [LATENT_NODE, 0]
    graph.pop('10', None)  # The VAE encode of the shrunken primary reference is gone.
    graph['6']['inputs']['prompt'] = PROMPTS[count]
    graph['13']['inputs']['filename_prefix'] = f'Studio/Qwen-{count}ref'
    return graph


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
        graph = geometry(json.loads(source.read_text(encoding='utf-8')), count)
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
               'width':[LATENT_NODE,'width'],'height':[LATENT_NODE,'height'],'steps':['11','steps'],'cfg':['11','cfg'],
               'reference':['4','image'], 'verified': originals.get(identifier,{}).get('verified',False) if unchanged else False,
               'description':'Assign identity, pose and style separately. Every reference is scaled to 1.0 MP with its aspect preserved; the canvas is set on its own and no longer follows a reference. Role guidance is compiled into the editable brief. Semantic guidance does not guarantee exact pose or protected pixels.',
               'reference_slots':[dict(roles[i],binding=[SLOTS[i][0],'image']) for i in range(count)],
               'dimension_multiple':16,'dimension_limits':[64,1536],'max_pixels':1024*1024,
               'reference_policy':{'primary':'scale-to-total-pixels','megapixels':REFERENCE_MEGAPIXELS,'upscale_method':'lanczos',
                                   'slots':'every slot is scaled to 1.0 MP before both encoders; no slot is fitted to a width',
                                   'secondary':'native Qwen encoder preprocessing: semantic branch ~384x384, reference-latent branch ~1 MP on the 8-pixel grid',
                                   'vae':'the encoder rounds each scaled reference to a multiple of 8',
                                   'budget':"max_reference_pixels caps the authored per-reference target (megapixels x 1024^2), which is what the compiler checks; the recorded resized and vae sizes are the node's and the encoder's own rounded results and can sit a fraction of a percent either side of it",
                                   'canvas':'explicit EmptySD3LatentImage; output size is independent of every reference'},
               'max_reference_pixels':1024*1024,
               'stages':['Role-assigned references','Every reference scaled to 1.0 MP (aspect preserved)',f'Explicit {CANVAS[0]}x{CANVAS[1]} canvas','Qwen edit + matching Lightning','4-step sampling','Tiled decode'],
               'source':'https://huggingface.co/Qwen/Qwen-Image-Edit-2511',
               'commercial_note':'Review exact Qwen model and adapter terms. Creative selection is recorded separately.',
               'variants':[{'name':'Quick study','controls':{'width':640,'height':960}},{'name':'Detailed study','controls':{'width':CANVAS[0],'height':CANVAS[1]}}],
               'source_graph_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
        if originals.get(identifier,{}).get('history'): entry['history']=originals[identifier]['history']
        if unchanged and originals.get(identifier,{}).get('execution_note'): entry['execution_note']=originals[identifier]['execution_note']
        added.append(entry)
    catalog['presets']=[p for p in catalog['presets'] if p['id'] not in {p['id'] for p in added}]+added
    (ROOT/'presets/catalog.json').write_text(json.dumps(catalog,indent=2)+'\n',encoding='utf-8')
    return added


if __name__=='__main__':
    info=json.load(urlopen('http://127.0.0.1:8188/object_info',timeout=20))
    print('Built '+str(len(build(info)))+' Qwen reference API/visual pairs; no jobs submitted.')
