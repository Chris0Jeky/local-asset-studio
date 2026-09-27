"""Owner cancel for one Create job (#1138): targeted, observed, never a retry.

The HTTP thread only records a request (memory plus `cancel-request.json`). The
single worker that owns the job's ComfyUI traffic picks it up at its checkpoints
and is the only writer of the outcome, so a cancel never races a submission or an
observation. A queued job the worker has not started is settled by the request
itself: nothing was sent. A prompt is dequeued or interrupted only after `/queue`
lists this job's own prompt ID as waiting or as the one running, and the result
is read back from `/queue` and `/history`, never assumed.

Cancellation states: requested -> cancelled (confirmed) | refused (ownership not
proven, nothing sent) | too_late (the job settled first) | unresolved (the
outcome could not be observed; the job stays uncertain). Nothing is resubmitted.
"""
from __future__ import annotations
import copy
import json
import time
import uuid
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote

import submission_evidence

CANCELLABLE = ('queued', 'waiting', 'submitting', 'running')
READ_ERRORS = (URLError, HTTPError, TimeoutError, OSError, ValueError, UnicodeError, HTTPException)
REQUEST_FILE = 'cancel-request.json'
MAX_DEQUEUES = 2   # a delete that ComfyUI ignored twice is refused, never looped


def not_started(job):
    """Queued and provably never sent: the worker takes the Studio lock before it touches such a job."""
    return job.get('status') == 'queued' and submission_evidence.never_submitted(job)


def pending(studio, job):
    request = (getattr(studio, 'cancel_requests', None) or {}).get(job.get('id'))
    current = job.get('cancellation')
    return request is not None or (isinstance(current, dict) and current.get('state') == 'requested')


def blocked(studio, job):
    """Why this job cannot be cancelled now, or None."""
    if not isinstance(job, dict) or not job: return 'Unknown job'
    status = job.get('status')
    if status == 'cancelled': return 'Already cancelled'
    if pending(studio, job): return 'Cancel requested; the Studio is checking ComfyUI'
    if status == 'uncertain': return 'The Studio is not watching this job and its outcome is unknown; use Stop tracking instead'
    if status == 'not_submitted': return 'Nothing is queued or running for this job; abandon it instead'
    if status not in CANCELLABLE: return 'This job has already finished'
    if job.get('project_id'): return 'This render belongs to a comparison; stop the comparison instead'
    if job.get('operation'): return 'This kind of job cannot be cancelled here'
    if 'pending_submission' in job and status != 'submitting':
        return 'A submission outcome is unknown; this batch is only being checked, not rendered'
    if not not_started(job):
        worker = getattr(studio, 'worker', None)
        if worker is not None and worker.ident is not None and not worker.is_alive():
            return 'The Studio worker is unavailable; restart the Studio'
    return None


def confirm_needed(job):
    """Something was sent to ComfyUI and may be rendering, so the UI asks before sending the cancel."""
    return job.get('status') in CANCELLABLE and not submission_evidence.never_submitted(job)


def new_record(job, now):
    record = {'event_id': uuid.uuid4().hex, 'requested_at': now, 'requested_by': 'owner', 'status_at_request': job.get('status'),
              'state': 'requested', 'actions': [], 'observations': []}
    previous = job.get('cancellation')
    if isinstance(previous, dict):
        record['previous'] = [p for p in previous.get('previous', []) if isinstance(p, dict)][-4:] + [{k: v for k, v in previous.items() if k != 'previous'}]
    return record


def not_started_message(): return 'Not started: cancelled by you. Nothing was sent to ComfyUI.'


def pickup(studio, job):
    """Worker checkpoint (caller holds studio.lock): adopt a new request into the job; return it while it is open."""
    request = (getattr(studio, 'cancel_requests', None) or {}).get(job.get('id'))
    current = job.get('cancellation')
    if request is not None and (not isinstance(current, dict) or current.get('event_id') != request['event_id']):
        job['cancellation'] = copy.deepcopy(request); studio._save(job)
    current = job.get('cancellation')
    return current if isinstance(current, dict) and current.get('state') == 'requested' else None


def _resolve(studio, job, state, note):
    record = job['cancellation']; record.update(state=state, resolved_at=time.time(), note=note)
    requests = getattr(studio, 'cancel_requests', None) or {}
    if (requests.get(job.get('id')) or {}).get('event_id') == record.get('event_id'): requests.pop(job.get('id'), None)


