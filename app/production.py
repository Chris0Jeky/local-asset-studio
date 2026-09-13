"""Bounded experiments on the Studio worker, with durable plans and attempts.

Plans contain prepared catalog graphs, never executable code from imported briefs.
Budget reservations belong to the root experiment and survive branches/restarts.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

import settings_planner
import prompting
import project_storage
import submission_evidence
import mixed_batch
import production_clock


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class Production:
    def __init__(self, studio):
        self.studio=studio
        self.root=(studio.experiments/'projects').resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'projects.sqlite3';self.lock=threading.RLock()
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS budgets(id TEXT PRIMARY KEY, allowance INTEGER NOT NULL, reserved INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, root_id TEXT NOT NULL REFERENCES budgets(id), plan TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL);
            ''')
            for row in db.execute('SELECT id,plan,state FROM projects').fetchall():
                plan=json.loads(row['plan'])
                state=json.loads(row['state'])
                if plan.get('kind')=='comparison' and 'time_budget' in state:
                    try:state['time_budget']=production_clock.recover(production_clock.read(plan,state))
                    except ValueError as exc:state['time_budget_error']=str(exc)
                    db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),row['id']))
                active_voice_attempt=plan.get('kind')=='voice' and any(attempt.get('status')=='running' for attempt in state.get('attempts',{}).values())
                if plan.get('kind')=='voice' and (state['status'] in ('queued','running','observing') or active_voice_attempt):
                    for attempt in state.get('attempts',{}).values():
                        if attempt.get('status')=='running':attempt.update(status='interrupted',message='Studio restarted while this voice attempt was active; execution state is unproven.')
                    state.update(status='interrupted',message='Studio restarted while a voice take was active. Inspect retained request, attempt, job and output records; no inference was resumed.')
                    db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),row['id']))
                elif state['status'] in ('queued','running','observing'):
                    state.update(status='interrupted',message='Studio restarted. Inspect known jobs before explicitly resuming; nothing was resubmitted.')
                    db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),row['id']))

                # Preserve execution/review state and reservations. This is a storage
                # observation, not permission to reconstruct files or replay work.
                if plan.get('kind') in project_storage.KINDS:
                    reason=project_storage.problem(self.root,row['id'],plan)
                    if reason:state['storage_issue']={'reason':reason,'checked_at':time.time()}
                    else:state.pop('storage_issue',None)
                    db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),row['id']))

        from review_desk import ReviewDesk
        self.reviews=ReviewDesk(self)
        from av_projects import AVProjects
        self.av=AVProjects(self)

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db,timeout=15);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:yield db
        finally:db.close()

    def _insert_materialized(self, db, identifier, root_id, plan, state):
        # Keep deterministic character imports idempotently rejected before touching
        # their existing directory, including when a shared budget already exists.
        if db.execute('SELECT 1 FROM projects WHERE id=?',(identifier,)).fetchone():
            raise sqlite3.IntegrityError('Project identity already exists')
        project_storage.materialize(self.root,identifier,plan,self.studio._write_json_atomic)
        db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',(identifier,root_id,json.dumps(plan),json.dumps(state),time.time()))

    def _get(self, identifier, db=None):
        if not isinstance(identifier,str) or not re.fullmatch('[0-9a-f]{32}',identifier):raise ValueError('Unknown experiment')
        if db is None:
            with self.connect() as connection:return self._get(identifier,connection)
        row=db.execute('SELECT * FROM projects WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('Unknown experiment')
        return {'id':row['id'],'root_id':row['root_id'],'plan':json.loads(row['plan']),'state':json.loads(row['state']),'created_at':row['created']}

    def _state(self, identifier, state):
        with self.connect() as db:db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),identifier))

    def _mutate(self, identifier, **fields):
        with self.lock:
            project=self._get(identifier);project['state'].update(fields)
            self._state(identifier,project['state']);return project

    def public(self, project, full=False):
        plan=project['plan'];state=copy.deepcopy(project['state'])
        if plan['kind']=='comparison':
            try:
                state['time_budget']=production_clock.read(plan,state)
                state['time_budget']['remaining_seconds']=production_clock.remaining(state['time_budget'])
            except ValueError as exc:state['time_budget_error']=str(exc)
        if state.get('storage_issue'):
            state['message']='Startup storage check: '+state['storage_issue']['reason']+'. Inspect project files before Start or Resume. '+state.get('message','')
        with self.connect() as db:
            budget=dict(db.execute('SELECT allowance,reserved FROM budgets WHERE id=?',(project['root_id'],)).fetchone())
        stages=[]
        for index,stage in enumerate(plan.get('stages',[])):
            attempt=state.get('attempts',{}).get(str(index),{})
            job=self.studio.jobs.get(attempt.get('job_id'))
            stages.append({'label':stage['label'],'operation':stage['operation'],'attempt':attempt,
                           'job':self.studio.public(job) if job else None})
        result={k:project[k] for k in ('id','root_id','created_at')}
        result.update(name=plan['name'],kind=plan['kind'],parent_project=plan.get('parent_project'),
                      plan_sha256=plan['sha256'],budget=budget,stages=stages,state=state,
                       recipe=plan.get('recipe'),axis=plan.get('axis'),values=plan.get('values'),
                       variants=plan.get('variants'),knowledge_sha256=plan.get('knowledge_sha256'))
        result['can_reconcile_tracking']=state['status'] in ('interrupted','uncertain','stopped') and bool(self._tracking_terminal_records(project))
        mixed=self._mixed_batch_jobs(project)
        result['can_reconcile_batch']=state['status'] in ('interrupted','uncertain','stopped') and bool(mixed) and all(mixed_batch.disposed(job) for _,job in mixed)
        if plan.get('kind')=='voice':
            from voice_baseline import resume_eligibility
            result['voice_resume']=resume_eligibility(self,project)
        if full:result['plan']=plan
        return result

    def list(self):
        with self.connect() as db:ids=[r['id'] for r in db.execute('SELECT id FROM projects ORDER BY created DESC')]
        return [self.public(self._get(i)) for i in ids]

    def get(self, identifier, full=False):return self.public(self._get(identifier),full)

    @staticmethod
    def _integer(value,name,low,high):
        if type(value) is not int or not low<=value<=high:raise ValueError(f'{name} must be an integer from {low} to {high}')
        return value

    def create(self, payload):
        with self.studio.lock:
            if isinstance(payload,dict) and 'character_handoff' in payload:return self._character_handoff(payload)
            return self._create(payload)

    def plan(self, payload):
        """Offer documented sweep variants.  Reserves nothing and submits nothing.

        Route hook (server.do_POST): /api/experiments/plan -> production.plan(payload).
        """
        if not isinstance(payload,dict):raise ValueError('Plan intent must be an object')
        preset=self.studio.preset(payload.get('preset_id'))
        controls=payload.get('controls') or {}
        if not isinstance(controls,dict):raise ValueError('controls must be an object')
        mode=payload.get('mode','grid')
        if mode not in ('grid','remix'):raise ValueError('Choose the settings grid or a LoRA remix')
        kb,digest=settings_planner.load_kb(self.studio.root)
        available=settings_planner.axes_for(preset,kb)
        limit=payload.get('limit')
        extra={} if limit is None else {'limit':limit}
        if mode=='grid':
            if not available:raise ValueError('The settings library documents no axis this recipe can change')
            identifiers=payload.get('axes') or [axis['id'] for axis in available[:2]]
            if not isinstance(identifiers,list):raise ValueError('axes must be a list of documented axis identifiers')
            variants=settings_planner.plan_grid(preset,kb,controls,identifiers,**extra)
        else:
            variants=settings_planner.plan_remix(preset,kb,controls,**extra)
        return {'mode':mode,'variants':[dict(v,description=settings_planner.describe(v)) for v in variants],
                'axes_available':available,'knowledge_sha256':digest}

    @staticmethod
    def _variants(variants):
        """Accept a planned sweep: labelled control overrides, one per candidate."""
        if not isinstance(variants,list) or not 1<=len(variants)<=8:raise ValueError('Use one to eight planned variants')
        result=[];labels=set()
        for entry in variants:
            if not isinstance(entry,dict):raise ValueError('Each variant must be an object with a label and controls')
            label=entry.get('label')
            if not isinstance(label,str) or not 1<=len(label.strip())<=120:raise ValueError('Every variant needs a label (1–120 characters)')
            label=label.strip()
            if label in labels:raise ValueError('Variant labels must differ')
            labels.add(label)
            controls=entry.get('controls')
            if not isinstance(controls,dict) or not controls:raise ValueError('Every variant must set at least one control')
            if any(isinstance(v,(dict,list)) or v is None for v in controls.values()):raise ValueError('Variant controls take numbers, text or documented choices')
            rationale=entry.get('rationale','')
            if not isinstance(rationale,str) or len(rationale)>2000:raise ValueError('Variant rationale must be text up to 2000 characters')
            sources=entry.get('sources',[])
            if not isinstance(sources,list) or any(not isinstance(s,str) for s in sources):raise ValueError('Variant sources must be a list of URLs')
            result.append({'label':label,'controls':copy.deepcopy(controls),'rationale':rationale,'sources':sources[:12]})
        return result

    def _verify_character_reference_inputs(self, graph, bundle, character_source):
        """Pin the bytes a prepared graph will load, including pre-existing Comfy inputs."""
        approved={item['file']: item['sha256'] for item in character_source['uploads']}
        if len(approved)!=len(character_source['uploads']):raise ValueError('Character handoff has duplicate reference inputs')
        graph_names=[]
        for node in graph.values():
            if node.get('class_type')!='LoadImage':continue
            name=(node.get('inputs') or {}).get('image')
            if not isinstance(name,str) or Path(name).name!=name or name not in approved:
                raise ValueError('Prepared graph has a reference input outside the approved handoff')
            graph_names.append(name)
        if sorted(graph_names)!=sorted(approved):raise ValueError('Prepared graph does not bind every approved character reference')
        inputs=bundle.get('inputs') if isinstance(bundle,dict) else None
        if not isinstance(inputs,list):raise ValueError('Production preflight did not pin character reference inputs')
        actual={}
        for item in inputs:
            if not isinstance(item,dict) or not isinstance(item.get('path'),str) or not isinstance(item.get('sha256'),str):
                raise ValueError('Production preflight returned an invalid character reference input')
            name=Path(item['path']).name
            if name not in approved or name in actual or item['sha256']!=approved[name]:
                raise ValueError('Production preflight reference bytes differ from the approved handoff')
            actual[name]=item['sha256']
        if actual!=approved:raise ValueError('Production preflight did not pin every approved character reference')
        input_root=(self.studio.comfy_root/'input').resolve()
        for name,digest in approved.items():
            path=(input_root/name).resolve()
            if not path.is_relative_to(input_root) or not path.is_file() or self._file_hash(path)!=digest:
                raise ValueError('Prepared Comfy reference bytes differ from the approved handoff')

    def _create(self, payload, *, character_source=None, root_override=None, allowance_override=None, identifier_override=None):
        if not isinstance(payload,dict):raise ValueError('Experiment intent must be an object')
        if any(k in payload for k in ('workflow','tasks','command','script')):raise ValueError('Use a Studio recipe intent; imported blueprints and commands are not executable')
        name=payload.get('name','')
        if not isinstance(name,str) or not 1<=len(name.strip())<=120:raise ValueError('Name the experiment (1–120 characters)')
        recipe=copy.deepcopy(payload.get('recipe'))
        if not isinstance(recipe,dict):raise ValueError('Choose a Studio recipe')
        recipe['batch_count']=1
        variants=self._variants(payload['variants']) if payload.get('variants') is not None else None
        if variants is not None:
            # A planned sweep changes several documented settings at once; the
            # labels carry the meaning the single-axis values used to carry.
            axis='variants';values=[v['label'] for v in variants];overrides=[v['controls'] for v in variants]
        else:
            axis=payload.get('axis','seed')
            if axis not in ('seed','lora','cfg','steps','denoise'):raise ValueError('Choose seed, LoRA strength, guidance, steps or denoise')
            values=payload.get('values')
            if not isinstance(values,list) or not 1<=len(values)<=4:raise ValueError('Use one to four comparison values')
            if any(isinstance(v,(dict,list,bool)) or v is None for v in values):raise ValueError('Comparison values must be numbers')
            try:
                if any(not Decimal(str(v)).is_finite() for v in values):raise ValueError('Comparison values must be finite numbers')
            except InvalidOperation:raise ValueError('Comparison axes take numeric values, not filenames')
            # Browser form controls arrive as strings. Compare their numeric meaning
            # before preparing graphs so spellings such as 1, 1.0 and 1e0 cannot
            # reserve and submit duplicate candidates.
            normalized_values=[]
            for value in values:
                normalized=Decimal(str(value))
                if normalized in normalized_values:raise ValueError('Comparison values must differ after numeric normalization')
                normalized_values.append(normalized)
            overrides=[{axis:value} for value in values]
        max_seconds=self._integer(payload.get('max_seconds',1800),'Time budget',60,14400)
        stages=[];bundle=None
        for index,override in enumerate(overrides):
            request=copy.deepcopy(recipe);request.setdefault('controls',{}).update(override)
            preset,graph,path,controls,_=self.studio.prepare(request)
            if variants is None and not preset.get(axis):raise ValueError('The selected recipe does not support this comparison axis')
            if variants is None and axis=='lora' and isinstance(preset.get('defaults',{}).get('lora'),str):raise ValueError('This recipe binds a LoRA filename; choose a numeric comparison axis')
            if preset.get('family')=='Hunyuan3D 2.1' and not self.studio.config.get('terms_decisions',{}).get('Hunyuan3D 2.1'):
                raise ValueError('Hunyuan3D needs its own recorded terms decision before automated experiments; use TRELLIS or authored geometry meanwhile')
            for key in ('positive','negative'):
                for node,field in ([preset[key]] if preset.get(key) else [])+(preset.get('bindings_extra') or {}).get(key,[]):
                    if prompting.has_wildcards(graph.get(str(node),{}).get('inputs',{}).get(str(field))):raise ValueError('Resolve prompt wildcards ({a|b}, __name__) before planning a comparison; they would re-roll per stage')
            stage_bundle=self.studio.production_preflight(preset,graph)
            if character_source is not None:self._verify_character_reference_inputs(graph,stage_bundle,character_source)
            if bundle is None:bundle=stage_bundle
            else:
                # Pruned LoRA slots make stage graphs heterogeneous: pin every model any stage loads.
                for key in ('models','inputs'):
                    seen={json.dumps(e,sort_keys=True) for e in bundle.get(key,[])}
                    bundle[key]=bundle.get(key,[])+[e for e in stage_bundle.get(key,[]) if json.dumps(e,sort_keys=True) not in seen]
            # Validate every graph against the same live node schema, including changed enum/control values.
            self.studio.validate_graph(graph)
            request['references']=preset.get('_prepared_references',[])
            request['expected_template_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            graph_hash=fingerprint(graph)
            stages.append({'operation':'comfy.generate.v1','label':chr(65+index),'request':request,'graph':graph,'graph_sha256':graph_hash})
        # Different labels are not different work: two planned variants that resolve
        # to the same graph would spend two reservations on one image.
        if variants is not None and len({s['graph_sha256'] for s in stages})!=len(stages):raise ValueError('Planned variants must resolve to different graphs')
        identifier=identifier_override or uuid.uuid4().hex
        parent=payload.get('parent_project')
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if parent:
                previous=self._get(parent,db);root_id=previous['root_id']
            elif root_override:
                root_id=root_override;allowance=allowance_override
                existing=db.execute('SELECT allowance FROM budgets WHERE id=?',(root_id,)).fetchone()
                if existing is None:db.execute('INSERT INTO budgets(id,allowance) VALUES (?,?)',(root_id,allowance))
                elif existing['allowance']!=allowance:raise ValueError('Study budget identity has a different allowance')
            else:
                root_id=identifier
                allowance=self._integer(payload.get('max_generations',len(stages)),'Generation budget',1,16)
                if len(stages)>allowance:raise ValueError('Comparison exceeds the generation budget')
                db.execute('INSERT INTO budgets(id,allowance) VALUES (?,?)',(root_id,allowance))
            plan={'version':1,'kind':'comparison','name':name.strip(),'recipe':recipe,'axis':axis,'values':values,
                  'variants':variants,'knowledge_sha256':settings_planner.load_kb(self.studio.root)[1] if variants is not None else None,
                  'parent_project':parent,'max_seconds':max_seconds,'stages':stages,'bundle':bundle,
                   'repair_allowance':0,'review':'unreviewed','created_at':time.time(),'character_source':character_source}
            plan['sha256']=fingerprint(plan)
            state={'status':'planned','message':'Ready for explicit Start. No generation submitted.','attempts':{},'artifacts':[],
                   'stop_requested':False,'review':{'status':'unreviewed','notes':''}}
            self._insert_materialized(db,identifier,root_id,plan,state)
        project_storage.complete(self.root,identifier,plan)
        return self.get(identifier)

    def _character_handoff(self, payload):
        from scripts import character_study
        allowed={'character_plan','character_handoff','uploads','name','max_seconds'}
        if set(payload)!=allowed:raise ValueError('Character handoff import accepts only plan, handoff, uploads, name and max_seconds')
        plan=copy.deepcopy(payload['character_plan']);handoff=copy.deepcopy(payload['character_handoff'])
        case,preset=character_study.check_handoff(plan,handoff,self.studio.root)
        uploads=payload['uploads'];requirements=handoff['upload_requirements']
        if not isinstance(uploads,list) or len(uploads)!=len(requirements):raise ValueError('Upload every approved reference in handoff order')
        bound=[]
        for item,requirement in zip(uploads,requirements):
            if not isinstance(item,dict) or set(item)!={'reference_id','file'} or item['reference_id']!=requirement['id']:raise ValueError('Uploads must retain the approved reference IDs and order')
            filename=item['file'];upload=self.studio.experiments/'uploads'/str(filename)
            if not isinstance(filename,str) or filename!=Path(filename).name or not upload.is_file() or character_study.file_sha(upload)!=requirement['sha256']:raise ValueError('Uploaded reference bytes differ from the approved handoff')
            bound.append({'file':filename,'sha256':requirement['sha256'],'role':requirement['role']})
        controls=copy.deepcopy(handoff['proposed_controls'])
        if preset.get('reference_slots'):references=bound
        else:controls['reference']=bound[0]['file'];references=[]
        identity=hashlib.sha256(('character-primary:'+plan['plan_sha256']+':'+case['id']).encode()).hexdigest()[:32]
        source={'kind':'character_primary_import','study_plan':plan,'handoff':handoff,'uploads':bound,'case_id':case['id'],'attempt_kind':'primary','parent_attempt_id':None}
        intent={'name':payload['name'],'recipe':{'preset_id':handoff['preset_id'],'controls':controls,'references':references,'expected_template_sha256':handoff['template_sha256']},
                'axis':'seed','values':[case['seed']],'max_seconds':payload['max_seconds'],'max_generations':plan['request']['budget']['max_generation_attempts']}
        try:return self._create(intent,character_source=source,root_override='character-study:'+plan['plan_sha256'],allowance_override=plan['request']['budget']['max_generation_attempts'],identifier_override=identity)
        except sqlite3.IntegrityError as exc:raise ValueError('This primary case is already imported; inspect its existing project') from exc

    def native(self, payload):
        from native_exports import NativeExports, krita_roundtrip
        if not isinstance(payload,dict):raise ValueError('Export intent must be an object')
        kind=payload.get('kind');ids=payload.get('ids');options=payload.get('options',{})
        if kind not in ('atlas','ora','godot'):raise ValueError('Choose atlas, ORA or Godot')
        if not isinstance(ids,list) or not 1<=len(ids)<=33 or len(set(ids))!=len(ids):raise ValueError('Select ordered images, plus an optional GLB for Godot')
        assets=[self.studio.assets.get(i) for i in ids]
        if any(a['trashed_at'] for a in assets):raise ValueError('Restore assets before exporting')
        if sum(a['bytes'] for a in assets)>512*1024**2:raise ValueError('Export source files exceed the 512 MiB budget')
        if shutil.disk_usage(self.root).free<2*1024**3:raise ValueError('Native export needs at least 2 GiB free storage')
        verify=payload.get('verify_engine',False)
        if type(verify) is not bool:raise ValueError('Engine verification must be boolean')
        if verify and (kind!='godot' or not Path(self.studio.config.get('godot','')).is_file()):raise ValueError('A configured Godot executable is required for engine verification')
        verify_krita=payload.get('verify_krita',False);krita_runtime=None
        if type(verify_krita) is not bool:raise ValueError('Krita roundtrip must be boolean')
        if verify_krita:
            if kind!='ora':raise ValueError('Krita roundtrip requires an OpenRaster export')
            krita_runtime=krita_roundtrip.preflight(self.studio.config.get('krita',krita_roundtrip.DEFAULT_KRITA))
        # Resolve the inputs and options before storing a startable plan, without writing or running tools.
        exporter=NativeExports(self.studio.root,self.studio.assets.media,self.studio.config.get('godot'))
        records=self._native_assets(ids)
        images,glb=exporter._asset_records(kind,records)
        dimensions,_,converted=exporter._images(images)
        resolved=exporter._options(options,images,dimensions)
        for _,image in converted:image.close()
        identifier=uuid.uuid4().hex
        plan={'version':1,'kind':'native','name':resolved['clip']+' · '+kind,'export_kind':kind,'assets':records,
              'source_assets':ids,'options':resolved,'verify_engine':verify,'godot':self.studio.config.get('godot'),
              'verify_krita':verify_krita,'krita':krita_runtime,
              'stages':[],'created_at':time.time()}
        plan['sha256']=fingerprint(plan)
        state={'status':'planned','message':'Native export prepared. Start explicitly; no generation is needed.','attempts':{},'artifacts':[],'stop_requested':False,'review':{'status':'unreviewed'}}
        with self.lock,self.connect() as db:
            db.execute('INSERT INTO budgets(id,allowance) VALUES (?,0)',(identifier,))
            self._insert_materialized(db,identifier,identifier,plan,state)
        project_storage.complete(self.root,identifier,plan)
        return self.get(identifier)

    def _native_assets(self, ids):
        result=[]
        for identifier in ids:
            asset=self.studio.assets.get(identifier);path=self.studio.assets.file(identifier)
            job=self.studio.jobs.get(asset['job_id'])
            media_type={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.glb':'model/gltf-binary'}.get(path.suffix.lower())
            result.append({'id':'asset-'+identifier,'path':path.relative_to(self.studio.assets.media).as_posix(),
                           'filename':asset['filename'],'media_type':media_type,'sha256':asset['sha256'],
                           'metadata':asset,'recipe':self.studio.export_recipe(job) if job else None})
        return result

    def articulated(self, payload):
        from articulated import prepare
        operation=prepare(self.studio,payload);identifier=uuid.uuid4().hex
        plan={'version':1,'kind':'articulated','name':operation['intent']['name'],'operation_plan':operation,'stages':[],'created_at':time.time()}
        plan['sha256']=fingerprint(plan)
        state={'status':'planned','message':'Authored chest prepared. Start builds a hinged BLEND, animated GLB and four inspection views on the CPU.','attempts':{},'artifacts':[],'stop_requested':False,'review':{'status':'unreviewed'}}
        with self.lock,self.connect() as db:
            db.execute('INSERT INTO budgets(id,allowance) VALUES (?,0)',(identifier,))
            self._insert_materialized(db,identifier,identifier,plan,state)
        project_storage.complete(self.root,identifier,plan)
        return self.get(identifier)

    def voice_baseline(self, payload):
        from voice_baseline import prepare
        return prepare(self,payload)

    def _run_articulated(self, identifier, plan):
        if self._get(identifier)['state'].get('stop_requested'):
            self._mutate(identifier,status='stopped',message='Stopped before Blender execution');return
        from articulated import run, recover, _native_job
        directory=self.root/identifier
        if (directory/'articulated-job.json').exists() or (directory/'articulated').exists():
            result=recover(self.studio,identifier,plan['operation_plan'])
        else:
            pending=_native_job(identifier,plan['operation_plan'])
            pending.update(graph={},graph_path='',controls=plan['operation_plan']['options'],batch_count=0,references=[],native_recipe=plan['operation_plan'])
            pending['outputs']=[]
            (self.studio.runs/pending['id']).mkdir(exist_ok=True);self.studio.jobs[pending['id']]=pending;self.studio._save(pending)
            self._attempt(identifier,0,job_id=pending['id'],operation=pending['operation'],status='running')
            result=run(self.studio,identifier,plan['operation_plan'])
        job=result['job']
        job.update(graph={},graph_path='',controls=plan['operation_plan']['options'],batch_count=0,references=[],native_recipe=plan['operation_plan'])
        for output in job['outputs']:
            output['native_path']='articulated/'+('views/' if output['media_type']=='image' else '')+output['filename']
        (self.studio.runs/job['id']).mkdir(exist_ok=True);self.studio.jobs[job['id']]=job;self.studio._save(job)
        self._attempt(identifier,0,job_id=job['id'],operation=job['operation'],status=job['status'])
        artifacts=result['artifacts'];receipt=self.root/identifier/'articulated-job.json'
        if receipt.is_file():artifacts.append({'path':receipt.name,'url':f'/api/production/{identifier}/files/{receipt.name}','role':'execution-receipt'})
        for relative in ('articulated/failure.json','articulated/blender-log.json'):
            if (directory/relative).is_file():artifacts.append({'path':relative,'url':f'/api/production/{identifier}/files/{relative}','role':'execution-diagnostic'})
        self._mutate(identifier,status=job['status'],message=job['message'],artifacts=artifacts,measurements=result['measurements'],limitations=result['limitations'],finished_at=time.time())

    def _run_native(self, identifier, plan):
        if self._get(identifier)['state'].get('stop_requested'):
            self._mutate(identifier,status='stopped',message='Export stopped before execution');return
        from native_exports import NativeExports, krita_roundtrip
        exporter=NativeExports(self.studio.root,self.studio.assets.media,plan.get('godot'))
        directory=self.root/identifier;target=directory/'native'
        if target.exists():
            self._mutate(identifier,status='interrupted',message='An earlier export left files. They are preserved; create a new export to retry.');return
        self._attempt(identifier,0,operation='media.'+plan['export_kind']+'.v1',started_at=time.time())
        result=exporter.execute(target,plan['export_kind'],plan['assets'],plan['options'])
        krita_result=None
        if plan.get('verify_krita'):
            current=krita_roundtrip.preflight(plan['krita']['path'])
            if current['sha256']!=plan['krita']['sha256']:raise ValueError('Krita changed after this export was prepared; prepare a new plan')
            krita_result=krita_roundtrip.execute(target/'layers.ora',target/'krita',plan['krita']['path'])
        engine=None
        if plan['verify_engine']:
            import godot_asset_adapter as godot
            source=next((s['source_snapshot'] for s in result['source_provenance'] if s['media_type']=='model/gltf-binary'),None)
            engine=godot.execute(target,'atlas/manifest.json',target/'engine-checked',plan['godot'],source)
            self.studio._write_json_atomic(target/'engine-verification.json',engine)
        # One portable pack includes original recipes, converted frames, native source and any engine report.
        pack=directory/'export.zip'
        with zipfile.ZipFile(pack,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(target.rglob('*')):
                if path.is_file() and '.godot' not in path.relative_to(target).parts and path.name!='native-sources.zip':archive.write(path,path.relative_to(target).as_posix())
            archive.write(directory/'plan.json','studio-plan.json')
        artifacts=[]
        for path in [pack]+[p for p in target.rglob('*') if p.is_file() and '.godot' not in p.relative_to(target).parts]:
            relative=path.relative_to(directory).as_posix()
            artifacts.append({'path':relative,'url':f'/api/production/{identifier}/files/{relative}','sha256':self._file_hash(path),'bytes':path.stat().st_size,'role':'native-source'})
        self._attempt(identifier,0,status='completed',finished_at=time.time())
        self._mutate(identifier,status='completed',finished_at=time.time(),artifacts=artifacts,
                     measurements=result['measurements'],limitations=result['limitations'],engine=engine,krita=krita_result,
                     message='Native export complete'+(' with actual Godot import/playback evidence.' if engine else ' with a saved and reopened Krita document.' if krita_result else '. Review it in your editor.'))

    @staticmethod
    def _file_hash(path):
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        return digest.hexdigest()

    def start(self, identifier):
        if self._get(identifier)['plan']['kind']=='av':raise ValueError('Render a specific scene revision from the Scene editor')
        with self.studio.lock:
            if getattr(getattr(self.studio, 'backends', None), 'busy', False): raise ValueError('Wait for the backend switch to finish')
            project = self._get(identifier)
            if project['plan']['kind'] == 'comparison' and project['plan']['bundle']['comfy_url'] != self.studio.comfy_url:
                raise ValueError('Switch to this experiment\'s backend before starting it')
            return self._start(identifier)

    def _start(self, identifier):
        self.studio.require_worker()
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE');project=self._get(identifier,db)
            state=project['state'];plan=project['plan']
            if state['status']!='planned':raise ValueError('This experiment has already been started; inspect its existing attempts')
            project_storage.require(self.root,identifier,plan)
            count=len(plan['stages']) if plan['kind']=='comparison' else 0
            budget=db.execute('SELECT * FROM budgets WHERE id=?',(project['root_id'],)).fetchone()
            if budget['reserved']+count>budget['allowance']:raise ValueError('The root experiment generation budget is exhausted, including its branches')
            db.execute('UPDATE budgets SET reserved=reserved+? WHERE id=?',(count,project['root_id']))
            state.update(status='queued',message='Queued on the Studio coordinator',reserved=count)
            db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),identifier))
        self.studio.queue.put(('production',identifier));return self.get(identifier)

    def stop(self, identifier):
        with self.lock:
            project=self._get(identifier)
            if project['plan']['kind']=='av':return self.av.cancel(identifier)
            if project['state']['status'] not in ('queued','running','observing'):raise ValueError('This experiment is not active')
            message='Stop requested. The current owned job may finish; later stages will not start.'
            if project['plan']['kind']=='voice':message='Stop requested. The current voice job may already be publishing retained Workspace outputs.'
            self._mutate(identifier,stop_requested=True,message=message)
        return self.get(identifier)

    def resume(self, identifier):
        project=self._get(identifier)
        if project['plan']['kind']=='voice':
            from voice_baseline import resume
            return resume(self,identifier)
        if project['plan']['kind']=='av':raise ValueError('Inspect the previous scene attempt and explicitly request a new render')
        with self.studio.lock, self.lock:
            project=self._get(identifier)
            project_storage.require(self.root,identifier,project['plan'])
            if self._reconcile_batch_disposition(identifier,project):return self.get(identifier)
            if self._mixed_batch_jobs(project):raise ValueError('Resume observation cannot resolve this mixed batch. Inspect it in Gallery: check known receipts or explicitly record a local disposition before new work')
            if self._reconcile_tracking_terminal(identifier,project):return self.get(identifier)
            self.studio.require_worker()
            if getattr(getattr(self.studio, 'backends', None), 'busy', False): raise ValueError('Wait for the backend switch to finish')
            project=self._get(identifier)
            if project['plan']['kind'] == 'comparison' and project['plan']['bundle']['comfy_url'] != self.studio.comfy_url:
                raise ValueError('Switch to this experiment\'s backend before resuming it')
            if project['state']['status'] not in ('interrupted','uncertain','stopped'):raise ValueError('Only interrupted experiments can resume')
            stop_tokens=[]
            for attempt in project['state'].get('attempts',{}).values():
                job=self.studio.jobs.get(attempt.get('job_id'))
                if job:
                    tokens=self.studio.tracking_stop_tokens(job)
                    if tokens and job.get('status')!='completed':
                        raise ValueError('Resume observation of the retained prompt before authorizing later stages')
                    stop_tokens.extend(tokens)
            state=dict(project['state']);authorized=set(state.get('tracking_stop_authorizations',[]));authorized.update(stop_tokens)
            if stop_tokens: self._mutate(identifier,tracking_stop_authorizations=sorted(authorized),message='Explicit continuation authorized after retained prompt observation')
            self._mutate(identifier,status='queued',stop_requested=False,message='Queued to reconcile known jobs and continue never-started stages')
            self.studio.queue.put(('production',identifier))
        return self.get(identifier)

    def extend_time(self, identifier, payload):
        if not isinstance(payload,dict):raise ValueError('Time extension must be an object')
        with self.studio.lock,self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE');project=self._get(identifier,db);state=project['state']
            if project['plan']['kind']!='comparison' or state['status'] not in ('interrupted','uncertain','stopped'):
                raise ValueError('Only inactive comparisons can extend their time allowance')
            project_storage.require(self.root,identifier,project['plan'])
            clock=production_clock.read(project['plan'],state)
            if type(payload.get('expected_revision')) is not int or payload['expected_revision']!=clock['revision']:
                raise ValueError('Time budget conflict: refresh the comparison before extending it')
            state['time_budget']=production_clock.extend(clock,payload.get('seconds'),payload.get('reason'),time.time())
            state['message']='Time allowance extended explicitly. Reconcile and resume separately; generation reservations and the pinned plan are unchanged.'
            db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),identifier))
        return self.get(identifier)

    @contextmanager
    def _comparison_clock(self, identifier, plan):
        token=uuid.uuid4().hex
        with self.lock:
            project=self._get(identifier)
            clock=production_clock.begin(production_clock.read(plan,project['state']),token)
            self._mutate(identifier,status='running',started_at=project['state'].get('started_at',time.time()),
                         time_budget=clock,stop_reason=None,message='Running the pinned experiment')
        previous=time.monotonic()
        def charge(finish=False):
            nonlocal previous
            with self.lock:
                now=time.monotonic();project=self._get(identifier)
                updated=production_clock.checkpoint(production_clock.read(plan,project['state']),token,now-previous,finish)
                self._mutate(identifier,time_budget=updated)
                previous=now
                return updated
        try:yield charge
        finally:charge(finish=True)

    def _comparison_may_start(self, identifier, charge):
        clock=charge();state=self._get(identifier)['state']
        if state.get('stop_requested'):
            self._mutate(identifier,status='stopped',stop_reason='operator',message='Stopped at your request between stages. Existing outputs and reservations are retained.');return False
        if production_clock.remaining(clock)<=0:
            self._mutate(identifier,status='stopped',stop_reason='time_budget',message='Time allowance exhausted. Known jobs were reconciled; no later stage started. Extend time explicitly, then resume. Outputs, plan and generation reservations are retained.');return False
        return True

    def _attempt(self, identifier, index, **fields):
        with self.lock:
            project=self._get(identifier);state=project['state']
            state.setdefault('attempts',{}).setdefault(str(index),{}).update(fields)
            self._state(identifier,state)

    def finish_voice(self, identifier, job, measurements):
        """Commit a fully published voice take under the same lock used by stop()."""
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE');project=self._get(identifier,db);state=project['state']
            too_late=bool(state.get('stop_requested'))
            message=('Stop arrived after complete Workspace publication; published voice outputs are retained for inspection.' if too_late else 'Dry and scene-ready baseline takes completed; listening review remains open.')
            job.update(status='completed',publication_status='published',message=message)
            if too_late:job['cancellation_too_late']=True
            else:job.pop('cancellation_too_late',None)
            self.studio._save(job);self.studio.jobs[job['id']]=job
            state.update(status='completed',message=message,artifacts=self._voice_artifacts(identifier),measurements=measurements,finished_at=time.time())
            state.setdefault('attempts',{}).setdefault('0',{}).update(status='completed',finished_at=time.time(),message=message)
            if too_late:state['cancellation_too_late']=True
            else:state.pop('cancellation_too_late',None)
            db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),identifier))
        return self.get(identifier)

    def _voice_artifacts(self, identifier):
        from voice_baseline import artifacts
        return artifacts(self,identifier)

    def _mixed_batch_jobs(self, project):
        if project['plan']['kind']!='comparison':return []
        return [(index,job) for index,attempt in project['state'].get('attempts',{}).items()
                if (job:=self.studio.jobs.get(attempt.get('job_id'))) and 'pending_submission' in job and job.get('prompt_ids')]

    def _reconcile_batch_disposition(self, identifier, project):
        # A local disposition releases the local dead end, not a remote outcome,
        # reservation or later stage. Caller holds Studio then Production locks.
        jobs=self._mixed_batch_jobs(project)
        if not jobs or not all(mixed_batch.disposed(job) for _,job in jobs):return False
        state=project['state']
        if state['status'] not in ('interrupted','uncertain','stopped','queued','running','observing','failed'):return False
        records=[{'stage':index,'job_id':job['id'],'status':'abandoned','prompt_ids':list(job['prompt_ids']),
                  'disposition_id':job['abandonment']['event_id']} for index,job in jobs]
        if state['status']=='failed' and state.get('batch_terminal_reconciliation',{}).get('jobs')==records:return True
        state=copy.deepcopy(state);now=time.time()
        for record in records:
            state['attempts'][record['stage']].update(status='abandoned',prompt_ids=record['prompt_ids'],reconciled_at=now)
        state.update(status='failed',message='Mixed batch abandoned locally; remote outcomes remain unknown. New work requires an explicit repair branch. No reservation was refunded or later stage authorized.',
                     batch_terminal_reconciliation={'version':1,'recorded_at':now,'jobs':records,'new_work_authorized':False})
        self._state(identifier,state)
        return True

    def _tracking_terminal_records(self, project):
        if project['plan']['kind']!='comparison':return []
        records=[]
        for index,attempt in project['state'].get('attempts',{}).items():
            job=self.studio.jobs.get(attempt.get('job_id'))
            if job and self.studio.tracking_stop_tokens(job) and submission_evidence.terminal_failure(job):
                records.append({'stage':index,'job_id':job['id'],'status':job['status'],'prompt_ids':list(job['prompt_ids'])})
        return records

    def _reconcile_tracking_terminal(self, identifier, project):
        # Caller holds Studio then Production locks. This is a single local state
        # write, not observation, cancellation, continuation consent or new work.
        state=project['state']
        if state['status'] not in ('interrupted','uncertain','stopped','queued','running','observing','failed'):return False
        records=self._tracking_terminal_records(project)
        if not records:return False
        if state['status']=='failed' and state.get('tracking_terminal_reconciliation',{}).get('jobs')==records:return True
        state=copy.deepcopy(state);now=time.time()
        for record in records:
            state['attempts'][record['stage']].update(status=record['status'],prompt_ids=record['prompt_ids'],reconciled_at=now)
        state.update(status='failed',message='Retained prompt observation ended failed or partial. An explicit repair branch is required; no later stage or retry was authorized.',
                     tracking_terminal_reconciliation={'version':1,'recorded_at':now,'jobs':records,'new_work_authorized':False})
        self._state(identifier,state)
        return True

    def _tracking_continuation_allowed(self, identifier):
        # Match resume's lock order; never retain these locks during backend I/O.
        with self.studio.lock, self.lock:
            project=self._get(identifier)
            if self._reconcile_batch_disposition(identifier,project):return False
            if self._mixed_batch_jobs(project):
                self._mutate(identifier,status='uncertain',message='A mixed batch retains an unknown submission. Inspect its known receipts or explicitly record a local disposition; no later stage was authorized.');return False
            if self._reconcile_tracking_terminal(identifier,project):return False
            state=project['state'];authorized=set(state.get('tracking_stop_authorizations',[]))
            for attempt in state.get('attempts',{}).values():
                job=self.studio.jobs.get(attempt.get('job_id'))
                if job and set(self.studio.tracking_stop_tokens(job))-authorized:
                    self._mutate(identifier,status='uncertain',message='A retained stop-tracking event has not authorized Production continuation. No later stage was submitted.');return False
            return True

    def run(self, identifier):
        project=self._get(identifier);plan=project['plan']
        if fingerprint({k:v for k,v in plan.items() if k!='sha256'})!=plan['sha256']:raise ValueError('Experiment plan changed')
        project_storage.require(self.root,identifier,plan)
        if plan['kind']=='voice' and project['state']['status'] in ('completed','failed','cancelled','stopped'):return
        if not self._tracking_continuation_allowed(identifier):return
        if plan['kind']=='comparison':
            with self._comparison_clock(identifier,plan) as charge:return self._run_comparison(identifier,plan,charge)
        self._mutate(identifier,status='running',started_at=project['state'].get('started_at',time.time()),message='Running the pinned experiment')
        if plan['kind']=='av':return self.av.run(identifier)
        if plan['kind']=='voice':
            from voice_baseline import run
            return run(self,identifier,plan)
        if plan['kind']=='native':return self._run_native(identifier,plan)
        if plan['kind']=='articulated':return self._run_articulated(identifier,plan)

    def _run_comparison(self, identifier, plan, charge):
        self.studio.check_production_bundle(plan['bundle'])
        for index,stage in enumerate(plan['stages']):
            project_storage.require(self.root,identifier,plan)
            if not self._tracking_continuation_allowed(identifier):return
            # Inspect retained evidence BEFORE a time/stop gate. A deadline is
            # not permission to discard a known prompt or repeat an unknown POST.
            job_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'asset-studio:{identifier}:stage:{index}'))
            self._attempt(identifier,index,job_id=job_id,operation=stage['operation'])
            job=self.studio.jobs.get(job_id)
            if job:
                if submission_evidence.never_submitted(job):
                    if not self._comparison_may_start(identifier,charge):return
                    # Re-enter the FIRST submission using the same stage ID and
                    # reservation, only after current pins and saved bytes agree.
                    self.studio.check_production_bundle(plan['bundle'])
                    prepared=self.studio.prepare(stage['request'])
                    if (fingerprint(prepared[1])!=stage['graph_sha256'] or fingerprint(job['graph'])!=stage['graph_sha256']
                            or job.get('controls')!=prepared[3] or job.get('batch_count')!=prepared[4]
                            or job.get('preset_id')!=prepared[0]['id']):
                        raise ValueError('The recovered recipe changed; create an explicit branch')
                    preset=prepared[0]
                    seeds=([preset['seed']] if preset.get('seed') else [])+preset.get('bindings_extra',{}).get('seed',[])
                    prompts={key:([preset[key]] if preset.get(key) else [])+preset.get('bindings_extra',{}).get(key,[]) for key in ('positive','negative')}
                    if job.get('seed_bindings')!=seeds or job.get('prompt_bindings')!=prompts or type(job.get('batch_count')) is not int:
                        raise ValueError('The recovered recipe bindings changed; create an explicit branch')
                    if job.get('comfy_url')!=plan['bundle']['comfy_url'] or job.get('comfy_root')!=str(self.studio.comfy_root):
                        raise ValueError('The recovered job belongs to a different backend')
                    with self.studio.lock:
                        if not submission_evidence.never_submitted(job):raise ValueError('Recovered job disposition changed; no submission was authorized')
                        job['status']='not_submitted'
                elif job['status']=='uncertain' or (job['status']=='queued' and (job.get('prompt_ids') or job.get('submissions') or 'pending_submission' in job)):
                    if 'pending_submission' in job or not job.get('prompt_ids'):
                        self._mutate(identifier,status='uncertain',message='A submission outcome is unknown. No duplicate or later stage was submitted.');return
                    try:self.studio._resume(job)
                    except Exception as exc:self.studio.record_job_failure(job,exc)
                elif job['status'] in ('failed','partial','abandoned'):
                    self._mutate(identifier,status='failed',message='A recorded stage failed. Branch with an explicit repair; no automatic generation retry.');return
                elif job['status'] not in ('completed','queued'):
                    self._mutate(identifier,status='uncertain',message='A stage has unresolved execution state. Inspect its known prompt ID.');return
            else:
                if not self._comparison_may_start(identifier,charge):return
                # Write the deterministic ID before creating a job, so a crash between stores is reconcilable.
                self.studio.check_production_bundle(plan['bundle'])
                prepared=self.studio.prepare(stage['request'])
                if fingerprint(prepared[1])!=stage['graph_sha256']:raise ValueError('The resolved recipe changed; create an explicit branch')
                if not self._tracking_continuation_allowed(identifier):return
                project_storage.require(self.root,identifier,plan)
                self.studio.create_job(stage['request'],enqueue=False,job_id=job_id)
                job=self.studio.jobs[job_id]
                job['project_id']=identifier;self.studio._save(job)
            if job['status'] in ('queued','not_submitted'):
                if not self._comparison_may_start(identifier,charge):
                    with self.studio.lock:
                        if submission_evidence.never_submitted(job):job['status']='not_submitted';self.studio._save(job)
                    return
                self._attempt(identifier,index,started_at=time.time())
                project_storage.require(self.root,identifier,plan)
                try:self.studio._run(job)
                except Exception as exc:
                    self.studio.record_job_failure(job,exc)
            self._attempt(identifier,index,finished_at=time.time(),status=job['status'],prompt_ids=job.get('prompt_ids',[]))
            if not self._tracking_continuation_allowed(identifier):return
            if job['status']!='completed':
                self._mutate(identifier,status='uncertain' if job['status']=='uncertain' else 'failed',message=job['message']);return
        artifacts=self.contact_sheet(identifier)
        self._mutate(identifier,status='awaiting_review',finished_at=time.time(),artifacts=artifacts,message='Comparison finished. Review candidates and record your choice.')

    def contact_sheet(self, identifier):
        from PIL import Image,ImageDraw,ImageOps
        project=self._get(identifier);records=[]
        for index,stage in enumerate(project['plan']['stages']):
            attempt=project['state']['attempts'].get(str(index),{})
            job=self.studio.jobs.get(attempt.get('job_id'),{})
            for output in job.get('outputs',[]):
                if output.get('asset_id') and output.get('media_type')=='image':records.append((stage['label'],output['asset_id']))
        if not records:return []
        records=records[:16];columns=min(4,len(records));rows=(len(records)+columns-1)//columns
        sheet=Image.new('RGB',(columns*320,rows*356),'#20222c');draw=ImageDraw.Draw(sheet)
        for i,(label,asset_id) in enumerate(records):
            with Image.open(self.studio.assets.file(asset_id)) as src:thumb=ImageOps.contain(src.convert('RGB'),(304,320))
            x=(i%columns)*320;y=(i//columns)*356
            sheet.paste(thumb,(x+(320-thumb.width)//2,y+(320-thumb.height)//2));draw.text((x+12,y+330),label,fill='white')
        target=self.root/identifier/'comparison.png';sheet.save(target)
        self.studio._write_json_atomic(target.with_suffix('.json'),{'labels':records,'note':'Thumbnails only; inspect originals for detail. Labels do not imply preference.'})
        return [{'path':target.name,'url':f'/api/production/{identifier}/files/{target.name}','sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'role':'comparison'}]

    def review(self, identifier, payload):
        if not isinstance(payload,dict):raise ValueError('Review command must be an object')
        if 'action' in payload:return self.reviews.command(identifier,payload)
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM comparison_reviews WHERE project_id=?',(identifier,)).fetchone():
                raise ValueError('Use Review desk for this study; legacy selection cannot overwrite its revisioned evidence')
            project=self._get(identifier,db)
            if project['state']['status'] not in ('awaiting_review','reviewed'):raise ValueError('Review is available after a completed comparison')
            selected=payload.get('asset_id');notes=payload.get('notes','')
            if not isinstance(notes,str) or len(notes)>8000:raise ValueError('Review notes must be text up to 8000 characters')
            candidates=[o.get('asset_id') for s in self.public(project)['stages'] for o in (s['job'] or {}).get('outputs',[])]
            if selected is not None and selected not in candidates:raise ValueError('Choose an output from this experiment')
            reviewer=payload.get('reviewer','local-user')
            if reviewer not in ('local-user','local-agent'):raise ValueError('Identify the local reviewer')
            project['state'].update(status='reviewed',review={'status':'selected' if selected else 'needs_work','asset_id':selected,'notes':notes,'reviewer':reviewer,'at':time.time()},message='Creative review recorded separately from model terms and engine checks.')
            db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(project['state']),identifier))
        return self.get(identifier)

    def file(self, identifier, relative):
        if relative.startswith('reviews/'):return self.reviews.file(identifier,relative)
        project=self._get(identifier)
        if project['plan']['kind']=='av':return self.av.file(identifier,relative)
        base=(self.root/project['id']).resolve();path=(base/relative).resolve()
        if not path.is_relative_to(base) or not path.is_file():raise ValueError('Artifact unavailable')
        allowed={a['path'] for a in project['state'].get('artifacts',[])}|{'plan.json','comparison.json'}
        if relative not in allowed:raise ValueError('This file is not a published experiment artifact')
        if project['plan']['kind']=='voice' and relative!='plan.json':
            artifact=next((a for a in project['state'].get('artifacts',[]) if a['path']==relative),None)
            if not artifact or self._file_hash(path)!=artifact['sha256']:raise ValueError('Voice artifact changed')
        return path
