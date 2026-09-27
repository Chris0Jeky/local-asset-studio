"""One prepared plan that runs the same Combine pair on several engines with the same seeds (#1163).

The client names the pair once (the recipe it would Generate on the Combine screen), the engines, the seeds and the
three answers. Every stage's reference layout, wording and continuation claim is derived here from the catalog, the
same way the Combine screen's engine switch derives them (StudioContinuation.combineReferences / combineFillValues):
the image order differs per recipe, so the client's layout for one engine is never copied to another.
Nothing here submits, reserves or writes; Production.create pins the result as one comparison plan.
"""
from __future__ import annotations
import hashlib
import math
import re

import continuation

MAX_ENGINES=6
MAX_SEEDS=4
MAX_STAGES=16
# The keys an attached picture keeps across recipes (continuation-core.js combineReferences).
KEPT=('file','sha256','bytes','width','height','parent_asset','missing')
DRAWN_GUIDE=re.compile(r'[a-f0-9]{32}_drawn-pose\.png');GUIDE_ID=re.compile(r'[a-f0-9]{64}')
POSE_RENDERERS=('studio.coco18-lines/v1','studio.coco18-openpose-xinsir/v1')
ANSWERS=('who','pose','clothes','outfit')


def kind(preset):
    """'skeleton' or 'picture' for a Combine recipe whose kept picture sits on last_reference; None otherwise."""
    cap=(preset or {}).get('continuation_capability') or {}
    if cap.get('operation')!='combine' or cap.get('source_input')!='last_reference' or not preset.get('reference_board') or not preset.get('last_reference'):return None
    return 'skeleton' if re.search('skeleton',preset.get('reference_board_label') or '',re.I) else 'picture'


def placeholders(preset):
    value=preset.get('continuation_placeholder')
    return [text for text in (value if isinstance(value,list) else [value]) if isinstance(text,str) and text]


def meaning(placeholder):
    label=str(placeholder).split(', e.g. ')[0].lower()
    # 'outfit' is the scene picture's clothes (the replace recipe): never a stand-in for the character's clothes.
    return 'outfit' if 'outfit' in label else 'who' if 'who' in label else 'clothes' if 'clothes' in label or 'colours' in label else 'pose' if 'pose' in label else None


def fill_values(preset, answers):
    holders=placeholders(preset);has_clothes=any(meaning(p) in ('clothes','outfit') for p in holders);result={}
    for placeholder in holders:
        key=meaning(placeholder);value=str(answers.get(key) or '') if key else ''
        clothes=answers.get('clothes') or ''
        if key=='who' and not has_clothes and clothes and clothes not in value:value+=(', wearing ' if value else '')+clothes
        result[placeholder]=value
    return result


def assemble(template, values):
    text=template if isinstance(template,str) else ''
    for placeholder,value in values.items():
        words=str(value or '').strip()
        if words and placeholder and placeholder not in words:text=text.replace(placeholder,words)
    return text


def prompt_for(preset, source):
    """The recipe's authored continuation wording; `{source}` stands for the source's own submitted description."""
    template=preset.get('continuation_prompt')
    if not isinstance(template,str) or not template.strip():return ''
    positive=source.get('positive')
    described=source.get('prompt_origin')=='submitted-output' and source.get('prompt_role')=='description' and isinstance(positive,str) and positive.strip()
    lead=' Image 1 shows: ' if ((preset.get('continuation_capability') or {}).get('board_min') or 0)>0 else ' The picture shows: '
    text=template.replace('{source}',lead+re.sub(r'[\s.]+$','',positive.strip())+'.' if described else '',1)
    return template.replace('{source}','',1) if len(text)>8000 else text


def references(preset, pictures):
    """The attached pictures in this recipe's own slots and roles, in the order they were attached."""
    slots=preset.get('reference_slots') or []
    if len(pictures)>len(slots):raise ValueError(f"{preset.get('name') or preset['id']} takes fewer pictures. Remove the extra board picture or leave that recipe out.")
    result=[]
    for index,slot in enumerate(slots):
        source=pictures[index] if index<len(pictures) else {}
        kept={key:source[key] for key in KEPT if key in source}
        if isinstance(source.get('file'),str) and DRAWN_GUIDE.fullmatch(source['file']) and isinstance(source.get('artifact_id'),str) and GUIDE_ID.fullmatch(source['artifact_id']):
            kept['artifact_id']=source['artifact_id']
            if source.get('renderer') in POSE_RENDERERS:kept['renderer']=source['renderer']
        result.append({'role':slot.get('role'),'contribution':'','avoid':'','file':None,**kept})
    return result