def settle(studio, job, how=None):
    """Terminal `cancelled` (caller holds studio.lock). Finished outputs stay recorded; nothing is retried."""
    done = sum(1 for s in job.get('submissions', []) if isinstance(s, dict) and s.get('status') == 'completed')
    total = job.get('batch_count') or 1
    if not job.get('prompt_ids') and 'pending_submission' not in job:
        message = not_started_message(); note = 'Stopped before submission; nothing was sent to ComfyUI.'
    else:
        lead = {'dequeued': 'Cancelled by you: ComfyUI removed the prompt before it started.',
                'interrupted': 'Stopped by you: ComfyUI reported the render interrupted.'}.get(how, 'Cancelled by you between outputs.')
        kept = f' {done} of {total} outputs finished and are kept.' if done else ''
        rest = ' The remaining outputs were not submitted.' if len(job.get('prompt_ids', [])) < total else ''
        message = lead + kept + rest + ' Nothing is retried.'; note = lead
    job['status'] = 'cancelled'; job['message'] = message
    _resolve(studio, job, 'cancelled', note)
    studio._stamp_finished(job); studio._save(job)


def finish(studio, job):
    """Reconcile a still-open request with the job's settled status, after the worker is done with it."""
    with studio.lock:
        if pickup(studio, job) is None: return
        status = job.get('status')
        if status in CANCELLABLE: return
        if status == 'not_submitted' and submission_evidence.never_submitted(job): settle(studio, job); return
        sent = any(a.get('action') == 'interrupt' for a in job['cancellation']['actions'])
        if status == 'uncertain':
            _resolve(studio, job, 'unresolved', 'The outcome could not be observed, so the cancel is not confirmed. Nothing was resubmitted.')
        elif status == 'completed' and sent:
            _resolve(studio, job, 'too_late', 'ComfyUI finished the render before the interrupt took effect; the outputs are kept.')
        else:
            _resolve(studio, job, 'too_late', f'The job had already settled as {status} before the cancel could act; nothing was cancelled.')
        studio._save(job)


def _observe(record, prompt_id, **facts):
    record['observations'].append(dict(facts, prompt_id=prompt_id, at=time.time()))


def _queue(studio, url, prompt_id):
    """Where /queue puts this prompt: ('pending'|'running'|'absent'|'unreadable', running prompt IDs)."""
    try: data = studio._request('/queue', timeout=10, base_url=url)
    except READ_ERRORS: return 'unreadable', []
    if not isinstance(data, dict) or any(type(data.get(key)) is not list for key in ('queue_running', 'queue_pending')): return 'unreadable', []
    ids = {}
    for key in ('queue_running', 'queue_pending'):
        for entry in data[key]:
            if not isinstance(entry, (list, tuple)) or len(entry) < 2: return 'unreadable', []
            ids.setdefault(key, []).append(entry[1])
    running = ids.get('queue_running', [])
    if prompt_id in running: return 'running', running
    return ('pending' if prompt_id in ids.get('queue_pending', []) else 'absent'), running


def _history(studio, url, prompt_id):
    try: response = studio._request('/history/' + quote(prompt_id, safe=''), timeout=15, base_url=url)
    except READ_ERRORS: return 'unreadable'
    if not isinstance(response, dict): return 'unreadable'
    entry = response.get(prompt_id)
    if entry is None: return 'absent'
    return 'present' if isinstance(entry, dict) else 'unreadable'


def _post(studio, url, path, body):
    try: studio._request(path, 'POST', body, timeout=10, base_url=url, allow_empty=True); return 'ok'
    except Exception as exc: return 'no reply: ' + (str(exc) or type(exc).__name__)[:200]


def interrupt_sent(job, prompt_id):
    record = job.get('cancellation')
    return isinstance(record, dict) and any(a.get('action') == 'interrupt' and a.get('prompt_id') == prompt_id for a in record.get('actions', []))


