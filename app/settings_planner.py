"""Turn the settings knowledge base into explicit, sourced sweep variants.

Pure module: it never imports the server or production lab, never touches the
network and writes nothing.  Every variant carries the rationale and sources of
the documented setting it changes, so a sweep records why it was run and an
undocumented number can never enter a plan by accident.
"""
from __future__ import annotations
import copy
import hashlib
import itertools
import math
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

KB_PATH='presets/settings-kb.json'
CHOICE_CONTROLS=('sampler','scheduler')
LORA_SLOTS=('lora','lora2','lora3','lora4','lora5','lora6')
SETTING_KEYS=set(LORA_SLOTS)|{s+'_name' for s in LORA_SLOTS}|{'steps','cfg','denoise','width','height','seed','frames','fps','sampler','scheduler'}
DEFAULT_LADDER=[1.0,0.8,0.6]
SCHEDULE_CONTROLS={'steps','cfg','sampler','scheduler','denoise'}
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
    try:
        result=Decimal(str(value));converted=float(result)
    except (InvalidOperation,ValueError,TypeError,OverflowError):result=converted=None
    if result is None or not result.is_finite() or not math.isfinite(converted):
        if fallback is None:raise ValueError('Expected a finite number, got '+repr(value)[:60])
        converted=float(fallback)
        if not math.isfinite(converted):raise ValueError('Expected a finite fallback number')
    return converted


def _cap(limit):
    if type(limit) is not int or not 1<=limit<=8:raise ValueError('Plan between one and eight variants')
    return limit


def _binding(value):
    return (isinstance(value,(list,tuple)) and len(value)==2
            and isinstance(value[0],(str,int)) and isinstance(value[1],str))


def _bound(preset,control):
    """A control is usable when the catalog binds it, primary or companion."""
    extras=(preset.get('bindings_extra') or {}).get(control,[])
    return _binding(preset.get(control)) or any(_binding(pair) for pair in extras)


def family_entry(preset,kb):
    return ((kb or {}).get('families') or {}).get(preset.get('family')) or {}


def accelerator_slots(preset,kb,base_controls=None):
    """Known KB roles only, not installed-byte or compatibility attestation."""
    base=base_controls or {};defaults=preset.get('defaults') or {};result={}
    for slot in LORA_SLOTS:
        if not _bound(preset,slot):continue
        entry=_slot_entry(slot,base,defaults,kb)
        if entry.get('role')!='accelerator':continue
        value=base.get(slot,defaults.get(slot))
        # Only explicit finite zero proves inactivity. Unknown and negative
        # strengths must not let a generic family schedule through.
        try:inactive=_number(value)==0
        except ValueError:inactive=False
        # A primary default does not describe potentially different authored
        # companion strengths. An explicit control edit writes every binding.
        if slot not in base and (preset.get('bindings_extra') or {}).get(slot):inactive=False
        result[slot]={'entry':entry,'value':value,'inactive':inactive}
    return result


def _control_pairs(preset,control):
    primary=[preset[control]] if _binding(preset.get(control)) else []
    extras=(preset.get('bindings_extra') or {}).get(control,[])
    return {tuple(pair) for pair in primary+list(extras) if _binding(pair)}


def _bound_controls(preset):
    extras=preset.get('bindings_extra') or {}
    keys=set(preset)|set(extras if isinstance(extras,dict) else {})
    return {key for key in keys if isinstance(key,str) and _bound(preset,key)}


def _held_controls(preset,held):
    blocked=set(held)
    if any(not item['inactive'] for item in held.values()):blocked.update(SCHEDULE_CONTROLS)
    pairs=set().union(*[_control_pairs(preset,key) for key in blocked]) if blocked else set()
    # Any catalog control can alias a held physical input; compatibility
    # policy cannot be limited to the planner's display-key allowlist.
    return blocked | {key for key in _bound_controls(preset) if _control_pairs(preset,key) & pairs}


def _family_axis_records(preset,kb):
    """Bound family axes plus explicit reasons documented choices are unavailable."""
    result=[]
    for axis in family_entry(preset,kb).get('axes') or []:
        if not isinstance(axis,dict):continue
        control=axis.get('control')
        if not isinstance(control,str) or not _bound(preset,control):continue
        documented=[]
        for value in axis.get('values') or []:
            if not isinstance(value,(dict,list)) and value not in documented:documented.append(value)
        if not documented:continue
        record={'id':axis.get('id') or control,'control':control,
                'rationale':axis.get('rationale') or '','sources':list(axis.get('sources') or [])}
        if control in CHOICE_CONTROLS:
            offered=[]
            for value in ((preset.get('choices') or {}).get(control) or []):
                if not isinstance(value,(dict,list)) and value not in offered:offered.append(value)
            values=[value for value in documented if value in offered]
            if not values:
                result.append(('withheld',{'id':record['id'],'control':control,
                    'code':'unsupported_choice_values','accelerator_slots':[],'accelerator_files':[],
                    'documented_values':documented,'offered_values':offered,
                    'message':"None of the documented values are offered by this recipe's current choices."}))
                continue
        else:values=documented
        result.append(('available',dict(record,values=values)))
    return result


