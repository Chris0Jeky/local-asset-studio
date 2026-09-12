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
JSON_LIMIT = 8 * 1024 * 1024
IMAGE_LIMIT = 20 * 1024 * 1024
HEX = re.compile(r'[0-9a-f]{64}\Z')
PROJECT = re.compile(r'[0-9a-f]{32}\Z')
UPLOAD = re.compile(r'[0-9a-f]{32}_[A-Za-z0-9._-]+\.png\Z')


def require(value, message):
    if not value: raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(raw): return hashlib.sha256(raw).hexdigest()
def hashed(value): return digest(canonical(value))


def decode(raw):
    require(len(raw) <= JSON_LIMIT, 'JSON response exceeds the byte limit')
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'Duplicate JSON key'); result[k] = v
        return result
    def reject(_): raise ValueError('Non-finite JSON number')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=reject)


def read(path):
    with Path(path).open('rb') as stream: return decode(stream.read(JSON_LIMIT + 1))


def relative(value):
    require(isinstance(value, str) and 0 < len(value) <= 240 and '\\' not in value and ':' not in value,
            'Use a portable workspace-relative path')
    require(not PurePosixPath(value).is_absolute() and all(x not in ('', '.', '..') for x in value.split('/')),
            'Noncanonical or escaping path')
    require(not any(ord(x) < 32 or x in '<>"|?*' for x in value), 'Invalid path character')
    for part in value.split('/'):
        stem = part.split('.')[0].upper()
        require(not part.endswith((' ', '.')) and stem not in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}, 'Nonportable path component')


def local(root, name, exists=True):
    relative(name); base = Path(root).resolve(strict=True); p = base / name
    require(p.resolve().is_relative_to(base), 'Path escapes workspace through a symlink')
    if exists: require(p.is_file() and not p.is_symlink(), 'Missing or symlinked artifact: ' + name)
    return p


def bytes_of(root, artifact, limit=IMAGE_LIMIT):
    require(isinstance(artifact, dict) and set(artifact) == {'path', 'sha256'}, 'Invalid artifact descriptor')
    require(isinstance(artifact['sha256'], str) and HEX.fullmatch(artifact['sha256']), 'Invalid artifact digest')
    with local(root, artifact['path']).open('rb') as stream: raw = stream.read(limit + 1)
    require(0 < len(raw) <= limit and digest(raw) == artifact['sha256'], 'Artifact changed or exceeds limit: ' + artifact['path'])
    return raw


def artifact(root, name):
    return {'path': name, 'sha256': digest(local(root, name).read_bytes())}


def save_new(path, data):
    raw = data if isinstance(data, bytes) else canonical(data)
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def image_info(raw):
    require(0 < len(raw) <= IMAGE_LIMIT, 'PNG byte limit exceeded')
    with Image.open(io.BytesIO(raw)) as im:
        require(im.format == 'PNG' and getattr(im, 'n_frames', 1) == 1, 'Single-frame PNG required')
        require(im.width * im.height <= 24_000_000 and im.mode in ('RGB', 'RGBA'), 'Unsupported PNG size/mode')
        require(not im.info.get('exif') and not im.info.get('icc_profile'), 'Normalize EXIF/ICC explicitly before this neural bridge')
        im.load(); return im.convert('RGBA').copy()


class StudioHTTP:
    """Numeric IPv4 loopback only: no DNS, proxies, redirects, cookies or retries."""
    def __init__(self, port=8191, timeout=120):
        require(type(port) is int and 1 <= port <= 65535, 'Invalid Studio port')
        require(type(timeout) in (int, float) and 0 < timeout <= 300, 'Invalid timeout')
        self.port, self.timeout = port, timeout
        self.origin = f'http://127.0.0.1:{port}'

    def request(self, method, path, body=None, *, binary=False, filename=None):
        require(method in ('GET', 'POST') and path.startswith('/api/') and '\\' not in path
                and '#' not in path and not any(ord(c) < 32 for c in path), 'Invalid Studio request')
        raw = body if isinstance(body, bytes) else (canonical(body) if body is not None else None)
        limit = IMAGE_LIMIT if binary else JSON_LIMIT
        require(raw is None or len(raw) <= (IMAGE_LIMIT if filename else JSON_LIMIT), 'Request too large')
        headers = {'Origin': self.origin, 'Accept': 'image/png' if binary else 'application/json'}
        if raw is not None: headers['Content-Type'] = 'image/png' if filename else 'application/json'
        if filename:
            require(re.fullmatch(r'[A-Za-z0-9._-]+\.png', filename), 'Invalid upload filename')
            headers['X-Filename'] = filename
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=self.timeout)
        try:
            conn.request(method, path, body=raw, headers=headers); response = conn.getresponse()
            length = response.getheader('Content-Length')
            if length is not None: require(length.isdigit() and int(length) <= limit, 'Response too large')
            require(200 <= response.status < 300, f'Studio HTTP {response.status}; no automatic retry')
            data = response.read(limit + 1)
            require(len(data) <= limit, 'Response too large')
            return data if binary else decode(data)
        finally: conn.close()


