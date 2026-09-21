"""One-shot fixture update for exact retained source receipt contracts."""
from pathlib import Path


def replace(path: str, old: str, new: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    count = text.count(old)
    print(f'{label}: {count} exact match(es)')
    if count != 1:
        raise SystemExit(f'{label}: expected one exact match, found {count}')
    target.write_text(text.replace(old, new), encoding='utf-8')


replace(
    'tests/test_setup_source_evidence.py',
    "RECEIPT = 'c' * 64\nREVIEW = 'sha256:' + 'd' * 64\n",
    "RECEIPT = 'c' * 64\nGALLERY_RECEIPT = 'f' * 64\nREVIEW = 'sha256:' + 'd' * 64\n",
    'gallery receipt constant',
)
replace(
    'tests/test_setup_source_evidence.py',
    """def source_scope(host='civitai.com', browsing='1'):
    return {'host': host, 'route': '/api/v1/images',
            'query': {'browsingLevel': browsing, 'modelVersionId': '101', 'withMeta': 'true'},
            'auth_context': 'anonymous', 'scope_sha256': ('e' if host == 'civitai.com' else 'f') * 64}
""",
    """def source_scope(host='civitai.com', browsing='1', version_id=101):
    return {'host': host, 'route': '/api/v1/images',
            'query': {'browsingLevel': browsing, 'modelVersionId': str(version_id), 'withMeta': 'true'},
            'auth_context': 'anonymous', 'scope_sha256': ('e' if host == 'civitai.com' else 'f') * 64}
""",
    'version-aware source scope',
)
replace(
    'tests/test_setup_source_evidence.py',
    """def report(*, resource_identity='urn:air:sdxl:lora:civitai:10@101',
           base_model='Illustrious', model_type='LORA', combinations=None,
           file_identity=FILE_ID, file_format='SafeTensor'):
    if combinations is None:
        combinations = [{
            'source_scope': source_scope(), 'version_ids': [101, 202],
            'distinct_observations': 4, 'distinct_posts': 4, 'distinct_uploaders': 2,
            'post_ids': [11, 12, 13, 14], 'uploaders': ['alice', 'bob'],
            'receipt_sha256s': [RECEIPT], 'resource_usages': [
                {'version_id': 101, 'types': ['lora'], 'weights': [0.8]},
                {'version_id': 202, 'types': ['checkpoint'], 'weights': []}],
            'settings': [{'steps': 24, 'cfg': 5, 'count': 4}],
            'engagement': {'reaction_total': 999999, 'comment_total': 5000},
            'reported_co_use': True, 'compatibility_proven': False, 'quality_proven': False,
        }]
    return {
""",
    """def report(*, resource_identity='urn:air:sdxl:lora:civitai:10@101',
           base_model='Illustrious', model_type='LORA', combinations=None,
           file_identity=FILE_ID, file_format='SafeTensor'):
    version_id = (int(resource_identity.removeprefix('civitai-version:'))
                  if resource_identity.startswith('civitai-version:')
                  else int(resource_identity.rsplit('@', 1)[1]))
    if combinations is None:
        combinations = [{
            'source_scope': source_scope(version_id=version_id),
            'version_ids': [version_id, 202],
            'distinct_observations': 4, 'distinct_posts': 4, 'distinct_uploaders': 2,
            'post_ids': [11, 12, 13, 14], 'uploaders': ['alice', 'bob'],
            'receipt_sha256s': [GALLERY_RECEIPT], 'resource_usages': [
                {'version_id': version_id, 'types': ['lora'], 'weights': [0.8]},
                {'version_id': 202, 'types': ['checkpoint'], 'weights': []}],
            'settings': [{'steps': 24, 'cfg': 5, 'count': 4}],
            'engagement': {'reaction_total': 999999, 'comment_total': 5000},
            'reported_co_use': True, 'compatibility_proven': False, 'quality_proven': False,
        }]
    source_receipts = [{
        'host': 'civitai.com', 'route': '/api/v1/model-versions/' + str(version_id),
        'query': {}, 'retrieved_at': '2026-09-21T00:00:00Z',
        'response_sha256': RECEIPT, 'etag': None, 'last_modified': None,
        'outcome': 'ok', 'auth_context': 'anonymous',
    }]
    for item in combinations:
        scope = item['source_scope']
        for response_sha in item['receipt_sha256s']:
            key = (response_sha, scope['host'], scope['route'])
            existing = {(row['response_sha256'], row['host'], row['route'])
                        for row in source_receipts}
            if key not in existing:
                source_receipts.append({
                    'host': scope['host'], 'route': scope['route'], 'query': {},
                    'retrieved_at': '2026-09-21T00:00:00Z',
                    'response_sha256': response_sha, 'etag': None,
                    'last_modified': None, 'outcome': 'ok',
                    'auth_context': 'anonymous',
                })
    return {
""",
    'receipt-separated report fixture',
)
replace(
    'tests/test_setup_source_evidence.py',
    "            'source_host': 'civitai.com', 'model_id': 10, 'version_id': 101,\n",
    "            'source_host': 'civitai.com', 'model_id': 10, 'version_id': version_id,\n",
    'dynamic resource version',
)
replace(
    'tests/test_setup_source_evidence.py',
    """        'source_receipts': [{
            'host': 'civitai.com', 'route': '/api/v1/model-versions/101', 'query': {},
            'retrieved_at': '2026-09-21T00:00:00Z', 'response_sha256': RECEIPT,
            'etag': None, 'last_modified': None, 'outcome': 'ok', 'auth_context': 'anonymous',
        }],
""",
    "        'source_receipts': source_receipts,\n",
    'dynamic retained receipts',
)

print('Setup source fixtures now retain separate exact provider and gallery receipts.')
