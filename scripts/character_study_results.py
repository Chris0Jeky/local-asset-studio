"""Collect saved primary-study results into the existing offline study summarizer.

Reads Production/Workspace SQLite stores and retained files only. Does not import
Studio, recover projects, contact a runtime, schedule work, or change reservations.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import character_study as study
from app import project_storage, submission_evidence, references, character_review

JSON_LIMIT = 16 * 1024**2
IMAGE_LIMIT = 20 * 1024**2
TOTAL_LIMIT = 256 * 1024**2
require = study.require


def job_identity(project_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'asset-studio:{project_id}:stage:0'))


def _production_sha(value):
    # Production fingerprints use ASCII escaping; study hashes use UTF-8 text.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _decode(raw):
    require(len(raw) <= JSON_LIMIT, 'Saved JSON exceeds the 16 MiB collection limit')
    def reject(_): raise ValueError('Non-finite saved JSON number')
    return json.loads(raw, object_pairs_hook=study._pairs, parse_constant=reject)


@contextmanager
def _database(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file(), 'Missing saved database')
    db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=5)
    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
        yield db
    finally: db.close()


def _projects(experiments, root_id):
    with _database(study.inside(experiments, 'projects/projects.sqlite3')) as db:
        budget = db.execute('SELECT allowance,reserved FROM budgets WHERE id=?', (root_id,)).fetchone()
        require(budget is not None, 'Study has no saved Production budget')
        rows = []; size = 0
        has_reviews = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='comparison_reviews'").fetchone() is not None
        for row in db.execute('SELECT id,root_id,plan,state,created FROM projects WHERE root_id=? ORDER BY created,id LIMIT 257', (root_id,)):
            size += len(row['plan'].encode('utf-8'))+len(row['state'].encode('utf-8'))
            require(size <= TOTAL_LIMIT, 'Study metadata exceeds collection limit')
            item = dict(id=row['id'], root_id=row['root_id'], plan=_decode(row['plan']), state=_decode(row['state']), created_at=row['created'], review_desk=None)
            review = db.execute('SELECT revision,document FROM comparison_reviews WHERE project_id=?', (row['id'],)).fetchone() if has_reviews else None
            if review:
                size += len(review['document'].encode('utf-8')); require(size <= TOTAL_LIMIT, 'Study reviews exceed collection limit')
                document = _decode(review['document']); receipt = document.get('character_review'); event = None
                if receipt:
                    event = db.execute('SELECT event FROM comparison_review_events WHERE project_id=? AND revision=?', (row['id'], receipt.get('review_revision'))).fetchone()
                    if event:size += len(event['event'].encode('utf-8')); require(size <= TOTAL_LIMIT, 'Study review events exceed collection limit')
                item['review_desk'] = {'revision': review['revision'], 'document': document, 'finalization_event': _decode(event['event']) if event else None}
            rows.append(item)
    require(0 < len(rows) <= 256, 'Expected 1..256 saved study projects')
    return {'budget': dict(budget), 'projects': rows}


def _read_saved(experiments, name, watched):
    path = study.inside(experiments, name)
    with path.open('rb') as stream: raw = stream.read(JSON_LIMIT+1)
    value = _decode(raw); watched[name] = hashlib.sha256(raw).hexdigest()
    return value


def _bindings_match(stage, source, case, plan):
    handoff = source['handoff']; controls = handoff['proposed_controls']
    require(controls.get('seed') == case['seed'], 'Handoff seed differs from case')
    for key in ('positive', 'seed'):
        require(stage['request']['controls'].get(key) == controls[key], 'Stage controls differ from handoff')
        bindings = handoff['control_bindings'].get(key)
        require(isinstance(bindings, list) and bindings, 'Missing handoff control bindings')
        for index, (node, field) in enumerate(bindings):
            value = controls[key]
            if key == 'positive' and index == 0 and stage['request'].get('references'):
                value = references.guidance_text(stage['request']['references'], value)
            require(stage['graph'].get(str(node), {}).get('inputs', {}).get(field) == value, 'Stage graph differs from handoff controls')
    requirements = handoff['upload_requirements']; uploads = source['uploads']
    require(len(requirements) == len(uploads) == len(case['reference_ids']), 'Saved reference count differs')
    refs = {r['id']: r for r in plan['canon']['references']}
    for rid, requirement, upload in zip(case['reference_ids'], requirements, uploads):
        require(requirement['id'] == rid and requirement['sha256'] == upload['sha256'] == refs[rid]['sha256']
                and requirement['role'] == upload['role'] == refs[rid]['role'], 'Saved reference identity or order differs')
        node, field = requirement['binding']
        require(stage['graph'].get(str(node), {}).get('inputs', {}).get(field) == upload['file'], 'Stage graph differs from saved reference binding')
    prepared = stage['request'].get('references', [])
    if prepared:
        require(len(prepared) == len(uploads), 'Prepared reference count differs')
        for index, (record, upload) in enumerate(zip(prepared, uploads)):
            require(record.get('slot') == index+1 and all(record.get(key) == upload[key] for key in ('file', 'sha256', 'role')), 'Prepared reference identity or order differs')


def _asset(experiments, job, output):
    expected = uuid.uuid5(uuid.NAMESPACE_URL, f"asset-studio:{job['id']}:0").hex
    require(output.get('asset_id') == expected, 'Output asset identity differs from the saved job')
    with _database(study.inside(experiments, 'workspace/assets.sqlite3')) as db:
        row = db.execute('SELECT id,job_id,output_index,media_type,path,sha256,bytes,source FROM assets WHERE id=?', (expected,)).fetchone()
    require(row is not None, 'Saved output asset is missing')
    asset = dict(row); source = _decode(asset['source'])
    require(asset['job_id'] == job['id'] and asset['output_index'] == 0 and asset['media_type'] == 'image', 'Saved asset ownership differs')
    require(all(source.get(k) == output.get(k) for k in ('filename', 'subfolder', 'type', 'prompt_id')), 'Saved asset source differs from job output')
    path = study.inside(experiments, _media_name(asset))
    require(type(asset['bytes']) is int and 0 < asset['bytes'] <= IMAGE_LIMIT and path.stat().st_size == asset['bytes'], 'Saved asset byte count differs or exceeds 20 MiB')
    require(study.file_sha(path) == asset['sha256'], 'Saved asset bytes changed')
    return asset


def _media_name(asset):
    # Workspace persists native relative paths, including Windows separators.
    require(isinstance(asset.get('path'), str), 'Invalid saved asset path')
    name = asset['path'].replace('\\', '/')
    study.relative(name); require(name.startswith('media/'), 'Saved asset is outside Workspace media')
    return 'workspace/'+name


def _copy_asset(experiments, asset, destination):
    source = study.inside(experiments, _media_name(asset))
    size = 0; digest = hashlib.sha256()
    with source.open('rb') as src, destination.open('xb') as dst:
        while chunk := src.read(min(1024**2, IMAGE_LIMIT+1-size)):
            size += len(chunk); require(size <= IMAGE_LIMIT, 'Saved asset exceeds 20 MiB')
            digest.update(chunk); dst.write(chunk)
    require(size == asset['bytes'] and digest.hexdigest() == asset['sha256'], 'Saved asset changed during collection')


def _case(experiments, project, plan, watched):
    production = project['plan']; source = production.get('character_source') or {}
    require(production.get('kind') == 'comparison' and source.get('kind') == 'character_primary_import'
            and source.get('study_plan') == plan and source.get('attempt_kind') == 'primary'
            and source.get('parent_attempt_id') is None, 'Every project sharing this budget must be a bound primary study case')
    case = study.get_case(plan, source['case_id'])
    expected = hashlib.sha256(('character-primary:'+plan['plan_sha256']+':'+case['id']).encode()).hexdigest()[:32]
    require(project['id'] == expected, 'Primary project identity differs from the study case')
    project_storage.require(experiments/'projects', project['id'], production)
    saved = _read_saved(experiments, f"projects/{project['id']}/plan.json", watched)
    require(saved == production, 'Saved project plan differs')
    handoff = source['handoff']
    require(handoff.get('plan_sha256') == plan['plan_sha256'] and handoff.get('case_id') == case['id']
            and handoff.get('preset_id') == case['preset_id']
            and handoff.get('handoff_sha256') == study.sha({k:v for k,v in handoff.items() if k != 'handoff_sha256'}), 'Saved handoff identity differs')
    stages = production['stages']
    require(len(stages) == 1 and stages[0]['operation'] == 'comfy.generate.v1', 'Primary study must have one generation stage')
    stage = stages[0]
    require(stage['graph_sha256'] == _production_sha(stage['graph']) and stage['request']['preset_id'] == case['preset_id'], 'Saved stage graph differs')
    _bindings_match(stage, source, case, plan)
    attempts = project['state']['attempts']; require(set(attempts) <= {'0'}, 'Unexpected primary study attempts')
    identifier = job_identity(project['id']); attempt = attempts.get('0')
    item = {'case_id': case['id'], 'project_id': project['id'], 'job_id': None, 'disposition': 'planned', 'record_id': None, 'execution_evidence': None}
    if not attempt:
        require(not (experiments/'runs'/identifier).exists(), 'Saved job has no Production attempt link')
        if project['state']['status'] != 'planned': item['disposition'] = 'reserved_unstarted'
        return item, None, None
    require(attempt.get('job_id') == identifier, 'Production attempt links a different job')
    job = _read_saved(experiments, f'runs/{identifier}/state.json', watched)
    graph = _read_saved(experiments, f'runs/{identifier}/workflow.json', watched)
    require(job.get('id') == identifier and job.get('project_id') == project['id']
            and job.get('preset_id') == case['preset_id'] and type(job.get('batch_count')) is int
            and job['batch_count'] == 1 and _production_sha(graph) == stage['graph_sha256'], 'Saved job ownership, batch or graph differs')
    ids = job.get('prompt_ids'); receipts = job.get('submissions'); outputs = job.get('outputs')
    require(type(ids) is list and len(ids) <= 1 and type(receipts) is list and len(receipts) == len(ids)
            and type(outputs) is list, 'Unexpected primary prompt or output collections')
    for prompt, receipt in zip(ids, receipts):
        study.text(prompt, 'saved prompt ID', 256)
        require(isinstance(receipt, dict) and receipt.get('index') == 0 and receipt.get('prompt_id') == prompt
                and _production_sha(receipt.get('graph')) == stage['graph_sha256'], 'Saved submission graph or prompt differs')
    if 'pending_submission' in job:
        pending = job['pending_submission']
        require(isinstance(pending, dict) and pending.get('index') == 0 and not ids
                and _production_sha(pending.get('graph')) == stage['graph_sha256'], 'Saved pending submission differs')
    item['job_id'] = identifier
    evidence = {'schema_version': 1, 'kind': 'character_production_evidence', 'project': project, 'job': dict(job, graph=graph)}
    if submission_evidence.never_submitted(job):
        item['disposition'] = 'not_submitted'; return item, evidence, None
    if job['status'] == 'failed' and not ids and not outputs and 'pending_submission' not in job and 'abandonment' not in job and not job.get('tracking_disposition'):
        # Both local preflight failures and explicit request rejections can have
        # this shape. Preserve the failure/reservation without counting an image
        # attempt or claiming that an HTTP request was never sent.
        item['disposition'] = 'failed_without_prompt'; return item, evidence, None
    asset = None
    if job['status'] == 'completed':
        require('pending_submission' not in job and len(ids) == 1 and receipts[0].get('status') == 'completed'
                and len(outputs) == 1 and outputs[0].get('media_type') == 'image' and outputs[0].get('prompt_id') == ids[0], 'Completed case needs one completed prompt and its one image')
        asset = _asset(experiments, job, outputs[0]); evidence['asset'] = asset; disposition = 'completed'
    elif submission_evidence.terminal_failure(job):
        disposition = 'failed'
    else:
        # A queue label, abandoned observation, partial result or active request
        # cannot certify that no remote work occurred. Preserve its uncertainty.
        disposition = 'submission_uncertain'
    item.update(disposition=disposition, record_id='production-'+project['id'])
    return item, evidence, asset


def collect(plan, workspace, experiments, out):
    study.check_plan(plan)
    workspace = Path(workspace).resolve(strict=True); experiments = Path(experiments).resolve(strict=True)
    out = Path(out).resolve()
    require(out != workspace and out.is_relative_to(workspace) and not out.is_relative_to(experiments), 'Collection must be a new directory inside the canon workspace and outside source experiments')
    prefix = out.relative_to(workspace).as_posix(); study.relative(prefix)
    if out.exists(): raise FileExistsError('Collection already exists; retain it and choose a new snapshot name')
    require(out.parent.is_dir(), 'Collection parent directory must already exist')
    preflight = study.preflight(plan, workspace)
    require(preflight['reference_and_canon_checks_passed'], 'Approved canon and unchanged reference bytes are required')
    root_id = 'character-study:'+plan['plan_sha256']; snapshot = _projects(experiments, root_id)
    budget = snapshot['budget']
    require(type(budget['allowance']) is int and type(budget['reserved']) is int
            and budget['allowance'] == plan['request']['budget']['max_generation_attempts']
            and 0 <= budget['reserved'] <= budget['allowance'], 'Saved Production budget differs from the study')
    watched = {}; cases = []; artifacts = []
    for project in snapshot['projects']:
        item, evidence, asset = _case(experiments, project, plan, watched)
        if evidence and asset:
            evidence['character_review'] = character_review.collected_review(project, asset, evidence['job'])
            if evidence['character_review']:
                candidate = project['review_desk']['document']['candidates'][0]
                relative = candidate['source_path']; study.relative(relative)
                require(relative.startswith('reviews/'), 'Character review snapshot escaped its review directory')
                name = f"projects/{project['id']}/"+relative; path = study.inside(experiments, name)
                require(path.stat().st_size == asset['bytes'] and study.file_sha(path) == asset['sha256'], 'Character review snapshot bytes changed')
                watched[name] = asset['sha256']
        cases.append(item); artifacts.append((item, evidence, asset))
    require(len({item['case_id'] for item in cases}) == len(cases), 'Duplicate primary case')
    require(sum(bool(item['record_id']) for item in cases) <= budget['reserved'], 'Attempt records exceed saved reservations')
    require(sum(len(study.canonical(evidence))+(asset['bytes'] if asset else 0) for _,evidence,asset in artifacts) <= TOTAL_LIMIT, 'Collection exceeds 256 MiB')
    out.mkdir(); (out/'.incomplete').write_text('Collection is incomplete. Preserve these files; use a new name for another snapshot.\n', encoding='utf-8')
    written = 0
    def save(name, value):
        nonlocal written
        raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8')
        require(len(raw) <= JSON_LIMIT and written+len(raw) <= TOTAL_LIMIT, 'Collection JSON or total byte limit exceeded')
        with (out/name).open('xb') as stream: stream.write(raw)
        written += len(raw)
    records = []
    for item, evidence, asset in artifacts:
        if evidence is None: continue
        name = item['project_id']+'-evidence.json'; save(name, evidence)
        item['execution_evidence'] = {'path': prefix+'/'+name, 'sha256': study.file_sha(out/name)}
        if not item['record_id']: continue
        output = None
        if asset:
            suffix = Path(asset['path']).suffix.lower()
            require(suffix in {'.png', '.jpg', '.jpeg', '.webp'}, 'Unsupported saved image extension')
            require(written+asset['bytes'] <= TOTAL_LIMIT, 'Collection total byte limit exceeded')
            output_name = item['project_id']+suffix; _copy_asset(experiments, asset, out/output_name)
            written += asset['bytes']
            output = {'path': prefix+'/'+output_name, 'sha256': asset['sha256']}
        job = evidence['job']; elapsed = job.get('elapsed_seconds')
        if item['disposition'] not in {'completed', 'failed'} or type(elapsed) not in {int, float} or not math.isfinite(elapsed) or elapsed < 0: elapsed = None
        records.append({'id': item['record_id'], 'plan_sha256': plan['plan_sha256'], 'case_id': item['case_id'],
            'kind': 'primary', 'state': item['disposition'], 'parent_attempt_id': None,
            'prompt_id': job['prompt_ids'][0] if job['prompt_ids'] else None, 'output': output,
            'execution_evidence': item['execution_evidence'],
            'elapsed_seconds': elapsed, 'cleanup_seconds': None, 'review': evidence.get('character_review')})
    require(_projects(experiments, root_id) == snapshot, 'Production changed during collection; retained snapshot is incomplete')
    for name, digest in watched.items():
        require(study.file_sha(study.inside(experiments, name)) == digest, 'Saved evidence changed during collection; retained snapshot is incomplete')
    summary = study.summarize(plan, records, workspace)
    save('production.json', snapshot)
    save('plan.json', plan); save('records.json', records); save('summary.json', summary)
    report = {'schema_version': 1, 'kind': 'character_production_collection', 'plan_sha256': plan['plan_sha256'],
        'source_experiments': str(experiments), 'source_snapshot_sha256': study.sha(snapshot),
        'production_snapshot': {'path': prefix+'/production.json', 'sha256': study.file_sha(out/'production.json')},
        'source_file_hashes': watched, 'production_budget': budget, 'cases': cases,
        'unimported_case_ids': [case['id'] for case in plan['cases'] if case['id'] not in {item['case_id'] for item in cases}],
        'records': {'path': prefix+'/records.json', 'sha256': study.file_sha(out/'records.json')},
        'summary': {'path': prefix+'/summary.json', 'sha256': study.file_sha(out/'summary.json')},
        'generation_submitted': False, 'grants_generation_allowance': False,
        'limits': ['Local saved attestations, not authenticated runtime or reviewer evidence.',
            'Primary imports only; unbound branches, missing jobs and mismatched bytes are refused.',
            'Study attempts_remaining counts records; it is not the remaining Production allowance.',
            'Reservations stay spent, including unstarted work. This collection grants no execution.',
            'Generic Production and Workspace selections are not character-check reviews or human acceptance.',
            'Elapsed values are retained job measurements, not model inference or cold/warm benchmark timings.',
            'SQLite rows and job files were checked twice; this is not a transaction across all source stores.',
            'No current runtime, model bytes, telemetry validity, art quality or licensing is verified.']}
    save('collection.json', report); (out/'.incomplete').unlink()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'workspace', 'experiments', 'out'): parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    try:
        report = collect(study.read_json(args.plan), args.workspace, args.experiments, args.out)
        summary = study.read_json(study.inside(args.workspace, report['summary']['path']))
        print(json.dumps({'collection': str(args.out/'collection.json'), 'completed_attempts': summary['completed_attempts'],
            'attempts_used': summary['attempts_used'], 'production_budget': report['production_budget'],
            'human_accepted_cases': summary['human_accepted_cases'], 'generation_submitted': False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc: parser.exit(2, f'character-study-results: {exc}\n')


if __name__ == '__main__': raise SystemExit(main())