def prepare(workspace, plan_name, output, seeds, *, repo=ROOT, max_seconds=1800):
    """Compile a local, reviewed edit to explicit Qwen reference slots. No HTTP."""
    from scripts import character_edit as edit, character_edit_pixels as pixels
    from scripts.character_study import validate_canon, verify_artifact
    root = Path(workspace).resolve(strict=True); plan_path = local(root, plan_name)
    plan = read(plan_path); edit.check_plan(plan)
    require(plan['intent']['operation'] in ('anatomy-repair', 'costume-change', 'local-repaint'),
            'This bridge currently supports single-actor local edits, not scene/interaction generation')
    require(len(plan['document']['actors']) == 1 and len(plan['targets']) == 1,
            'Multi-actor conditioning needs a separate native bridge; no actor references will be dropped')
    require('qwen-edit-local' in plan['candidate_routes'], 'Qwen is excluded by this edit policy')
    require(canonical(plan['catalog']) == canonical(read(Path(repo)/'research/character-consistency/edit-routes.json')),
            'Route evidence changed; recompile the edit plan')
    require(isinstance(seeds, list) and 1 <= len(seeds) <= 4 and all(type(s) is int and 0 <= s <= 2**63-1 for s in seeds)
            and len(set(seeds)) == len(seeds), 'Use one to four distinct integer seeds')
    budget = plan['intent']['budget']
    require(1 <= budget['max_candidates'] <= 16 and len(seeds) + budget['max_repairs'] <= budget['max_candidates'],
            'Primary candidates and reserved repairs must fit the existing Production cap (16)')
    require(type(max_seconds) is int and 60 <= max_seconds <= 14400, 'Invalid time budget')
    actor = plan['document']['actors'][0]; refs = actor['references']
    require(1 <= len(refs) <= 2 and sum(r['role'] == 'identity' for r in refs) == 1,
            'Use exactly one identity and at most one other reference; this bridge never truncates references')
    canon = validate_canon(read(verify_artifact(root, actor['canon'])))
    require(canon['approval']['state'] == 'approved', 'An approved canon attestation is required; no owner decision is inferred')
    identity = next(r for r in refs if r['role'] == 'identity')
    require(any(r['role'] == 'identity' and r['sha256'] == identity['image']['sha256'] for r in canon['references']),
            'Actor identity image is not an identity reference of its approved canon')
    source, mask, protection = pixels._inputs(root, plan)
    crop = source.crop(tuple(plan['intent']['context_box'])).convert('RGBA')
    require(crop.getchannel('A').getextrema() == (255, 255),
            'Transparent source crops need an explicit matting/alpha contract; this bridge does not invent one')
    require(not source.info.get('icc_profile'), 'Normalize source ICC explicitly before this neural bridge')
    refs = sorted(refs, key=lambda r: r['role'] != 'identity')
    for r in refs:
        image_info(bytes_of(root, r['image']))
        require(len('; '.join(r['take'])) <= 1500 and len('; '.join(r['ignore'])) <= 1500,
                'Reference guidance exceeds native limit; nothing is truncated')
    expected_preset = f'qwen-{len(refs)+1}ref'
    cat = read(Path(repo)/'presets/catalog.json')
    preset = next((p for p in cat['presets'] if p['id'] == expected_preset), None)
    require(preset is not None and len(preset.get('reference_slots', [])) == len(refs)+1, 'Matching native Qwen preset missing')
    template_path = Path(repo)/preset['graph']
    require(template_path.resolve().is_relative_to((Path(repo)/'workflows/api').resolve()), 'Unexpected native template location')
    template = template_path.read_bytes(); graph = decode(template)
    require(sum(n.get('class_type') == 'LoadImage' for n in graph.values()) == len(refs)+1, 'Unexpected native reference count')
    # Staging is local and exclusive; an incomplete folder is preserved for inspection.
    target = local(root, output, exists=False)
    require(not target.exists() and not target.is_symlink(), 'Choose a new handoff directory')
    target.mkdir(parents=True)
    prepared_name = output + '/prepared'; bundle = pixels.prepare(root, plan, prepared_name)
    context = pixels.png(target/'prepared/context.png').convert('RGBA')
    w, h = context.size
    require(64 <= w <= 1536 and 64 <= h <= 1536 and w % 8 == 0 and h % 8 == 0
            and w*h <= preset.get('max_reference_pixels', 1024*1024), 'Crop does not fit native Qwen dimensions; no silent resampling')
    # Only alignment padding can be transparent here. Its explicit model matte is black.
    rgb = Image.new('RGB', context.size, (0, 0, 0)); rgb.paste(context, mask=context.getchannel('A'))
    with (target/'model-context.png').open('xb') as stream: rgb.save(stream, format='PNG')
    specs = [{'image': artifact(root, output+'/model-context.png'), 'role': 'composition',
              'contribution': 'Current source crop, camera, pose and surrounding context. Apply only the requested change.',
              'avoid': 'Unrequested redesign, labels or additional figures.'}]
    for r in refs:
        specs.append({'image': copy.deepcopy(r['image']), 'role': r['role'],
                      'contribution': '; '.join(r['take']), 'avoid': '; '.join(r['ignore'])})
    originals = [plan['document']['source'], actor['canon'], plan['intent']['edit_mask']]
    if plan['intent']['protect_mask']: originals.append(plan['intent']['protect_mask'])
    originals += [r['image'] for r in refs]
    for r in canon['references']:
        ref = {'path': r['path'], 'sha256': r['sha256']}; bytes_of(root, ref); originals.append(ref)
    originals += [artifact(root, plan_name), artifact(root, prepared_name+'/bundle.json'),
                  artifact(root, prepared_name+'/context.png'), artifact(root, prepared_name+'/edit-mask.png')]
    instruction = '\n'.join(c['instruction'] for c in plan['intent']['changes'])
    prompt = (instruction + '\nReturn one edited image of the current source crop (Image 1), at the same framing and scale. '
              'Keep identity from the identity reference; do not copy its pose or background. '
              'Preserve details not requested to change. Do not add text or panels.')
    require(len(prompt) <= 12000, 'Combined brief exceeds the bridge limit; nothing is truncated')
    handoff = {'schema_version': 1, 'kind': 'character_edit_studio_handoff', 'plan': artifact(root, plan_name),
        'edit_plan_sha256': plan['plan_sha256'], 'document_sha256': plan['intent']['document_sha256'],
        'bundle': prepared_name, 'bundle_sha256': bundle['bundle_sha256'], 'references': specs,
        'originals': list({r['path']: r for r in originals}.values()), 'size': [w, h], 'seeds': seeds,
        'preset_id': expected_preset, 'template_sha256': digest(template), 'positive': prompt,
        'max_candidates': budget['max_candidates'], 'reserved_repairs': budget['max_repairs'],
        'max_seconds': max_seconds, 'budget_owner': plan['budget_owner'],
        'policy': next(r for r in plan['route_reports'] if r['route_id'] == 'qwen-edit-local'),
        'scope': 'One actor; semantic reference conditioning; write mask applied after generation, not sent as a native pose/inpaint control.',
        'context_conversion': 'Opaque source crop; zero-fill alignment padding explicitly matted to black RGB without resampling.',
        'submits_generation': False}
    handoff['sha256'] = hashed(handoff); save_new(target/'handoff.json', handoff)
    return handoff