def _text(value, name, limit):
    if not isinstance(value,str) or len(value)>limit:raise ValueError(f'{name} must be text up to {limit} characters')
    return value


def stages(studio, intent):
    """Validate a multi-engine Combine intent and derive its stage recipes. Reads the catalog, the source and the
    local timing history; submits, reserves and writes nothing."""
    if not isinstance(intent,dict):raise ValueError('The Combine plan must be an object')
    unknown=sorted(set(intent)-{'base','engines','seeds','answers','wording'})
    if unknown:raise ValueError('Unknown Combine plan field: '+', '.join(unknown))
    base=intent.get('base')
    if not isinstance(base,dict) or not isinstance(base.get('controls'),dict):raise ValueError('Name the pair: the recipe you would Generate on the Combine screen')
    first=studio.preset(base.get('preset_id'));pair_kind=kind(first)
    if not pair_kind:raise ValueError('A Combine plan starts from a Combine recipe that keeps your picture')
    claim=base.get('continuation')
    if not isinstance(claim,dict) or claim.get('intent')!='combine' or claim.get('preset_id')!=first['id']:raise ValueError('Continue with your picture into Combine before planning several engines')
    for key in ('source_asset_id','source_sha256','reference_file'):
        if not isinstance(claim.get(key),str) or not claim[key] or len(claim[key])>255:raise ValueError('Invalid continuation context field: '+key)
    if base['controls'].get('last_reference')!=claim['reference_file']:raise ValueError('The picture you keep must be the continuation source')
    parents=base.get('parent_assets')
    if not isinstance(parents,list) or not all(isinstance(p,str) for p in parents) or claim['source_asset_id'] not in parents:raise ValueError('Continuation source is missing from lineage.')
    if len(parents)>8:raise ValueError('Use up to eight parent assets')
    for parent in parents:studio.assets.get(parent) # the job refuses an unknown parent at Start; refuse it here instead
    supplied=base.get('references')
    if not isinstance(supplied,list) or len(supplied)>len(first.get('reference_slots') or []) or not all(isinstance(r,dict) for r in supplied):raise ValueError('Attach the board pictures in their slots')
    if any(r.get('missing') for r in supplied):raise ValueError('Reattach the missing picture before planning')
    pictures=[r for r in supplied if r.get('file')]
    if not pictures:raise ValueError('Add the pose picture to the board before planning')
    engines=intent.get('engines')
    if not isinstance(engines,list) or not 1<=len(engines)<=MAX_ENGINES or not all(isinstance(e,str) for e in engines) or len(set(engines))!=len(engines):
        raise ValueError(f'Choose one to {MAX_ENGINES} different Combine recipes')
    seeds=intent.get('seeds')
    if not isinstance(seeds,list) or not 1<=len(seeds)<=MAX_SEEDS or any(type(s) is not int or not 0<=s<=2**63-1 for s in seeds) or len(set(seeds))!=len(seeds):
        raise ValueError(f'Choose one to {MAX_SEEDS} different whole-number seeds')
    if len(engines)*len(seeds)>MAX_STAGES:raise ValueError(f'{len(engines)} recipes × {len(seeds)} seeds is {len(engines)*len(seeds)} pictures; a plan runs at most {MAX_STAGES}')
    answers=intent.get('answers') or {}
    if not isinstance(answers,dict) or set(answers)-set(ANSWERS):raise ValueError('Answers are who, pose, clothes and outfit')
    answers={key:_text(value,key.capitalize(),2000).strip() for key,value in answers.items()}
    wording=intent.get('wording') or {}
    if not isinstance(wording,dict) or set(wording)-set(engines):raise ValueError('Edited wording must belong to a chosen recipe')
    for value in wording.values():_text(value,'Wording',8000)
    source=continuation.source_context(studio,claim['source_asset_id'])
    if source['sha256']!=claim['source_sha256']:raise ValueError('The continuation source changed. Reopen Continue with this asset.')
    presets=[studio.preset(e) for e in engines]
    for preset in presets:
        name=preset.get('name') or preset['id']
        if kind(preset)!=pair_kind:raise ValueError(f'{name} takes a different input ({"a pose skeleton" if kind(preset)=="skeleton" else "a pose picture" if kind(preset) else "not a Combine pair"}); leave it out of this plan')
        if preset.get('runtime_block'):raise ValueError(f"{name}: {preset['runtime_block']}")
    backends={preset.get('backend_id','primary') for preset in presets}
    if len(backends)!=1:raise ValueError('These recipes run in different backend environments. A plan runs in one environment; plan each environment separately.')
    size={key:base['controls'][key] for key in ('width','height') if base['controls'].get(key) not in (None,'')}
    requests=[];estimates={}
    for preset in presets:
        graph_path=studio.graph_for(preset)[1];template=hashlib.sha256(graph_path.read_bytes()).hexdigest()
        stage_claim={'version':1,'intent':'combine','preset_id':preset['id'],'source_asset_id':claim['source_asset_id'],
                     'source_sha256':claim['source_sha256'],'reference_file':claim['reference_file'],'template_sha256':template}
        if preset['id']==first['id']:
            # The recipe open on the screen runs exactly as Generate would run it, the owner's own settings included, and
            # like Generate it refuses a graph that changed since the page opened it (#1186).
            if claim.get('template_sha256')!=template or base.get('expected_template_sha256') not in (None,'',template):
                raise ValueError('The destination graph changed. Reopen the handoff and review the new route.')
            controls={key:value for key,value in base['controls'].items() if key not in ('seed','batch_count')}
        else:
            controls=dict({key:value for key,value in size.items() if preset.get(key)},last_reference=claim['reference_file'])
        if preset['id'] in wording:controls['positive']=wording[preset['id']]
        elif preset['id']!=first['id'] or 'positive' not in controls:controls['positive']=assemble(prompt_for(preset,source),fill_values(preset,answers))
        left=continuation.unfilled(preset,controls['positive'])
        if left:raise ValueError(f"{preset.get('name') or preset['id']}: fill in the wording, replace "+' and '.join(f'“{item}”' for item in left))
        estimate=studio.estimate({'preset_id':preset['id'],'controls':{k:v for k,v in controls.items() if k in ('width','height')},'batch_count':1,'reference_count':len(pictures)})
        estimates[preset['id']]={key:estimate.get(key) for key in ('available','estimate_seconds','range_seconds','confidence','matched_samples')}
        for seed in seeds:
            requests.append({'label':f"{preset['id']} · seed {seed}",'engine':preset['id'],'seed':seed,
                             'request':{'preset_id':preset['id'],'controls':dict(controls,seed=seed),'references':references(preset,pictures),
                                        'parent_assets':list(parents),'continuation':stage_claim,'expected_template_sha256':template,'batch_count':1}})
    known=[e for e in estimates.values() if e.get('available') and isinstance(e.get('estimate_seconds'),(int,float))]
    order=('none','low','medium','high')
    total=sum(estimates[r['engine']]['estimate_seconds'] or 0 for r in requests) if len(known)==len(estimates) else None
    upper=sum((estimates[r['engine']]['range_seconds'] or [0,0])[1] for r in requests) if total is not None else None
    summary={'per_engine':estimates,'total_seconds':round(total,1) if total is not None else None,'total_upper_seconds':upper,
             'confidence':min((e.get('confidence') or 'none' for e in estimates.values()),key=lambda c:order.index(c) if c in order else 0),
             'note':'Read-only estimate from this PC\'s completed runs at preparation time; not a promise and not rechecked at Start.'}
    pair={'kind':pair_kind,'source_asset_id':claim['source_asset_id'],'source_sha256':claim['source_sha256'],'reference_file':claim['reference_file'],
          'pictures':[{key:p.get(key) for key in ('file','sha256')} for p in pictures]}
    return {'stages':requests,'engines':list(engines),'seeds':list(seeds),'estimate':summary,'pair':pair,'backend_id':backends.pop()}


def default_seconds(estimate):
    """A time allowance for the whole plan: the estimate's upper range with a quarter to spare, never under 30 minutes."""
    upper=estimate.get('total_upper_seconds')
    return 1800 if not upper else max(1800,min(14400,math.ceil(upper*1.25)))
