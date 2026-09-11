"""Explicit switches between known local ComfyUI environments, never package upgrades."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import threading
import time
import uuid
from urllib.request import urlopen


class BackendManager:
    def __init__(self, studio):
        self.studio=studio;self.busy=False;self.operation=None
        self.state_path=studio.root/'.runtime/backend-state.json'
        config=studio.config;primary=Path(config.get('comfy_root',studio.comfy_root)).resolve()
        python=Path(config.get('python','C:/AI/ComfyUI_windows_portable/python_embeded/python.exe')).resolve()
        isolated=Path(config.get('hidream_root','C:/AI/experiments/hidream-o1/ComfyUI')).resolve()
        self.profiles={
            'primary':{'id':'primary','name':'Main library','root':str(primary),'url':config.get('comfy_url','http://127.0.0.1:8188'),
                       'python':str(python),'port':8188,'entry':str(primary/'main.py'),
                       'pidfile':str(primary.parent.parent/'comfyui.pid'),'description':'Everyday image, video and 3D workflows'},
            'hidream':{'id':'hidream','name':'HiDream O1 · isolated','root':str(isolated),'url':'http://127.0.0.1:8192',
                       'python':str(python),'port':8192,'entry':str(studio.root/'scripts/hidream-launch.py'),
                       'description':'Separate Transformers overlay; the ROCm Torch installation is shared unchanged'},
            'h3':{'id':'h3','name':'H3 loader experiment','root':str(primary),'url':'http://127.0.0.1:8194',
                  'python':str(python),'port':8194,'entry':str(studio.root/'scripts/h3-launch.py'),
                  'description':'Opt-in encoder loader; uses the main model folders without editing installed ComfyUI code'},
        }
        self.active='primary'
        try:
            saved=json.loads(self.state_path.read_text(encoding='utf-8'))
            if saved.get('active') in self.profiles:self.active=saved['active']
            self.operation=saved.get('operation')
            if self.operation and self.operation.get('status')=='running':self.operation.update(status='interrupted',message='Studio restarted during a switch. Inspect the runtime before trying again.')
        except (OSError,ValueError):pass

    @staticmethod
    def request(profile, route, timeout=2):
        with urlopen(profile['url']+route,timeout=timeout) as response:return json.load(response)

    def available(self, profile):
        extra=profile['id']=='primary' or (profile['id']=='hidream' and Path(profile['root'],'python_packages/transformers').is_dir()) or (profile['id']=='h3' and Path(profile['root'],'models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors').is_file())
        return Path(profile['python']).is_file() and Path(profile['root'],'main.py').is_file() and extra

    def snapshot(self):
        profiles=[]
        for profile in self.profiles.values():
            record={k:profile[k] for k in ('id','name','url','root','description')};record['installed']=self.available(profile)
            try:record['online']=bool(self.request(profile,'/system_stats',0.8).get('system'))
            except (OSError,ValueError):record['online']=False
            record['active']=self.active==profile['id'];profiles.append(record)
        return {'active':self.active,'busy':self.busy,'operation':self.operation,'profiles':profiles}

    def _save(self):
        self.studio._write_json_atomic(self.state_path,{'active':self.active,'operation':self.operation})

    def activate(self, identifier):
        from model_library import ModelLibrary
        profile=self.profiles[identifier]
        self.active=identifier;self.studio.comfy_url=profile['url'];self.studio.comfy_root=Path(profile['root'])
        self.studio.library=ModelLibrary(self.studio.root,self.studio.comfy_root)
        self.studio._schema=None;self.studio._schema_at=0

    def _local_work(self):
        return any(j.get('status') in ('queued','waiting','submitting','running','uncertain') for j in self.studio.jobs.values()) or any(p['state']['status'] in ('queued','running','observing') for p in self.studio.production.list())

    @staticmethod
    def matches_configured_process(profile, executable, argv, cwd):
        if Path(executable).resolve()!=Path(profile['python']).resolve():return False
        files=[]
        for arg in argv[1:]:
            if isinstance(arg,str) and arg.lower().endswith('.py'):
                files.append((Path(cwd)/arg).resolve())
        if Path(profile['entry']).resolve() not in files:return False
        if profile['id']=='primary':
            try:return argv[argv.index('--listen')+1]=='127.0.0.1' and argv[argv.index('--port')+1]==str(profile['port'])
            except (ValueError,IndexError):return False
        flag='--install-root' if profile['id']=='hidream' else '--comfy-root'
        expected=Path(profile['root']).parent if profile['id']=='hidream' else Path(profile['root'])
        try:return Path(argv[argv.index(flag)+1]).resolve()==expected.resolve()
        except (ValueError,IndexError):return False

    def process(self, profile):
        import psutil
        candidates=[]
        for connection in psutil.net_connections(kind='tcp'):
            if connection.status=='LISTEN' and connection.laddr.port==profile['port'] and connection.laddr.ip=='127.0.0.1' and connection.pid:candidates.append(connection.pid)
        for pid in set(candidates):
            try:
                process=psutil.Process(pid)
                if self.matches_configured_process(profile,process.exe(),process.cmdline(),process.cwd()):return process
                raise ValueError(f"Port {profile['port']} is owned by another command. Studio will not stop it.")
            except (psutil.NoSuchProcess,psutil.AccessDenied):continue
        return None

    def switch(self, identifier):
        if identifier not in self.profiles:raise ValueError('Unknown backend')
        if not self.available(self.profiles[identifier]):raise ValueError('This isolated environment is not installed')
        with self.studio.lock:
            if self.busy:raise ValueError('A backend switch is already running; follow its current status')
            if self._local_work():raise ValueError('Finish or reconcile active Studio work before switching backends')
            # Check every configured endpoint, including work submitted directly through ComfyUI.
            for profile in self.profiles.values():
                try:queue=self.request(profile,'/queue')
                except OSError:continue
                if queue.get('queue_running') or queue.get('queue_pending'):raise ValueError('ComfyUI has active or queued work. Its queue was preserved.')
            self.busy=True;self.operation={'id':uuid.uuid4().hex,'target':identifier,'status':'running','started_at':time.time(),'message':'Checking owned local runtimes'};self._save()
        threading.Thread(target=self._switch,args=(identifier,),daemon=True,name='studio-backend-switch').start()
        return self.snapshot()

    def _switch(self, identifier):
        launched=None
        try:
            target=self.profiles[identifier]
            for key,profile in self.profiles.items():
                if key==identifier:continue
                process=self.process(profile)
                if not process:continue
                # Recheck just before termination; only this verified, idle local process is stopped.
                queue=self.request(profile,'/queue')
                if queue.get('queue_running') or queue.get('queue_pending'):raise ValueError('New ComfyUI work arrived; switch stopped and its queue was preserved')
                self.operation.setdefault('stopped_processes', []).append({'profile':key,'pid':process.pid,'created_at':process.create_time(),'matched_entry':profile['entry']})
                self.operation['message']='Stopping idle '+profile['name'];self._save()
                process.terminate();process.wait(timeout=15)
            owned=self.process(target)
            if not owned:
                self.operation['message']='Starting '+target['name'];self._save()
                stamp=time.strftime('%Y%m%d-%H%M%S');logs=self.studio.root/'.runtime/backends';logs.mkdir(exist_ok=True)
                if identifier=='primary':
                    argv=[target['python'],'-s',target['entry'],'--windows-standalone-build','--disable-auto-launch','--disable-api-nodes','--preview-method','latent2rgb','--listen','127.0.0.1','--port',str(target['port']),'--reserve-vram','2']
                elif identifier=='hidream':argv=[target['python'],'-s',target['entry'],'--install-root',str(Path(target['root']).parent)]
                else:argv=[target['python'],'-s',target['entry'],'--comfy-root',target['root']]
                with (logs/(stamp+'-out.log')).open('w') as out,(logs/(stamp+'-error.log')).open('w') as err:
                    launched=subprocess.Popen(argv,cwd=target['root'],stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                self.operation.update(pid=launched.pid,log_directory=str(logs));self._save()
                if identifier=='primary':Path(target['pidfile']).write_text(str(launched.pid))
                for _ in range(120):
                    if launched.poll() is not None:raise ValueError('The selected runtime exited during startup; inspect its saved log')
                    try:
                        if self.request(target,'/system_stats').get('system'):break
                    except (OSError,ValueError):pass
                    time.sleep(1)
                else:raise ValueError('Runtime startup timed out; no generation was submitted')
            self.activate(identifier)
            self.operation.update(status='completed',finished_at=time.time(),message=target['name']+' is ready. No generation submitted.');self._save()
        except Exception as exc:
            if launched and launched.poll() is None:
                launched.terminate()
                try:launched.wait(timeout=10)
                except subprocess.TimeoutExpired:pass
            self.operation.update(status='failed',finished_at=time.time(),message=str(exc)[:500]);self._save()
        finally:self.busy=False