def validate_handoff(root, value):
    require(isinstance(value, dict) and value.get('kind') == 'character_edit_studio_handoff'
            and type(value.get('schema_version')) is int and value['schema_version'] == 1, 'Invalid handoff')
    require(value.get('sha256') == hashed({k: v for k, v in value.items() if k != 'sha256'}), 'Handoff hash mismatch')
    require(all(isinstance(value.get(k), str) and HEX.fullmatch(value[k]) for k in ('edit_plan_sha256','document_sha256','bundle_sha256')), 'Invalid identity digest')
    relative(value['bundle'])
    require(value['submits_generation'] is False and value['policy']['eligible_by_preference'] is True, 'Invalid handoff claim/policy')
    require(value['preset_id'] in ('qwen-2ref', 'qwen-3ref') and HEX.fullmatch(value['template_sha256']), 'Unsupported native profile')
    refs = value['references']; require(len(refs) == int(value['preset_id'][5]) and refs[0]['role'] == 'composition', 'Wrong reference projection')
    require(sum(r['role'] == 'identity' for r in refs) == 1, 'Exactly one identity binding required')
    require(all(r['role'] in ('composition', 'identity', 'costume', 'style', 'pose') for r in refs), 'Invalid reference role')
    seeds = value['seeds']
    require(isinstance(seeds, list) and 1 <= len(seeds) <= 4 and all(type(s) is int and 0 <= s <= 2**63-1 for s in seeds)
            and len(set(seeds)) == len(seeds), 'Invalid seed budget')
    require(type(value['max_candidates']) is int and 1 <= value['max_candidates'] <= 16
            and type(value['reserved_repairs']) is int and 0 <= value['reserved_repairs'] <= 3
            and len(seeds)+value['reserved_repairs'] <= value['max_candidates'], 'Invalid candidate allowance')
    require(type(value['max_seconds']) is int and 60 <= value['max_seconds'] <= 14400, 'Invalid time budget')
    require(isinstance(value['positive'], str) and 0 < len(value['positive']) <= 12000, 'Invalid compiled brief')
    for ref in value['originals']: bytes_of(root, ref)
    bytes_of(root, value['plan'])
    for ref in refs:
        require(isinstance(ref['contribution'], str) and len(ref['contribution']) <= 1500
                and isinstance(ref['avoid'], str) and len(ref['avoid']) <= 1500, 'Invalid reference guidance')
        im = image_info(bytes_of(root, ref['image']))
        if ref is refs[0]: require(list(im.size) == value['size'] and im.getchannel('A').getextrema() == (255,255), 'Model context changed')
    w,h=value['size']; require(type(w) is int and type(h) is int and 64<=w<=1536 and 64<=h<=1536 and w%8==h%8==0 and w*h<=1024**2, 'Invalid native crop size')
    return value


