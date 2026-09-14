"""Review-only setup intents over the existing shortlist and reference compiler.

A captured browser draft is a caller declaration, not a shared revision. These
reports deliberately cannot be submitted as saved recipes or execution tickets.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError

from .core import canonical, decode, digest, need
from .shortlist import query as shortlist_query, request as shortlist_request, _runtime

PREFIX='/api/workflow-studio/setup-proposal'
FORMAT='studio.setup-proposal/v1'
MAX_BYTES=131072
DRAFT_SCOPE='caller-declared browser draft; not a server revision'
HASH=re.compile(r'[0-9a-f]{64}\Z')
ID=re.compile(r'[A-Za-z0-9_.-]{1,96}\Z')


def _text(value, maximum):
    return type(value) is str and len(value)<=maximum


def _exact_json(value):
    """Copy bounded JSON; callers must use text for integers unsafe in a browser."""
    try:
        raw=canonical(value)
        need(len(raw)<=MAX_BYTES, 'Setup proposal input exceeds 128 KiB')
        result=decode(raw)
    except (TypeError, OverflowError, RecursionError) as exc:
        raise ValueError('Supply bounded JSON setup data') from exc
    def check(item):
        if type(item) in (int,float): need(abs(item)<=2**53-1, 'Use text for wide integers to preserve browser precision')
        elif type(item) is list:
            for x in item: check(x)
        elif type(item) is dict:
            for x in item.values(): check(x)
    check(result)
    return result


def query(value):
    q=_exact_json(value)
    need(type(q) is dict and set(q)=={'goal','preset_id','expected_template_sha256','sources','draft','positive','negative','guidance'},
         'Supply goal, preset_id, expected_template_sha256, ordered sources, draft, positive, negative and guidance')
    need(type(q['preset_id']) is str and ID.fullmatch(q['preset_id']), 'Invalid target preset identity')
    need(type(q['expected_template_sha256']) is str and HASH.fullmatch(q['expected_template_sha256']), 'Invalid target graph identity')
    shortlist_query({'goal':q['goal'],'sources':q['sources']})
    need(_text(q['positive'],8000) and _text(q['negative'],8000), 'positive and negative wording must be text up to 8000 characters')
    need(type(q['guidance']) is list and len(q['guidance'])==len(q['sources']), 'Provide guidance for every Picture in order')
    for row in q['guidance']:
        need(type(row) is dict and set(row)=={'contribution','avoid'} and all(_text(x,1500) for x in row.values()),
             'Reference guidance must contain contribution and avoid text up to 1500 characters')
    q['draft']=validate_draft(q['draft'])
    return q


def validate_draft(value):
    """Shared normalized Create data; no persistence or staging authority."""
    draft=_exact_json(value)
    need(type(draft) is dict and set(draft)=={'version','updatedAt','recipe','pendingInputs','templateHash'}
         and type(draft['version']) is int and draft['version']==1 and type(draft['updatedAt']) is int and draft['updatedAt']==0,
         'Supply a complete normalized browser draft with updatedAt=0')
    need(draft['templateHash'] is None or type(draft['templateHash']) is str and HASH.fullmatch(draft['templateHash']), 'Invalid draft template identity')
    need(type(draft['pendingInputs']) is list and len(draft['pendingInputs'])<=2
         and all(x in ('reference','lastReference') for x in draft['pendingInputs']) and len(set(draft['pendingInputs']))==len(draft['pendingInputs']),
         'Invalid draft pending inputs')
    recipe=draft['recipe']; required={'preset','controls','batch','references','parent_assets','parent_by_input'}
    need(type(recipe) is dict and required<=set(recipe) and set(recipe)<=required|{'continuation'}, 'Supply the complete current recipe declaration')
    need(type(recipe['preset']) is str and ID.fullmatch(recipe['preset']), 'Invalid draft preset')
    need(type(recipe['batch']) is int and 1<=recipe['batch']<=4, 'Invalid draft batch')
    need(type(recipe['controls']) is dict and len(recipe['controls'])<=64, 'Invalid draft controls')
    for key,item in recipe['controls'].items():
        need(re.fullmatch(r'[a-z][a-z0-9_]{0,63}',key) and (_text(item,20000) or type(item) in (int,float)), 'Invalid draft control')
    need(type(recipe['references']) is list and len(recipe['references'])<=8 and all(type(x) is dict for x in recipe['references']), 'Invalid retained reference declarations')
    need(type(recipe['parent_assets']) is list and len(recipe['parent_assets'])<=32 and all(_text(x,160) for x in recipe['parent_assets']), 'Invalid draft lineage')
    need(type(recipe['parent_by_input']) is dict and set(recipe['parent_by_input'])<={'reference','lastReference'}
         and all(type(x) is str and x in recipe['parent_assets'] for x in recipe['parent_by_input'].values()), 'Invalid draft input lineage')
    need('continuation' not in recipe or recipe['continuation'] is None or type(recipe['continuation']) is dict, 'Invalid draft continuation')
    return draft


def _capture(studio, items):
    from app.references import image_record
    from PIL import Image
    result=[]
    for index,item in enumerate(items):
        label=f'Picture {index+1}: '
        try:asset=studio.assets.get(item['asset_id'])
        except (OSError,ValueError,KeyError) as exc:raise ValueError(label+'Workspace image unavailable; reselect it.') from exc
        need(asset and not asset.get('trashed_at') and asset.get('media_type')=='image', label+'Restore an available image from the Workspace before previewing.')
        try:
            path=studio.assets.file(item['asset_id'])
            record=image_record(path.parent,path.name,strict_pixels=True)
        except (OSError,ValueError,KeyError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
            raise ValueError(label+'Image could not be read within the byte/pixel safety limits; choose a valid smaller image.') from exc
        need(record['sha256']==item['sha256']==asset['sha256'], label+'Source bytes changed; select the intended image again.')
        result.append({**item,'slot':index+1,'title':str(asset.get('title') or item['asset_id'])[:160],
                       **{k:record[k] for k in ('bytes','width','height')},'staged':False})
    return result


def _controls(preset, graph, positive, negative):
    from app.server import CONTROL_KEYS
    controls={};bindings={}
    for key in CONTROL_KEYS:
        if key in ('reference','last_reference'): continue
        targets=([preset[key]] if preset.get(key) else [])+list((preset.get('bindings_extra') or {}).get(key,[]))
        if not targets:
            need(key not in ('positive','negative') or not (positive if key=='positive' else negative), f'This route has no {key} prompt binding; wording would be dropped')
            continue
        values=[]
        for target in targets:
            need(type(target) is list and len(target)==2, 'Unsupported control binding: '+key)
            node,field=map(str,target)
            need(node in graph and type(graph[node].get('inputs')) is dict and field in graph[node]['inputs'], 'Missing control binding: '+key)
            value=graph[node]['inputs'][field]
            need(type(value) in (str,int,float) and (type(value) is not float or math.isfinite(value)), 'Unsupported default control: '+key)
            values.append(value)
        if key in ('positive','negative'): value=positive if key=='positive' else negative
        else:
            need(all(canonical(x)==canonical(values[0]) for x in values), 'Default fan-out differs for '+key+'; inspect it in the existing editor')
            value=str(values[0])
        need(len(value)<=8000, 'Default control exceeds review limit: '+key)
        controls[key]=value;bindings[key]=copy.deepcopy(targets)
    return controls,bindings


def _diff(before, intent):
    recipe=before['recipe']
    sections=[('Recipe',{'preset':recipe['preset'],'template':before['templateHash']},{'preset':intent['preset_id'],'template':intent['template_sha256']}),
              ('Settings and wording',recipe['controls'],intent['controls']),('Batch',recipe['batch'],intent['batch']),
              ('References',recipe['references'],intent['sources']),
              ('Lineage',{'parents':recipe['parent_assets'],'by_input':recipe['parent_by_input']},intent['lineage']),
              ('Continuation context',recipe.get('continuation'),None),('Pending local inputs',before['pendingInputs'],[])]
    return [{'section':title,'before':old,'proposed':new,'changed':canonical(old)!=canonical(new)} for title,old,new in sections]


def request(value, studio):
    q=query(value)
    runtime=_runtime(studio);catalog_bytes=studio.catalog_path.read_bytes()
    need(len(catalog_bytes)<=8*1024*1024, 'Preset catalog exceeds review limit')
    entries=studio.catalog()['presets'];matches=[p for p in entries if p.get('id')==q['preset_id']]
    need(len(matches)==1, 'Target recipe is unavailable or ambiguous')
    preset=copy.deepcopy(matches[0]);graph,path=studio.graph_for(preset);graph=copy.deepcopy(graph)
    raw=path.read_bytes();need(len(raw)<=1048576 and hashlib.sha256(raw).hexdigest()==q['expected_template_sha256'], 'Target graph identity changed; check recipes again')
    need(canonical(graph)==canonical(decode(raw)), 'Parsed graph differs from the verified target bytes; check again')
    need(preset.get('continuation_capability',{}).get('template_sha256')==q['expected_template_sha256'], 'Target graph identity differs from catalog')
    captured=_capture(studio,q['sources'])
    report=shortlist_request({'goal':q['goal'],'sources':q['sources'],'limit':1},studio,preset_id=q['preset_id'])
    need(len(report['candidates'])==1 and report['total']==1, 'The target recipe does not match this goal')
    candidate=report['candidates'][0];assignments=candidate.get('source_assignments',[])
    from app.references import reference_transform, guidance_text, board_spec, board_transform, ROLES
    named=preset.get('reference_slots') or [];board=board_spec(preset) if preset.get('reference_board') else None
    if board:
        need(board['minimum']<=len(captured)<=board['slot_count'],
             f'This style board needs {board["minimum"]}-{board["slot_count"]} ordered Picture sources')
        need(len(assignments)==len(captured), 'Every supplied board Picture needs a distinct target slot')
    else:
        need(len(assignments)==len(captured) and candidate['reference_count']==len(captured), 'Every Picture needs a distinct target slot')
    need(not preset.get('requires_rgba_mask') and not preset.get('continuation_capability',{}).get('requires_mask'), 'Mask routes need a reviewed mask; setup proposal does not validate masks')
    # Motion modes and native transforms require a separate complete proposed-state contract.
    need(not preset.get('i2v_modes'), 'Motion-mode proposals are not supported yet; use the existing animation controls')
    controls,bindings=_controls(preset,graph,q['positive'],q['negative'])
    source_intents=[]
    for index,(source,assignment,guidance) in enumerate(zip(captured,assignments,q['guidance'])):
        need(assignment.get('binding') is not None, f'Picture {index+1} has no distinct target binding')
        if board:
            need(not guidance['contribution'] and not guidance['avoid'],
                 f'Picture {index+1}: style-board images are visual-only; per-Picture prompt guidance is not compiled')
            need(source['role']==board['roles'][index], f'Picture {index+1}: choose the {board["roles"][index]} board role before previewing')
            role_mode='style-board';transform=board_transform(preset);binding=copy.deepcopy(named[index]['binding'])
        elif named:
            need(source['role'] in ROLES and assignment.get('role_mode')=='prompt-guidance', f'Picture {index+1}: choose a named reference role before previewing wording')
            role_mode=assignment['role_mode'];binding=assignment['binding']
            transform=reference_transform(preset,graph,binding[0],source)
        else:
            need(assignment.get('role_mode')=='whole-image', f'Picture {index+1} has no supported whole-image binding')
            need(not guidance['contribution'] and not guidance['avoid'], 'This whole-image route does not compile per-Picture guidance; review the main wording instead')
            role_mode=assignment['role_mode'];binding=assignment['binding']
            transform={'policy':'native graph preprocessing; not projected by this adapter'}
        source_intents.append({**source,**{k:v.strip() for k,v in guidance.items()},'binding':binding,
                               'role_mode':role_mode,'transform':transform})
    compiled=controls.get('positive') if board or not named else guidance_text(source_intents,q['positive'])
    by_input={} if board else {'reference':captured[0]['asset_id']}
    intent={'preset_id':q['preset_id'],'template_sha256':q['expected_template_sha256'],'backend_id':candidate['backend_id'],
            'controls':controls,'control_bindings':bindings,'batch':1,'sources':source_intents,'compiled_positive':compiled,
            'compiled_positive_binding':preset.get('positive'),
            'lineage':{'parents':list(dict.fromkeys(x['asset_id'] for x in captured)),'by_input':by_input,
                       'source_slots':[{'slot':x['slot'],'asset_id':x['asset_id'],'role':x['role']} for x in captured]}}
    if board:intent['reference_board']={k:board[k] for k in ('minimum','slot_count','roles')}
    if not named and len(captured)==2 and assignments[1]['binding']==preset.get('last_reference'):
        intent['lineage']['by_input']['lastReference']=captured[1]['asset_id']
    # These are observations; no leases, mutations or preflight/worker calls occur.
    need(captured==_capture(studio,q['sources']), 'Source context changed during preview; check again')
    need(runtime==_runtime(studio) and catalog_bytes==studio.catalog_path.read_bytes() and raw==path.read_bytes(), 'Studio context changed during preview; check again')
    result={'format':FORMAT,'request':q,'before':q['draft'],'intent':intent,'diff':_diff(q['draft'],intent),
            'precondition':{'draft_sha256':digest(q['draft']),'scope':DRAFT_SCOPE},
            'observation':{'snapshot_sha256':report['snapshot_sha256'],'backend_id':report['backend_id'],
                           'schema_sha256':report['schema_sha256'],'candidate':candidate},
            'side_effects':['Preview performs no attachment, source upload, setting change, save or generation.',
                            'A future apply would replace the listed setup, reset batch to one, clear continuation context and require explicit source staging.',
                            'Pending local inputs and old reference/lineage declarations must be retained for a separately implemented undo.'],
            'limits':['Draft values were supplied by the caller, not read from an authoritative shared draft.',
                      'Reference geometry uses the existing compiler projection; native interpolation, masks, licensing and artistic quality are not certified.',
                      'Prerequisite observations concern defaults; preparation must recheck exact state. This report is not a recipe or run ticket.'],
            'can_apply':False,'execution_authorized':False,'generation_submitted':False}
    need(len(canonical(result))<=1048576, 'Setup proposal response exceeds review limit')
    exact=canonical(result).decode('utf-8')
    return {**result,'proposal_sha256':hashlib.sha256(exact.encode('utf-8')).hexdigest(),'proposal_json':exact}


def validate_reply(result, value):
    q=query(value);message='Setup proposal response does not match the captured request'
    need(type(result) is dict and result.get('format')==FORMAT and canonical(result.get('request'))==canonical(q) and canonical(result.get('before'))==canonical(q['draft']),message)
    need(all(result.get(k) is False for k in ('can_apply','execution_authorized','generation_submitted')),message)
    need(result.get('precondition')=={'draft_sha256':digest(q['draft']),'scope':DRAFT_SCOPE},message)
    need(type(result.get('proposal_json')) is str and len(result['proposal_json'].encode('utf-8'))<=1048576,message)
    need(result.get('proposal_sha256')==hashlib.sha256(result['proposal_json'].encode('utf-8')).hexdigest()
         and decode(result['proposal_json'])=={k:v for k,v in result.items() if k not in ('proposal_sha256','proposal_json')},message)
    intent=result.get('intent');need(type(intent) is dict and intent.get('preset_id')==q['preset_id'] and intent.get('template_sha256')==q['expected_template_sha256'],message)
    need(type(intent.get('controls')) is dict and type(intent.get('batch')) is int and intent['batch']==1
         and not {'reference','last_reference'}&set(intent['controls']),message)
    for field in ('positive','negative'):
        need(intent['controls'].get(field,'')==q[field],message)
    need(type(intent.get('sources')) is list and len(intent['sources'])==len(q['sources']),message)
    for index,(item,expected) in enumerate(zip(intent['sources'],q['sources'])):
        need(type(item) is dict and all(item.get(k)==v for k,v in expected.items()) and type(item.get('slot')) is int and item['slot']==index+1 and item.get('staged') is False,message)
        need(all(item.get(k)==v.strip() for k,v in q['guidance'][index].items()),message)
        need(item.get('role_mode') in ('whole-image','prompt-guidance','style-board') and type(item.get('binding')) is list,message)
    board=intent.get('reference_board')
    if board is not None:
        need(type(board) is dict and set(board)=={'minimum','slot_count','roles'} and type(board['minimum']) is int
             and type(board['slot_count']) is int and 1<=board['minimum']<=len(intent['sources'])<=board['slot_count']
             and type(board['roles']) is list and len(board['roles'])==board['slot_count'],message)
        need(intent.get('compiled_positive')==intent['controls'].get('positive') and intent.get('lineage',{}).get('by_input')=={}
             and all(x.get('role_mode')=='style-board' and not x.get('contribution') and not x.get('avoid') for x in intent['sources']),message)
    need(result.get('diff')==_diff(q['draft'],intent),message)
    return result


def observe(transport, value):
    from .client import ClientError, read_response
    q=query(value)
    try: result=transport(PREFIX,q)
    except HTTPError as exc:
        try:
            with exc: detail=decode(read_response(exc,65536))
        except (ValueError,OSError,HTTPException):detail={}
        message=detail.get('error') if type(detail) is dict else None
        raise ClientError(exc.code,{'error':message if type(message) is str else 'Setup preview unavailable; retry explicitly.',
                                    'code':'setup_proposal_unavailable','generation_submitted':False}) from exc
    return validate_reply(result,q)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Review a complete setup proposal; never apply, stage or run it.')
    parser.add_argument('request_json',type=Path,help='Strict UTF-8 request JSON, maximum 128 KiB')
    parser.add_argument('--url',default='http://127.0.0.1:8191')
    args=parser.parse_args(argv)
    try:
        with args.request_json.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
        need(len(raw)<=MAX_BYTES,'Setup proposal input exceeds 128 KiB')
        from .sdk import WorkflowClient
        result=WorkflowClient(args.url).setup_proposal(query(decode(raw)))
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0
    except (ValueError,OSError,HTTPException) as exc:
        print(json.dumps({'error':str(exc),'generation_submitted':False}),file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