def act(studio, job, submission):
    """Worker: send the one targeted action this prompt's verified queue position allows. True when the job is settled."""
    prompt_id = submission['prompt_id']; url = job.get('comfy_url')
    with studio.lock:
        record = pickup(studio, job)
        if record is None or interrupt_sent(job, prompt_id): return False
        dequeues = sum(1 for a in record['actions'] if a.get('action') == 'dequeue' and a.get('prompt_id') == prompt_id)
    where, running = _queue(studio, url, prompt_id)
    with studio.lock:
        _observe(record, prompt_id, queue=where, running=running[:4])
        if where == 'unreadable':
            _resolve(studio, job, 'refused', "Could not read ComfyUI's queue, so this job's prompt could not be found. Nothing was cancelled; the render continues.")
            studio._save(job); return False
        if where == 'absent':
            other = ' ComfyUI is running another prompt.' if running else ''
            _resolve(studio, job, 'refused', 'ComfyUI does not list this job\'s prompt as waiting or running, so nothing was cancelled.' + other + ' The Studio keeps reading its history.')
            studio._save(job); return False
        if where == 'running' and running != [prompt_id]:
            _resolve(studio, job, 'refused', 'ComfyUI lists more than one running prompt, so the Studio cannot prove the interrupt would reach only this job. Nothing was interrupted.')
            studio._save(job); return False
        if where == 'pending' and dequeues >= MAX_DEQUEUES:
            _resolve(studio, job, 'refused', 'ComfyUI kept this prompt queued after two delete requests; nothing more was sent.')
            studio._save(job); return False
        studio._save(job)
    if where == 'running':
        # /queue listed exactly this prompt as the one running. The targeted body makes ComfyUI (0.35.0+) re-check the
        # running prompt ID itself before interrupting; the outcome is read from /history by the observer.
        reply = _post(studio, url, '/interrupt', {'prompt_id': prompt_id})
        with studio.lock:
            record['actions'].append({'action': 'interrupt', 'prompt_id': prompt_id, 'at': time.time(), 'reply': reply}); studio._save(job)
        return False
    reply = _post(studio, url, '/queue', {'delete': [prompt_id]})
    with studio.lock: record['actions'].append({'action': 'dequeue', 'prompt_id': prompt_id, 'at': time.time(), 'reply': reply})
    # Read back in this order: ComfyUI moves a prompt from running to history under one lock, so a prompt that is in
    # neither the queue read first nor the history read second was removed and never ran.
    after, running = _queue(studio, url, prompt_id)
    history = _history(studio, url, prompt_id) if after == 'absent' else None
    with studio.lock:
        _observe(record, prompt_id, queue=after, history=history, running=running[:4])
        if after == 'absent' and history == 'absent':
            submission['status'] = 'cancelled'; submission['cancelled'] = {'basis': 'dequeued', 'at': time.time()}
            settle(studio, job, 'dequeued'); return True
        studio._save(job)
    return False


def interrupted(history):
    status = history.get('status') if isinstance(history, dict) else None
    messages = status.get('messages') if isinstance(status, dict) else None
    return (status.get('status_str') == 'error' and isinstance(messages, list)
            and any(isinstance(m, list) and m and m[0] == 'execution_interrupted' for m in messages)) if isinstance(status, dict) else False


def record_interrupted(studio, job, submission):
    """Worker: history reports our prompt interrupted after our own interrupt was sent."""
    with studio.lock:
        replies = [a.get('reply') for a in job['cancellation']['actions'] if a.get('action') == 'interrupt' and a.get('prompt_id') == submission['prompt_id']]
        submission['status'] = 'cancelled'; submission['cancelled'] = {'basis': 'interrupted', 'at': time.time(), 'interrupt_reply': replies[-1] if replies else None}
        settle(studio, job, 'interrupted')


def reconcile_restart(job, directory):
    """At load: a request the worker never resolved. A never-sent job is cancelled; anything else is unresolved."""
    try: request = json.loads((directory / REQUEST_FILE).read_text(encoding='utf-8'))
    except (OSError, ValueError): return False
    if not isinstance(request, dict) or type(request.get('event_id')) is not str: return False
    current = job.get('cancellation')
    same = isinstance(current, dict) and current.get('event_id') == request['event_id']
    if same and current.get('state') != 'requested': return False
    record = current if same else dict(request, actions=[], observations=[])
    status = job.get('status'); now = time.time()
    if status == 'not_submitted' and submission_evidence.never_submitted(job):
        job['status'] = 'cancelled'; job['message'] = not_started_message()
        record.update(state='cancelled', resolved_at=now, note='The Studio restarted before submission; nothing was sent to ComfyUI.')
    elif status in CANCELLABLE + ('uncertain',):
        record.update(state='unresolved', resolved_at=now, note='The Studio restarted before it confirmed the cancel. The prompt may still run in ComfyUI; nothing was resubmitted.')
    else:
        record.update(state='too_late', resolved_at=now, note=f'The job had already settled as {status} before the cancel could act; nothing was cancelled.')
    job['cancellation'] = record
    return True
