"""Versioned scenes in the existing Production database and owned worker queue."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import shutil
import time
import uuid
import zipfile

from studio_av import project as av
from studio_av.render import render, validate_media, probe, tool, RenderCancelled

ACTIVE = ('queued','running')
EDITABLE = {'shots':{'source_in','frames','transition_frames'},
            'audio':{'bus','start_sample','source_sample','samples','gain_db','fade_in','fade_out','mute'},
            'overlays':{'start','frames','x','y','width','height','opacity'}}


class AVProjects:
    def __init__(self, production):
        self.production=production;self.studio=production.studio
        with production.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS av_documents(project_id TEXT PRIMARY KEY REFERENCES projects(id),revision INTEGER NOT NULL,document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS av_events(project_id TEXT REFERENCES projects(id),revision INTEGER NOT NULL,event TEXT NOT NULL,document TEXT NOT NULL,PRIMARY KEY(project_id,revision));
                CREATE TABLE IF NOT EXISTS av_renders(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id),revision INTEGER NOT NULL,snapshot TEXT NOT NULL,status TEXT NOT NULL,details TEXT NOT NULL,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS av_exports(project_id TEXT REFERENCES projects(id),revision INTEGER NOT NULL,artifact TEXT NOT NULL,PRIMARY KEY(project_id,revision));
            ''')
            for row in db.execute("SELECT id,details FROM av_renders WHERE status IN ('queued','running')").fetchall():
                details=json.loads(row['details']);details['message']='Studio restarted; inspect retained output and explicitly request a new render.'
                db.execute("UPDATE av_renders SET status='interrupted',details=? WHERE id=?",(json.dumps(details),row['id']))

    def executables(self):
        result={name:self.studio.config.get(name,'') for name in ('ffmpeg','ffprobe')}
        for name in result:tool(name,result)
        return result

    def capabilities(self):
        missing=[name for name in ('ffmpeg','ffprobe') if not isinstance(self.studio.config.get(name),str)
                 or not Path(self.studio.config[name]).is_absolute() or not Path(self.studio.config[name]).is_file()]
        return {'render_ready':not missing,'missing_tools':missing,
                'supported':['PNG / MP4 / 48 kHz PCM WAV','cuts','dissolves','static overlays','audio trim / gain / fades / mix','revision history','owned render cancellation'],
                'model_inference':False,'max_seconds':120}

    @staticmethod
    def actor(payload):
        actor=payload.get('actor','user');av.need(actor in ('user','agent','cli'),'Unknown scene actor');return actor

    def directory(self, identifier):
        project=self.production._get(identifier)
        av.need(project['plan']['kind']=='av','This project is not an AV scene')
        directory=(self.production.root/identifier).resolve()
        av.need(directory.is_relative_to(self.production.root),'Scene directory escapes project storage')
        return directory

    @staticmethod
    def _read(db, identifier):
        row=db.execute('SELECT document FROM av_documents WHERE project_id=?',(identifier,)).fetchone()
        av.need(row is not None,'Unknown AV scene');return json.loads(row['document'])

    @staticmethod
    def _expected(document, payload):
        av.need(type(payload.get('expected_revision')) is int and payload['expected_revision']==document['revision'],
                'Scene conflict: reload the current revision before applying this change')

    def _save(self, db, identifier, document, action, actor, summary):
        raw=json.dumps(document);revision=document['revision']
        db.execute('INSERT INTO av_documents VALUES (?,?,?) ON CONFLICT(project_id) DO UPDATE SET revision=excluded.revision,document=excluded.document',
                   (identifier,revision,raw))
        event={'revision':revision,'action':action,'actor':actor,'at':time.time(),'summary':summary}
        db.execute('INSERT INTO av_events VALUES (?,?,?,?)',(identifier,revision,json.dumps(event),raw))

    def list(self):
        with self.production.connect() as db:
            rows=db.execute('SELECT project_id FROM av_documents ORDER BY rowid DESC').fetchall()
        scenes=[self.inspect(row['project_id']) for row in rows]
        return {'projects':[{'id':s['id'],'name':s['name'],'revision':s['revision'],'status':s['status'],
                             'render_stale':bool(s['render'] and s['render']['stale']),
                             'preview_url':s['render']['preview_url'] if s['render'] else None} for s in scenes],
                'capabilities':self.capabilities()}

    def inspect(self, identifier):
        self.directory(identifier)
        with self.production.connect() as db:
            db.execute('BEGIN');document=self._read(db,identifier)
            state=self.production._get(identifier,db)['state']
            history=[json.loads(r['event']) for r in db.execute('SELECT event FROM av_events WHERE project_id=? ORDER BY revision DESC LIMIT 100',(identifier,))]
            row=db.execute('SELECT * FROM av_renders WHERE project_id=? ORDER BY created DESC LIMIT 1',(identifier,)).fetchone()
            preview=db.execute("SELECT * FROM av_renders WHERE project_id=? AND status='completed' ORDER BY created DESC LIMIT 1",(identifier,)).fetchone()
        attempt=None
        if row:
            details=json.loads(row['details']);preview_details=json.loads(preview['details']) if preview else {}
            preview_artifact=next((a for a in preview_details.get('artifacts',[]) if a['role']=='preview'),None)
            attempt={'id':row['id'],'status':row['status'],'revision':row['revision'],'preview_revision':preview['revision'] if preview else None,
                     'stale':not preview or preview['revision']!=document['revision'],'preview_url':preview_artifact['url'] if preview_artifact else None,
                     'progress':details.get('progress',0),'message':details.get('message',''),'artifacts':details.get('artifacts',[])}
        return {'id':identifier,'name':document['project']['name'],'revision':document['revision'],'project':document['project'],
                'timing':av.validate(document['project']),'sources':[{**s,'url':f'/api/av/{identifier}/sources/{s["key"]}'} for s in document['sources']],
                'history':history,'render':attempt,'status':state['status'],'capabilities':self.capabilities()}

    def create(self, payload):
        av.fields(payload,('action','name','asset_ids'),('fps','size','frames_per_shot','actor'))
        av.need(payload['action']=='create','Unknown scene action');actor=self.actor(payload);av.text(payload['name'])
        ids=payload['asset_ids'];av.need(isinstance(ids,list) and 1<=len(ids)<=48 and all(isinstance(i,str) for i in ids) and len(set(ids))==len(ids),'Select distinct scene sources')
        assets=[self.studio.assets.get(i) for i in ids]
        av.need(not any(a['trashed_at'] for a in assets),'Restore trashed scene sources first')
        av.need(sum(a['bytes'] for a in assets)<=av.MAX_TOTAL,'Scene source byte budget exceeded')
        tools=self.executables();frames=payload.get('frames_per_shot',72);av.number(frames,1,7200,'shot frames',True)
        project={'schema_version':1,'name':payload['name'],'fps':payload.get('fps',[24,1]),'size':payload.get('size',[640,360]),'sample_rate':48000,
                 'assets':{},'shots':[],'overlays':[],'audio':[],'master_gain_db':0}
        # Validate numeric settings before any file writes or division.
        trial=copy.deepcopy(project);trial['assets']={'test':{'kind':'image','path':'test.png','sha256':'0'*64}}
        trial['shots']=[{'id':'test','asset':'test','source_in':0,'frames':frames,'transition_frames':0}];av.validate(trial)
        identifier=uuid.uuid4().hex;directory=self.production.root/identifier;directory.mkdir()
        (directory/'inputs').mkdir();(directory/'.incomplete-create').write_text('Source intake is incomplete. No render was requested.\n')
        sources=[];audio=[]
        try:
            av.need(shutil.disk_usage(directory).free>=sum(a['bytes'] for a in assets)+2*1024**3,'Scene intake needs source space plus 2 GiB free')
            for i,asset in enumerate(assets):
                original=self.studio.assets.file(asset['id']);kind=asset['media_type'];suffix=original.suffix.lower()
                av.need((kind,suffix) in (('image','.png'),('video','.mp4'),('audio','.wav')),'Scenes accept PNG, MP4 and 48 kHz PCM WAV; convert other media explicitly first')
                key='source'+str(i);relative=f'inputs/{key}{suffix}';target=directory/relative
                with original.open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,1024**2)
                av.need(av.file_hash(target)==asset['sha256'],'Scene source changed during intake')
                project['assets'][key]={'path':relative,'kind':kind,'sha256':asset['sha256']}
                sources.append({'key':key,'asset_id':asset['id'],'filename':asset['filename'],'kind':kind,'sha256':asset['sha256'],'bytes':target.stat().st_size})
                if kind=='audio':audio.append(key)
                else:
                    count=frames
                    if kind=='video':
                        info=probe(target,kind,tools);duration=float(info.get('format',{}).get('duration',0))
                        av.need(math.isfinite(duration) and duration>0,'Video duration is unavailable')
                        count=min(frames,math.floor(duration*project['fps'][0]/project['fps'][1]+1e-6))
                    project['shots'].append({'id':'shot'+str(i),'asset':key,'source_in':0,'frames':count,'transition_frames':0})
            timing=av.validate(project,directory)
            import wave
            for i,key in enumerate(audio):
                with wave.open(str(directory/project['assets'][key]['path']),'rb') as w:count=min(w.getnframes(),timing['samples'])
                project['audio'].append({'id':'audio'+str(i),'asset':key,'bus':'music','start_sample':0,'source_sample':0,'samples':count,
                                         'gain_db':0,'fade_in':0,'fade_out':0,'mute':False})
            validate_media(project,directory,tools)
            plan={'version':1,'kind':'av','name':project['name'],'source_assets':ids,'stages':[],'created_at':time.time()}
            from production import fingerprint
            plan['sha256']=fingerprint(plan)
            state={'status':'planned','message':'Scene created. Edits are saved revisions; render explicitly.','attempts':{},'artifacts':[],'stop_requested':False,'review':{'status':'unreviewed'}}
            document={'revision':0,'project':project,'sources':sources}
            self.studio._write_json_atomic(directory/'plan.json',plan)
            with self.production.connect() as db:
                db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO budgets(id,allowance) VALUES (?,0)',(identifier,))
                db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',(identifier,identifier,json.dumps(plan),json.dumps(state),time.time()))
                self._save(db,identifier,document,'create',actor,'Create scene from registered source assets')
            (directory/'.incomplete-create').unlink()
        except Exception as exc:
            (directory/'intake-failure.txt').write_text(str(exc)[:1000],encoding='utf-8');raise
        return self.inspect(identifier)

    def _edited(self, document, payload, directory):
        result=copy.deepcopy(document);project=result['project'];action=payload['action'];section=payload.get('section')
        av.need((isinstance(section,str) and section in EDITABLE) or action=='move','Choose a supported scene section')
        if action=='move':
            clips=project['shots'];index=payload['index'];av.number(index,0,len(clips)-1,'shot position',True)
            found=[c for c in clips if c['id']==payload['clip_id']];av.need(len(found)==1,'Unknown shot')
            clips.remove(found[0]);clips.insert(index,found[0]);return result
        clips=project[section]
        if action=='add':
            key=payload['asset_key'];av.need(isinstance(key,str),'Choose a scene source');asset=project['assets'].get(key);av.need(asset is not None,'Unknown scene source')
            identifier='clip-'+uuid.uuid4().hex[:16];timing=av.validate(project)
            if section=='shots':
                av.need(asset['kind'] in ('image','video'),'Shots require visual media');frames=72
                if asset['kind']=='video':
                    info=probe(av.safe_path(directory,asset['path']),'video',self.executables())
                    frames=min(frames,math.floor(float(info.get('format',{}).get('duration',0))*project['fps'][0]/project['fps'][1]+1e-6))
                clip={'id':identifier,'asset':key,'source_in':0,'frames':frames,'transition_frames':0}
            elif section=='overlays':
                av.need(asset['kind']=='image','Static overlays require PNG sources')
                from PIL import Image
                with Image.open(av.safe_path(directory,asset['path'])) as image:width,height=image.size
                scale=min(1,200/width,project['size'][1]/height);width=max(1,int(width*scale));height=max(1,int(height*scale))
                clip={'id':identifier,'asset':key,'start':0,'frames':timing['frames'],'x':0,'y':0,'width':width,'height':height,'opacity':1}
            else:
                av.need(asset['kind']=='audio','Audio clips require PCM WAV')
                import wave
                with wave.open(str(av.safe_path(directory,asset['path'])),'rb') as w:count=min(w.getnframes(),timing['samples'])
                clip={'id':identifier,'asset':key,'bus':'music','start_sample':0,'source_sample':0,'samples':count,'gain_db':0,'fade_in':0,'fade_out':0,'mute':False}
            clips.append(clip);return result
        found=[c for c in clips if c['id']==payload['clip_id']];av.need(len(found)==1,'Unknown scene clip');clip=found[0]
        if action in ('edit','preview'):
            changes=payload['changes'];av.need(isinstance(changes,dict) and changes and set(changes)<=EDITABLE[section],'Unsupported clip changes');clip.update(changes)
        elif action=='remove':clips.remove(clip)
        elif action=='split':
            av.need(section in ('shots','audio'),'Split a shot or audio clip');at=payload['at'];length=clip['frames'] if section=='shots' else clip['samples']
            av.number(at,1,length-1,'split offset',True);second=copy.deepcopy(clip);second['id']='clip-'+uuid.uuid4().hex[:16]
            if section=='shots':
                av.need(at>clip['transition_frames'],'Split must follow the incoming dissolve')
                second['frames']=length-at;second['transition_frames']=0;clip['frames']=at
                if project['assets'][clip['asset']]['kind']=='video':second['source_in']+=at
            else:
                av.need(at>=clip['fade_in'] and length-at>=clip['fade_out'],'Split outside the existing fade regions')
                second.update(start_sample=clip['start_sample']+at,source_sample=clip['source_sample']+at,samples=length-at,fade_in=0)
                clip.update(samples=at,fade_out=0)
            clips.insert(clips.index(clip)+1,second)
        return result

    def command(self, identifier, payload):
        av.need(isinstance(payload,dict),'Scene command must be an object');action=payload.get('action');actor=self.actor(payload)
        fields={'edit':('section','clip_id','changes'),'preview':('section','clip_id','changes'),'move':('clip_id','index'),
                'split':('section','clip_id','at'),'add':('section','asset_key'),'remove':('section','clip_id'),
                'restore':('source_revision',),'render':(),'export':(),'cancel':('render_id',)}
        av.need(isinstance(action,str) and action in fields,'Unsupported scene action')
        av.fields(payload,('action',)+fields[action]+(() if action=='cancel' else ('expected_revision',)),('actor',))
        if action=='cancel':return self.cancel(identifier,payload['render_id'])
        directory=self.directory(identifier)
        with self.production.connect() as db:document=self._read(db,identifier)
        self._expected(document,payload)
        if action=='render':return self.request_render(identifier,payload)
        if action=='export':return self.export(identifier,payload)
        if action=='restore':
            av.number(payload['source_revision'],0,document['revision'],'source revision',True)
            with self.production.connect() as db:row=db.execute('SELECT document FROM av_events WHERE project_id=? AND revision=?',(identifier,payload['source_revision'])).fetchone()
            av.need(row is not None,'Unknown scene revision');changed=json.loads(row['document'])
        else:changed=self._edited(document,payload,directory)
        timing,_=validate_media(changed['project'],directory,self.executables())
        if action=='preview':return {'revision':document['revision'],'project':changed['project'],'timing':timing,'proposal':True,'generation_submitted':False}
        with self.production.lock,self.production.connect() as db:
            db.execute('BEGIN IMMEDIATE');current=self._read(db,identifier);self._expected(current,payload)
            av.need(current['revision']<500,'Scene revision budget reached; export and branch explicitly')
            av.validate(changed['project'],directory);changed['revision']=current['revision']+1
            self._save(db,identifier,changed,action,actor,action.title()+' '+str(payload.get('clip_id',payload.get('section',payload.get('source_revision','')))))
        return self.inspect(identifier)

    def request_render(self, identifier, payload):
        self.executables();directory=self.directory(identifier)
        with self.production.connect() as db:document=self._read(db,identifier)
        self._expected(document,payload);av.validate(document['project'],directory)
        av.need(shutil.disk_usage(directory).free>=2*1024**3,'Render needs at least 2 GiB free')
        attempt=uuid.uuid4().hex
        with self.studio.lock,self.production.lock,self.production.connect() as db:
            db.execute('BEGIN IMMEDIATE');document=self._read(db,identifier);self._expected(document,payload)
            active=db.execute("SELECT id FROM av_renders WHERE project_id=? AND status IN ('queued','running')",(identifier,)).fetchone()
            av.need(active is None,'This scene already has an active render')
            details={'message':'Queued on the Studio worker','progress':0,'stop_requested':False,'artifacts':[]}
            db.execute('INSERT INTO av_renders VALUES (?,?,?,?,?,?,?)',(attempt,identifier,document['revision'],json.dumps(document),'queued',json.dumps(details),time.time()))
            state=self.production._get(identifier,db)['state'];state.update(status='queued',message=f'Render revision {document["revision"]} queued',stop_requested=False)
            state.setdefault('attempts',{})[attempt]={'render_id':attempt,'revision':document['revision'],'status':'queued'}
            db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),identifier))
        self.studio.queue.put(('production',identifier));return self.inspect(identifier)

    def _render_state(self, attempt, status=None, **fields):
        with self.production.lock,self.production.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM av_renders WHERE id=?',(attempt,)).fetchone();av.need(row is not None,'Unknown render')
            details=json.loads(row['details']);details.update(fields);status=status or row['status']
            db.execute('UPDATE av_renders SET status=?,details=? WHERE id=?',(status,json.dumps(details),attempt))
            state=self.production._get(row['project_id'],db)['state'];state.update(status=status,message=details['message'])
            state.setdefault('attempts',{}).setdefault(attempt,{}).update(status=status,revision=row['revision'],render_id=attempt)
            if fields.get('artifacts') is not None:state['artifacts']=fields['artifacts']
            db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps(state),row['project_id']))

    def cancel(self, identifier, attempt=None):
        self.directory(identifier)
        with self.production.lock,self.production.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute("SELECT * FROM av_renders WHERE project_id=? AND status IN ('queued','running') ORDER BY created DESC LIMIT 1",(identifier,)).fetchone()
            av.need(row is not None and (attempt is None or row['id']==attempt),'That render is no longer active')
            details=json.loads(row['details']);details.update(stop_requested=True,message='Stopping the owned render; source media and incomplete output are retained')
            db.execute('UPDATE av_renders SET details=? WHERE id=?',(json.dumps(details),row['id']))
        return self.inspect(identifier)

    def _artifacts(self, identifier, attempt):
        root=self.directory(identifier);out=root/'renders'/attempt;result=[]
        if not out.exists():return result
        for filename in ('picture.mp4','mix.wav','preview.mp4','receipt.json','ffmpeg.log','mux.log','project-source.json','project-snapshot.json','render-plan.json','.incomplete'):
            path=out/filename
            if not path.is_file():continue
            relative=path.relative_to(root).as_posix()
            result.append({'path':relative,'url':f'/api/production/{identifier}/files/{relative}','sha256':av.file_hash(path),'bytes':path.stat().st_size,
                           'role':'preview' if filename=='preview.mp4' else 'audio' if filename=='mix.wav' else 'evidence'})
        return result

    def run(self, identifier):
        with self.production.connect() as db:row=db.execute("SELECT * FROM av_renders WHERE project_id=? AND status='queued' ORDER BY created LIMIT 1",(identifier,)).fetchone()
        av.need(row is not None,'No queued scene render; inspect previous attempts before requesting another')
        attempt=row['id'];document=json.loads(row['snapshot']);directory=self.directory(identifier);out=directory/'renders'/attempt
        def cancelled():
            with self.production.connect() as db:current=db.execute('SELECT details FROM av_renders WHERE id=?',(attempt,)).fetchone()
            return bool(json.loads(current['details']).get('stop_requested'))
        def progress(message):
            percent={'Inspecting pinned sources':5,'Rendering picture and PCM mix':30,'Muxing preview':80,'Verifying output':95}.get(message,0)
            self._render_state(attempt,'running',message=message,progress=percent)
        try:
            if cancelled():raise RenderCancelled('Render cancelled before execution')
            self._render_state(attempt,'running',message='Starting pinned scene render',progress=1)
            receipt=render(document['project'],directory,out,executables=self.executables(),cancel=cancelled,progress=progress)
            if cancelled():raise RenderCancelled('Render cancelled before publication')
            job={'id':attempt,'operation':'native.av-preview.v1','project_id':identifier,'status':'completed','created_at':row['created'],
                 'preset_id':'av-preview','preset_name':document['project']['name'],'controls':{},'batch_count':1,'prompt_ids':[],'submissions':[],
                 'parent_assets':[s['asset_id'] for s in document['sources']],'references':[],'graph_path':'','graph':{},
                 'native_recipe':{'scene_id':identifier,'revision':row['revision'],'project':document['project'],'source_assets':document['sources'],'receipt':receipt},
                 'message':f'CPU scene preview from revision {row["revision"]}; not creative acceptance',
                 'outputs':[{'filename':name,'native_path':f'renders/{attempt}/{name}','type':'output','media_type':kind} for name,kind in (('preview.mp4','video'),('mix.wav','audio'))]}
            self.studio.index_outputs(job)
            av.need(all(o.get('asset_id') and not o.get('snapshot_error') for o in job['outputs']),'Preview rendered but Workspace publication failed; inspect retained output')
            (self.studio.runs/attempt).mkdir(exist_ok=True)
            with self.studio.lock:self.studio._save(job);self.studio.jobs[attempt]=job
            self._render_state(attempt,'completed',message=f'Preview completed for revision {row["revision"]}',progress=100,
                               artifacts=self._artifacts(identifier,attempt),receipt=receipt,job_id=attempt)
        except RenderCancelled as exc:self._render_state(attempt,'cancelled',message=str(exc),artifacts=self._artifacts(identifier,attempt))
        except Exception as exc:self._render_state(attempt,'failed',message=str(exc)[:500],artifacts=self._artifacts(identifier,attempt))

    def source(self, identifier, key):
        directory=self.directory(identifier)
        with self.production.connect() as db:document=self._read(db,identifier)
        asset=document['project']['assets'].get(key);av.need(asset is not None,'Unknown scene source')
        path=av.safe_path(directory,asset['path']);av.need(av.file_hash(path)==asset['sha256'],'Scene source changed');return path

    def file(self, identifier, relative):
        directory=self.directory(identifier)
        if relative=='plan.json':return av.safe_path(directory,relative)
        with self.production.connect() as db:
            artifacts=[json.loads(r['artifact']) for r in db.execute('SELECT artifact FROM av_exports WHERE project_id=?',(identifier,))]
            for row in db.execute('SELECT details FROM av_renders WHERE project_id=?',(identifier,)):artifacts.extend(json.loads(row['details']).get('artifacts',[]))
        artifact=next((a for a in artifacts if a['path']==relative),None);av.need(artifact is not None,'Unknown scene artifact')
        path=av.safe_path(directory,relative);av.need(av.file_hash(path)==artifact['sha256'],'Scene artifact changed');return path

    def export(self, identifier, payload):
        directory=self.directory(identifier)
        with self.production.connect() as db:
            document=self._read(db,identifier);self._expected(document,payload)
            row=db.execute('SELECT artifact FROM av_exports WHERE project_id=? AND revision=?',(identifier,document['revision'])).fetchone()
            history=[json.loads(r['event']) for r in db.execute('SELECT event FROM av_events WHERE project_id=? ORDER BY revision',(identifier,))]
        if row:
            artifact=json.loads(row['artifact']);self.file(identifier,artifact['path']);return {**self.inspect(identifier),'export_url':artifact['url']}
        av.validate(document['project'],directory)
        sources=[av.safe_path(directory,a['path']) for a in document['project']['assets'].values()]
        av.need(shutil.disk_usage(directory).free>=sum(p.stat().st_size for p in sources)+2*1024**3,'Scene export needs source space plus 2 GiB free')
        relative=f'exports/revision-{document["revision"]}-{uuid.uuid4().hex}.zip';target=directory/relative;target.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_STORED) as pack:
            pack.writestr('project.json',json.dumps(document['project'],indent=2));pack.writestr('sources.json',json.dumps(document['sources'],indent=2));pack.writestr('history.json',json.dumps(history,indent=2))
            for asset in document['project']['assets'].values():
                path=av.safe_path(directory,asset['path']);av.need(av.file_hash(path)==asset['sha256'],'Source changed during export');pack.write(path,asset['path'])
        import hashlib
        with zipfile.ZipFile(target) as pack:
            for asset in document['project']['assets'].values():
                hashed=hashlib.sha256()
                with pack.open(asset['path']) as stream:
                    for chunk in iter(lambda:stream.read(1024**2),b''):hashed.update(chunk)
                av.need(hashed.hexdigest()==asset['sha256'],'Source changed while the scene pack was written; incomplete pack retained')
        artifact={'path':relative,'url':f'/api/production/{identifier}/files/{relative}?download','sha256':av.file_hash(target),'bytes':target.stat().st_size,'role':'scene-source-pack'}
        with self.production.connect() as db:
            db.execute('BEGIN IMMEDIATE');self._expected(self._read(db,identifier),payload)
            db.execute('INSERT OR IGNORE INTO av_exports VALUES (?,?,?)',(identifier,document['revision'],json.dumps(artifact)))
            artifact=json.loads(db.execute('SELECT artifact FROM av_exports WHERE project_id=? AND revision=?',(identifier,document['revision'])).fetchone()['artifact'])
        return {**self.inspect(identifier),'export_url':artifact['url']}
