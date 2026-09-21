"""One-shot exact-head patch helper for #601; removes itself after validation."""
from __future__ import annotations

from pathlib import Path
import re


def replace(path: str, old: str, new: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    print(f"{label}: {count} exact match(es)")
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def replace_re(path: str, pattern: str, replacement: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.S)
    print(f"{label}: {count} regex match(es)")
    if count != 1:
        raise SystemExit(f"{label}: expected one regex match, found {count}")
    target.write_text(updated, encoding="utf-8")


replace_re(
    "app/settings_planner.py",
    r"def _number\(value,fallback=None\):.*?\n\n\ndef _cap\(limit\):",
    '''def _number(value,fallback=None):
    if isinstance(value,bool):value=None
    try:
        result=Decimal(str(value));converted=float(result)
    except (InvalidOperation,ValueError,TypeError,OverflowError):result=converted=None
    if result is None or not result.is_finite() or not math.isfinite(converted):
        if fallback is None:raise ValueError('Expected a finite number, got '+repr(value)[:60])
        converted=float(fallback)
        if not math.isfinite(converted):raise ValueError('Expected a finite fallback number')
    return converted


def _cap(limit):''',
    "finite number conversion",
)

replace_re(
    "app/settings_planner.py",
    r"def _bound\(preset,control\):.*?\n\n\ndef family_entry\(preset,kb\):",
    '''def _binding(value):
    return (isinstance(value,(list,tuple)) and len(value)==2
            and isinstance(value[0],(str,int)) and isinstance(value[1],str))


def _bound(preset,control):
    """A control is usable when the catalog binds it, primary or companion."""
    extras=(preset.get('bindings_extra') or {}).get(control,[])
    return _binding(preset.get(control)) or any(_binding(pair) for pair in extras)


def family_entry(preset,kb):''',
    "typed bindings",
)

replace_re(
    "app/settings_planner.py",
    r"def _control_pairs\(preset,control\):.*?\n\n\ndef _family_axes\(preset,kb\):",
    '''def _control_pairs(preset,control):
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


def _family_axes(preset,kb):''',
    "physical alias discovery",
)

replace_re(
    "app/settings_planner.py",
    r"def _family_axes\(preset,kb\):.*?\n\n\ndef axes_for\(preset,kb,base_controls=None\):",
    '''def _family_axis_records(preset,kb):
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


def axes_for(preset,kb,base_controls=None):''',
    "unavailable axis records",
)

replace(
    "app/settings_planner.py",
    '''    held=accelerator_slots(preset,kb,base)
    if not active:raise ValueError('Turn on at least one LoRA slot before remixing its weights')
    blocked=_held_controls(preset,held)
    active=[slot for slot in active if slot not in blocked]
    if not active:raise ValueError('Turn on a non-accelerator LoRA slot to remix; acceleration settings stay unchanged')
    for slot,item in held.items():
''',
    '''    held=accelerator_slots(preset,kb,base)
    active_held={slot:item for slot,item in held.items() if not item['inactive']}
    if not active:raise ValueError('Turn on at least one LoRA slot before remixing its weights')
    blocked=_held_controls(preset,held)
    active=[slot for slot in active if slot not in blocked]
    if not active:raise ValueError('Turn on a non-accelerator LoRA slot to remix; acceleration settings stay unchanged')
    for slot,item in active_held.items():
''',
    "active accelerator preservation",
)
replace(
    "app/settings_planner.py",
    "    held_note=('; selected accelerator strengths and sampling settings remain unchanged' if held else '')\n    counted=active+[slot for slot,item in held.items() if not item['inactive']]\n",
    "    held_note=('; selected accelerator strengths and sampling settings remain unchanged' if active_held else '')\n    counted=active+list(active_held)\n",
    "active accelerator rationale",
)
replace(
    "app/settings_planner.py",
    "        variants.append({'label':f\"All {'non-accelerator' if held else 'active'} LoRAs at {steps[1]}\",'controls':controls,'rationale':_warned(rationale+held_note,controls,counted,warn),\n",
    "        variants.append({'label':f\"All {'non-accelerator' if active_held else 'active'} LoRAs at {steps[1]}\",'controls':controls,'rationale':_warned(rationale+held_note,controls,counted,warn),\n",
    "active accelerator blend label",
)

replace(
    "app/production.py",
    "        elif mode=='grid':\n            if not available:raise ValueError('The settings library documents no axis this recipe can change; selected accelerator settings need a reviewed exact-configuration comparison')\n",
    "        elif mode=='grid':\n            if not available:\n                message='The settings library documents no axis this recipe can change'\n                held=settings_planner.accelerator_slots(preset,kb,controls)\n                if any(not item['inactive'] for item in held.values()):\n                    message+='; selected accelerator settings need a reviewed exact-configuration comparison'\n                raise ValueError(message)\n",
    "truthful no-axis message",
)

replace(
    "app/static/production.js",
    "    $('#clearPlanned').onclick=()=>{++plannerRequestId;plannedVariants=null;renderPlanner();};\n    $('#plannerAxes').onchange=()=>{plannerAxisIds=[...$('#plannerAxes').querySelectorAll('input:checked')].map(i=>i.value);requestPlan('grid');};\n    $('#plannedVariants').onclick=e=>{const drop=e.target.closest('[data-drop-variant]');if(!drop)return;++plannerRequestId;plannedVariants.splice(Number(drop.dataset.dropVariant),1);if(!plannedVariants.length)plannedVariants=null;renderPlanner();};\n",
    "    $('#clearPlanned').onclick=()=>{++plannerRequestId;plannedVariants=null;renderPlanner();$('#experimentStatus').textContent='Planned variants cleared locally. Nothing was reserved or submitted.';};\n    $('#plannerAxes').onchange=()=>{plannerAxisIds=[...$('#plannerAxes').querySelectorAll('input:checked')].map(i=>i.value);requestPlan('grid');};\n    $('#plannedVariants').onclick=e=>{const drop=e.target.closest('[data-drop-variant]');if(!drop)return;++plannerRequestId;plannedVariants.splice(Number(drop.dataset.dropVariant),1);if(!plannedVariants.length)plannedVariants=null;renderPlanner();$('#experimentStatus').textContent='Variant removed locally. Nothing was reserved or submitted.';};\n",
    "local planner completion status",
)
replace(
    "app/static/production.js",
    "  $('#plannerLimits').innerHTML=(plannerWithheld.length?'<p><b>Settings held for acceleration</b></p><ul>'+plannerWithheld.map(a=>'<li><b>'+esc(a.id)+'</b>: '+esc(a.message)+' ('+esc((a.accelerator_slots||[]).join(', '))+')</li>').join('')+'</ul>':'')+(plannerNotice?'<p>'+esc(plannerNotice)+'</p>':'');\n",
    "  $('#plannerLimits').innerHTML=(plannerWithheld.length?'<p><b>Settings unavailable for this recipe</b></p><ul>'+plannerWithheld.map(a=>{const slots=a.accelerator_slots||[];return '<li><b>'+esc(a.id)+'</b>: '+esc(a.message)+(slots.length?' ('+esc(slots.join(', '))+')':'')+'</li>';}).join('')+'</ul>':'')+(plannerNotice?'<p>'+esc(plannerNotice)+'</p>':'');\n",
    "generic unavailable-axis UI",
)
replace(
    "app/static/production.js",
    "    $('#experimentStatus').textContent=mode==='inspect'?plannerAxes.length+' settings available; '+plannerWithheld.length+' held. Existing variants are unchanged. Nothing was reserved or submitted.':plannedVariants.length+' documented variants planned. Nothing is reserved until you prepare the plan.';\n",
    "    $('#experimentStatus').textContent=mode==='inspect'?plannerAxes.length+' settings available; '+plannerWithheld.length+' unavailable. Existing variants are unchanged. Nothing was reserved or submitted.':plannedVariants.length+' documented variants planned. Nothing is reserved until you prepare the plan.';\n",
    "inspection status language",
)
replace(
    "app/static/production.js",
    "    plannerAxes=[];plannerWithheld=[];plannerNotice='';renderPlanner(mode!=='inspect');$('#experimentStatus').textContent=err.message;\n",
    "    plannerAxes=[];plannerAxisIds=[];plannerWithheld=[];plannerNotice='';renderPlanner(mode!=='inspect');$('#experimentStatus').textContent=err.message;\n",
    "failed inspection identities",
)

replace(
    "tests/test_settings_inspection.py",
    "        self.assertEqual([r['id'] for r in report['axes_withheld']], ['steps', 'sampler', 'accelerator'])\n        self.assertEqual([r['code'] for r in report['axes_withheld']],\n                         ['accelerator_schedule', 'accelerator_schedule', 'accelerator_strength'])\n        self.assertTrue(all(r['accelerator_slots'] == ['lora'] for r in report['axes_withheld']))\n",
    "        self.assertEqual([r['id'] for r in report['axes_withheld']], ['steps', 'sampler', 'empty', 'accelerator'])\n        self.assertEqual([r['code'] for r in report['axes_withheld']],\n                         ['accelerator_schedule', 'accelerator_schedule', 'unsupported_choice_values', 'accelerator_strength'])\n        held=[r for r in report['axes_withheld'] if r['code']!='unsupported_choice_values']\n        self.assertTrue(all(r['accelerator_slots'] == ['lora'] for r in held))\n        unavailable=next(r for r in report['axes_withheld'] if r['id']=='empty')\n        self.assertEqual((unavailable['documented_values'],unavailable['offered_values']),(['karras'],['simple','beta']))\n",
    "inspection unavailable choice expectations",
)
replace(
    "tests/test_settings_inspection.py",
    "        self.assertEqual([r['id'] for r in report['axes_withheld']], ['accelerator'])\n",
    "        self.assertEqual([r['id'] for r in report['axes_withheld']], ['empty', 'accelerator'])\n",
    "inactive accelerator withheld list",
)
replace(
    "tests/test_settings_inspection.py",
    "        self.assertEqual(report['axes_withheld'], [])\n        self.assertIn('unknown files', report['notice'].lower())\n",
    "        self.assertEqual([r['id'] for r in report['axes_withheld']], ['empty'])\n        self.assertIn('unknown files', report['notice'].lower())\n",
    "unknown file withheld list",
)
replace(
    "tests/test_settings_inspection.py",
    "        self.assertNotIn('empty', ids)\n",
    "        self.assertIn('empty', ids)\n        self.assertEqual(next(r for r in self.inspect()['axes_withheld'] if r['id']=='empty')['code'],\n                         'unsupported_choice_values')\n",
    "deterministic unavailable choice",
)

replace(
    "docs/EXPERIMENTS.md",
    """Two buttons under **Advanced: plan several settings from the library** plan
several documented settings at once, through `POST /api/experiments/plan`. **Plan from settings library** reads the family
entry for this recipe in `presets/settings-kb.json` and offers a grid of the
axes the recipe can actually change — steps, sampler, scheduler, LoRA strengths
— with the first axis varying slowest and at most eight candidates. **Remix
LoRA weights** re-weights only the adapter slots that are already on: one
variant per slot at the top of the family ladder while the others support at
its bottom, plus one blend at the middle step. Slots that are off stay off.
""",
    """Three actions under **Advanced: plan several settings from the library** use
`POST /api/experiments/plan`. **Inspect available settings** reads the current
recipe without replacing a local plan. **Plan from settings library** reads the
family entry in `presets/settings-kb.json` and offers a grid of the axes the
recipe can actually change — steps, sampler, scheduler, LoRA strengths — with
the first axis varying slowest and at most eight candidates. **Remix LoRA
weights** re-weights only the ordinary adapter slots that are already on: one
variant per slot at the top of the family ladder while the others support at
its bottom, plus one blend at the middle step. Slots that are off stay off and
are not injected into candidate controls or described as selected.
""",
    "three planner actions",
)
replace(
    "docs/EXPERIMENTS.md",
    "The current recipe's bound axes are split into available choices and accelerator holds, with\nreasons for a held strength, a held family schedule, or an alias sharing a held input.\n",
    "The current recipe's bound axes are split into available choices and explicit unavailable rows,\nwith reasons for a held strength, a held family schedule, an alias sharing a held input,\nor documented combo values that the recipe's current socket choices do not offer.\n",
    "inspection categories",
)
replace(
    "docs/EXPERIMENTS.md",
    "A hold names its `control`, stable `code`, contributing `accelerator_slots`/`accelerator_files`\nand a plain-text `message`. The inspector and planner use one policy, not two compatibility\n",
    "An unavailable row names its `control`, stable `code`, contributing\n`accelerator_slots`/`accelerator_files` and a plain-text `message`. A filtered combo also\nretains its documented and currently offered values, rather than disappearing. The inspector\nand planner use one policy, not two compatibility\n",
    "unavailable row evidence",
)
replace(
    "docs/EXPERIMENTS.md",
    "A replaced or closed dialog, cleared plan or removed candidate cannot be overwritten by an older\nreply. A failed inspection keeps existing variants while removing stale advice. No inspection is\n",
    "A replaced or closed dialog, cleared plan or removed candidate cannot be overwritten by an older\nreply. Local clear/remove actions also finish the in-flight status instead of leaving a stale\n“Reading…” message. A failed inspection keeps existing variants while removing stale advice and\nselected axis identities. No inspection is\n",
    "browser latest-action evidence",
)

replace(
    "docs/strategy/anime-qualification/ACCELERATOR-PLANS.md",
    "Unknown or negative strength does not prove inactivity. Primary and companion aliases\nthat write those same inputs are withheld too. A primary default alone cannot prove a companion\n",
    "Unknown or negative strength does not prove inactivity. Every catalog control whose primary or\ncompanion binding writes those same physical inputs is withheld, including controls outside the\nplanner's display-key allowlist. A primary default alone cannot prove a companion\n",
    "all physical aliases",
)
replace(
    "docs/strategy/anime-qualification/ACCELERATOR-PLANS.md",
    "Remix varies only the remaining active non-accelerator slots. Selected accelerator filenames and\nstrengths are preserved, including single-binding defaults omitted from the caller's snapshot. A missing\n",
    "Remix varies only the remaining active non-accelerator slots. Active selected accelerator filenames\nand strengths are preserved, including single-binding defaults omitted from the caller's snapshot.\nAn explicitly inactive accelerator stays absent unless the caller supplied that zero; it is not\ninjected into candidate controls, labelled as selected, or used to rename an ordinary blend. A missing\n",
    "inactive accelerator semantics",
)
replace(
    "docs/strategy/anime-qualification/ACCELERATOR-PLANS.md",
    "This is a conservative hold based on declared KB roles. It is not a complete compatibility engine,\n",
    "Choice axes whose documented values are absent from the recipe's current combo choices remain\nvisible as `unsupported_choice_values`, including both documented and offered values. They are not\nsilently dropped or mislabelled as accelerator conflicts.\n\nThis is a conservative hold based on declared KB roles. It is not a complete compatibility engine,\n",
    "choice mismatch limit",
)

Path(".github/workflows/accelerator-planner-integrity.yml").unlink()
Path(__file__).unlink()
print("Patch staged; temporary helper files removed.")
