"""Bounded returning-owner observations; existing stores retain all authority."""
import json
import math
import re
import sqlite3

import native_export_history
import project_storage
from studio_workflow.asset_reads import _state, privacy_scope
from studio_workflow.privacy import is_regular
from workspace import WorkspaceError

PLAN_WINDOW = 40
READ_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, sqlite3.DatabaseError)


def latest_native(studio, workspace_id):
    # shortcut: inspect at most 40 candidates; offer an incomplete result until a deeper history reader is needed.
    with studio.production.connect() as db:
        rows = db.execute('''SELECT id,created,
            CASE WHEN length(plan)<=? THEN plan END AS plan,
            CASE WHEN length(state)<=? THEN state END AS state
            FROM projects WHERE NOT json_valid(plan)
            OR json_extract(CASE WHEN json_valid(plan) THEN plan ELSE '{}' END,'$.kind') IS NULL
            OR json_extract(CASE WHEN json_valid(plan) THEN plan ELSE '{}' END,'$.kind')='native'
            ORDER BY (typeof(created) NOT IN ('integer','real')) DESC,created DESC,id DESC LIMIT ?''',
            (project_storage.PLAN_LIMIT, project_storage.PLAN_LIMIT, PLAN_WINDOW+1))
        for index,row in enumerate(rows):
            if index == PLAN_WINDOW:return {'state':'incomplete'}
            plan,state = json.loads(row['plan']),json.loads(row['state'])
            if not isinstance(plan,dict) or not isinstance(state,dict):raise ValueError('Invalid plan record')
            if not is_regular(plan):continue
            ids,snapshots = plan.get('source_assets'),plan.get('assets')
            if (plan.get('kind')!='native' or not isinstance(ids,list) or not 1<=len(ids)<=33
                    or any(not isinstance(key,str) or not re.fullmatch('[A-Za-z0-9_-]{1,128}',key) for key in ids)
                    or len(set(ids))!=len(ids)
                    or not isinstance(snapshots,list)):raise ValueError('Invalid source identities')
            with studio.assets.connection() as assets:
                studio.assets._check_scope(assets,workspace_id)
                sources=[assets.execute('SELECT privacy FROM assets WHERE id=?',(key,)).fetchone() for key in ids]
            if any(source is not None and source['privacy']!='regular' for source in sources):continue
            if any(source is None for source in sources):raise ValueError('Source no longer available')
            if not native_export_history.visible(studio,plan,ids[0]):continue
            for key in ids:
                current=studio.assets.get(key,privacy='regular')
                saved=[record for record in snapshots if isinstance(record,dict) and record.get('id')=='asset-'+key]
                metadata=saved[0].get('metadata') if len(saved)==1 else None
                if (not isinstance(metadata,dict) or metadata.get('id')!=key
                        or metadata.get('job_id')!=current['job_id']
                        or metadata.get('workspace_id',workspace_id)!=workspace_id):raise ValueError('Source ownership changed')
            if project_storage.problem(studio.production.root,row['id'],plan):raise ValueError('Plan evidence unavailable')
            created=row['created'];status=state.get('status')
            if (type(created) not in (int,float) or not math.isfinite(created)
                    or not isinstance(status,str) or not status or len(status)>40):raise ValueError('Invalid recorded date or state')
            return {'state':'ready','plan':{'id':row['id'],'name':str(plan.get('name','Native export'))[:200],
                                          'created_at':created,'status':status}}
    return {'state':'empty'}


def inspect(studio, workspace_id=None, scope='regular'):
    scope=privacy_scope(scope)
    with studio.assets.connection() as db:
        identity=studio.assets._check_scope(db,workspace_id)
        stamp=_state(db,scope)
    result={'workspace_id':identity,'scope':scope,'observation_only':True,'generation_submitted':False}
    try:
        page=studio.assets.asset_page(workspace_id=identity,limit=1,filters={
            'privacy':scope,'review':'selected','media_type':'image','visibility':'active','source':'mine'})
        asset=page['assets'][0] if page['assets'] else None
        result['kept']={'state':'ready','asset':{**{key:asset[key] for key in ('id','title','created_at')},'privacy':asset.get('privacy','regular')}} if asset else {'state':'empty'}
    except READ_ERRORS:result['kept']={'state':'unavailable'}
    if scope=='private':result['native']={'state':'excluded'}
    else:
        try:result['native']=latest_native(studio,identity)
        except READ_ERRORS:result['native']={'state':'unavailable'}
    result['native']['scope']='regular'
    with studio.assets.connection() as db:
        studio.assets._check_scope(db,identity)
        if _state(db,scope)!=stamp:
            raise WorkspaceError('Workspace changed during this observation. Refresh Continue.',status=409,code='asset_continue_stale')
    return result
