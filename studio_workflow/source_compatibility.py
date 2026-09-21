"""Bridge retained source evidence into reviewed, provider-neutral setup candidates."""
from __future__ import annotations

import argparse
import copy
from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from . import setup_compatibility as compatibility
from .core import canonical, decode, digest, need

INPUT_FORMAT = 'studio.setup-source-adapter/v1'
REPORT_FORMAT = 'studio.setup-source-candidate/v1'
SOURCE_FORMAT = 'studio.source-composition-evidence/v1'
MAX_INPUT_BYTES = 1048576
SHA256 = re.compile(r'[a-f0-9]{64}\Z')
REVIEW_REVISION = re.compile(r'sha256:[a-f0-9]{64}\Z')
ZERO_AUTHORITY_FIELDS = (
    'network_performed', 'model_downloaded', 'image_downloaded',
    'installation_authorized', 'generation_submitted',
)


def text(value: Any, limit: int = 300) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit and '\x00' not in value


def token(value: Any, limit: int = 300) -> bool:
    return text(value, limit) and value.strip() == value and not any(ch in value for ch in '\r\n\t')


def sha256(value: Any, label: str) -> str:
    need(isinstance(value, str) and SHA256.fullmatch(value) is not None,
         label + ' must be a lowercase SHA-256')
    return value


def reviewed_date(value: Any) -> str:
    need(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is not None,
         'Invalid review date')
    date.fromisoformat(value)
    return value


def normalize_format(value: str) -> str:
    compact = re.sub(r'[^a-z0-9]', '', value.casefold())
    aliases = {'safetensor': 'safetensors', 'safetensors': 'safetensors'}
    return aliases.get(compact, compact)


def validate_mapping(value: Any) -> dict[str, Any]:
    fields = {'candidate_id', 'name', 'role', 'modality', 'architecture', 'base_lineage',
              'loaders', 'format', 'runtime', 'requires', 'resource_identity',
              'file_identity', 'expected_source_context', 'review'}
    need(isinstance(value, dict) and set(value) == fields, 'Invalid reviewed source mapping')
    review = value['review']
    need(isinstance(review, dict) and set(review) == {'revision', 'reviewed_at'},
         'Invalid review metadata')
    need(isinstance(review['revision'], str) and REVIEW_REVISION.fullmatch(review['revision']) is not None,
         'Pinned review revision must be sha256:<64 lowercase hex>')
    reviewed_at = reviewed_date(review['reviewed_at'])
    resource_identity = compatibility.identity(value['resource_identity'])
    file_identity = compatibility.identity(value['file_identity'])
    need(resource_identity is not None, 'Reviewed resource identity is required')
    need(file_identity is not None, 'Reviewed file identity is required')
    expected_context = sha256(value['expected_source_context'], 'Expected source context')
    candidate = compatibility.validate_candidate({
        'id': value['candidate_id'], 'name': value['name'], 'role': value['role'],
        'modality': value['modality'], 'architecture': value['architecture'],
        'base_lineage': value['base_lineage'], 'loaders': value['loaders'],
        'format': value['format'], 'runtime': value['runtime'],
        'requires': value['requires'], 'identity': file_identity,
    })
    return {'candidate': candidate, 'resource_identity': resource_identity,
            'file_identity': file_identity, 'expected_source_context': expected_context,
            'review': {'revision': review['revision'], 'reviewed_at': reviewed_at}}


