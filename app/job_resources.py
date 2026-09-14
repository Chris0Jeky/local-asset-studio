"""Optional resource evidence owned by the existing generation worker.

No thread, queue, generation, admission, retry, cleanup or process-control authority.
Sidecars never write back into a job or its recipe. Sensor/writer failure is diagnostic.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

import resource_probe
from performance_history import summarize_resource_profile

MAX_WINDOWS = 8
MAX_SAMPLE_BYTES = 16 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_DOCUMENT_BYTES = 128 * 1024
MAX_EVENTS = 160


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def fingerprint(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 2**63-1 and math.isfinite(value)


def _read(path, limit=MAX_DOCUMENT_BYTES):
    if path.is_symlink(): raise ValueError('Linked evidence is not supported')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('Evidence must be a regular file')
        stream = os.fdopen(fd, 'rb'); fd = None
        with stream: data = stream.read(limit + 1)
    finally:
        if fd is not None: os.close(fd)
    if len(data) > limit: raise ValueError('Evidence exceeds its byte limit')
    return data


def _document(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ValueError('Duplicate evidence key')
            result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=unique)
    if not isinstance(value,dict): raise ValueError('Evidence document must be an object')
    _encoded(value)  # Non-finite constants are not valid evidence, including ignored fields.
    return value


def _publish(path, value):
    raw = _encoded(value)
    if len(raw) > MAX_DOCUMENT_BYTES: raise ValueError('Evidence document exceeds its byte limit')
    # The whole window is exclusively claimed first. Link publication is atomic
    # and no-clobber; a failed new temporary file is retained, never overwritten.
    temp = path.with_suffix('.tmp')
    with temp.open('xb') as stream: stream.write(raw)
    os.link(temp, path)
    temp.unlink()
    return hashlib.sha256(raw).hexdigest()


def _notice(job, error):
    try: print('Resource telemetry unavailable for job ' + str(job.get('id', ''))[:80] + ': ' + type(error).__name__, file=sys.stderr)
    except Exception: pass


def settings(config):
    value = config.get('performance_telemetry')
    if not isinstance(value, dict) or value.get('enabled') is not True: return None
    interval, count = value.get('interval_seconds', 5), value.get('max_samples', 120)
    if not _finite(interval) or not 1 <= interval <= 60: raise ValueError('Invalid telemetry interval')
    if type(count) is not int or not 1 <= count <= 120: raise ValueError('Invalid telemetry sample count')
    if set(value) - {'enabled', 'interval_seconds', 'max_samples'}: raise ValueError('Unknown telemetry setting')
    return {'interval_seconds': interval, 'max_samples': count}


def source_identity(studio):
    files = {}
    for name in ('server', 'job_resources', 'resource_probe', 'performance_history', 'backends', 'production'):
        path = studio.root/'app'/(name+'.py')
        try: files[name] = hashlib.sha256(_read(path, MAX_FILE_BYTES)).hexdigest()
        except (OSError, ValueError): files[name] = None
    head = None
    if (studio.root/'.git').exists():
        try:
            reply = subprocess.run(['git','-C',str(studio.root),'rev-parse','--verify','HEAD'],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   timeout=2, check=True)
            candidate = reply.stdout.decode('ascii').strip()
            if re.fullmatch('[0-9a-f]{40,64}', candidate): head = candidate
        except (OSError, ValueError, subprocess.SubprocessError): pass
    return {'git_head': head, 'files': files, 'configuration_sha256': fingerprint(studio.config),
            'scope': 'Git HEAD and on-disk source observations; not loaded-bytecode or clean-checkout certification'}


def runtime_identity(studio, job):
    """Reuse the existing listener/launcher matcher. Matching is not control permission."""
    result = {'profile_id': None, 'profile_sha256': None, 'process': None, 'unknown_reason': None}
    try:
        manager = studio.backends
        profile = manager.profiles[manager.active]
        if profile['url'].rstrip('/') != job['comfy_url'].rstrip('/') or Path(profile['root']).resolve() != Path(job['comfy_root']).resolve():
            return dict(result, unknown_reason='job_backend_not_selected')
        result.update(profile_id=profile['id'], profile_sha256=fingerprint(profile))
        process = manager.process(profile)
        if process is None: return dict(result, unknown_reason='verified_listener_unavailable')
        created = process.create_time(); pid = process.pid
        argv = process.cmdline()
        # The first Process caches create_time; ask the owner for a fresh listener.
        verified = manager.process(profile)
        if (type(pid) is not int or pid <= 0 or not _finite(created) or verified is None
                or type(verified.pid) is not int or verified.pid != pid
                or not _finite(final_created := verified.create_time()) or final_created != created or verified.cmdline() != argv
                or manager.active != profile['id'] or fingerprint(manager.profiles[manager.active]) != result['profile_sha256']):
            return dict(result, unknown_reason='process_identity_unavailable')
        result['process'] = {'pid': pid, 'created_at': created, 'argv_sha256': fingerprint(argv)}
        return result
    except Exception:
        return dict(result, unknown_reason='runtime_identity_unavailable')


def _pins(studio, job):
    """Retain only an actually associated existing Production plan; never hash weights."""
    empty = {'status': 'not_bound', 'reason': 'No associated Production evidence; model and input pins were not captured'}
    if not job.get('project_id'): return empty
    try:
        project = studio.production._get(job['project_id']); plan = project['plan']
        if project['id'] != job['project_id']: raise ValueError('Project mismatch')
        if fingerprint({k:v for k,v in plan.items() if k != 'sha256'}) != plan['sha256']: raise ValueError('Plan digest')
        matches = []
        for index, stage in enumerate(plan['stages']):
            attempt = project['state']['attempts'].get(str(index), {})
            if attempt.get('job_id') == job['id']:
                if (stage['graph_sha256'] != fingerprint(job['graph']) or fingerprint(stage['graph']) != stage['graph_sha256']
                        or stage['request']['preset_id'] != job['preset_id']): raise ValueError('Stage graph changed')
                matches.append(index)
        if len(matches) != 1: raise ValueError('Unbound stage')
        bundle = plan['bundle']
        if bundle['comfy_url'] != job['comfy_url'] or bundle['comfy_root'] != job['comfy_root']: raise ValueError('Backend mismatch')
        result = {'status':'bound_preflight','project_id':project['id'],'root_id':project['root_id'],
                  'plan_sha256':plan['sha256'],'stage_index':matches[0],'bundle_sha256':fingerprint(bundle),
                  'schema_sha256':bundle.get('schema_sha256'),'models':[],'inputs':[],
                  'scope':'Existing pinned preflight, not freshly rehashed by telemetry; package revisions and cold/warm condition remain unknown'}
        for name in ('models','inputs'):
            records = bundle[name]
            if not isinstance(records,list) or len(records)>256: raise ValueError('Unbounded pins')
            for item in records:
                sha = item.get('sha256'); size = item.get('bytes')
                if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) or type(size) is not int or size<0: raise ValueError('Invalid pin')
                result[name].append({'sha256':sha,'bytes':size})
        return result
    except Exception:
        return dict(empty, reason='Production binding could not be verified; no pins were inferred')


def engine_timing(prompt_id, history):
    result = {'prompt_id':prompt_id,'elapsed_seconds':None,'source':'Comfy history status.messages',
              'scope':'Engine execution total only; includes cached work, not per-node or GPU-exclusive time'}
    status = history.get('status', {}) if isinstance(history,dict) else {}
    messages = status.get('messages') if isinstance(status,dict) else None
    if not isinstance(messages,list) or len(messages)>4096: return result
    starts, ends = [], []
    terminal = 'execution_success' if status.get('status_str')=='success' else 'execution_error' if status.get('status_str')=='error' else None
    if terminal is None: return result
    for message in messages:
        if not isinstance(message,list) or len(message)!=2 or not isinstance(message[1],dict): continue
        name, data = message
        if data.get('prompt_id') != prompt_id: continue
        if name in ('execution_success','execution_error','execution_interrupted') and name!=terminal: return result
        if name=='execution_start': starts.append(data.get('timestamp'))
        if name==terminal:
            if not starts: return result
            ends.append(data.get('timestamp'))
    if len(starts)==len(ends)==1 and _finite(starts[0]) and _finite(ends[0]) and ends[0]>=starts[0]:
        result['elapsed_seconds']=(ends[0]-starts[0])/1000
    return result


def _root(studio, job_id):
    if not isinstance(job_id,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}',job_id): raise ValueError('Invalid job identity')
    directory = studio.runs/job_id
    if directory.is_symlink() or not directory.is_dir() or directory.resolve().parent != studio.runs.resolve():
        raise ValueError('Job evidence directory is unavailable')
    path = directory/'resources'
    if path.is_symlink(): raise ValueError('Linked telemetry root is unsupported')
    return path


class Window:
    def __init__(self, studio, job, options, clock):
        self.studio,self.job,self.options,self.clock = studio,job,options,clock
        self.started=clock(); self.next_sample=self.started; self.samples=0; self.events=0
        self.stop_reason=None; self.overhead=0.0; self.engine=[]; self.submissions=[]; self.sampling_started=False; self.handles={}; self.digests={}; self.sizes={}
        self.initial_identity=runtime_identity(studio,job)
        root=_root(studio,job['id']); root.mkdir(exist_ok=True)
        self.directory=None
        for index in range(1,MAX_WINDOWS+1):
            candidate=root/f'{index:02d}'
            try: candidate.mkdir()
            except FileExistsError: continue
            self.directory=candidate; self.window_id=f'{index:02d}'; break
        if self.directory is None: raise ValueError('Per-job telemetry window limit reached')
        manifest={'schema':'studio.job-resource-window/v1','window_id':self.window_id,'job_id':job['id'],
                  'preset_id':job['preset_id'],'prepared_graph_sha256':fingerprint(job['graph']),
                  'controls_sha256':fingerprint(job.get('controls',{})), 'batch_count':job['batch_count'],
                  'source':source_identity(studio),'runtime':self.initial_identity,'production':_pins(studio,job),
                  'options':options,'condition':'unknown','execution_authority':False}
        self.manifest_sha=_publish(self.directory/'manifest.json',manifest)
        try:
            for name in ('samples','events'):
                self.handles[name]=(self.directory/(name+'.jsonl')).open('xb')
                self.digests[name]=hashlib.sha256(); self.sizes[name]=0
            self._write_line('samples',resource_probe.profile_metadata(options['max_samples'],options['interval_seconds']))
            pids=[os.getpid()]
            if self.initial_identity['process']: pids.append(self.initial_identity['process']['pid'])
            self.sampler=resource_probe.ResourceSampler(pids=pids,comfy_url=job['comfy_url'])
            self.event('worker_start')
        except Exception:
            self.close(); raise
        self.overhead=clock()-self.started

    def close(self):
        for stream in self.handles.values():
            try: stream.close()
            except Exception: pass

    def _write_line(self, name, data):
        raw=_encoded(data)+b'\n'
        if len(raw)>MAX_SAMPLE_BYTES or self.sizes[name]+len(raw)>MAX_FILE_BYTES: raise ValueError('Telemetry byte budget exhausted')
        written=self.handles[name].write(raw)
        if written!=len(raw): raise OSError('Partial telemetry write')
        self.handles[name].flush(); self.digests[name].update(raw); self.sizes[name]+=len(raw)

    def _event(self, name, fields):
        if self.events>=MAX_EVENTS: return
        record={'event':name,'offset_seconds':self.clock()-self.started}
        for key in ('index','prompt_id','phase'):
            if key in fields: record[key]=fields[key]
        if 'graph' in fields: record['graph_sha256']=fingerprint(fields['graph'])
        if name=='submission_intent':
            if len(self.submissions)>=4: raise ValueError('Too many submissions')
            self.submissions.append({'index':fields['index'],'graph_sha256':record['graph_sha256'],'prompt_id':None})
        elif name=='acknowledged':
            matches=[item for item in self.submissions if item['index']==fields['index']]
            if len(matches)!=1: raise ValueError('No unique submission intent')
            matches[0]['prompt_id']=fields['prompt_id']
        self._write_line('events',record); self.events+=1

    def event(self, name, **fields):
        started=self.clock()
        try: self._event(name,fields)
        except Exception: self.stop_reason=self.stop_reason or 'observation_error'
        finally: self.overhead+=self.clock()-started

    def sample(self, phase, force=False):
        if self.stop_reason: return
        if self.samples>=self.options['max_samples']:
            self.stop_reason='sample_limit'; return
        self.sampling_started=True
        started=self.clock()
        if not force and started<self.next_sample: return
        try:
            if runtime_identity(self.studio,self.job)!=self.initial_identity:
                self.stop_reason='runtime_identity_changed_or_unknown'; return
            record=self.sampler.sample()
            if runtime_identity(self.studio,self.job)!=self.initial_identity:
                self.stop_reason='runtime_identity_changed_or_unknown'; return
            self._write_line('samples',record); self.samples+=1
            self._event('sample',{'phase':phase,'index':self.samples-1})
        except Exception:
            self.stop_reason='observation_error'
        finally:
            self.overhead+=self.clock()-started
            self.next_sample=self.clock()+self.options['interval_seconds']

    def history(self, submission, history):
        started=self.clock()
        try:
            if len(self.engine)>=4: return
            result=engine_timing(submission['prompt_id'],history)
            result.update(index=submission['index'],graph_sha256=fingerprint(submission['graph']))
            self.engine.append(result)
            self._event('history_received',{'index':submission['index'],'prompt_id':submission['prompt_id']})
        except Exception:
            self.stop_reason=self.stop_reason or 'observation_error'

        finally: self.overhead+=self.clock()-started

    def finish(self):
        if self.sampling_started: self.sample('worker_end',force=True)
        self.event('worker_end')
        self.close()
        summary=None; summary_error=None
        try:
            summary=summarize_resource_profile(io.BytesIO(_read(self.directory/'samples.jsonl',MAX_FILE_BYTES)))
        except Exception: summary_error='incomplete_or_incompatible_samples'
        elapsed=self.job.get('elapsed_seconds')
        result={'schema':'studio.job-resource-result/v1','window_id':self.window_id,'job_id':self.job['id'],
                'manifest_sha256':self.manifest_sha,'samples_sha256':self.digests['samples'].hexdigest(),
                'events_sha256':self.digests['events'].hexdigest(),'sampling_stop_reason':self.stop_reason or 'worker_returned',
                'summary':summary,'summary_error':summary_error,'observed_job_status':self.job.get('status'),
                'prompt_ids':list(self.job.get('prompt_ids',[])), 'has_pending_submission':'pending_submission' in self.job,
                'worker_observation_seconds':self.clock()-self.started,'overhead_seconds_observed':self.overhead,
                'retained_job_elapsed_seconds':elapsed if _finite(elapsed) else None,
                'phase_seconds':dict.fromkeys(('load','encode','sample','decode','export')),
                'engine_executions':self.engine,'submissions':self.submissions,'execution_authority':False,
                'scope':'Shared host/backend observations including queue/request/indexing overhead; not exclusive job allocation or guaranteed peaks'}
        _publish(self.directory/'result.json',result)


@contextmanager
def observe(studio, job, *, clock=None):
    window=None
    try:
        options=settings(studio.config)
        if options: window=Window(studio,job,options,clock or time.perf_counter)
    except Exception as exc: _notice(job,exc)
    try: yield window
    finally:
        if window is not None:
            try: window.finish()
            except Exception as exc: _notice(job,exc)
            finally: window.close()


def record(window, operation, *args, **fields):
    """The worker's best-effort instrumentation seam never changes its outcome."""
    if window is None: return
    try: getattr(window, operation)(*args, **fields)
    except Exception as exc:
        window.stop_reason = window.stop_reason or 'observation_error'
        _notice(window.job, exc)