class Bridge:
    """Command receipts, not a second queue or a trust boundary against the local owner."""
    def __init__(self, workspace, handoff_name, client=None):
        self.root = Path(workspace).resolve(strict=True)
        self.handoff_name = handoff_name
        self.handoff = validate_handoff(self.root, read(local(self.root, handoff_name)))
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

    def project(self, state, identifier=None):
        identifier = identifier or state.get('project_id')
        require(isinstance(identifier,str) and PROJECT.fullmatch(identifier), 'No valid known project ID')
        project = self.client.request('GET','/api/production/'+identifier)
        p = project['plan']; stages = p['stages']; expected = state['previews']
        require(project['id'] == identifier and project['root_id'] == identifier and p['name'] == self.name
                and p['kind'] == 'comparison' and p.get('parent_project') is None, 'Unexpected Production ownership')
        require(canonical(p['values']) == canonical(self.handoff['seeds']) and p['axis'] == 'seed'
                and len(stages) == len(expected), 'Production cases differ from this handoff')
        require(type(project['budget']['allowance']) is int and type(project['budget']['reserved']) is int and
                0 <= project['budget']['reserved'] <= project['budget']['allowance'] and project['budget']['allowance'] == self.handoff['max_candidates'], 'Production budget differs')
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
            state['identity'] = self.identity(state); self.templates()
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
                'controls':{'positive':self.handoff['positive'],'width':self.handoff['size'][0]},
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
                require(records[0]['transform']['vae_size']==self.handoff['size'], 'Native preprocessing changes candidate dimensions')
                previews.append(preview)
            state['previews']=previews
            state['request']={'name':self.name,'recipe':recipe,'axis':'seed','values':self.handoff['seeds'],
                              'max_generations':self.handoff['max_candidates'],'max_seconds':self.handoff['max_seconds']}
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
            require(project['state']['status']=='planned' and project['budget']['reserved']==0, 'Project has already been started elsewhere')
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
            dest.mkdir(); save_new(dest/'candidate.png',raw)
            receipt={'kind':'character_edit_candidate','handoff_sha256':self.handoff['sha256'], 'project_id':project['id'],
                'project_sha256':project['plan']['sha256'],'stage_index':index,'job_id':expected_id,'prompt_ids':job.get('prompt_ids',[]),
                'asset_id':aid,'candidate':artifact(self.root,(dest/'candidate.png').relative_to(self.root).as_posix()),
                'job_recipe':recipe,'review_state':'unreviewed','semantic_approval':False}
            receipt['sha256']=hashed(receipt); save_new(dest/'receipt.json',receipt)
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
    for name in ('stage','start','status','reconcile','collect','compose'):
        p=sub.add_parser(name); p.add_argument('--workspace',required=True); p.add_argument('--handoff',required=True)
        p.add_argument('--studio-port',type=int,default=8191)
        if name=='stage':p.add_argument('--resume-uploads',action='store_true')
        if name in ('collect','compose'):p.add_argument('--index',type=int,required=True)
        if name=='compose':p.add_argument('--current-document',required=True); p.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        if args.command=='prepare':value=prepare(args.workspace,args.plan,args.out,args.seeds,max_seconds=args.max_seconds)
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