def validate_report(value: Any) -> dict[str, Any]:
    fields = {'format', 'provider', 'context_sha256', 'resource', 'source_receipts',
              'image_observations', 'combinations', 'coverage_complete', 'diagnostics',
              'network_performed', 'model_downloaded', 'image_downloaded',
              'installation_authorized', 'generation_submitted', 'notice'}
    need(isinstance(value, dict) and set(value) == fields, 'Invalid retained source report')
    need(value['format'] == SOURCE_FORMAT, 'Unsupported retained source report')
    need(value['provider'] == 'civitai', 'Unsupported source provider')
    context = sha256(value['context_sha256'], 'Source context')
    for field in ZERO_AUTHORITY_FIELDS:
        need(value[field] is False, 'Source report must retain zero authority: ' + field)
    need(type(value['coverage_complete']) is bool,
         'Source coverage_complete must be boolean')
    need(isinstance(value['resource'], dict), 'Source resource must be an object')
    need(isinstance(value['source_receipts'], list) and len(value['source_receipts']) <= 64,
         'Source receipts must be a bounded list')
    need(isinstance(value['image_observations'], list) and len(value['image_observations']) <= 1000,
         'Source image observations must be a bounded list')
    need(isinstance(value['combinations'], list) and len(value['combinations']) <= 1000,
         'Source combinations must be a bounded list')
    need(isinstance(value['diagnostics'], list), 'Source diagnostics must be a list')
    return {**copy.deepcopy(value), 'context_sha256': context}


def select_file(resource: dict[str, Any], file_identity: str) -> dict[str, Any]:
    files = resource.get('files')
    need(isinstance(files, list) and len(files) <= 256, 'Source files must be a bounded list')
    matches = [item for item in files if isinstance(item, dict) and item.get('identity') == file_identity]
    need(len(matches) == 1, 'Reviewed source file identity was not found exactly once')
    selected = copy.deepcopy(matches[0])
    if file_identity.startswith('sha256:'):
        hashes = selected.get('hashes')
        need(isinstance(hashes, dict), 'Selected source file hashes are missing')
        claimed = hashes.get('sha256')
        need(claimed is None or claimed == file_identity.removeprefix('sha256:'),
             'Selected source file hash conflicts with its identity')
    return selected


def receipt_date(report: dict[str, Any], host: str, fallback: str) -> str:
    values = []
    for item in report['source_receipts']:
        if not isinstance(item, dict) or item.get('host') != host:
            continue
        retrieved = item.get('retrieved_at')
        if isinstance(retrieved, str) and len(retrieved) >= 10:
            candidate = retrieved[:10]
            try:
                date.fromisoformat(candidate)
            except ValueError:
                continue
            values.append(candidate)
    return min(values) if values else fallback


