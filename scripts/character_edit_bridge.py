"""Explicit local-agent client for the existing Studio Production queue.

Prepare locally, stage (uploads/preflight only), explicitly start, inspect, collect,
then compose through the original write mask. No direct Comfy calls or retry loop.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import copy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import time
import uuid

from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.character_edit_bridge_io import (
    JSON_LIMIT, IMAGE_LIMIT, HEX, PROJECT, UPLOAD, StudioHTTP, require,
    canonical, digest, hashed, decode, read, relative, local, bytes_of,
    artifact, save_new, image_info,
)


from scripts.character_edit_bridge_plan import (
    preset_contract, compile_instruction, projected_graph, prepare, validate_handoff,
)


def campaign_record(value, campaign):
    require(isinstance(value,dict) and value.get('campaign')==campaign
            and value.get('root_id')=='character-edit:'+campaign['campaign_id'], 'Registered campaign differs from the selected receipt')
    budget=value.get('budget',{})
    require(type(budget.get('allowance')) is int and type(budget.get('reserved')) is int
            and budget['allowance']==campaign['max_generation_attempts'] and 0<=budget['reserved']<=budget['allowance'],
            'Registered campaign budget differs')
    return value


def register_campaign(workspace, campaign_name, client=None, *, inspect_only=False):
    from scripts.character_edit_campaign import validate
    root=Path(workspace).resolve(strict=True); campaign=validate(read(local(root,campaign_name)))
    client=client or StudioHTTP()
    if inspect_only:result=client.request('GET','/api/production/campaigns/'+campaign['campaign_id'])
    else:result=client.request('POST','/api/production/campaigns',{'campaign':campaign})
    return campaign_record(result,campaign)


class Bridge:
    """Command receipts, not a second queue or a trust boundary against the local owner."""
    def __init__(self, workspace, handoff_name, client=None):
        self.root = Path(workspace).resolve(strict=True)
        self.handoff_name = handoff_name
        self.handoff = validate_handoff(self.root, read(local(self.root, handoff_name)))
        self.campaign = decode(bytes_of(self.root,self.handoff['campaign'])) if self.handoff['schema_version']==2 else None
        self.edit_plan = decode(bytes_of(self.root,self.handoff['plan'])) if self.campaign else None
        self.client = client or StudioHTTP()
        # One client receipt location per edit plan, not one fresh budget per seed/output folder.
        self.directory = self.root/('.edit-bridge-'+self.handoff['edit_plan_sha256'])
        require(not self.directory.is_symlink(), 'Bridge journal cannot be symlinked')
        self.directory.mkdir(exist_ok=True)
        self.name = 'Edit bridge '+self.handoff['edit_plan_sha256']

    @contextmanager
    def locked(self):
        lock = self.directory/'command.lock'
        try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc: raise ValueError('Another bridge command or retained crash lock exists; inspect before recovery') from exc
        try:
            with os.fdopen(fd,'w') as stream: stream.write(str(os.getpid())); stream.flush(); os.fsync(stream.fileno())
            yield
        finally: lock.unlink(missing_ok=True)

    def state(self):
        path = self.directory/'state.json'
        require(not path.is_symlink(), 'Bridge state cannot be symlinked')
        if not path.exists(): return {'handoff_sha256': self.handoff['sha256'], 'phase': 'prepared', 'uploads': [], 'project_id': None}
        value = read(path)
        require(value.get('handoff_sha256') == self.handoff['sha256'], 'This edit plan already has a different handoff; do not reset its budget')
        require(isinstance(value.get('uploads'), list) and len(value['uploads']) <= len(self.handoff['references'])
                and all(isinstance(u, dict) and isinstance(u.get('file'), str) and UPLOAD.fullmatch(u['file']) for u in value['uploads']), 'Invalid upload journal')
        require(value.get('phase') in ('prepared','uploading','create_pending','staged','start_pending','started'), 'Unknown bridge state')
        return value

    def write_state(self, value):
        # Intent is fsynced before a mutating request. An abrupt loss never enables a second POST.
        fd, temporary = tempfile.mkstemp(prefix='.state-', dir=self.directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.directory/'state.json')
            log=self.directory/'events.jsonl'; require(not log.is_symlink(), 'Event log cannot be symlinked')
            event={k:value.get(k) for k in ('phase','project_id','handoff_sha256','pending_upload_index')}
            event['recorded_at']=time.time()
            with log.open('ab') as stream:
                stream.write(canonical(event)+b'\n'); stream.flush(); os.fsync(stream.fileno())
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def inputs(self):
        current = validate_handoff(self.root, read(local(self.root, self.handoff_name)))
        require(canonical(current) == canonical(self.handoff), 'Handoff changed during this command')

    def identity(self, state):
        value = self.client.request('GET','/api/identity')
        require(isinstance(value, dict) and value.get('app') == 'local-asset-studio' and isinstance(value.get('workspace'), str) and value['workspace'], 'Not a Studio workspace')
        if state.get('identity'): require(canonical(value) == canonical(state['identity']), 'Studio workspace identity changed')
        return value

    def templates(self):
        raw = self.client.request('GET','/api/workflows/'+self.handoff['preset_id'],binary=True)
        require(digest(raw) == self.handoff['template_sha256'], 'Live native template changed; no job submitted')
        catalog=self.client.request('GET','/api/catalog')
        matches=[p for p in catalog['presets'] if p.get('id')==self.handoff['preset_id']]
        require(len(matches)==1 and canonical(preset_contract(matches[0]))==canonical(self.handoff['native_preset']),
                'Live native catalog bindings or settings changed; prepare a reviewed new handoff')
        require(not matches[0].get('runtime_block'), 'The selected Studio runtime is blocked: '+str(matches[0].get('runtime_block')))
        return decode(raw)

    def project(self, state, identifier=None):
        identifier = identifier or state.get('project_id')
        require(isinstance(identifier,str) and PROJECT.fullmatch(identifier), 'No valid known project ID')
        project = self.client.request('GET','/api/production/'+identifier)
        p = project['plan']; stages = p['stages']; expected = state['previews']
        root_id='character-edit:'+self.campaign['campaign_id'] if self.campaign else identifier
        require(project['id'] == identifier and project['root_id'] == root_id and p['name'] == self.name
                and p['kind'] == 'comparison' and p.get('parent_project') is None, 'Unexpected Production ownership')
        require(canonical(p['values']) == canonical(self.handoff['seeds']) and p['axis'] == 'seed'
                and len(stages) == len(expected), 'Production cases differ from this handoff')
        require(type(project['budget']['allowance']) is int and type(project['budget']['reserved']) is int and
                0 <= project['budget']['reserved'] <= project['budget']['allowance'] and project['budget']['allowance'] ==
                (self.campaign['max_generation_attempts'] if self.campaign else self.handoff['max_candidates']), 'Production budget differs')
        if self.campaign:
            expected_id=hashlib.sha256(('character-edit:'+self.campaign['campaign_id']+':'+self.handoff['edit_plan_sha256']).encode()).hexdigest()[:32]
            source=p.get('character_source') or {}
            expected_uploads=[dict(file=u['file'],sha256=r['image']['sha256'],role=r['role'],contribution=r['contribution'],avoid=r['avoid'])
                              for u,r in zip(state['uploads'],self.handoff['references'])]
            require(identifier==expected_id and source=={'kind':'character_edit_import','campaign':self.campaign,
                    'edit_plan':self.edit_plan,'handoff':self.handoff,'uploads':expected_uploads,
                    'attempt_kind':'primary','parent_attempt_id':None}, 'Production campaign provenance differs')
        expected_inputs = {u['file']: r['image']['sha256'] for u,r in zip(state['uploads'], self.handoff['references'])}
        actual = p.get('bundle',{}).get('inputs',[])
        require(len(actual) == len(expected_inputs) and
                {a['path'].replace('\\','/').rsplit('/',1)[-1]:a['sha256'] for a in actual} == expected_inputs,
                'Production did not pin the exact uploaded reference bytes')
        for stage, preview in zip(stages, expected):
            require(stage['graph_sha256'] == digest(json.dumps(stage['graph'],sort_keys=True,separators=(',',':')).encode()), 'Prepared graph fingerprint changed')
            require(stage['operation'] == 'comfy.generate.v1' and canonical(stage['graph']) == canonical(preview['workflow'])
                    and stage['request']['expected_template_sha256'] == self.handoff['template_sha256'], 'Prepared Production graph changed')
        require(p['sha256'] == digest(json.dumps({k:v for k,v in p.items() if k!='sha256'},sort_keys=True,separators=(',',':')).encode()), 'Production plan hash mismatch')
        if state.get('project_sha256'): require(p['sha256'] == state['project_sha256'], 'Remote plan revision changed')
        return project

    def stage(self, *, resume_uploads=False):
        with self.locked():
            self.inputs(); state = self.state()
            require(state['phase'] in ('prepared','uploading'), 'Already staged or creation outcome uncertain: use status/reconcile, never repeat creation')
            require(state['phase'] != 'uploading' or resume_uploads, 'Uploads interrupted; explicitly use --resume-uploads (no neural retry)')
            state['identity'] = self.identity(state); template_graph=self.templates()
            if self.campaign:
                campaign_record(self.client.request('GET','/api/production/campaigns/'+self.campaign['campaign_id']),self.campaign)
            state['phase'] = 'uploading'; self.write_state(state)
            for i,ref in enumerate(self.handoff['references']):
                if i < len(state['uploads']):
                    upload = state['uploads'][i]
                else:
                    body = bytes_of(self.root,ref['image'])
                    state['pending_upload_index'] = i; self.write_state(state)
                    upload = self.client.request('POST','/api/upload',body,filename=f'edit-reference-{i}.png')
                    require(isinstance(upload,dict) and isinstance(upload.get('file'),str) and UPLOAD.fullmatch(upload['file']), 'Unexpected uploaded filename')
                    require(upload.get('sha256') == ref['image']['sha256'], 'Upload changed reference bytes')
                    state['uploads'].append(upload); state.pop('pending_upload_index',None); self.write_state(state)
                returned = self.client.request('GET','/api/uploads/'+upload['file'],binary=True)
                require(digest(returned) == ref['image']['sha256'], 'Stored Studio upload differs from the source')
            recipe = {'preset_id':self.handoff['preset_id'], 'batch_count':1,
                'controls':{'positive':self.handoff['positive'],'width':self.handoff['size'][0],'height':self.handoff['size'][1]},
                'references':[dict(file=u['file'],sha256=r['image']['sha256'],role=r['role'],contribution=r['contribution'],avoid=r['avoid'])
                              for u,r in zip(state['uploads'],self.handoff['references'])],
                'expected_template_sha256':self.handoff['template_sha256']}
            previews = []
            for seed in self.handoff['seeds']:
                request = copy.deepcopy(recipe); request['controls']['seed'] = seed
                preview = self.client.request('POST','/api/preview',request)
                require(preview['submitted'] is False and type(preview['batch_count']) is int and preview['batch_count']==1
                        and preview['template_sha256']==self.handoff['template_sha256'], 'Unexpected preview semantics')
                records=preview['references']
                require(len(records)==len(recipe['references']), 'Preview lost a reference')
                for actual, supplied in zip(records,recipe['references']):
                    require(all(actual.get(k)==supplied[k] for k in ('file','sha256','role','contribution','avoid')), 'Preview changed a reference role or contribution')
                # The canvas is an explicit latent now, not a VAE encode of the composition reference, so
                # candidate dimensions come from the bound width/height and the crop must reach Studio intact.
                # A missing key here is untrusted remote/catalog shape, not a bug: refuse, never raise KeyError.
                require((records[0].get('transform') or {}).get('source_size')==self.handoff['size'], 'Native preprocessing changes candidate dimensions')
                bindings=[self.handoff['native_preset'].get(key) for key in ('width','height')]
                require(all(isinstance(b,list) and len(b)==2 for b in bindings), 'Pinned canvas binding is unavailable')
                canvas=[((preview['workflow'].get(str(node)) or {}).get('inputs') or {}).get(str(field)) for node,field in bindings]
                require(canvas==self.handoff['size'], 'Native preprocessing changes candidate dimensions')
                expected=projected_graph(template_graph,self.handoff['native_preset'],request)
                require(canonical(preview['workflow'])==canonical(expected), 'Native preview differs from the pinned catalog projection')
                previews.append(preview)
            state['previews']=previews
            state['request']={'name':self.name,'recipe':recipe,'axis':'seed','values':self.handoff['seeds'],
                              'max_generations':self.handoff['max_candidates'],'max_seconds':self.handoff['max_seconds']}
            if self.campaign:
                state['request']={'name':self.name,'character_edit_campaign':self.campaign,'character_edit_plan':self.edit_plan,
                    'character_edit_handoff':self.handoff,
                    'uploads':[{'role':r['role'],'file':u['file']} for u,r in zip(state['uploads'],self.handoff['references'])]}
            existing = self.client.request('GET','/api/production')
            require(not any(p.get('name')==self.name for p in existing), 'An edit project already exists; creation is not repeated')
            self.inputs(); self.templates()
            state['phase']='create_pending'; self.write_state(state)
            created=self.client.request('POST','/api/production',state['request'])
            require(isinstance(created.get('id'),str) and PROJECT.fullmatch(created['id']), 'Unexpected created project ID')
            state['project_id']=created['id']; self.write_state(state)
            project=self.project(state); state['project_sha256']=project['plan']['sha256']; state['phase']='staged'; self.write_state(state)
            return {'project':project,'generation_submitted':False,'next':'Explicit start; inspect the pinned model bundle and policy warnings first.'}

    def reconcile(self):
        with self.locked():
            self.inputs(); state=self.state(); self.identity(state)
            require(state['phase']=='create_pending', 'Only an uncertain project creation needs adoption; use status for known starts')
            records=self.client.request('GET','/api/production'); matches=[p for p in records if p.get('name')==self.name]
            require(len(matches)==1, 'No unique matching project; leave creation unresolved and inspect Studio. Nothing was resubmitted.')
            project=self.project(state,matches[0]['id'])
            state.update(project_id=project['id'],project_sha256=project['plan']['sha256'],phase='staged')
            self.write_state(state); return {'project':project,'mutating_http_requests':0}

    def start(self):
        with self.locked():
            self.inputs(); state=self.state(); require(state['phase']=='staged', 'Start already requested or not staged; inspect the known project, do not retry')
            self.identity(state); self.templates(); project=self.project(state)
            # Other revisions may already hold reservations in the shared root.
            require(project['state']['status']=='planned' and (self.campaign is not None or project['budget']['reserved']==0), 'Project has already been started elsewhere')
            state['phase']='start_pending'; self.write_state(state)
            response=self.client.request('POST','/api/production/'+state['project_id']+'/start',{})
            state['phase']='started'; self.write_state(state)
            return {'project':response,'generation_requested':True,'note':'Only Studio owns execution. This command does not poll or retry.'}

    def status(self):
        state=self.state(); self.identity(state)
        project=self.project(state) if state.get('project_id') else None
        return {'client_phase':state['phase'],'project':project,'mutating_http_requests':0,
                'note':'An uncertain start remains tied to this project ID. Use the Studio to inspect/reconcile it; this client never resubmits it.'}

    def collect(self, index):
        with self.locked():
            self.inputs(); state=self.state(); self.identity(state); project=self.project(state)
            require(type(index) is int and 0<=index<len(project['stages']), 'Unknown stage index')
            stage=project['stages'][index]; job=stage['job']; attempt=stage['attempt']
            expected_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f"asset-studio:{project['id']}:stage:{index}"))
            require(job and job['id']==attempt.get('job_id')==expected_id and job['status']=='completed'
                    and type(job['batch_count']) is int and job['batch_count']==1, 'A completed, matching single-image job is required')
            require(isinstance(job.get('prompt_ids'),list) and len(job['prompt_ids'])==1 and isinstance(job['prompt_ids'][0],str) and job['prompt_ids'][0], 'Candidate lacks its single known prompt ID')
            outputs=job['outputs']; require(len(outputs)==1 and outputs[0].get('media_type')=='image', 'Expected exactly one image candidate')
            aid=outputs[0].get('asset_id'); require(isinstance(aid,str) and PROJECT.fullmatch(aid), 'Candidate has no published Workspace asset')
            recipe=self.client.request('GET','/api/jobs/'+expected_id+'/recipe')
            require(canonical(recipe['workflow'])==canonical(project['plan']['stages'][index]['graph']) and type(recipe['batch_count']) is int and recipe['batch_count']==1,
                    'Candidate recipe is not the prepared graph')
            assets=self.client.request('GET','/api/workspace')['assets']; matches=[a for a in assets if a['id']==aid]
            require(len(matches)==1 and matches[0]['job_id']==expected_id and not matches[0].get('trashed_at') and matches[0].get('media_type')=='image', 'Candidate asset provenance mismatch')
            raw=self.client.request('GET','/api/assets/'+aid+'/file',binary=True)
            require(digest(raw)==matches[0]['sha256'], 'Downloaded candidate does not match Workspace digest')
            im=image_info(raw); require(list(im.size)==self.handoff['size'], 'Candidate size mismatch; no silent resize')
            dest=self.directory/f'candidate-{index}'
            require(not dest.exists() and not dest.is_symlink(), 'Candidate already collected; retain the existing evidence')
            receipt={'kind':'character_edit_candidate','handoff_sha256':self.handoff['sha256'], 'project_id':project['id'],
                'project_sha256':project['plan']['sha256'],'stage_index':index,'job_id':expected_id,'prompt_ids':job.get('prompt_ids',[]),
                'asset_id':aid,'candidate':{'path':(dest/'candidate.png').relative_to(self.root).as_posix(),'sha256':digest(raw)},
                'job_recipe':recipe,'review_state':'unreviewed','semantic_approval':False}
            receipt['sha256']=hashed(receipt)
            require(len(canonical(receipt)) <= JSON_LIMIT, 'Candidate receipt exceeds the JSON byte limit')
            # Publish a pair, never an image-only final directory. A failed staging
            # directory is evidence: retain it rather than cleaning up or adopting it.
            # The existing command lock serializes cooperating bridge writers.
            staging=Path(tempfile.mkdtemp(prefix=f'.candidate-{index}-', dir=self.directory))
            save_new(staging/'candidate.png',raw); save_new(staging/'receipt.json',receipt)
            staged={'path':(staging/'candidate.png').relative_to(self.root).as_posix(),'sha256':receipt['candidate']['sha256']}
            bytes_of(self.root,staged)
            require(canonical(read(staging/'receipt.json')) == canonical(receipt), 'Staged candidate receipt changed')
            self.inputs()  # Downloads/writes may have overlapped a source or mask edit.
            require(not dest.exists() and not dest.is_symlink(), 'Candidate already collected; retain the existing evidence')
            os.rename(staging,dest)  # Same parent/filesystem; not os.replace and not a copy.
            return receipt

    def compose(self, index, current_document, output):
        from scripts import character_edit_pixels as pixels
        with self.locked():
            self.inputs(); require(type(index) is int and 0<=index<len(self.handoff['seeds']), 'Unknown stage index')
            require(hashed(read(local(self.root,current_document)))==self.handoff['document_sha256'], 'Current exported document is stale; do not apply this candidate')
            receipt=read(self.directory/f'candidate-{index}'/'receipt.json')
            require(receipt.get('sha256')==hashed({k:v for k,v in receipt.items() if k!='sha256'}) and receipt['handoff_sha256']==self.handoff['sha256'], 'Candidate receipt changed')
            require(receipt['candidate']['path']==(self.directory/f'candidate-{index}'/'candidate.png').relative_to(self.root).as_posix(), 'Unexpected candidate path')
            bytes_of(self.root,receipt['candidate'])
            result=pixels.apply(self.root,read(local(self.root,self.handoff['plan']['path'])),self.handoff['bundle'],receipt['candidate'],output)
            return {'composition':result,'execution_receipt':(self.directory/f'candidate-{index}'/'receipt.json').relative_to(self.root).as_posix(),
                    'semantic_approval':False,'note':'New local image only. No native-editor layer import, owner approval or automatic Workspace publication.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare'); p.add_argument('--workspace',required=True); p.add_argument('--plan',required=True)
    p.add_argument('--out',required=True); p.add_argument('--seeds',type=int,nargs='+',required=True); p.add_argument('--max-seconds',type=int,default=1800)
    p.add_argument('--campaign',help='Explicit campaign receipt; omitted keeps legacy v1 behavior')
    for name in ('register-campaign','campaign-status'):
        p=sub.add_parser(name); p.add_argument('--workspace',required=True); p.add_argument('--campaign',required=True)
        p.add_argument('--studio-port',type=int,default=8191)
    for name in ('stage','start','status','reconcile','collect','compose'):
        p=sub.add_parser(name); p.add_argument('--workspace',required=True); p.add_argument('--handoff',required=True)
        p.add_argument('--studio-port',type=int,default=8191)
        if name=='stage':p.add_argument('--resume-uploads',action='store_true')
        if name in ('collect','compose'):p.add_argument('--index',type=int,required=True)
        if name=='compose':p.add_argument('--current-document',required=True); p.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        if args.command=='prepare':value=prepare(args.workspace,args.plan,args.out,args.seeds,max_seconds=args.max_seconds,campaign=args.campaign)
        elif args.command in ('register-campaign','campaign-status'):
            value=register_campaign(args.workspace,args.campaign,StudioHTTP(args.studio_port),inspect_only=args.command=='campaign-status')
        else:
            bridge=Bridge(args.workspace,args.handoff,StudioHTTP(args.studio_port))
            if args.command=='stage':value=bridge.stage(resume_uploads=args.resume_uploads)
            elif args.command=='collect':value=bridge.collect(args.index)
            elif args.command=='compose':value=bridge.compose(args.index,args.current_document,args.out)
            else:value=getattr(bridge,args.command)()
        print(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)); return 0
    except (ValueError,KeyError,TypeError,OSError,http.client.HTTPException) as exc:
        print(json.dumps({'error':str(exc),'type':type(exc).__name__,'automatic_retry':False}),file=sys.stderr); return 2

if __name__=='__main__':raise SystemExit(main())
