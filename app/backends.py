"""Explicit switches between known local ComfyUI environments, never package upgrades."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener
from backend_contracts import connection_refused, endpoint_ready, loopback_port, queue_is_idle, readiness


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):return None


# --reserve-vram replaces ComfyUI's default rather than adding to it. That default is 600+100 MiB on
# this 16,304 MB Windows card (comfy/model_management.py:863-867), so 0.6 GB is ~86 MiB under it,
# while 2 GB left the Qwen Q4_K_M unet on the full/partial load boundary. docs/RUNTIME-PRECONDITIONS.md.
PRIMARY_RESERVE_VRAM='0.6'


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
                       'disable_pinned_memory':config.get('primary_disable_pinned_memory') is True,
                       'pidfile':str(primary.parent.parent/'comfyui.pid'),'description':'Everyday image, video and 3D workflows'},
            'hidream':{'id':'hidream','name':'HiDream O1 · isolated','root':str(isolated),'url':'http://127.0.0.1:8192',
                       'python':str(python),'port':8192,'entry':str(studio.root/'scripts/hidream-launch.py'),
                       'description':'Separate Transformers overlay; the ROCm Torch installation is shared unchanged'},
            'h3':{'id':'h3','name':'H3 loader experiment','root':str(primary),'url':'http://127.0.0.1:8194',
                  'python':str(python),'port':8194,'entry':str(studio.root/'scripts/h3-launch.py'),
                  'description':'Opt-in encoder and diffusion loader; uses the main model folders without editing installed ComfyUI code'},
        }
        ports=[]
        for profile in self.profiles.values():
            profile['port']=loopback_port(profile['url']);profile['url']=profile['url'].rstrip('/')
            ports.append(profile['port'])
        if len(set(ports))!=len(ports):raise ValueError('Managed backends must use distinct loopback ports')
        self.active='primary'
        try:
            saved=json.loads(self.state_path.read_text(encoding='utf-8'))
            if not isinstance(saved,dict):raise ValueError('Invalid backend state')
            if saved.get('active') in self.profiles:self.active=saved['active']
            self.operation=saved.get('operation') if isinstance(saved.get('operation'),dict) else None
            if self.operation and self.operation.get('status')=='running':self.operation.update(status='interrupted',message='Studio restarted during a switch. Inspect the runtime before trying again.')
        except (OSError,ValueError):pass

    @staticmethod
    def request(profile, route, timeout=2):
        loopback_port(profile['url'])
        # Never send a local control request through environment proxies or redirects.
        with build_opener(ProxyHandler({}),_NoRedirect()).open(profile['url']+route,timeout=timeout) as response:
            payload=response.read(1024*1024+1)
            if len(payload)>1024*1024:raise ValueError('Backend response exceeds the observation limit')
            return json.loads(payload)

    def readiness(self, profile):
        return readiness(profile,self.studio.root)

    def available(self, profile):
        return self.readiness(profile)['ready']

    def snapshot(self):
        profiles=[]
        for profile in self.profiles.values():
            record={k:profile[k] for k in ('id','name','url','root','description')};record['readiness']=self.readiness(profile);record['installed']=record['readiness']['ready']
            try:record['online']=endpoint_ready(self.request(profile,'/system_stats',0.8))
            except (OSError,ValueError):record['online']=False
            record['active']=self.active==profile['id'];profiles.append(record)
        return {'active':self.active,'busy':self.busy,'operation':copy.deepcopy(self.operation),'profiles':profiles}

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
    def primary_argv(target):
        argv=[target['python'],'-s',target['entry'],'--windows-standalone-build','--disable-auto-launch','--disable-api-nodes','--preview-method','latent2rgb','--listen','127.0.0.1','--port',str(target['port']),'--reserve-vram',PRIMARY_RESERVE_VRAM]
        if target.get('disable_pinned_memory') is True:argv.append('--disable-pinned-memory')
        return argv

    @staticmethod
    def matches_configured_process(profile, executable, argv, cwd):
        if Path(executable).resolve()!=Path(profile['python']).resolve():return False
        # The entry must be the executed script, not a later .py argument to another command.
        args=list(argv[1:])
        while args and args[0] in ('-s','-u','-B','-E','-I','-O','-OO'):args.pop(0)
        if not args or not isinstance(args[0],str) or args[0].startswith('-'):return False
        if (Path(cwd)/args.pop(0)).resolve()!=Path(profile['entry']).resolve():return False
        argv=args
        if profile['id']=='primary':
            try:return argv.count('--listen')==1 and argv.count('--port')==1 and argv[argv.index('--listen')+1]=='127.0.0.1' and argv[argv.index('--port')+1]==str(profile['port'])
            except (ValueError,IndexError):return False
        flag='--install-root' if profile['id']=='hidream' else '--comfy-root'
        expected=Path(profile['root']).parent if profile['id']=='hidream' else Path(profile['root'])
        try:return argv.count(flag)==1 and (Path(cwd)/argv[argv.index(flag)+1]).resolve()==expected.resolve()
        except (ValueError,IndexError):return False

    def process(self, profile):
        import psutil
        candidates=set()
        try:
            for connection in psutil.net_connections(kind='tcp'):
                if connection.status!='LISTEN' or connection.laddr.port!=profile['port']:continue
                if connection.laddr.ip!='127.0.0.1' or not connection.pid:
                    raise ValueError(f"Port {profile['port']} has an unverified listener. Studio will not stop it.")
                candidates.add(connection.pid)
            if len(candidates)>1:raise ValueError('Backend process ownership is ambiguous; all processes preserved')
            for pid in candidates:
                process=psutil.Process(pid)
                if self.matches_configured_process(profile,process.exe(),process.cmdline(),process.cwd()):return process
                raise ValueError(f"Port {profile['port']} is owned by another command. Studio will not stop it.")
        except (psutil.NoSuchProcess,psutil.AccessDenied) as exc:
            raise ValueError('Backend process ownership could not be verified; retry after inspecting the runtime') from exc
        return None

    def configured_processes(self, profile):
        """Find exact configured launch commands even before they bind their fixed port."""
        import psutil
        matches=[]
        for process in psutil.process_iter():
            try:
                name=process.name()
            except psutil.NoSuchProcess:continue
            except psutil.AccessDenied:
                # Without even a name, this process could be the configured launcher.
                raise ValueError('A process identity could not be read while checking the configured backend; no recovery launch was authorized')
            if not isinstance(name,str) or not name:
                name=self.windows_process_name(process.pid)
                if not name:raise ValueError('A process name could not be read while checking the configured backend; no recovery launch was authorized')
            if Path(name).stem.casefold()!=Path(profile['python']).stem.casefold():continue
            try:
                if self.matches_configured_process(profile,process.exe(),process.cmdline(),process.cwd()):matches.append(process)
            except psutil.NoSuchProcess:continue
            except psutil.AccessDenied as exc:
                # A protected Python process can be our launcher before it has bound its port.
                raise ValueError('A candidate configured Python process could not be verified; no recovery launch was authorized') from exc
        return matches

    @staticmethod
    def windows_process_name(pid):
        """Read one protected Windows process name without trusting psutil's blank fields."""
        if os.name!='nt' or not isinstance(pid,int) or pid<=0:return None
        # `-Command` consumes trailing arguments, so interpolate only the validated observed integer.
        command=f'$p=[System.Diagnostics.Process]::GetProcessById({pid});[Console]::Out.Write($p.ProcessName)'
        try:
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],stdin=subprocess.DEVNULL,
                                  capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=2,check=False,
                                  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except (OSError,subprocess.TimeoutExpired):return None
        name=result.stdout.strip() if result.returncode==0 else ''
        return name or None

    def launch_recovery(self, profile):
        """Launch exactly one selected profile without switching or stopping any process."""
        identifier=profile['id'];stamp=time.strftime('%Y%m%d-%H%M%S')+'-recovery';logs=self.studio.root/'.runtime/backends';logs.mkdir(parents=True,exist_ok=True)
        if identifier=='primary':argv=self.primary_argv(profile)
        elif identifier=='hidream':argv=[profile['python'],'-s',profile['entry'],'--install-root',str(Path(profile['root']).parent)]
        else:argv=[profile['python'],'-s',profile['entry'],'--comfy-root',profile['root']]
        with (logs/(stamp+'-out.log')).open('w') as out,(logs/(stamp+'-error.log')).open('w') as err:
            launched=subprocess.Popen(argv,cwd=profile['root'],stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if identifier=='primary':Path(profile['pidfile']).write_text(str(launched.pid))
        return launched.pid

    def _idle(self, profile, allow_offline=False):
        try:queue=self.request(profile,'/queue')
        except OSError as exc:
            # Timeouts, HTTP errors and inaccessible listeners are not evidence of absence.
            if allow_offline and connection_refused(exc) and self.process(profile) is None:return False
            raise ValueError('ComfyUI queue state is unknown for '+profile['name']+'; existing processes were preserved') from exc
        queue_is_idle(queue)
        return True

    def _check_retained_startup(self):
        """A previously launched process can still be loading before it binds its port."""
        operation=self.operation or {}
        if operation.get('status') not in ('failed','interrupted'):return
        pid=operation.get('preserved_pid',operation.get('pid'));profile=self.profiles.get(operation.get('target'))
        if not isinstance(pid,int) or not profile:return
        import psutil
        try:
            process=psutil.Process(pid)
            if not self.matches_configured_process(profile,process.exe(),process.cmdline(),process.cwd()):return
            listener=self.process(profile)
            if listener is None or listener.pid!=pid:
                raise ValueError('A retained startup process is still alive without a verified listener. Inspect it before switching again.')
            self._idle(profile)
        except psutil.NoSuchProcess:return
        except psutil.AccessDenied as exc:raise ValueError('Cannot inspect the retained startup process; no new backend will be launched') from exc

    def _check_startup_processes(self):
        """A refused port is not evidence that its configured launcher is absent."""
        for profile in self.profiles.values():
            processes=self.configured_processes(profile)
            if not processes:continue
            listener=self.process(profile)
            identity=(listener.pid,listener.create_time()) if listener else None
            if len(processes)!=1 or identity!=(processes[0].pid,processes[0].create_time()):
                raise ValueError(profile['name']+' has a configured startup process without a unique matching listener. '
                                 'Existing processes were preserved; inspect startup before switching explicitly.')

    def switch(self, identifier):
        if identifier not in self.profiles:raise ValueError('Unknown backend')
        if not self.available(self.profiles[identifier]):raise ValueError('This environment is not installed completely. '+self.readiness(self.profiles[identifier])['message'])
        with self.studio.lock:
            if self.busy:raise ValueError('A backend switch is already running; follow its current status')
            if self._local_work():raise ValueError('Finish or reconcile active Studio work before switching backends')
            self._check_retained_startup()
            self._check_startup_processes()
            # Check every endpoint, including work submitted directly through ComfyUI.
            for profile in self.profiles.values():self._idle(profile,allow_offline=True)
            previous=self.operation
            self.busy=True;self.operation={'id':uuid.uuid4().hex,'target':identifier,'status':'running','started_at':time.time(),'message':'Checking owned local runtimes'}
            try:self._save()
            except Exception:
                self.busy=False;self.operation=previous
                raise
        try:threading.Thread(target=self._switch,args=(identifier,),daemon=True,name='studio-backend-switch').start()
        except Exception as exc:
            with self.studio.lock:
                self.busy=False;self.operation.update(status='failed',finished_at=time.time(),message='Switch worker did not start: '+str(exc)[:300]);self._save()
            raise
        return self.snapshot()

    def _switch(self, identifier):
        launched=None
        try:
            target=self.profiles[identifier]
            if not self.available(target):raise ValueError(self.readiness(target)['message'])
            with self.studio.lock:
                if self._local_work():raise ValueError('New Studio work arrived; reconcile it before switching')
            # Preflight every process before any destructive action. A foreign target
            # must not be discovered only after stopping the healthy current backend.
            observed={}
            for key,profile in self.profiles.items():
                self._idle(profile,allow_offline=True)
                process=self.process(profile)
                observed[key]=(process.pid,process.create_time()) if process else None
            self._check_startup_processes()
            for key,profile in self.profiles.items():
                if key==identifier:continue
                process=self.process(profile)
                if not process:
                    if observed[key] is not None:raise ValueError('Backend process changed during preflight; retry explicitly')
                    continue
                if observed[key]!=(process.pid,process.create_time()):raise ValueError('Backend process changed during preflight; all remaining processes preserved')
                # Recheck just before termination; only this verified, idle local process is stopped.
                self._idle(profile)
                self._check_startup_processes()
                self.operation.setdefault('stopped_processes', []).append({'profile':key,'pid':process.pid,'created_at':process.create_time(),'matched_entry':profile['entry']})
                self.operation['message']='Stopping idle '+profile['name'];self._save()
                process.terminate();process.wait(timeout=15)
            owned=self.process(target)
            if owned and observed[identifier]!=(owned.pid,owned.create_time()):raise ValueError('Target process changed during preflight; retry explicitly')
            if not owned:
                if observed[identifier] is not None:raise ValueError('Target process disappeared during preflight; retry explicitly')
                self.operation['message']='Starting '+target['name'];self._save()
                self._check_startup_processes()
                stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+self.operation['id'];logs=self.studio.root/'.runtime/backends';logs.mkdir(parents=True,exist_ok=True)
                if identifier=='primary':
                    argv=self.primary_argv(target)
                elif identifier=='hidream':argv=[target['python'],'-s',target['entry'],'--install-root',str(Path(target['root']).parent)]
                else:argv=[target['python'],'-s',target['entry'],'--comfy-root',target['root']]
                with (logs/(stamp+'-out.log')).open('w') as out,(logs/(stamp+'-error.log')).open('w') as err:
                    launched=subprocess.Popen(argv,cwd=target['root'],stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                self.operation.update(pid=launched.pid,log_directory=str(logs));self._save()
                if identifier=='primary':Path(target['pidfile']).write_text(str(launched.pid))
                for _ in range(120):
                    if launched.poll() is not None:raise ValueError('The selected runtime exited during startup; inspect its saved log')
                    try:
                        if endpoint_ready(self.request(target,'/system_stats')):break
                    except (OSError,ValueError):pass
                    time.sleep(1)
                else:raise ValueError('Runtime startup timed out; no generation was submitted')
            # Reusing an existing listener also requires a healthy, idle endpoint.
            if not endpoint_ready(self.request(target,'/system_stats')):raise ValueError('Target endpoint is not ready')
            self._idle(target)
            if launched:
                listener=self.process(target)
                if listener is None or listener.pid!=launched.pid:raise ValueError('Ready endpoint does not belong to the launched process; inspect retained runtime')
            self.activate(identifier)
            self.operation.update(status='completed',finished_at=time.time(),message=target['name']+' endpoint is ready. Model inference was not checked; no generation submitted.');self._save()
        except Exception as exc:
            # A timed-out launcher may already be accepting direct ComfyUI jobs.
            # Never terminate it blindly during cleanup or silently restart the old family.
            if launched and launched.poll() is None:
                self.operation.update(preserved_pid=launched.pid,recovery='Inspect the retained runtime and queue, then switch explicitly. No automatic retry.')
            self.operation.update(status='failed',finished_at=time.time(),message=str(exc)[:500]);self._save()
        finally:
            with self.studio.lock:self.busy=False
