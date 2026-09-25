"""Pinned registered-recipe tickets on the existing Studio worker.

This is an at-most-one dispatch attempt per retained ticket, NOT exactly-once
execution. A durable intent with no job is deliberately parked for reconciliation.
No arbitrary graph execution, retry loop, GPU lock or second queue lives here.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import uuid
from .core import canonical, digest, need

TICKET_VERSION = 'studio.run-ticket/v1'
RECIPE_KEYS = {'preset_id', 'controls', 'references', 'parent_assets', 'batch_count', 'expected_template_sha256', 'label'}
NAMESPACE = uuid.UUID('33791d36-41a5-4bc8-b793-c567ffb8a73a')


def _clean_run_label(value):
    # Keep guidance/qualification imports free of the runtime app package.
    # server.py puts this repository's app directory ahead of ComfyUI's own app package.
    try:
        from workspace import clean_run_label
    except ModuleNotFoundError as exc:
        if exc.name != 'workspace':
            raise
        from app.workspace import clean_run_label
    return clean_run_label(value)


def _pins(studio, recipe):
    need(isinstance(recipe, dict) and set(recipe) <= RECIPE_KEYS, 'Only registered recipe fields are accepted; raw graphs are not runnable')
    if isinstance(recipe, dict) and 'label' in recipe and recipe['label'] is not None:
        _clean_run_label(recipe['label'])
    need(recipe.get('batch_count', 1) == 1 and type(recipe.get('batch_count', 1)) is int, 'This ticket supports one graph invocation, not a batch')
    parents = recipe.get('parent_assets', [])
    need(isinstance(parents, list) and len(parents) <= 8, 'Use up to eight parent assets')
    for parent in parents: studio.assets.get(parent)
    preset, graph, path, _, batch = studio.prepare(recipe)
    # Preset lookup is the existing allow-list. Its normal validation remains authoritative.
    raw = path.read_bytes()
    template_sha = hashlib.sha256(raw).hexdigest()
    need(json.loads(raw) == studio.graph_for(preset)[0], 'Template changed while preparing')
    references = []
    for node in graph.values():
        if node.get('class_type') != 'LoadImage':
            continue
        name = node.get('inputs', {}).get('image')
        need(isinstance(name, str) and '/' not in name and '\\' not in name and name not in ('.', '..'), 'LoadImage requires a staged local input file')
        root = (studio.comfy_root / 'input').resolve()
        source = (root / name).resolve()
        need(root in source.parents and source.is_file(), 'Staged reference is unavailable: ' + name)
        before = source.stat()
        with source.open('rb') as stream:
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = source.stat()
        need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'Reference changed during preparation')
        references.append({'name': name, 'sha256': sha})
    return {'template_sha256': template_sha, 'preset_sha256': digest(preset),
            'graph_sha256': digest(graph), 'backend_id': studio.backends.active,
            'backend_url': studio.comfy_url, 'workspace': str(studio.root),
            'experiments_root': str(studio.experiments.resolve()), 'runs_root': str(studio.runs.resolve()),
            'load_image_files': sorted(references, key=lambda x: x['name']),
            'reference_bindings_sha256': digest(preset.get('_prepared_references', []))}


def prepare_ticket(studio, recipe):
    with studio.lock:
        pins = _pins(studio, recipe)
        recipe = json.loads(canonical(recipe))
        if 'label' in recipe:
            if recipe['label'] is None:
                del recipe['label']
            else:
                recipe['label'] = _clean_run_label(recipe['label'])
        recipe['batch_count'] = 1
        recipe['expected_template_sha256'] = pins['template_sha256']
        # Recompute after inserting the explicit template guard, so preparation and
        # submission use the same recipe shape even for an omitted initial guard.
        pins = _pins(studio, recipe)
    return {'format': TICKET_VERSION, 'request_id': str(uuid.uuid4()), 'recipe': recipe, 'pins': pins,
            'generation_submitted': False,
            'notice': 'Registered recipe only. One graph invocation may produce several outputs. Preparation is not runtime/resource or creative acceptance.'}


def run_ticket(studio, ticket, approved=False):
    need(approved is True, 'Explicit approval is required')
    need(isinstance(ticket, dict) and ticket.get('format') == TICKET_VERSION, 'Expected a prepared run ticket')
    need(set(ticket) == {'format', 'request_id', 'recipe', 'pins', 'generation_submitted', 'notice'}, 'Invalid ticket fields')
    try:
        request_id = str(uuid.UUID(ticket['request_id']))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError('Invalid request identity') from exc
    need(request_id == ticket['request_id'], 'Use the exact prepared request identity')
    recipe = ticket.get('recipe')
    if isinstance(recipe, dict) and 'label' in recipe and recipe['label'] is not None:
        _clean_run_label(recipe['label'])
    identity = digest(ticket)
    job_id = str(uuid.uuid5(NAMESPACE, request_id))
    with studio.lock:
        # Resolve the actual evidence location before looking up or creating receipts.
        # Repository identity alone does not identify an experiments workspace.
        need(isinstance(ticket['pins'], dict)
             and ticket['pins'].get('experiments_root') == str(studio.experiments.resolve())
             and ticket['pins'].get('runs_root') == str(studio.runs.resolve()),
             'Run workspace changed or ticket lacks workspace pins; inspect the original workspace before any new attempt')
        root = studio.runs.resolve()
        directory = root / 'workflow-requests'
        directory.mkdir(exist_ok=True)
        need(directory.resolve().parent == root and not directory.is_symlink(), 'Request directory must stay in the workspace')
        receipt = directory / (request_id + '.json')
        need(not receipt.is_symlink(), 'Request receipt cannot be a symbolic link')
        if receipt.exists():
            recorded = json.loads(receipt.read_bytes())
            need(recorded.get('ticket_sha256') == identity, 'Ticket identity already belongs to different content')
            if job_id in studio.jobs:
                return {'replayed': True, 'job': studio.public(studio.jobs[job_id]), 'dispatch_attempted': False}
            return {'replayed': True, 'job_id': job_id, 'status': 'reconciliation_required',
                    'dispatch_attempted': False, 'message': 'Intent exists but no job record is available. Do not create a new ticket or resubmit blindly.'}
        need(job_id not in studio.jobs, 'Job exists without its request receipt; reconcile before proceeding')
        current = _pins(studio, ticket['recipe'])
        need(current == ticket['pins'], 'Recipe, references, workspace or environment changed; prepare and review again')
        # Exclusive create + fsync precedes any call capable of enqueueing work.
        # If writing/creating a job fails, this receipt intentionally prevents retry.
        with receipt.open('xb') as stream:
            stream.write(canonical({'ticket_sha256': identity, 'job_id': job_id, 'ticket': ticket}))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            job = studio.create_job(ticket['recipe'], job_id=job_id)
        except Exception as exc:
            # No assertion of failure after the side-effect boundary. The receipt
            # remains even if the worker accepted the job before an exception.
            return {'replayed': False, 'job_id': job_id, 'status': 'reconciliation_required',
                    'dispatch_attempted': True, 'message': 'Dispatch outcome needs inspection; retain this ticket.',
                    'error_type': type(exc).__name__}
        return {'replayed': False, 'job': job, 'dispatch_attempted': True}