def _family_axes(preset,kb):
    """Bound, currently offered family axes before the accelerator policy."""
    return [axis for disposition,axis in _family_axis_records(preset,kb) if disposition=='available']


def inspect_axes(preset,kb,base_controls=None):
    """Explain existing holds and unsupported choices without changing inputs."""
    held=accelerator_slots(preset,kb,base_controls)
    blocked=_held_controls(preset,held)
    causes={slot:_held_controls(preset,{slot:item}) for slot,item in held.items()}
    available=[];withheld=[]
    for disposition,axis in _family_axis_records(preset,kb):
        if disposition=='withheld':withheld.append(axis);continue
        control=axis['control']
        if control not in blocked:
            available.append(axis);continue
        slots=[slot for slot,controls in causes.items() if control in controls]
        if control in held:
            code='accelerator_strength'
            message='Acceleration strength is not a style sweep; use a reviewed exact-configuration comparison to change it.'
        elif control in SCHEDULE_CONTROLS and any(not item['inactive'] for item in held.values()):
            code='accelerator_schedule'
            message='Accelerator inactivity is not established for every bound input; inspect exact-configuration guidance rather than a generic family schedule.'
        else:
            code='shared_accelerator_input'
            message='This control shares an input with held acceleration settings; use a reviewed exact-configuration comparison.'
        withheld.append({'id':axis['id'],'control':control,'code':code,'accelerator_slots':slots,
                         'accelerator_files':[held[slot]['entry']['file'] for slot in slots], 'message':message})
    return copy.deepcopy({'axes_available':available,'axes_withheld':withheld,
                          'notice':'Known settings-library roles only, not installed-byte or compatibility attestation. '
                                   'Unknown files and embedded acceleration are not covered. Inspection does not validate existing variants.'})


def axes_for(preset,kb,base_controls=None):
    """Keep the existing list projection and the inspection policy identical."""
    return inspect_axes(preset,kb,base_controls)['axes_available']


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
    available={axis['id']:axis for axis in axes_for(preset,kb,base_controls)}
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
    re-weighting the stack. Known accelerator slots are held, never remixed.
    """
    limit=_cap(limit)
    rules=family_entry(preset,kb).get('lora_rules') or {}
    steps=[_number(value) for value in (ladder or rules.get('ladder') or DEFAULT_LADDER)]
    if len(steps)<2:raise ValueError('A remix ladder needs at least two strengths')
    base=dict(base_controls or {});defaults=preset.get('defaults') or {}
    active=[slot for slot in slots if _bound(preset,slot) and _number(base.get(slot,defaults.get(slot,0)),0)>0]
    held=accelerator_slots(preset,kb,base)
    active_held={slot:item for slot,item in held.items() if not item['inactive']}
    if not active:raise ValueError('Turn on at least one LoRA slot before remixing its weights')
    blocked=_held_controls(preset,held)
    active=[slot for slot in active if slot not in blocked]
    if not active:raise ValueError('Turn on a non-accelerator LoRA slot to remix; acceleration settings stay unchanged')
    for slot,item in active_held.items():
        try:known=math.isfinite(_number(item['value']))
        except (ValueError,OverflowError):known=False
        if not known:raise ValueError('Set a finite accelerator strength explicitly before remixing; authored strength is unknown')
        if slot not in base and len(_control_pairs(preset,slot))>1:
            raise ValueError('Set the accelerator strength explicitly before remixing; companion defaults may differ')
        # Freeze omitted authored values explicitly as well as caller overrides.
        if item['value'] is not None:base.setdefault(slot,item['value'])
        base.setdefault(slot+'_name',item['entry']['file'])
    held_note=('; selected accelerator strengths and sampling settings remain unchanged' if active_held else '')
    counted=active+list(active_held)
    entries={slot:_slot_entry(slot,base,defaults,kb) for slot in active}
    warn=rules.get('warn_total_strength');notes=[n for n in (rules.get('notes') or []) if isinstance(n,str)]
    variants=[]
    for slot in active:
        controls=dict(base)
        for other in active:controls[other]=steps[0] if other==slot else steps[-1]
        entry=entries[slot]
        rationale=' · '.join([p for p in [f"{entry['label']} leads at {steps[0]}; the rest support at {steps[-1]}",
                                          entry.get('role') or '','; '.join(entry.get('notes') or [])] if p])
        variants.append({'label':f"{entry['label']} lead","controls":controls,'rationale':_warned(rationale+held_note,controls,counted,warn),
                         'sources':_merge_sources([entry.get('source'),entry.get('mirror')])})
    if len(active)>1 and len(variants)<limit:
        controls=dict(base)
        for other in active:controls[other]=steps[1]
        rationale=f"Every remixed adapter at the ladder's middle step {steps[1]}"+(' · '+'; '.join(notes) if notes else '')
        variants.append({'label':f"All {'non-accelerator' if active_held else 'active'} LoRAs at {steps[1]}",'controls':controls,'rationale':_warned(rationale+held_note,controls,counted,warn),
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