def inspect(studio, job_id):
    if job_id not in studio.jobs: raise ValueError('Unknown job')
    result={'job_id':job_id,'current_job_status':studio.jobs[job_id].get('status'),'status':'available','windows':[],'window_limit':MAX_WINDOWS,'execution_authority':False}
    try: root=_root(studio,job_id)
    except (OSError,ValueError): return dict(result,status='unavailable')
    # Fixed slots bound traversal even when an unrelated directory contains many files.
    for index in range(1,MAX_WINDOWS+1):
        directory=root/f'{index:02d}'
        if not directory.exists() and not directory.is_symlink(): continue
        row={'window_id':f'{index:02d}','status':'corrupt'}
        try:
            if directory.is_symlink() or not directory.is_dir(): raise ValueError('Invalid telemetry directory')
            raw=_read(directory/'manifest.json'); manifest=_document(raw)
            if manifest.get('execution_authority') is not False or manifest.get('prepared_graph_sha256')!=fingerprint(studio.jobs[job_id]['graph']):
                raise ValueError('Manifest no longer describes this job')
            if manifest.get('schema')!='studio.job-resource-window/v1' or manifest.get('job_id')!=job_id or manifest.get('window_id')!=row['window_id']:
                raise ValueError('Manifest identity mismatch')
            if not (directory/'result.json').exists(): row.update(status='not_finalized',manifest=manifest)
            else:
                final=_document(_read(directory/'result.json'))
                if final.get('execution_authority') is not False: raise ValueError('Telemetry grants no authority')
                if final.get('schema')!='studio.job-resource-result/v1' or final.get('job_id')!=job_id or final.get('window_id')!=row['window_id']:
                    raise ValueError('Result identity mismatch')
                if final.get('manifest_sha256')!=hashlib.sha256(raw).hexdigest(): raise ValueError('Manifest changed')
                for name in ('samples','events'):
                    if final.get(name+'_sha256')!=hashlib.sha256(_read(directory/(name+'.jsonl'),MAX_FILE_BYTES)).hexdigest():
                        raise ValueError('Raw evidence changed')
                row.update(status='finalized',manifest=manifest,result=final)
        except Exception: pass
        result['windows'].append(row)
    return result
