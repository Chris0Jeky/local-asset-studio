"""Bounded, prompt-safe explanations of imported workflow drift."""
import re


def summary(old, new):
    def label(value): return ' '.join(str(value).split())[:40]
    def order(node_id): return tuple((0,int(part)) if part.isdecimal() else (1,part) for part in re.split(r'(\d+)',str(node_id))) + ((1,str(node_id)),)
    def value(field, item):
        if isinstance(item,str):
            # Custom nodes use arbitrary prompt input names; only model filenames are safe to show.
            if field not in ('ckpt_name','checkpoint_name','lora_name','unet_name','vae_name','clip_name','clip_name1','clip_name2','model_name','diffusion_model'): return None
            item=item.replace('\\','/').rsplit('/',1)[-1]
            return label(item) if len(item)<=40 else None
        return str(item) if item is None or isinstance(item,(bool,int,float)) else None
    def link(item): return isinstance(item,list) and len(item)==2 and isinstance(item[0],str) and type(item[1]) is int
    changes=[]
    for node_id in sorted(old.keys() | new.keys(),key=order):
        before=old.get(node_id);after=new.get(node_id)
        before=before if isinstance(before,dict) else {};after=after if isinstance(after,dict) else {}
        prefix='node '+label(node_id)
        if node_id not in new: changes.append(f'{prefix} {label(before.get("class_type",""))} removed'.replace('  ',' '));continue
        if node_id not in old: changes.append(f'{prefix} {label(after.get("class_type",""))} added'.replace('  ',' '));continue
        if before.get('class_type')!=after.get('class_type'):
            changes.append(f'{prefix} class_type {label(before.get("class_type","?"))}→{label(after.get("class_type","?"))}')
        prefix+=' '+label(after.get('class_type','')) if after.get('class_type') else ''
        left=before.get('inputs');right=after.get('inputs')
        left=left if isinstance(left,dict) else {};right=right if isinstance(right,dict) else {}
        for field in sorted(left.keys() | right.keys()):
            name=f'{prefix} {label(field)}'
            if field not in right: changes.append(name+' removed');continue
            if field not in left: changes.append(name+' added');continue
            if left[field]==right[field]: continue
            if link(left[field]) or link(right[field]): changes.append(name+' link changed');continue
            a=value(field,left[field]);b=value(field,right[field])
            detail=f'{a}→{b}' if a is not None and b is not None else 'text changed' if isinstance(left[field],str) or isinstance(right[field],str) else 'value changed'
            changes.append(name+' '+detail)
    shown=changes[:6]
    while shown:
        remaining=len(changes)-len(shown)
        result='; '.join(shown+([f'+{remaining} more'] if remaining else []))
        if len(result)<400: return result
        shown.pop()
    return ''