def provider_diagnostics(resource: dict[str, Any], candidate: dict[str, Any],
                         selected: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    provider_base = resource.get('base_model')
    if isinstance(provider_base, str):
        claimed = re.sub(r'[^a-z0-9]', '', provider_base.casefold())
        reviewed = {re.sub(r'[^a-z0-9]', '', str(value).casefold())
                    for value in (candidate['architecture'], candidate['base_lineage'])
                    if value is not None}
        if claimed not in reviewed:
            diagnostics.append({'code': 'provider_claim_differs',
                'message': 'Provider base label differs from the reviewed architecture or lineage.',
                'claim': 'base_model'})
    provider_type = resource.get('model_type')
    if isinstance(provider_type, str):
        claimed = re.sub(r'[^a-z0-9]', '', provider_type.casefold())
        reviewed = re.sub(r'[^a-z0-9]', '', candidate['role'].casefold())
        if claimed != reviewed:
            diagnostics.append({'code': 'provider_claim_differs',
                'message': 'Provider model type differs from the reviewed component role.',
                'claim': 'model_type'})
    provider_format = selected.get('format')
    if provider_format is None:
        diagnostics.append({'code': 'provider_format_unknown',
                            'message': 'Provider file format was not retained; reviewed format remains authoritative.'})
    else:
        need(token(provider_format, 200), 'Invalid provider file format')
        need(normalize_format(provider_format) == normalize_format(candidate['format']),
             'Provider file format conflicts with the reviewed format')
    return diagnostics


def combination_key(value: dict[str, Any]) -> tuple[Any, ...]:
    scope = value.get('source_scope') if isinstance(value, dict) else None
    scope = scope if isinstance(scope, dict) else {}
    query = scope.get('query') if isinstance(scope.get('query'), dict) else {}
    versions = value.get('version_ids') if isinstance(value, dict) else []
    versions = tuple(versions) if isinstance(versions, list) else ()
    return (str(scope.get('host', '')), json.dumps(query, sort_keys=True,
            separators=(',', ':'), ensure_ascii=False),
            str(scope.get('scope_sha256', '')), versions)


def gallery_claims(report: dict[str, Any], candidate_id: str, version_id: int,
                   reviewed_at: str,
                   diagnostics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]],
                                                                list[dict[str, Any]]]:
    observations = sorted(copy.deepcopy(report['combinations']), key=combination_key)
    claims: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in observations:
        need(isinstance(item, dict), 'Source combination must be an object')
        scope = item.get('source_scope')
        need(isinstance(scope, dict), 'Source combination scope is required')
        host = scope.get('host')
        need(host in ('civitai.com', 'civitai.red'), 'Unsupported gallery source host')
        scope_identity = sha256(scope.get('scope_sha256'), 'Gallery source scope')
        versions = item.get('version_ids')
        need(isinstance(versions, list)
             and all(type(entry) is int and entry > 0 for entry in versions),
             'Invalid gallery version identities')
        if version_id not in versions:
            diagnostics.append({'code': 'gallery_target_missing',
                                'message': 'Gallery observation does not include the reviewed source version.',
                                'scope_sha256': scope_identity})
            continue
        need(item.get('reported_co_use') is True
             and item.get('compatibility_proven') is False
             and item.get('quality_proven') is False,
             'Gallery source must remain non-authoritative co-use evidence')
        observations_count = item.get('distinct_observations')
        uploaders = item.get('distinct_uploaders')
        need(type(observations_count) is int and observations_count > 0,
             'Gallery observations must be positive')
        need(type(uploaders) is int and uploaders >= 0,
             'Gallery uploader breadth must be non-negative')
        need(uploaders <= observations_count,
             'Gallery uploader breadth cannot exceed distinct observations')
        if uploaders == 0:
            diagnostics.append({'code': 'gallery_independence_unknown',
                                'message': 'Gallery observation has no retained independent-uploader breadth.',
                                'scope_sha256': scope_identity})
            continue
        claim_identity = digest({'candidate_id': candidate_id,
                                 'scope_sha256': scope_identity,
                                 'version_ids': sorted(versions)})
        claim_id = 'gallery-' + claim_identity[:24]
        need(claim_id not in seen_ids, 'Duplicate gallery evidence combination')
        seen_ids.add(claim_id)
        claims.append({
            'id': claim_id, 'candidate_id': candidate_id,
            'resource_identity': None, 'kind': 'gallery_co_use',
            'scope': 'family', 'direction': 'supports',
            'objective': 'compatibility', 'observations': observations_count,
            'independent_sources': uploaders,
            'source': {'locator': 'Retained ' + host + ' gallery composition',
                       'revision': 'sha256:' + report['context_sha256'],
                       'retrieved_at': receipt_date(report, host, reviewed_at)},
        })
    claims.sort(key=lambda item: (item['source']['locator'], item['id']))
    return observations, claims


