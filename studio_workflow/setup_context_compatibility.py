"""Bind reviewed setup candidates to exact local and runtime observations.

This module is a pure decision adapter. It does not contact providers, hash files,
download models, install resources, switch backends, mutate a selection or submit
generation work.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from . import setup_compatibility as compatibility
from . import source_compatibility
from .core import canonical, decode, digest, need

INPUT_FORMAT = 'studio.setup-context-compatibility/v1'
REPORT_FORMAT = 'studio.setup-context-compatibility-report/v1'
SOURCE_FORMAT = source_compatibility.REPORT_FORMAT
MAX_INPUT_BYTES = 1024 * 1024
MAX_ASSETS = 2048
MAX_NODE_CLASSES = 2048
MAX_DIAGNOSTICS = 2048
MAX_BINDING_NODES = 64
SHA256 = re.compile(r'[a-f0-9]{64}\Z')
ZERO_AUTHORITY_FIELDS = (
    'provider_accessed',
    'file_hashed',
    'model_downloaded',
    'selection_changed',
    'installation_authorized',
    'generation_submitted',
)


def _hash(value: Any, label: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    need(isinstance(value, str) and SHA256.fullmatch(value) is not None,
         'Invalid ' + label)
    return value


def _bounded_records(value: Any, label: str) -> list:
    need(isinstance(value, list) and len(value) <= MAX_DIAGNOSTICS,
         'Invalid ' + label)
    need(all(isinstance(item, dict) for item in value), 'Invalid ' + label)
    need(len(canonical(value)) <= 256 * 1024, label + ' exceed the bounded limit')
    return copy.deepcopy(value)


def _safe_file(value: Any) -> str:
    need(compatibility.token(value, 500), 'Invalid binding file')
    need('\\' not in value and not value.startswith('/'), 'Invalid binding file')
    path = PurePosixPath(value)
    parts = value.split('/')
    need(path.parts and path.as_posix() == value
         and all(part not in ('', '.', '..') for part in parts),
         'Invalid binding file')
    for part in parts:
        stem = part.split('.', 1)[0]
        need(part[-1:] not in ('.', ' ')
             and re.search(r'[<>:"|?*\x00-\x1f]', part) is None
             and re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])',
                              stem, re.I) is None,
             'Invalid binding file')
    return value


def _sort_records(values: list[dict]) -> list[dict]:
    return sorted(values, key=lambda item: canonical(item))


def _finding(code: str, message: str, **details: Any) -> dict:
    return {'code': code, 'message': message, **details}


def _validate_source_report(value: Any) -> dict:
    fields = {
        'format',
        'context_sha256',
        'source_context_sha256',
        'source_coverage_complete',
        'review_revision',
        'candidate',
        'evidence',
        'source_observations',
        'source_diagnostics',
        'diagnostics',
        'provider_claims',
        'provider_accessed',
        'file_hashed',
        'model_downloaded',
        'selection_changed',
        'installation_authorized',
        'generation_submitted',
        'notice',
    }
    need(isinstance(value, dict) and set(value) == fields,
         'Invalid source candidate report fields')
    need(value['format'] == SOURCE_FORMAT, 'Unsupported source candidate report')
    for field in ZERO_AUTHORITY_FIELDS:
        need(value[field] is False,
             'source candidate report must retain zero authority')
    result = copy.deepcopy(value)
    result['context_sha256'] = _hash(
        value['context_sha256'], 'source candidate context fingerprint')
    result['source_context_sha256'] = _hash(
        value['source_context_sha256'], 'retained source context fingerprint')
    need(type(value['source_coverage_complete']) is bool,
         'source_coverage_complete must be boolean')
    result['review_revision'] = compatibility.identity(value['review_revision'])
    need(result['review_revision'] is not None,
         'Reviewed mapping revision is required')
    result['candidate'] = compatibility.validate_candidate(value['candidate'])
    need(isinstance(value['evidence'], list)
         and len(value['evidence']) <= compatibility.MAX_EVIDENCE,
         'Invalid source candidate evidence')
    result['evidence'] = [
        compatibility.validate_evidence(item) for item in value['evidence']
    ]
    evidence_ids = [item['id'] for item in result['evidence']]
    need(len(set(evidence_ids)) == len(evidence_ids),
         'Duplicate source candidate evidence ID')
    candidate_id = result['candidate']['id']
    need(all(item['candidate_id'] == candidate_id
             for item in result['evidence']),
         'Source evidence must target its candidate')
    result['source_observations'] = _sort_records(_bounded_records(
        value['source_observations'], 'source observations'))
    result['source_diagnostics'] = _sort_records(_bounded_records(
        value['source_diagnostics'], 'source diagnostics'))
    result['diagnostics'] = _sort_records(_bounded_records(
        value['diagnostics'], 'source adapter diagnostics'))
    need(isinstance(value['provider_claims'], dict)
         and len(canonical(value['provider_claims'])) <= 256 * 1024,
         'Invalid provider claims')
    need(compatibility.text(value['notice'], 1000)
         and value['notice'].strip() == value['notice'],
         'Source candidate notice is required')
    need(result['context_sha256'] == source_compatibility.candidate_report_digest(result),
         'Source candidate report fingerprint does not match retained fields; regenerate the reviewed report')
    return result


def _validate_asset(value: Any) -> dict:
    fields = {'asset_id', 'file', 'sha256', 'present', 'verified', 'verification'}
    need(isinstance(value, dict) and set(value) == fields,
         'Invalid local asset fields')
    result = copy.deepcopy(value)
    result['asset_id'] = compatibility.identifier(value['asset_id'])
    result['file'] = _safe_file(value['file'])
    result['sha256'] = _hash(value['sha256'], 'local asset SHA-256')
    need(type(value['present']) is bool and type(value['verified']) is bool,
         'Local asset presence and verification must be boolean')
    need(compatibility.token(value['verification'], 200),
         'Local asset verification reason is required')
    need(not value['verified'] or value['present'],
         'A missing local asset cannot be verified')
    if value['verified']:
        need(value['verification'] == 'stat-fresh-sha256-receipt',
             'Verified local assets require a current retained SHA-256 receipt')
    return result


def _validate_context(value: Any) -> dict:
    fields = {
        'backend_id',
        'runtime',
        'switching',
        'inventory_revision',
        'schema_revision',
        'schema_complete',
        'node_classes',
        'assets',
    }
    need(isinstance(value, dict) and set(value) == fields,
         'Invalid live setup context fields')
    result = copy.deepcopy(value)
    result['backend_id'] = compatibility.identifier(value['backend_id'])
    need(compatibility.token(value['runtime'], 160),
         'Live context runtime is required')
    need(type(value['switching']) is bool, 'switching must be boolean')
    result['inventory_revision'] = _hash(
        value['inventory_revision'], 'inventory revision')
    need(type(value['schema_complete']) is bool,
         'schema_complete must be boolean')
    result['schema_revision'] = _hash(
        value['schema_revision'], 'schema revision', optional=True)
    need(not value['schema_complete'] or result['schema_revision'] is not None,
         'A complete node schema requires a schema revision')
    result['node_classes'] = sorted(compatibility.strings(
        value['node_classes'], 'node classes', MAX_NODE_CLASSES))
    need(isinstance(value['assets'], list)
         and len(value['assets']) <= MAX_ASSETS,
         'Use at most 2,048 local assets')
    result['assets'] = sorted(
        (_validate_asset(item) for item in value['assets']),
        key=lambda item: (item['asset_id'], item['file'], item['sha256']),
    )
    for label, values in (
        ('asset ID', [item['asset_id'] for item in result['assets']]),
        ('asset file', [item['file'] for item in result['assets']]),
    ):
        need(len(set(values)) == len(values), 'Duplicate local ' + label)
    return result


def _validate_binding(value: Any) -> dict:
    fields = {
        'candidate_id',
        'asset_id',
        'file',
        'backend_id',
        'required_node_classes',
    }
    need(isinstance(value, dict) and set(value) == fields,
         'Invalid candidate binding fields')
    return {
        'candidate_id': compatibility.identifier(value['candidate_id']),
        'asset_id': compatibility.identifier(value['asset_id']),
        'file': _safe_file(value['file']),
        'backend_id': compatibility.identifier(value['backend_id']),
        'required_node_classes': sorted(compatibility.strings(
            value['required_node_classes'],
            'binding required node classes',
            MAX_BINDING_NODES,
            allow_empty=False,
        )),
    }


def _required_nodes(candidate: dict) -> set[str]:
    result = {
        requirement[len('node:'):]
        for requirement in candidate['requires']
        if requirement.startswith('node:') and len(requirement) > len('node:')
    }
    for loader in candidate['loaders']:
        node_class = loader.split('.', 1)[0]
        if node_class:
            result.add(node_class)
    return result


def _validate_request(value: Any) -> tuple[dict, list[dict], list[dict], dict, list[dict]]:
    fields = {'format', 'slot', 'source_candidates', 'bindings', 'context', 'evidence'}
    need(isinstance(value, dict) and set(value) == fields,
         'Supply format, slot, source_candidates, bindings, context and evidence')
    need(value['format'] == INPUT_FORMAT,
         'Unsupported setup context compatibility request')
    slot = compatibility.validate_slot(value['slot'])
    need(isinstance(value['source_candidates'], list)
         and 1 <= len(value['source_candidates']) <= compatibility.MAX_CANDIDATES,
         'Use 1–256 source candidates')
    sources = sorted(
        (_validate_source_report(item) for item in value['source_candidates']),
        key=lambda item: item['candidate']['id'],
    )
    candidate_ids = [item['candidate']['id'] for item in sources]
    need(len(set(candidate_ids)) == len(candidate_ids),
         'Duplicate source candidate ID')
    identities = [
        item['candidate']['identity'] for item in sources
        if item['candidate']['identity'] is not None
    ]
    need(len(set(identities)) == len(identities),
         'Duplicate source candidate resource identity')

    need(isinstance(value['bindings'], list)
         and len(value['bindings']) <= compatibility.MAX_CANDIDATES,
         'Invalid candidate bindings')
    bindings = sorted(
        (_validate_binding(item) for item in value['bindings']),
        key=lambda item: item['candidate_id'],
    )
    binding_ids = [item['candidate_id'] for item in bindings]
    need(len(set(binding_ids)) == len(binding_ids),
         'Duplicate candidate binding')
    need(binding_ids == candidate_ids,
         'Candidate and binding sets must match exactly')

    context = _validate_context(value['context'])
    need(context['runtime'] == slot['runtime'],
         'slot runtime contradicts live context runtime')

    need(isinstance(value['evidence'], list)
         and len(value['evidence']) <= compatibility.MAX_EVIDENCE,
         'Use at most 1,024 additional evidence records')
    evidence = sorted(
        (compatibility.validate_evidence(item) for item in value['evidence']),
        key=lambda item: item['id'],
    )
    evidence_ids = [item['id'] for item in evidence]
    need(len(set(evidence_ids)) == len(evidence_ids),
         'Duplicate additional evidence ID')
    need(all(item['candidate_id'] in set(candidate_ids) for item in evidence),
         'Additional evidence names an unknown candidate')
    return slot, sources, bindings, context, evidence


def _local_evidence(candidate: dict, context: dict) -> dict:
    return {
        'id': compatibility.identifier(
            'local-' + digest({'candidate_id': candidate['id']})[:32]),
        'candidate_id': candidate['id'],
        'resource_identity': candidate['identity'],
        'kind': 'local_observation',
        'scope': 'exact_resource',
        'direction': 'supports',
        'objective': 'compatibility',
        'observations': 1,
        'independent_sources': 1,
        'source': {
            'locator': 'Local Model Library verification receipt',
            'revision': 'sha256:' + context['inventory_revision'],
            'retrieved_at': None,
        },
    }


def _project(
    slot: dict,
    sources: list[dict],
    bindings: list[dict],
    context: dict,
) -> tuple[dict, list[dict], list[dict], list[dict], list[dict]]:
    source_by_id = {item['candidate']['id']: item for item in sources}
    binding_by_id = {item['candidate_id']: item for item in bindings}
    asset_by_id = {item['asset_id']: item for item in context['assets']}
    def adapter_owned(capability: str) -> bool:
        return capability.startswith(('local-file:', 'backend:', 'node:'))

    # These namespaces are observations owned by this adapter. Caller claims
    # cannot turn an unverified file, backend transition or partial schema into
    # false presence or false absence.
    observed = {item for item in slot['capabilities'] if not adapter_owned(item)}
    absent = {item for item in slot['known_absent_capabilities']
              if not adapter_owned(item)}
    candidates: list[dict] = []
    local_evidence: list[dict] = []
    observations: list[dict] = []
    diagnostics: list[dict] = []

    def present(capability: str) -> None:
        need(capability not in absent,
             'Live context contradicts a declared absent capability')
        observed.add(capability)

    def missing(capability: str) -> None:
        need(capability not in observed,
             'Live context contradicts a declared present capability')
        absent.add(capability)

    for candidate_id in sorted(source_by_id):
        report = source_by_id[candidate_id]
        candidate = copy.deepcopy(report['candidate'])
        binding = binding_by_id[candidate_id]
        need(candidate['identity'] is not None
             and candidate['identity'].startswith('sha256:'),
             'Candidate resource identity must be an exact SHA-256 identity')
        need(binding['asset_id'] in asset_by_id,
             'Candidate binding names an unknown local asset')
        asset = asset_by_id[binding['asset_id']]
        expected_identity = 'sha256:' + asset['sha256']
        need(candidate['identity'] == expected_identity,
             'Candidate resource identity does not match bound asset SHA-256 identity')
        need(binding['file'] == asset['file'],
             'binding file does not match the selected local asset')
        required_nodes = _required_nodes(candidate)
        need(required_nodes <= set(binding['required_node_classes']),
             'Candidate binding omits a reviewed required node class')

        file_capability = 'local-file:' + expected_identity
        backend_capability = 'backend:' + binding['backend_id']
        node_capabilities = {
            'node:' + node_class
            for node_class in binding['required_node_classes']
        }
        requirements = set(candidate['requires'])
        requirements.add(file_capability)
        requirements.add(backend_capability)
        requirements.update(node_capabilities)
        need(len(requirements) <= 64,
             'Projected candidate requirements exceed evaluator limit')
        candidate['requires'] = sorted(requirements)

        if asset['present'] and asset['verified']:
            present(file_capability)
            local_evidence.append(_local_evidence(candidate, context))
            observations.append({
                'candidate_id': candidate_id,
                'kind': 'local_file',
                'state': 'verified',
                'asset_id': asset['asset_id'],
                'file': asset['file'],
                'identity': expected_identity,
                'verification': asset['verification'],
            })
        elif asset['present']:
            diagnostics.append(_finding(
                'local_file_unverified',
                'The exact local file is present but lacks a current retained SHA-256 receipt.',
                candidate_id=candidate_id,
                asset_id=asset['asset_id'],
                file=asset['file'],
                identity=expected_identity,
                verification=asset['verification'],
            ))
            observations.append({
                'candidate_id': candidate_id,
                'kind': 'local_file',
                'state': 'unverified',
                'asset_id': asset['asset_id'],
                'file': asset['file'],
                'identity': expected_identity,
                'verification': asset['verification'],
            })
        else:
            missing(file_capability)
            diagnostics.append(_finding(
                'local_file_missing',
                'The exact bound local file is known absent.',
                candidate_id=candidate_id,
                asset_id=asset['asset_id'],
                file=asset['file'],
                identity=expected_identity,
            ))
            observations.append({
                'candidate_id': candidate_id,
                'kind': 'local_file',
                'state': 'missing',
                'asset_id': asset['asset_id'],
                'file': asset['file'],
                'identity': expected_identity,
                'verification': asset['verification'],
            })

        if context['switching']:
            diagnostics.append(_finding(
                'backend_switching',
                'Backend identity is changing; the target backend has not been observed as active.',
                candidate_id=candidate_id,
                expected=binding['backend_id'],
                observed=context['backend_id'],
            ))
        elif context['backend_id'] == binding['backend_id']:
            present(backend_capability)
        else:
            missing(backend_capability)
            diagnostics.append(_finding(
                'backend_mismatch',
                'The stable active backend does not match the reviewed candidate binding.',
                candidate_id=candidate_id,
                expected=binding['backend_id'],
                observed=context['backend_id'],
            ))

        available_nodes = set(context['node_classes'])
        for node_class in binding['required_node_classes']:
            capability = 'node:' + node_class
            if node_class in available_nodes:
                present(capability)
            elif context['schema_complete']:
                missing(capability)
                diagnostics.append(_finding(
                    'node_missing',
                    'A required node class is absent from the complete cached schema.',
                    candidate_id=candidate_id,
                    node_class=node_class,
                    schema_revision=context['schema_revision'],
                ))
            else:
                diagnostics.append(_finding(
                    'node_unknown',
                    'The cached node schema is incomplete, so absence is not established.',
                    candidate_id=candidate_id,
                    node_class=node_class,
                    schema_revision=context['schema_revision'],
                ))
        candidates.append(candidate)

    need(not observed & absent,
         'Live context capability observations contradict each other')
    need(len(observed) <= 256 and len(absent) <= 256,
         'Projected live capabilities exceed evaluator limit')
    projected_slot = {
        **copy.deepcopy(slot),
        'capabilities': sorted(observed),
        'known_absent_capabilities': sorted(absent),
    }
    return (
        projected_slot,
        sorted(candidates, key=lambda item: item['id']),
        _sort_records(local_evidence),
        _sort_records(observations),
        _sort_records(diagnostics),
    )


def evaluate(value: Any) -> dict:
    need(len(canonical(value)) <= MAX_INPUT_BYTES,
         'Setup context request exceeds 1 MiB')
    original = copy.deepcopy(value)
    slot, sources, bindings, context, extra_evidence = _validate_request(value)
    projected_slot, candidates, local_evidence, observations, diagnostics = _project(
        slot, sources, bindings, context)

    evidence = []
    for report in sources:
        evidence.extend(copy.deepcopy(report['evidence']))
    evidence.extend(copy.deepcopy(extra_evidence))
    evidence.extend(copy.deepcopy(local_evidence))
    evidence = sorted(evidence, key=lambda item: item['id'])
    need(len(evidence) <= compatibility.MAX_EVIDENCE,
         'Combined setup evidence exceeds evaluator limit')
    evidence_ids = [item['id'] for item in evidence]
    need(len(set(evidence_ids)) == len(evidence_ids),
         'Duplicate evidence ID across setup context inputs')

    compatibility_input = {
        'format': compatibility.INPUT_FORMAT,
        'slot': projected_slot,
        'candidates': candidates,
        'evidence': evidence,
    }
    report = compatibility.evaluate(compatibility_input)
    source_observations = []
    source_diagnostics = []
    source_contexts = []
    for source in sources:
        candidate_id = source['candidate']['id']
        source_observations.extend({
            **copy.deepcopy(item),
            'candidate_id': candidate_id,
        } for item in source['source_observations'])
        source_diagnostics.extend({
            **copy.deepcopy(item),
            'candidate_id': candidate_id,
            'origin': 'source',
        } for item in source['source_diagnostics'])
        source_diagnostics.extend({
            **copy.deepcopy(item),
            'candidate_id': candidate_id,
            'origin': 'adapter',
        } for item in source['diagnostics'])
        source_contexts.append({
            'candidate_id': candidate_id,
            'context_sha256': source['context_sha256'],
            'source_context_sha256': source['source_context_sha256'],
            'source_coverage_complete': source['source_coverage_complete'],
            'review_revision': source['review_revision'],
        })

    normalized_context = {
        'slot': slot,
        'source_candidates': sources,
        'bindings': bindings,
        'context': context,
        'evidence': extra_evidence,
    }
    result = {
        'format': REPORT_FORMAT,
        'context_sha256': digest(normalized_context),
        'precondition': {
            'inventory_revision': context['inventory_revision'],
            'schema_revision': context['schema_revision'],
            'backend_id': context['backend_id'],
            'runtime': context['runtime'],
            'switching': context['switching'],
        },
        'compatibility_input': compatibility_input,
        'compatibility': report,
        'source_contexts': sorted(source_contexts,
                                  key=lambda item: item['candidate_id']),
        'observations': _sort_records(observations + source_observations),
        'diagnostics': _sort_records(diagnostics + source_diagnostics),
        'provider_accessed': False,
        'file_hashed': False,
        'model_downloaded': False,
        'installation_authorized': False,
        'backend_switched': False,
        'selection_changed': False,
        'generation_submitted': False,
        'notice': (
            'Pure compatibility advice from retained source mappings and supplied '
            'local/runtime observations; no provider, filesystem or generation '
            'authority was exercised.'
        ),
    }
    need(value == original, 'Setup context evaluation mutated its input')
    need(len(canonical(result)) <= MAX_INPUT_BYTES,
         'Setup context report exceeds 1 MiB')
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Bind retained setup candidates to local/runtime observations.')
    parser.add_argument('request', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.request.open('rb') as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        need(len(raw) <= MAX_INPUT_BYTES,
             'Setup context request exceeds 1 MiB')
        result = evaluate(decode(raw))
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            'error': {
                'code': 'invalid_setup_context',
                'message': str(exc)[:500],
            },
        }, indent=2, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
