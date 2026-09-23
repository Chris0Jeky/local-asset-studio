"""Reference-role compilation and byte-level provenance, independent of inference."""
import copy
import hashlib
import io
import math
from pathlib import Path

MAX_REFERENCE_BYTES=20*1024*1024

ROLES={'identity','pose','style','costume','composition','geometry','motion','mask'}
BOARD_POLICY='native IP-Adapter CLIP-vision preprocessing (224 px centre crop)'


def board_spec(preset):
    """Return one validated description shared by board review and compilation."""
    slots=preset.get('reference_slots') or [];board=preset.get('reference_board')
    if not isinstance(board,dict) or not slots:raise ValueError('This recipe has no reference board')
    minimum=board.get('min',1);policy=board.get('policy',BOARD_POLICY)
    if type(minimum) is not int or not 0<=minimum<=len(slots):raise ValueError('Reference-board minimum must fit its declared slots')
    if not isinstance(policy,str) or not policy or len(policy)>500:raise ValueError('Reference-board preprocessing policy is invalid')
    roles=[]
    for slot in slots:
        role=slot.get('role','style') if isinstance(slot,dict) else None
        if role not in ROLES:raise ValueError('Every board slot needs a supported role')
        roles.append(role)
    return {'minimum':minimum,'slot_count':len(slots),'roles':roles,'policy':policy}


def board_transform(preset):
    return {'policy':board_spec(preset)['policy']}


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


def prune_missing_slot(graph, node):
    """Remove an unfilled board slot's loader and every node that existed only to encode it.

    An IPAdapterCombineEmbeds input that pointed at a removed encoder is dropped (its embed2..5 are
    optional); when embed1 goes, the next present embed slides into its place so the combiner still
    has a first input. A ReferenceLatent whose latent is gone is bypassed: whatever consumed it now
    consumes its conditioning input, so a chain of reference latents (FLUX.2 Klein boards) closes up
    around the empty slot. Anything else that consumed a removed node is removed in turn.
    """
    removed={str(node)}; graph.pop(str(node),None); changed=True
    while changed:
        changed=False
        for key,item in list(graph.items()):
            inputs=item.get('inputs') or {}
            for field,value in list(inputs.items()):
                if not (isinstance(value,list) and len(value)==2 and str(value[0]) in removed): continue
                if item.get('class_type')=='IPAdapterCombineEmbeds':
                    del inputs[field]
                    if field=='embed1':
                        rest=[f for f in ('embed2','embed3','embed4','embed5') if f in inputs]
                        if not rest: raise ValueError('The style board needs at least one picture')
                        inputs['embed1']=inputs.pop(rest[0])
                elif item.get('class_type')=='ReferenceLatent' and field=='latent' and isinstance(inputs.get('conditioning'),list):
                    upstream=list(inputs['conditioning']); graph.pop(key); removed.add(key)
                    for other in graph.values():
                        for name,link in list((other.get('inputs') or {}).items()):
                            if isinstance(link,list) and len(link)==2 and str(link[0])==key: other['inputs'][name]=list(upstream)
                    changed=True
                else: graph.pop(key); removed.add(key); changed=True
                break
            if changed: break
    return graph