def adapt(value: Any) -> dict[str, Any]:
    need(isinstance(value, dict) and set(value) == {'format', 'report', 'mapping'},
         'Supply format, report and mapping')
    need(len(canonical(value)) <= MAX_INPUT_BYTES,
         'Source mapping input exceeds 1 MiB')
    need(value['format'] == INPUT_FORMAT,
         'Unsupported setup source adapter request')
    report = validate_report(value['report'])
    mapping = validate_mapping(value['mapping'])
    need(report['context_sha256'] == mapping['expected_source_context'],
         'Retained source context does not match the reviewed mapping')
    resource = report['resource']
    need(resource.get('identity') == mapping['resource_identity'],
         'Retained source resource identity does not match the reviewed mapping')
    version_id = resource.get('version_id')
    need(type(version_id) is int and version_id > 0,
         'Source version identity is required')
    source_host = resource.get('source_host')
    need(source_host in ('civitai.com', 'civitai.red'),
         'Unsupported source resource host')
    receipt_identity = sha256(resource.get('receipt_sha256'),
                              'Source resource receipt')
    selected = select_file(resource, mapping['file_identity'])
    candidate = mapping['candidate']
    diagnostics = provider_diagnostics(resource, candidate, selected)
    if not report['coverage_complete']:
        diagnostics.append({
            'code': 'source_coverage_incomplete',
            'message': ('Retained gallery coverage is incomplete; positive observations remain '
                        'inspectable, but missing records cannot establish absence.'),
        })
    source_diagnostics = copy.deepcopy(report['diagnostics'])
    reviewed_at = mapping['review']['reviewed_at']
    provider_identity = digest({'candidate_id': candidate['id'],
                                'resource_identity': mapping['resource_identity'],
                                'file_identity': mapping['file_identity']})
    provider_evidence = {
        'id': 'provider-' + provider_identity[:24],
        'candidate_id': candidate['id'],
        'resource_identity': candidate['identity'],
        'kind': 'provider_metadata', 'scope': 'exact_resource',
        'direction': 'supports', 'objective': 'compatibility',
        'observations': 1, 'independent_sources': 1,
        'source': {'locator': 'Retained Civitai model-version metadata',
                   'revision': 'sha256:' + receipt_identity,
                   'retrieved_at': receipt_date(report, source_host, reviewed_at)},
    }
    provider_evidence = compatibility.validate_evidence(provider_evidence)
    source_observations, gallery = gallery_claims(
        report, candidate['id'], version_id, reviewed_at, diagnostics)
    evidence = [provider_evidence] + [
        compatibility.validate_evidence(item) for item in gallery
    ]
    diagnostics.sort(key=lambda item: canonical(item))
    basis = {
        'format': INPUT_FORMAT,
        'source_context': report['context_sha256'],
        'source_coverage_complete': report['coverage_complete'],
        'review': mapping['review'],
        'candidate': candidate,
        'selected_file': selected,
        'evidence': evidence,
        'source_observations': source_observations,
        'source_diagnostics': source_diagnostics,
        'diagnostics': diagnostics,
    }
    return {
        'format': REPORT_FORMAT,
        'context_sha256': digest(basis),
        'source_context_sha256': report['context_sha256'],
        'source_coverage_complete': report['coverage_complete'],
        'review_revision': mapping['review']['revision'],
        'candidate': copy.deepcopy(candidate),
        'evidence': evidence,
        'source_observations': source_observations,
        'source_diagnostics': source_diagnostics,
        'diagnostics': diagnostics,
        'provider_claims': {
            'model_type': copy.deepcopy(resource.get('model_type')),
            'base_model': copy.deepcopy(resource.get('base_model')),
            'base_model_type': copy.deepcopy(resource.get('base_model_type')),
            'file_format': copy.deepcopy(selected.get('format')),
            'terms': copy.deepcopy(resource.get('terms')),
        },
        'provider_accessed': False,
        'file_hashed': False,
        'model_downloaded': False,
        'selection_changed': False,
        'installation_authorized': False,
        'generation_submitted': False,
        'notice': ('Provider metadata and gallery co-use remain retained evidence only. '
                   'Reviewed mappings supply compatibility facts; no provider, setup, '
                   'model, runtime or queue was changed.'),
    }


def read_json(path: Path) -> dict[str, Any]:
    with path.open('rb') as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    return decode(raw)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'mapping', type=Path,
        help='Retained source report plus reviewed mapping; no provider request is made')
    args = parser.parse_args(argv)
    try:
        result = adapt(read_json(args.mapping))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError,
            json.JSONDecodeError) as exc:
        print(json.dumps({
            'error': {
                'code': 'invalid_source_mapping',
                'message': str(exc)[:500],
            },
        }, ensure_ascii=False, allow_nan=False))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
