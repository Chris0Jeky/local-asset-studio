"""Explicit, receipt-backed Studio adapter for the existing procedural factory.

Discovery and preparation never run a native tool. Each project owns one attempt;
recovery inspects its files rather than repeating a possibly completed build.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import uuid
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'scripts') not in sys.path:sys.path.append(str(ROOT / 'scripts'))
import engine_validation as engine
import procgen_factory as factory
import project_storage
import observation_state

OPERATION = 'native.procedural-asset.v1'
VALIDATOR_DIR = ROOT / 'tools/gltf-validation/node_modules/gltf-validator'
SOURCE_FILES = ('app/procedural.py','scripts/procgen_factory.py','scripts/procgen_blender.py',
                'scripts/procgen_generators.json','scripts/procgen_godot_probe.gd',
                'scripts/engine_validation.py','tools/gltf-validation/validate.cjs')
LABELS = {'room_kit':'Room kit','prop':'Small prop','shrine':'Shrine','lighthouse_room':'Lighthouse room',
          'pier':'Harbour pier','coastal_path':'Coastal path','tide_pools':'Tide pools','market_street':'Market street'}
LOD_FILES = tuple(f'asset_LOD{i}.glb' for i in range(3))
MAX_FILE_BYTES = 512 * 1024**2
MAX_PACK_BYTES = 512 * 1024**2
SHA = re.compile(r'[a-f0-9]{64}')


def require(condition, message):
    if not condition:raise ValueError(message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _executable(config, key):
    value = config.get(key)
    require(isinstance(value,str) and bool(value), f'Set {key.title()} in config/local.json to an absolute executable path')
    path = Path(value).expanduser()
    require(path.is_absolute() and path.is_file(), f'{key.title()} must be an existing absolute executable path in config/local.json')
    return path.resolve()


def _validator_files():
    require(VALIDATOR_DIR.is_dir(), 'Install the pinned Khronos validator: npm ci --prefix tools/gltf-validation --ignore-scripts')
    metadata = engine.read_json(VALIDATOR_DIR / 'package.json')
    require(metadata.get('name')=='gltf-validator' and metadata.get('version')==engine.VALIDATOR_VERSION,
            'Installed Khronos validator differs from the pinned version; reinstall tools/gltf-validation')
    files = sorted(path for path in VALIDATOR_DIR.rglob('*') if path.is_file())
    require(files and len(files)<=64 and sum(p.stat().st_size for p in files)<=64*1024**2,
            'Khronos validator package exceeds its inspection budget')
    require(any(p.suffix=='.js' for p in files), 'Khronos validator package is incomplete; reinstall tools/gltf-validation')
    require(all(p.resolve().is_relative_to(VALIDATOR_DIR.resolve()) and not p.is_symlink() for p in files),
            'Khronos validator files must stay inside the installed package')
    return files


def readiness(studio, verify_engine=False):
    missing = []
    for key in ('blender','node') + (('godot',) if verify_engine else ()):
        try:_executable(studio.config,key)
        except (OSError,ValueError) as exc:missing.append(str(exc))
    try:_validator_files()
    except (OSError,ValueError) as exc:missing.append(str(exc))
    try:_executable(studio.config,'godot');godot = True
    except (OSError,ValueError):godot = False
    return {'ready':not missing,'missing':missing,'godot_available':godot,
            'note':'Blender 5.4 is required by these generators. This check finds configured files only; it does not verify application versions. Native compatibility is measured when you explicitly start a build.'}


def catalog(studio):
    schema = factory.load_schema()
    return {'version':1,'units':schema['units'],
            'generators':{key:{**copy.deepcopy(spec),'label':LABELS.get(key,key.replace('_',' ').title())}
                          for key,spec in schema['generators'].items()},
            'runtime':readiness(studio),'privacy':'regular','execution':'Prepare a plan, then Start explicitly in Comparisons.'}


def validate(payload):
    require(isinstance(payload,dict), 'Procedural asset intent must be an object')
    require(set(payload)<={'name','generator','params','render','verify_engine'},
            'Procedural assets accept only name, generator, params, render and verify_engine; this workflow is Regular-only')
    name = payload.get('name')
    require(isinstance(name,str) and 1<=len(name.strip())<=120, 'Name the asset (1–120 characters)')
    generator = payload.get('generator');schema = factory.load_schema()
    require(isinstance(generator,str) and generator in schema['generators'], 'Choose an available procedural generator')
    spec = schema['generators'][generator]
    params, errors = factory.resolve_params(spec,payload.get('params',{}))
    if not errors:errors = factory.check_constraints(spec,params)
    require(not errors, '; '.join(errors))
    render, verify = payload.get('render',True), payload.get('verify_engine',False)
    require(type(render) is bool and type(verify) is bool, 'render and verify_engine must be boolean')
    return {'name':name.strip(),'generator':generator,'params':params,'render':render,'verify_engine':verify}


def _pins(studio, verify):
    paths = {key:_executable(studio.config,key) for key in ('blender','node') + (('godot',) if verify else ())}
    return {'executables':{key:{'path':str(path),'sha256':engine.file_sha(path)} for key,path in paths.items()},
            'sources':{name:engine.file_sha(ROOT / name) for name in SOURCE_FILES},
            'validator':{path.relative_to(VALIDATOR_DIR).as_posix():engine.file_sha(path) for path in _validator_files()}}


def prepare(studio, payload):
    intent = validate(payload)
    available = readiness(studio,intent['verify_engine'])
    require(available['ready'], '; '.join(available['missing']))
    plan = {'version':1,'operation':OPERATION,'intent':intent,'pins':_pins(studio,intent['verify_engine']),
            'no_comfy_submission':True,'outputs':[*LOD_FILES,'asset.blend'] + (['contact_sheet.png'] if intent['render'] else [])}
    plan['sha256'] = fingerprint(plan)
    return plan


def _validate_plan(studio, plan, live=True):
    fields = {'version','operation','intent','pins','no_comfy_submission','outputs','sha256'}
    require(isinstance(plan,dict) and set(plan)==fields, 'Procedural plan shape changed')
    require(plan['sha256']==fingerprint({k:v for k,v in plan.items() if k!='sha256'}), 'Procedural plan fingerprint changed')
    require(type(plan['version']) is int and plan['version']==1 and plan['operation']==OPERATION
            and plan['no_comfy_submission'] is True, 'Unsupported procedural plan')
    if live:
        expected = prepare(studio,plan['intent'])
        require(plan==expected, 'Factory sources, configured tools or parameters changed; prepare a new plan')
    return copy.deepcopy(plan)


def _directory(studio, identifier):
    root = (Path(studio.experiments) / 'projects').resolve()
    path = project_storage.directory(root,identifier)
    require(path.is_dir() and path.resolve().is_relative_to(root), 'Procedural project directory is unavailable')
    return path


def attempt_exists(directory):
    return any(path.exists() or project_storage._linked(path)
               for path in (directory/'procedural',directory/'procedural-job.json'))


def _file(base, relative, limit=MAX_FILE_BYTES):
    candidate = base / relative
    require(candidate.resolve().is_relative_to(base.resolve()) and candidate.is_file(), 'Procedural artifact is missing or escapes its project: '+relative)
    for part in (candidate,*candidate.parents):
        if part==base.parent:break
        require(not project_storage._linked(part), 'Procedural artifact must not be a link: '+relative)
    require(0<candidate.stat().st_size<=limit, 'Procedural artifact is empty or exceeds its byte limit: '+relative)
    return candidate


def _write(path, value):
    require(not project_storage._linked(path), 'Procedural receipt must not be a link')
    observation_state.publish(path,value)


def native_job(identifier, plan):
    return {'id':uuid.uuid5(uuid.NAMESPACE_URL,f'asset-studio:{identifier}:{OPERATION}').hex,
            'status':'running','operation':OPERATION,'prompt_ids':[],'submissions':[],
            'created_at':time.time(),'preset_id':'procedural-'+plan['intent']['generator'],
            'preset_name':plan['intent']['name'],'parent_assets':[],'outputs':[],'project_id':identifier,
            'graph':{},'graph_path':'','controls':plan['intent']['params'],'batch_count':0,'references':[],
            'native_recipe':plan,'privacy':'regular','publication_status':'pending',
            'message':'Building the prepared procedural asset; no ComfyUI prompt is submitted.'}


def _output_records(plan):
    return [{'filename':name,'media_type':'3d' if name.endswith('.glb') else 'image',
             'native_path':'procedural/'+name,'source':{'operation':OPERATION,'generator':plan['intent']['generator']}}
            for name in plan['outputs'] if name!='asset.blend']


def _retained_outputs(job, *records):
    """Only known Library identities may survive an incomplete/failed inspection.

    Registration is ordered, so retained outputs form a prefix with their original
    indexes. Unregistered native paths must not appear as playable job outputs.
    """
    records=[record for record in records if isinstance(record,dict) and record.get('id')==job['id']
             and record.get('native_recipe')==job['native_recipe']]
    outputs=[]
    for index,output in enumerate(_output_records(job['native_recipe'])):
        for record in records:
            known=record.get('outputs',[])
            if not isinstance(known,list) or index>=len(known):continue
            saved=known[index]
            if (isinstance(saved,dict) and all(saved.get(k)==output[k] for k in ('filename','native_path','media_type'))
                    and isinstance(saved.get('asset_id'),str) and re.fullmatch('[a-f0-9]{32}',saved['asset_id'])):
                output['asset_id']=saved['asset_id'];break
        if 'asset_id' not in output:break
        outputs.append(output)
    return outputs


def _retain_job_evidence(job, record):
    if not isinstance(record,dict) or record.get('id')!=job['id'] or record.get('native_recipe')!=job['native_recipe']:return
    job['outputs']=_retained_outputs(job,job,record)
    for key in ('created_at','publication_error','receipt_error'):
        if key in record:job[key]=copy.deepcopy(record[key])
    if record.get('failure_files'):job['failure_files']=True


def _artifact(identifier, directory, relative, role):
    path = _file(directory,relative)
    return {'path':relative,'url':f'/api/production/{identifier}/files/{relative}','role':role,
            'sha256':engine.file_sha(path),'bytes':path.stat().st_size}


def _diagnostics(identifier, directory):
    names = ['procedural-job.json','recipe.json','procedural/report.json','procedural/request.json',
             'procedural/measurements.json','procedural/blender-exit.json','procedural/blender-stdout.log','procedural/blender-stderr.log']
    names += [f'procedural/khronos-asset_LOD{i}/{name}' for i in range(3)
              for name in ('khronos-report.json','khronos-exit.json','khronos-stdout.log','khronos-stderr.log')]
    names += [f'procedural/{name}' for name in ('godot-import-exit.json','godot-import-stdout.log','godot-import-stderr.log',
                                                     'godot-probe-exit.json','godot-probe-stdout.log','godot-probe-stderr.log')]
    artifacts = []
    for name in names:
        try:artifacts.append(_artifact(identifier,directory,name,'execution-diagnostic'))
        except (OSError,ValueError):pass # Missing/unsafe diagnostic files are never made downloadable.
    return artifacts


def _checked_report(directory, plan):
    base = directory / 'procedural'
    report = engine.read_json(_file(base,'report.json',4*1024**2))
    intent = plan['intent']
    require(isinstance(report,dict) and report.get('schema_version')==1 and report.get('generator')==intent['generator']
            and report.get('params')==intent['params'], 'Factory report does not match the prepared parameters')
    require(report.get('schema_sha256')==plan['pins']['sources']['scripts/procgen_generators.json']
            and report.get('blender_script_sha256')==plan['pins']['sources']['scripts/procgen_blender.py'], 'Factory report source identity changed')
    if report.get('state') in ('failed','rejected'):
        failures=[str(message) for gate in report.get('gates',[]) if isinstance(gate,dict)
                  for message in gate.get('failures',[]) if isinstance(message,str)]
        raise ValueError('Procedural build failed: '+('; '.join(failures)[:400] or 'inspect the retained factory report'))
    execution = engine.read_json(_file(base,'blender-exit.json',4*1024**2))
    require(execution.get('state')=='completed' and type(execution.get('returncode')) is int and execution['returncode']==0,
            'Retained Blender execution does not prove completion')
    gates = report.get('gates')
    require(isinstance(gates,list) and all(isinstance(g,dict) and isinstance(g.get('gate'),str) for g in gates), 'Factory gate report is incomplete')
    by_name = {g['gate']:g for g in gates}
    require(len(by_name)==len(gates), 'Factory gate report has duplicate checks')
    expected = {'params','constraints','gn_interface','parts_present','dimensions','manifold','uv','triangle_budget',
                'lod_chain','naming','pivots','interpenetration','khronos','godot_import'}
    require(expected<=set(by_name), 'Factory gate report is missing required checks')
    for name, gate in by_name.items():
        skipped = name=='godot_import' and not intent['verify_engine']
        require(gate.get('passed') is (None if skipped else True) and gate.get('failures')==[], 'Factory check did not pass: '+name)
    state = 'passed' if intent['verify_engine'] else 'incomplete'
    require(report.get('state')==state and report.get('failed_gates')==[]
            and report.get('skipped_gates')==([] if intent['verify_engine'] else ['godot_import']), 'Factory verification status is inconsistent')
    outputs = report.get('outputs')
    require(isinstance(outputs,dict) and set(outputs)==set(plan['outputs']), 'Factory output list does not match the prepared contract')
    for name,digest in outputs.items():
        path = _file(base,name)
        require(isinstance(digest,str) and SHA.fullmatch(digest) and engine.file_sha(path)==digest, 'Procedural artifact changed: '+name)
        if name.endswith('.glb'):engine.inspect_glb(path)
        if name=='contact_sheet.png':
            with Image.open(path) as image:
                require(image.format=='PNG' and image.size==(768,768), 'Factory contact sheet must be a 768 × 768 PNG')
                image.verify()
    return report


def _publish(studio, identifier, directory, plan, job):
    report = _checked_report(directory,plan)
    outputs = _output_records(plan)
    for index,known in enumerate(_retained_outputs(job,job)):outputs[index]['asset_id']=known['asset_id']
    pack = directory / 'export.zip'
    files = [*('procedural/'+name for name in plan['outputs']),'procedural/report.json','recipe.json']
    require(sum(_file(directory,name).stat().st_size for name in files)<=MAX_PACK_BYTES, 'Procedural source pack exceeds 512 MiB')
    if pack.exists():
        require(not project_storage._linked(pack), 'Procedural source pack must not be a link')
        with zipfile.ZipFile(pack) as archive:
            require(archive.namelist()==files, 'Retained procedural source pack changed')
            for name in files:
                require(archive.getinfo(name).file_size==_file(directory,name).stat().st_size, 'Retained procedural source pack changed')
                with archive.open(name) as stream:
                    digest = hashlib.file_digest(stream,'sha256').hexdigest()
                require(digest==engine.file_sha(_file(directory,name)), 'Retained procedural source pack changed')
    else:
        with zipfile.ZipFile(pack,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for name in files:archive.write(_file(directory,name),name)
    _file(directory,'export.zip') # Check the completed archive before any Library write.
    job.update(outputs=outputs,publication_status='publishing')
    _write(directory / 'procedural-job.json',job)
    for index,output in enumerate(outputs):
        asset = studio.assets.register(job,index,_file(directory,output['native_path']))
        require(asset is not None, 'Procedural output could not be registered in the Library')
        output['asset_id'] = asset
        _write(directory / 'procedural-job.json',job) # Checkpoint each idempotent Library registration.
    job.update(status='completed',publication_status='published',finished_at=time.time(),
               message='Procedural asset built. '+('All requested technical checks passed; inspect the result in your engine.'
                    if report['state']=='passed' else 'Godot import was not checked; technical verification is incomplete.'))
    _write(directory / 'procedural-job.json',job)
    artifacts = [_artifact(identifier,directory,'export.zip','native-export')]
    for name in plan['outputs']:
        role = 'procedural-model' if name=='asset_LOD0.glb' else 'inspection-render' if name=='contact_sheet.png' else 'native-source'
        artifact = _artifact(identifier,directory,'procedural/'+name,role)
        output = next((o for o in outputs if o['filename']==name),None)
        if output:artifact['asset_id'] = output['asset_id']
        artifacts.append(artifact)
    return {'job':job,'artifacts':artifacts+_diagnostics(identifier,directory),'verification':report,
            'limitations':['Technical checks are not art acceptance.','This is a procedural asset, not a physics simulation.']}


def _record_failure(directory, job):
    try:_write(directory / 'procedural-job.json',job)
    except (OSError,ValueError) as exc:
        # The original attempt marker remains; Production persists these known
        # output identities in the separate run record even if this receipt failed.
        job['receipt_error']=str(exc)[:500]


def _failed(identifier, directory, job, exc, status='failed'):
    published=_retained_outputs(job,job)
    if job.get('publication_status') in ('publishing','published') and not job.get('failure_files'):
        # Native checks and the source pack passed before registration began.
        # An insertion/receipt failure is recoverable publication, not native failure.
        job.update(status='uncertain',publication_status='incomplete',outputs=published,finished_at=time.time(),
                   publication_error=str(exc)[:500],
                   message='Library publication is incomplete. Known asset identities are retained. Reconcile and resume to inspect the files and finish publication without rerunning Blender. '+str(exc)[:250])
        _record_failure(directory,job)
        return {'job':job,'artifacts':_diagnostics(identifier,directory),'verification':None,
                'limitations':['Native work is not repeated. Reconciliation rechecks retained files before idempotently publishing any remaining outputs.']}
    job.update(status=status,publication_status='incomplete' if published else 'unpublished',outputs=published,
               finished_at=time.time(),message=str(exc)[:500])
    if status=='failed':job['failure_files'] = True
    # Inspection errors must not erase the original failure/completion evidence.
    if status=='failed':_record_failure(directory,job)
    return {'job':job,'artifacts':_diagnostics(identifier,directory),'verification':None,
            'limitations':['The owned attempt and diagnostics are retained. Prepare a new plan to retry; this attempt is never rerun.']}


def run(studio, identifier, plan):
    plan = _validate_plan(studio,plan)
    directory = _directory(studio,identifier)
    require(not attempt_exists(directory),
            'A procedural attempt already exists; inspect its retained evidence')
    job = native_job(identifier,plan)
    engine.write_json(directory / 'procedural-job.json',job) # exclusive durable marker before native execution
    try:
        engine.write_json(directory / 'recipe.json',plan)
        intent, tools = plan['intent'], plan['pins']['executables']
        factory.build(intent['generator'],intent['params'],directory / 'procedural',tools['blender']['path'],
                      godot=tools.get('godot',{}).get('path'),node=tools['node']['path'],render=intent['render'],timeout=600)
        return _publish(studio,identifier,directory,plan,job)
    except Exception as exc:return _failed(identifier,directory,job,exc)


def recover(studio, identifier, plan):
    """Only completed, matching retained files can be published; no native tool is invoked."""
    plan = _validate_plan(studio,plan,live=False)
    directory = _directory(studio,identifier);job = native_job(identifier,plan)
    _retain_job_evidence(job,getattr(studio,'jobs',{}).get(job['id']))
    try:
        receipt = engine.read_json(_file(directory,'procedural-job.json',4*1024**2))
        require(receipt.get('id')==job['id'] and receipt.get('native_recipe')==plan, 'Procedural attempt identity changed')
        _retain_job_evidence(job,receipt)
        require(receipt.get('status')!='failed' and not job.get('failure_files'), 'The retained procedural attempt records a failure')
        require(engine.read_json(_file(directory,'recipe.json',4*1024**2))==plan, 'Procedural recipe differs from its prepared plan')
        return _publish(studio,identifier,directory,plan,job)
    except Exception as exc:return _failed(identifier,directory,job,exc,status='uncertain')
