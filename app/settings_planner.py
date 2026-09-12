"""Turn the settings knowledge base into explicit, sourced sweep variants.

Pure module: it never imports the server or production lab, never touches the
network and writes nothing.  Every variant carries the rationale and sources of
the documented setting it changes, so a sweep records why it was run and an
undocumented number can never enter a plan by accident.
"""
from __future__ import annotations
import hashlib
import itertools
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

KB_PATH='presets/settings-kb.json'
CHOICE_CONTROLS=('sampler','scheduler')
LORA_SLOTS=('lora','lora2','lora3','lora4','lora5','lora6')
SETTING_KEYS=set(LORA_SLOTS)|{s+'_name' for s in LORA_SLOTS}|{'steps','cfg','denoise','width','height','seed','frames','fps','sampler','scheduler'}
DEFAULT_LADDER=[1.0,0.8,0.6]
EMPTY={'version':0,'families':{},'loras':{}}


def load_kb(root):
    """Return (knowledge base, sha256 of the file on disk).

    A missing or unreadable file is not an error: the planner simply has nothing
    documented to offer, and the empty digest records that honestly.
    """
    try:raw=(Path(root)/KB_PATH).read_bytes()
    except OSError:return dict(EMPTY,families={},loras={}),''
    digest=hashlib.sha256(raw).hexdigest()
    try:data=json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError,json.JSONDecodeError):return dict(EMPTY,families={},loras={}),digest
    if not isinstance(data,dict):return dict(EMPTY,families={},loras={}),digest
    if not isinstance(data.get('families'),dict):data['families']={}
    if not isinstance(data.get('loras'),dict):data['loras']={}
    return data,digest


def _number(value,fallback=None):
    if isinstance(value,bool):value=None
    try:result=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):result=None
    if result is None or not result.is_finite():
        if fallback is None:raise ValueError('Expected a finite number, got '+repr(value)[:60])
        return float(fallback)
    return float(result)


def _cap(limit):
    if type(limit) is not int or not 1<=limit<=8:raise ValueError('Plan between one and eight variants')
    return limit


def _bound(preset,control):
    """A control is usable when the catalog binds it, primary or companion."""
    return bool(preset.get(control)) or bool((preset.get('bindings_extra') or {}).get(control))


def family_entry(preset,kb):
    return ((kb or {}).get('families') or {}).get(preset.get('family')) or {}


def axes_for(preset,kb):
    """Documented axes of the preset's family that this preset can actually change."""
    result=[]
    for axis in family_entry(preset,kb).get('axes') or []:
        if not isinstance(axis,dict):continue
        control=axis.get('control')
        if not isinstance(control,str) or not _bound(preset,control):continue
        values=[v for v in (axis.get('values') or []) if not isinstance(v,(dict,list))]
        if control in CHOICE_CONTROLS:
            allowed=(preset.get('choices') or {}).get(control) or []
            values=[v for v in values if v in allowed]
        seen=[]
        for value in values:
            if value not in seen:seen.append(value)
        if not seen:continue
        result.append({'id':axis.get('id') or control,'control':control,'values':seen,
                       'rationale':axis.get('rationale') or '','sources':list(axis.get('sources') or [])})
    return result


def _merge_sources(parts):
    result=[]
    for source in parts:
        if isinstance(source,str) and source and source not in result:result.append(source)
    return result


