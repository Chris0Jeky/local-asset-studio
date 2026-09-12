"""Bounded project schema and immutable edits shared by CLI, MCP and workbench."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path, PurePosixPath
import re

MAX_JSON = 2 * 1024 * 1024
MAX_ASSET = 512 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024

def need(ok, message):
    if not ok: raise ValueError(message)

def number(value, low, high, name, integer=False):
    need(type(value) is int if integer else type(value) in (int, float), f'{name}: wrong numeric type')
    need(math.isfinite(value) and low <= value <= high, f'{name}: outside {low}..{high}')

def fields(obj, required, optional=()):
    need(isinstance(obj, dict), 'Expected object')
    need(set(required) <= obj.keys() and obj.keys() <= set(required) | set(optional), 'Missing or unknown fields')

def ident(value):
    need(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value), 'Invalid ID')

def text(value):
    need(isinstance(value, str) and 0 < len(value) <= 1000 and '\0' not in value, 'Invalid text')

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def digest(value): return hashlib.sha256(canonical(value)).hexdigest()

def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def read_json(path):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'Duplicate JSON key'); result[k] = v
        return result
    def bad(value): raise ValueError('Nonfinite JSON number')
    with Path(path).open('rb') as f: raw = f.read(MAX_JSON+1)
    need(len(raw) <= MAX_JSON, 'JSON size cap exceeded')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)

def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as f: f.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')

def safe_path(root, relative, must_exist=True):
    text(relative)
    need('\\' not in relative and ':' not in relative and not relative.startswith('/'), 'Use local portable relative paths')
    need(all(p not in ('', '.', '..') for p in relative.split('/')), 'Noncanonical or escaping path')
    path = (Path(root).resolve()/PurePosixPath(relative)).resolve()
    need(path.is_relative_to(Path(root).resolve()), 'Path/symlink escapes workspace')
    if must_exist: need(path.is_file(), f'Missing file: {relative}')
    return path

def layout(project):
    start = 0; out = []
    for shot in project['shots']:
        start -= shot['transition_frames']
        out.append({'id':shot['id'], 'start_frame':start, 'end_frame':start+shot['frames']})
        start += shot['frames']
    return out

def validate(p, root=None):
    fields(p, ['schema_version','name','fps','size','sample_rate','assets','shots','overlays','audio','master_gain_db'])
    need(type(p['schema_version']) is int and p['schema_version']==1, 'Expected schema 1')
    text(p['name'])
    need(isinstance(p['fps'], list) and len(p['fps'])==2, 'fps must be numerator/denominator')
    for x in p['fps']: number(x,1,60000,'fps component',True)
    fps=p['fps'][0]/p['fps'][1]; need(1 <= fps <= 60, 'fps outside 1..60')
    need(isinstance(p['size'], list) and len(p['size'])==2, 'Expected width,height')
    for x in p['size']: number(x,64,1920,'dimension',True); need(x%2==0,'Even dimensions required')
    need(p['size'][0]*p['size'][1] <= 1920*1080,'Pixel budget exceeded')
    need(type(p['sample_rate']) is int and p['sample_rate']==48000,'Interchange rate must be 48000')
    number(p['master_gain_db'],-60,6,'master gain')
    need(isinstance(p['assets'],dict) and 1<=len(p['assets'])<=64,'Expected 1..64 assets')
    total=0
    for key,a in p['assets'].items():
        ident(key); fields(a,['path','kind','sha256'])
        need(a['kind'] in ('image','video','audio'),'Unsupported media kind')
        need(isinstance(a['sha256'],str) and re.fullmatch(r'[0-9a-f]{64}',a['sha256']),'Expected SHA256')
        safe_path(root or Path.cwd(),a['path'],False)
        need(Path(a['path']).suffix.lower() in {'image':('.png',),'video':('.mp4',),'audio':('.wav',)}[a['kind']], 'Use PNG, MP4 or WAV interchange')
        if root is not None:
            path=safe_path(root,a['path']); sz=path.stat().st_size
            need(0<sz<=MAX_ASSET,'Empty/oversize input'); total+=sz
            need(file_hash(path)==a['sha256'],f'Changed asset: {key}')
    need(total<=MAX_TOTAL,'Total input byte cap exceeded')
    def asset(key, kinds):
        need(isinstance(key,str) and key in p['assets'] and p['assets'][key]['kind'] in kinds,'Wrong or missing asset kind')
    ids=set()
    def unique(key): ident(key); need(key not in ids,'Duplicate clip ID'); ids.add(key)
    need(isinstance(p['shots'],list) and 1<=len(p['shots'])<=16,'Expected 1..16 shots')
    for i,s in enumerate(p['shots']):
        fields(s,['id','asset','source_in','frames','transition_frames']); unique(s['id']); asset(s['asset'],('image','video'))
        number(s['source_in'],0,216000,'source frame',True); number(s['frames'],1,7200,'frames',True)
        number(s['transition_frames'],0,180,'transition',True)
        if i==0: need(s['transition_frames']==0,'First shot cannot have transition')
        else: need(s['transition_frames'] < min(s['frames'],p['shots'][i-1]['frames']-p['shots'][i-1]['transition_frames']), 'Transitions consume shot or overlap each other')
        if p['assets'][s['asset']]['kind']=='image': need(s['source_in']==0,'Still image source_in must be zero')
    length=layout(p)[-1]['end_frame']; need(length/fps<=120,'Preview duration cap is 120 seconds')
    need(isinstance(p['overlays'],list) and len(p['overlays'])<=16,'Overlay cap exceeded')
    for o in p['overlays']:
        fields(o,['id','asset','start','frames','x','y','width','height','opacity']);unique(o['id']);asset(o['asset'],('image',))
        for k,lo,hi in [('start',0,length-1),('frames',1,length),('x',0,p['size'][0]-1),('y',0,p['size'][1]-1),('width',1,p['size'][0]),('height',1,p['size'][1])]: number(o[k],lo,hi,k,True)
        need(o['start']+o['frames']<=length and o['x']+o['width']<=p['size'][0] and o['y']+o['height']<=p['size'][1],'Overlay exceeds canvas/time')
        number(o['opacity'],0,1,'opacity')
    samples=round(Fraction(length*p['fps'][1]*48000,p['fps'][0]))
    need(isinstance(p['audio'],list) and len(p['audio'])<=32,'Audio clip cap exceeded')
    for c in p['audio']:
        fields(c,['id','asset','bus','start_sample','source_sample','samples','gain_db','fade_in','fade_out','mute']);unique(c['id']);asset(c['asset'],('audio',))
        need(c['bus'] in ('dialogue','music','fx','ambience'),'Unknown bus')
        for k,lo,hi in [('start_sample',0,samples-1),('source_sample',0,48000*3600),('samples',1,samples),('fade_in',0,samples),('fade_out',0,samples)]:number(c[k],lo,hi,k,True)
        need(c['start_sample']+c['samples']<=samples,'Audio exceeds project end')
        need(c['fade_in']+c['fade_out']<=c['samples'],'Fades overlap')
        need(type(c['mute']) is bool,'mute must be boolean');number(c['gain_db'],-60,6,'clip gain')
    return {'project_sha256':digest(p),'frames':length,'samples':samples,'duration_seconds':length/fps,'shots':layout(p),'gpu_required':False}

def edit(p, expected_revision, section, clip_id, field, value):
    validate(p); need(digest(p)==expected_revision,'Stale project revision')
    allowed={'audio':{'gain_db','mute','start_sample','source_sample','samples','fade_in','fade_out'},'shots':{'frames','source_in','transition_frames'},'overlays':{'start','frames','x','y','width','height','opacity'}}
    need(section in allowed and field in allowed[section], 'Unsupported edit operation')
    q=copy.deepcopy(p); hits=[c for c in q[section] if c['id']==clip_id];need(len(hits)==1,'Unknown clip')
    old=hits[0][field];hits[0][field]=value;validate(q)
    return {'project':q,'revision':digest(q),'operation':{'parent':expected_revision,'section':section,'clip_id':clip_id,'field':field,'before':old,'after':value},'render_stale':True}
