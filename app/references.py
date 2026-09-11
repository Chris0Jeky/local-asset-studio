"""Reference-role compilation and byte-level provenance, independent of inference."""
import hashlib
from pathlib import Path

ROLES={'identity','pose','style','costume','composition','geometry','motion','mask'}


def image_record(root, name):
    from PIL import Image, ImageOps
    path=(root/name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Saved reference is unavailable. Attach it again; the saved recipe was preserved.')
    if path.stat().st_size>20*1024*1024: raise ValueError('Reference exceeds 20 MiB')
    raw=path.read_bytes()
    with Image.open(path) as image: width,height=ImageOps.exif_transpose(image).size
    return {'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'width':width,'height':height}


def compile_references(preset, graph, supplied, uploads):
    slots=preset.get('reference_slots',[])
    if not isinstance(supplied,list) or len(supplied)!=len(slots):
        raise ValueError(f'This recipe needs {len(slots)} reference images. Fill the slots or choose a different reference recipe.')
    records=[]
    for index,(slot,reference) in enumerate(zip(slots,supplied)):
        if not isinstance(reference,dict) or reference.get('role') not in ROLES:
            raise ValueError('Every reference needs an explicit supported role')
        name=reference.get('file')
        if not isinstance(name,str) or name!=Path(name).name:
            raise ValueError('Choose an uploaded image for every reference slot')
        record=image_record(uploads,name)
        if reference.get('sha256') and reference['sha256']!=record['sha256']:
            raise ValueError('Reference bytes changed since this recipe was saved; reattach the intended image.')
        for field in ('contribution','avoid'):
            value=reference.get(field,'')
            if not isinstance(value,str) or len(value)>1500: raise ValueError('Reference guidance must be text up to 1500 characters')
            record[field]=value.strip()
        record.update(role=reference['role'],slot=index+1)
        node,field=slot['binding']; graph[node]['inputs'][field]=name
        record['transform']={'policy':'native Qwen encoder preprocessing'}
        if index==0:
            width=graph['5']['inputs']['width']
            height=max(1,round(record['height']*width/record['width']))
            if width*height>preset.get('max_reference_pixels',1024*1024):
                raise ValueError('The reference aspect ratio exceeds this recipe’s pixel budget. Reduce reference width or crop deliberately.')
            record['transform']={'policy':'fit-width-preserve-aspect','source_size':[record['width'],record['height']],
                'resized_size':[width,height],'vae_size':[width-width%8,height-height%8],
                'vae_center_crop':[width%8//2,height%8//2]}
            if min(record['transform']['vae_size'])<8: raise ValueError('Reference is too narrow for the VAE')
        records.append(record)
    prompt_node,prompt_field=preset['positive']
    brief=graph[prompt_node]['inputs'][prompt_field]
    guidance='\n'.join(f"Image {r['slot']} — {r['role']}: use {r['contribution'] or 'the assigned visual role'}. Avoid transferring: {r['avoid'] or 'unrequested details'}." for r in records)
    graph[prompt_node]['inputs'][prompt_field]=guidance+'\n\nRequested result:\n'+brief
    return records