def prune_empty_board(preset, graph):
    """Bypass a whole native IP-Adapter board, refusing unknown or shared paths.

    This is deliberately narrower than pruning one absent slot: an empty board must
    never remove a sampler/output or fall back to an undeclared example. Plan on a
    copy and commit only after all surviving consumers have valid replacements.
    """
    def refuse():
        raise ValueError('Cannot remove this empty optional board safely; its graph needs an explicit supported bypass.')

    def link(value):
        return (str(value[0]), value[1]) if (isinstance(value, list) and len(value) == 2
            and isinstance(value[0], (str, int)) and not isinstance(value[0], bool)
            and type(value[1]) is int and value[1] >= 0) else None

    loaders = set()
    for slot in preset['reference_slots']:
        binding = slot.get('binding')
        if not isinstance(binding, (list, tuple)) or len(binding) != 2: refuse()
        node, field = str(binding[0]), binding[1]
        if field != 'image' or node in loaders or graph.get(node, {}).get('class_type') != 'LoadImage': refuse()
        loaders.add(node)
    protected = {str(binding[0]) for name in ('reference', 'last_reference')
                 if isinstance(binding := preset.get(name), (list, tuple)) and binding}
    loader_outputs = {(key, 0) for key in loaders}
    embeddings = {key for key, item in graph.items() if item.get('class_type') == 'IPAdapterEncoder'
                  and link((item.get('inputs') or {}).get('image')) in loader_outputs}
    # Combine only embeddings owned by this board. Mixed/unknown consumers remain
    # outside the removal set and are refused by the surviving-link check below.
    while True:
        before = len(embeddings)
        for key, item in graph.items():
            if key in embeddings or item.get('class_type') != 'IPAdapterCombineEmbeds': continue
            inputs = item.get('inputs') or {}
            values = [link(inputs[name]) for name in ('embed1', 'embed2', 'embed3', 'embed4', 'embed5') if name in inputs]
            if 'embed1' in inputs and values and all(value and value[0] in embeddings and value[1] == 0 for value in values):
                embeddings.add(key)
        if len(embeddings) == before: break
    embedding_outputs = {(key, 0) for key in embeddings}
    bypass = {key: (item.get('inputs') or {}).get('model') for key, item in graph.items()
              if item.get('class_type') == 'IPAdapterEmbeds'
              and link((item.get('inputs') or {}).get('pos_embed')) in embedding_outputs}
    if not bypass: refuse()
    removed = loaders | embeddings | set(bypass)
    # A named input owns its claim independently of every board role, even if a
    # malformed catalog aliases it to an intermediate node rather than a loader.
    if removed & protected: refuse()
    for key, upstream in bypass.items():
        # Negative-embedding boards need their own explicit contract; do not
        # silently discard a separately conditioned input while removing this board.
        if (graph[key].get('inputs') or {}).get('neg_embed') is not None: refuse()
        bound = link(upstream)
        if not bound or bound[0] not in graph: refuse()
        # Contracting a model edge is valid only when it cannot create a cycle.
        seen, pending = set(), [bound[0]]
        while pending:
            node = pending.pop()
            if node == key: refuse()
            if node in seen: continue
            seen.add(node)
            pending.extend(edge[0] for value in (graph.get(node, {}).get('inputs') or {}).values()
                           if (edge := link(value)))

    working = copy.deepcopy(graph)
    for key in removed: working.pop(key)
    for item in working.values():
        for field, value in list((item.get('inputs') or {}).items()):
            edge = link(value)
            seen = set()
            while edge and edge[0] in bypass:
                if edge[1] != 0 or edge[0] in seen: refuse()
                seen.add(edge[0])
                value = list(bypass[edge[0]])
                edge = link(value)
            if isinstance(value, list) and len(value) == 2 and str(value[0]) in removed: refuse()
            item['inputs'][field] = value
    # Remove only now-unused adapter/vision loaders, never a shared model resource.
    auxiliary = {edge[0] for key in embeddings | set(bypass) for field in ('ipadapter', 'clip_vision')
                 if (edge := link((graph[key].get('inputs') or {}).get(field)))}
    used = {edge[0] for item in working.values() for value in (item.get('inputs') or {}).values()
            if (edge := link(value))}
    for key in auxiliary - used:
        if working.get(key, {}).get('class_type') in ('IPAdapterModelLoader', 'CLIPVisionLoader'):
            if key in protected: refuse()
            working.pop(key)
    graph.clear()
    graph.update(working)


def compile_board(preset, graph, supplied, uploads):
    """A style board: every slot is optional, missing slots are pruned, no prompt guidance is written."""
    slots=preset.get('reference_slots',[]);spec=board_spec(preset);transform=board_transform(preset)
    supplied=[] if supplied is None else supplied
    if not isinstance(supplied,list) or len(supplied)>len(slots): raise ValueError(f'This recipe has {len(slots)} board slots')
    supplied=list(supplied)+[{}]*(len(slots)-len(supplied))
    minimum=spec['minimum']
    if sum(1 for r in supplied if isinstance(r,dict) and r.get('file'))<minimum:
        raise ValueError(f'Attach at least {minimum} picture{"s" if minimum!=1 else ""} to the board, or leave the recipe example in place')
    empty = minimum == 0 and not any(isinstance(r, dict) and r.get('file') for r in supplied)
    if empty: prune_empty_board(preset, graph)
    records=[]
    for index,(slot,reference) in enumerate(zip(slots,supplied)):
        node,field=slot['binding']
        if not isinstance(reference,dict) or not reference.get('file'):
            # Keep the slot's position in the persisted record: a saved recipe restores by index, so a
            # two-picture board must still come back as three slots with the empty one marked.
            if not empty: prune_missing_slot(graph,node)
            records.append({'slot':index+1,'role':spec['roles'][index],'file':None,'pruned':True,'contribution':'','avoid':''}); continue
        if reference.get('role',slot.get('role')) not in ROLES: raise ValueError('Every reference needs an explicit supported role')
        name=reference['file']
        if not isinstance(name,str) or name!=Path(name).name: raise ValueError('Choose an uploaded image for every reference slot')
        record=image_record(uploads,name)
        if reference.get('sha256') and reference['sha256']!=record['sha256']:
            raise ValueError('Reference bytes changed since this recipe was saved; reattach the intended image.')
        record.update(role=reference.get('role',slot.get('role')),slot=index+1,contribution='',avoid='',transform=transform)
        graph[str(node)]['inputs'][field]=name
        records.append(record)
    return records


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
    if preset.get('reference_board'): return compile_board(preset, graph, supplied, uploads)
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
