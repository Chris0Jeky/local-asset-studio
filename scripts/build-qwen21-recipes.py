"""Build the isolated Qwen-Image 2.1 recipes (text to image, transparent RGBA, one-picture edit); never submit a job.

Graphs follow Comfy-Org's day-0 templates (image_qwen_image_2_1_t2i / _image_edit, flattened): 25 steps, CFG 1,
euler/simple, the int8 ConvRot diffusion model and Qwen3-VL 8B int8 text encoder. The transparent recipe wraps
the prompt in the model card's RGBA wording. Visual graphs need the live schema of the isolated backend (8196).
The recipes are appended once (a rebuild refuses while they exist); the rest of presets/catalog.json stays byte-identical.
"""
import copy
import importlib.util
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
DIFFUSION='qwen_image_2.1_int8_convrot.safetensors';ENCODER='qwen3vl_8b_int8_convrot.safetensors';DECODER='qwen_image_2.1_vae_bf16.safetensors'
RGBA_PREFIX='This is an RGBA image with transparency.'
RGBA_SUFFIX='The image has alpha channel and the background is transparent.'
NOTE=('Qwen Research License (20 September 2026): non-commercial research or evaluation only; commercial use needs a separate '
      'licence from Qwen. Private experiments only. Runs on the isolated ComfyUI v0.37.0 backend (8196); the primary ComfyUI '
      '(v0.35.0) has no Qwen-Image 2.1 model class.')
SOURCE='https://huggingface.co/Qwen/Qwen-Image-2.1'
MODEL_FILES=['diffusion_models/'+DIFFUSION,'text_encoders/'+ENCODER,'vae/'+DECODER]


def base():
    return {
        '1':{'class_type':'UNETLoader','inputs':{'unet_name':DIFFUSION,'weight_dtype':'default'}},
        '2':{'class_type':'CLIPLoader','inputs':{'clip_name':ENCODER,'type':'qwen_image','device':'default'}},
        '3':{'class_type':'VAELoader','inputs':{'vae_name':DECODER}},
        '4':{'class_type':'TextEncodeQwenImage21','inputs':{'clip':['2',0],'prompt':'','negative_prompt':'','resolution':1024}},
        '5':{'class_type':'EmptyLatentImage','inputs':{'width':1024,'height':1024,'batch_size':1}},
        '6':{'class_type':'KSampler','inputs':{'model':['1',0],'positive':['4',0],'negative':['4',1],'latent_image':['5',0],
             'seed':2026092201,'steps':25,'cfg':1.0,'sampler_name':'euler','scheduler':'simple','denoise':1.0}},
        '7':{'class_type':'VAEDecode','inputs':{'samples':['6',0],'vae':['3',0]}},
        '8':{'class_type':'SaveImage','inputs':{'images':['7',0],'filename_prefix':'Studio/qwen21'}},
    }


def graphs():
    t2i=base();t2i['8']['inputs']['filename_prefix']='Studio/qwen21-t2i'
    t2i['4']['inputs']['prompt']=('Anime key visual of an adult silver-haired sorceress in a midnight-blue travelling coat, holding a glowing '
                                  'brass lantern on a rainy stone bridge at blue hour. Clean linework, layered cel shading, teal and warm amber light.')
    t2i['5']['inputs'].update(width=832,height=1248)
    rgba=base();rgba['8']['inputs']['filename_prefix']='Studio/qwen21-rgba'
    # The model card's transparent-image wording, with the user's subject in the middle.
    rgba['9']={'class_type':'StringConcatenate','inputs':{'string_a':RGBA_PREFIX,'string_b':'A fantasy healing potion game icon: a round glass flask with a cork, '
               'glowing teal liquid and a small brass tag, clean cel-shaded style, centred, full object visible.','delimiter':' '}}
    rgba['10']={'class_type':'StringConcatenate','inputs':{'string_a':['9',0],'string_b':RGBA_SUFFIX,'delimiter':' '}}
    rgba['4']['inputs']['prompt']=['10',0]
    edit=base();edit['8']['inputs']['filename_prefix']='Studio/qwen21-edit'
    # Output size follows picture 1 at about resolution x resolution pixels (the encoder's own latent).
    del edit['5']
    edit['9']={'class_type':'QwenImage21Cache','inputs':{'model':['1',0],'device':'auto','dtype':'default'}}
    edit['10']={'class_type':'LoadImage','inputs':{'image':'studio-lantern-cutout.png'}}
    edit['4']['inputs'].update(vae=['3',0],prompt='Keep the object, its shape and its colours. Redraw it as a clean anime game prop illustration with crisp '
                               'ink outlines and soft cel shading on a plain light background.')
    edit['4']['inputs']['images.image_1']=['10',0]
    edit['6']['inputs'].update(model=['9',0],latent_image=['4',2])
    return {'qwen21-t2i':t2i,'qwen21-rgba':rgba,'qwen21-edit':edit}