def plan_grid(preset,kb,base_controls,axis_ids,limit=8):
    """Cartesian product of the chosen documented axes.

    Order is fixed and documented: the first axis in `axis_ids` varies slowest,
    the last fastest, and the product is truncated to `limit` (1-8) so a plan can
    never exceed the comparison ceiling.
    """
    limit=_cap(limit)
    available={axis['id']:axis for axis in axes_for(preset,kb)}
    if not isinstance(axis_ids,(list,tuple)) or not axis_ids:raise ValueError('Choose at least one documented axis')
    chosen=[]
    for identifier in axis_ids:
        if not isinstance(identifier,str):raise ValueError('Unknown or unbound axis: '+repr(identifier)[:60])
        axis=available.get(identifier)
        if not axis:raise ValueError('Unknown or unbound axis: '+str(identifier)[:60])
        if axis not in chosen:chosen.append(axis)
    base=dict(base_controls or {});variants=[]
    for combination in itertools.product(*[axis['values'] for axis in chosen]):
        controls=dict(base)
        for axis,value in zip(chosen,combination):controls[axis['control']]=value
        variants.append({'label':' · '.join(f"{axis['control']}={value}" for axis,value in zip(chosen,combination)),
                         'controls':controls,
                         'rationale':'; '.join(axis['rationale'] for axis in chosen if axis['rationale']),
                         'sources':_merge_sources([s for axis in chosen for s in axis['sources']])})
        if len(variants)==limit:break
    return variants


def _slot_entry(slot,base,defaults,kb):
    name=base.get(slot+'_name',defaults.get(slot+'_name'))
    entry=((kb or {}).get('loras') or {}).get(name) if isinstance(name,str) else None
    entry=dict(entry) if isinstance(entry,dict) else {}
    entry.setdefault('label',Path(name).stem if isinstance(name,str) and name else slot)
    entry['file']=name if isinstance(name,str) else ''
    return entry


def plan_remix(preset,kb,base_controls,slots=LORA_SLOTS,ladder=None,limit=8):
    """One variant per active LoRA slot at the top of the ladder, plus one blend.

    Only slots the preset binds and whose base strength is above zero take part:
    an off slot stays off, because turning one on is a different question than
    re-weighting the stack.
    """
    limit=_cap(limit)
    rules=family_entry(preset,kb).get('lora_rules') or {}
    steps=[_number(value) for value in (ladder or rules.get('ladder') or DEFAULT_LADDER)]
    if len(steps)<2:raise ValueError('A remix ladder needs at least two strengths')
    base=dict(base_controls or {});defaults=preset.get('defaults') or {}
    active=[slot for slot in slots if _bound(preset,slot) and _number(base.get(slot,defaults.get(slot,0)),0)>0]
    if not active:raise ValueError('Turn on at least one LoRA slot before remixing its weights')
    entries={slot:_slot_entry(slot,base,defaults,kb) for slot in active}
    warn=rules.get('warn_total_strength');notes=[n for n in (rules.get('notes') or []) if isinstance(n,str)]
    variants=[]
    for slot in active:
        controls=dict(base)
        for other in active:controls[other]=steps[0] if other==slot else steps[-1]
        entry=entries[slot]
        rationale=' · '.join([p for p in [f"{entry['label']} leads at {steps[0]}; the rest support at {steps[-1]}",
                                          entry.get('role') or '','; '.join(entry.get('notes') or [])] if p])
        variants.append({'label':f"{entry['label']} lead","controls":controls,'rationale':_warned(rationale,controls,active,warn),
                         'sources':_merge_sources([entry.get('source'),entry.get('mirror')])})
    if len(active)>1 and len(variants)<limit:
        controls=dict(base)
        for other in active:controls[other]=steps[1]
        rationale=f"Every active adapter at the ladder's middle step {steps[1]}"+(' · '+'; '.join(notes) if notes else '')
        variants.append({'label':f'All active LoRAs at {steps[1]}','controls':controls,'rationale':_warned(rationale,controls,active,warn),
                         'sources':_merge_sources([entries[slot].get('source') for slot in active])})
    return variants[:limit]


def _warned(rationale,controls,active,warn):
    if warn is None:return rationale
    total=sum(_number(controls.get(slot,0),0) for slot in active)
    if total<=_number(warn,0):return rationale
    return rationale+f' · warning: total LoRA strength {round(total,3)} exceeds the documented {warn}'


def describe(variant):
    """One line for the browser: what changes, and why it is worth a run."""
    controls=variant.get('controls') or {}
    shown=', '.join(f'{key}={controls[key]}' for key in sorted(controls) if key in SETTING_KEYS)
    text=str(variant.get('label') or 'variant')
    if shown:text+=' · '+shown
    if variant.get('rationale'):text+=' — '+variant['rationale']
    return text
