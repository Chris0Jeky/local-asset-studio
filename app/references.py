"""Reference-role compilation and byte-level provenance, independent of inference."""
import hashlib
import io
import math
from pathlib import Path

MAX_REFERENCE_BYTES=20*1024*1024

ROLES={'identity','pose','style','costume','composition','geometry','motion','mask'}


def scale_node(graph, node):
    """The ImageScaleToTotalPixels node this slot's loader feeds, or None."""
    for item in graph.values():
        if item.get('class_type')=='ImageScaleToTotalPixels' and (item.get('inputs') or {}).get('image')==[node,0]: return item
    return None


def scaled_size(width, height, megapixels, steps=1):
    """ComfyUI's own arithmetic: comfy_extras/nodes_post_processing.ImageScaleToTotalPixels."""
    factor=math.sqrt(megapixels*1024*1024/(width*height))
    return [int(round(width*factor/steps)*steps), int(round(height*factor/steps)*steps)]


def image_record(root, name, *, strict_pixels=False):
    from PIL import Image, ImageOps
    path=(root/name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Saved reference is unavailable. Attach it again; the saved recipe was preserved.')
    if path.stat().st_size>MAX_REFERENCE_BYTES: raise ValueError('Reference exceeds 20 MiB')
    # Capture once: both provenance and dimensions must describe these exact bytes.
    # The read bound also holds when a source grows after the stat precheck.
    with path.open('rb') as stream: raw=stream.read(MAX_REFERENCE_BYTES+1)
    if len(raw)>MAX_REFERENCE_BYTES: raise ValueError('Reference exceeds 20 MiB')
    with io.BytesIO(raw) as stream, Image.open(stream) as image:
        if strict_pixels and Image.MAX_IMAGE_PIXELS is not None and image.width*image.height>Image.MAX_IMAGE_PIXELS:
            raise ValueError('Reference exceeds the image safety pixel limit')
        with ImageOps.exif_transpose(image) as oriented: width,height=oriented.size
    return {'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'width':width,'height':height}



def reference_transform(preset, graph, node, record):
    """Project the same reference resize arithmetic used by compilation; no writes."""
    result={'policy':'native Qwen encoder preprocessing'}
    scaler=scale_node(graph,node)
    if scaler is not None:
        inputs=scaler.get('inputs') or {}; megapixels=inputs.get('megapixels'); steps=inputs.get('resolution_steps',1)
        budget=preset.get('max_reference_pixels',1024*1024)
        if isinstance(megapixels,bool) or not isinstance(megapixels,(int,float)) or not 0<megapixels*1024*1024<=budget:
            raise ValueError('This recipe scales every reference past its own pixel budget. Fix the workflow megapixels or the recipe budget.')
        if isinstance(steps,bool) or not isinstance(steps,int) or steps<1: raise ValueError('Reference resize step must be a whole number of pixels')
        resized=scaled_size(record['width'],record['height'],megapixels,steps)
        if min(resized)<16:
            raise ValueError('The reference aspect ratio is too extreme for this recipe’s pixel budget. Crop it deliberately before attaching.')
        # The encoder derives its own reference latent from the already scaled image, on the eight-pixel grid.
        vae=scaled_size(resized[0],resized[1],1.0,8)
        if min(resized+vae)<16:
            raise ValueError('The reference aspect ratio is too extreme for this recipe’s pixel budget. Crop it deliberately before attaching.')
        result={'policy':'scale-to-total-pixels','megapixels':megapixels,
            'upscale_method':inputs.get('upscale_method'),'source_size':[record['width'],record['height']],
            'resized_size':resized,'vae_size':vae}
    return result


def guidance_text(records, brief):
    """Picture numbering and wording shared by review and actual compilation."""
    guidance="\n".join(f"Picture {r['slot']} — {r['role']}: use {r['contribution'] or 'the assigned visual role'}. Avoid transferring: {r['avoid'] or 'unrequested details'}." for r in records)
    return guidance+"\n\nRequested result:\n"+brief


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
        record['transform']=reference_transform(preset,graph,node,record)
        records.append(record)
    prompt_node,prompt_field=preset['positive']
    brief=graph[prompt_node]['inputs'][prompt_field]
    # TextEncodeQwenImageEditPlus injects "Picture {i+1}:" tokens, so the guidance names the same slots.
    graph[prompt_node]['inputs'][prompt_field]=guidance_text(records,brief)
    return records