def entries():
    common=dict(category='Qwen-Image 2.1 · isolated',collection='production-workspace',family='Qwen-Image 2.1',backend_id='qwen21',modality='image',
                negative=['4','negative_prompt'],seed=['6','seed'],steps=['6','steps'],cfg=['6','cfg'],sampler=['6','sampler_name'],scheduler=['6','scheduler'],
                choices={'sampler':['euler','euler_ancestral','dpmpp_2m'],'scheduler':['simple','normal','beta']},
                verified=False,model_files=MODEL_FILES,source=SOURCE,commercial_note=NOTE)
    steps=[{'name':'25-step template','controls':{'steps':25}},{'name':'40-step model card','controls':{'steps':40}}]
    size=dict(width=['5','width'],height=['5','height'],dimension_limits=[512,2752],dimension_multiple=32,
              resolution_choices=[[1024,1024],[832,1248],[1248,832],[2048,2048],[1792,2400],[2400,1792],[1696,2528],[2528,1696],[1536,2752],[2752,1536]])
    size['max_pixels']=max(w*h for w,h in size['resolution_choices'])   # 1792 x 2400 = 4,300,800: every native 2K size must pass the pixel budget
    sizes=[{'name':'Portrait 832 × 1248','controls':{'width':832,'height':1248}},{'name':'Square 1024','controls':{'width':1024,'height':1024}},
           {'name':'Native 2K square','controls':{'width':2048,'height':2048}}]
    return [
        dict(id='qwen21-t2i',name='Qwen-Image 2.1 - Text to Image',positive=['4','prompt'],**common,**size,
             description='Qwen-Image 2.1 (7B, int8 ConvRot) from a written brief, on the isolated v0.37.0 backend. Native 2K is supported; 1 MP is the everyday size. '
                         'CFG 1 as in Comfy-Org\'s template, so the negative prompt has little effect.',
             stages=['Qwen3-VL 8B text encoder (int8)','Qwen-Image 2.1 7B (int8 ConvRot)','25-step euler','RGBA-capable decoder','PNG'],
             variants=steps+sizes),
        dict(id='qwen21-rgba',name='Qwen-Image 2.1 - Transparent sprite (RGBA)',positive=['9','string_b'],**common,**size,
             description='A picture with a real alpha channel, no background removal: your subject is wrapped in the model card\'s transparent-image wording ("'
                         +RGBA_PREFIX+' … '+RGBA_SUFFIX+'"). Describe one object or character and keep it fully in frame. The PNG keeps the alpha channel.',
             stages=['RGBA wording around your subject','Qwen3-VL 8B text encoder (int8)','Qwen-Image 2.1 7B (int8 ConvRot)','25-step euler','4-channel decoder','PNG with alpha'],
             variants=steps+[{'name':'Icon 1024','controls':{'width':1024,'height':1024}},{'name':'Character 832 × 1248','controls':{'width':832,'height':1248}}]),
        dict(id='qwen21-edit',name='Qwen-Image 2.1 - Edit one picture',positive=['4','prompt'],reference=['10','image'],**common,
             description='Instruction edit of one picture on the isolated v0.37.0 backend. The result keeps picture 1\'s aspect ratio at about 1 MP (the encoder\'s own latent); '
                         'the model sees the picture both through Qwen3-VL and as a VAE latent. Unrequested details can change.',
             stages=['Picture 1 resized to ~1 MP on the 32-pixel grid','Qwen3-VL 8B reads picture and instruction','Reference latent spliced in','25-step euler','PNG'],
             variants=steps),
    ]


def insert(entries_):
    """Replace or append the recipes without reserialising the hand-formatted rest of the catalog."""
    path=ROOT/'presets/catalog.json';raw=path.read_text(encoding='utf-8')
    catalog=json.loads(raw);ids={e['id'] for e in entries_}
    if any(p['id'] in ids for p in catalog['presets']):raise SystemExit('Recipes already in the catalog; remove them first to rebuild')
    tail='\n  ]\n}\n'
    if not raw.endswith(tail):raise SystemExit('Unexpected catalog ending')
    body=',\n'.join('    '+json.dumps(e,indent=2,ensure_ascii=False).replace('\n','\n    ') for e in entries_)
    path.write_text(raw[:-len(tail)]+',\n'+body+tail,encoding='utf-8',newline='\n')


def build(info):
    spec=importlib.util.spec_from_file_location('expansion_builder',ROOT/'scripts/build-expansion.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    built=graphs();made=[]
    visuals={'qwen21-t2i':'58 - Qwen-Image 2.1 - Text to Image.json','qwen21-rgba':'59 - Qwen-Image 2.1 - Transparent Sprite.json','qwen21-edit':'60 - Qwen-Image 2.1 - Edit One Picture.json'}
    records=entries()
    for record in records:
        graph=built[record['id']];api=f"workflows/api/{record['id']}-api.json";visual='workflows/comfyui/'+visuals[record['id']]
        (ROOT/api).write_text(json.dumps(graph,indent=2)+'\n',encoding='utf-8',newline='\n')
        (ROOT/visual).write_text(json.dumps(builder.visual(copy.deepcopy(graph),record['name'],info),indent=2)+'\n',encoding='utf-8',newline='\n')
        record['graph']=api;record['visual']=visual;made.append(record['id'])
    insert(records)
    return made


if __name__=='__main__':
    print('Built',build(json.load(urlopen('http://127.0.0.1:8196/object_info',timeout=30))),'- nothing submitted.')
