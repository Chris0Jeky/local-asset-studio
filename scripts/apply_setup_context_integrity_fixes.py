"""One-shot guarded implementation for PR #809 review findings."""
from __future__ import annotations

from pathlib import Path
import re


def replace(path: str, old: str, new: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    count = text.count(old)
    print(f'{label}: {count} exact match(es)')
    if count != 1:
        raise SystemExit(f'{label}: expected one exact match, found {count}')
    target.write_text(text.replace(old, new), encoding='utf-8')


def replace_all(path: str, old: str, new: str, expected: int, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    count = text.count(old)
    print(f'{label}: {count} exact match(es)')
    if count != expected:
        raise SystemExit(f'{label}: expected {expected} exact matches, found {count}')
    target.write_text(text.replace(old, new), encoding='utf-8')


def replace_re(path: str, pattern: str, replacement: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    updated, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.S)
    print(f'{label}: {count} regex match(es)')
    if count != 1:
        raise SystemExit(f'{label}: expected one regex match, found {count}')
    target.write_text(updated, encoding='utf-8')


replace(
    'studio_workflow/source_compatibility.py',
    "REPORT_FORMAT = 'studio.setup-source-candidate/v1'\n",
    "REPORT_FORMAT = 'studio.setup-source-candidate/v2'\n",
    'source candidate contract version',
)

replace(
    'studio_workflow/source_compatibility.py',
    """ZERO_AUTHORITY_FIELDS = (
    'network_performed', 'model_downloaded', 'image_downloaded',
    'installation_authorized', 'generation_submitted',
)


def text(value: Any, limit: int = 300) -> bool:
""",
    """ZERO_AUTHORITY_FIELDS = (
    'network_performed', 'model_downloaded', 'image_downloaded',
    'installation_authorized', 'generation_submitted',
)
REPORT_FINGERPRINT_FIELDS = (
    'format', 'source_context_sha256', 'source_coverage_complete',
    'review_revision', 'candidate', 'evidence', 'source_observations',
    'source_diagnostics', 'diagnostics', 'provider_claims',
    'provider_accessed', 'file_hashed', 'model_downloaded',
    'selection_changed', 'installation_authorized',
    'generation_submitted', 'notice',
)


def candidate_report_basis(value: Any) -> dict[str, Any]:
    need(isinstance(value, dict), 'Source candidate report must be an object')
    missing = [field for field in REPORT_FINGERPRINT_FIELDS if field not in value]
    need(not missing,
         'Source candidate report fingerprint fields are missing: ' + ', '.join(missing))
    return {field: copy.deepcopy(value[field]) for field in REPORT_FINGERPRINT_FIELDS}


def candidate_report_digest(value: Any) -> str:
    """Fingerprint every retained field trusted by downstream compatibility."""
    return digest(candidate_report_basis(value))


def text(value: Any, limit: int = 300) -> bool:
""",
    'reproducible report fingerprint helper',
)

replace_re(
    'studio_workflow/source_compatibility.py',
    r"    basis = \{.*?\n    return \{.*?\n    \}\n\n\ndef read_json",
    """    result = {
        'format': REPORT_FORMAT,
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
    result['context_sha256'] = candidate_report_digest(result)
    return result


def read_json""",
    'source report output fingerprint',
)

replace(
    'studio_workflow/setup_context_compatibility.py',
    "from . import setup_compatibility as compatibility\n",
    "from . import setup_compatibility as compatibility\nfrom . import source_compatibility\n",
    'source bridge import',
)
replace(
    'studio_workflow/setup_context_compatibility.py',
    "SOURCE_FORMAT = 'studio.setup-source-candidate/v1'\n",
    "SOURCE_FORMAT = source_compatibility.REPORT_FORMAT\n",
    'source report version binding',
)
replace(
    'studio_workflow/setup_context_compatibility.py',
    """    need(compatibility.text(value['notice'], 1000)
         and value['notice'].strip() == value['notice'],
         'Source candidate notice is required')
    return result
""",
    """    need(compatibility.text(value['notice'], 1000)
         and value['notice'].strip() == value['notice'],
         'Source candidate notice is required')
    need(result['context_sha256'] == source_compatibility.candidate_report_digest(result),
         'Source candidate report fingerprint does not match retained fields; regenerate the reviewed report')
    return result
""",
    'source report fingerprint verification',
)
replace(
    'studio_workflow/setup_context_compatibility.py',
    """    observed = set(slot['capabilities'])
    absent = set(slot['known_absent_capabilities'])
    candidates: list[dict] = []
""",
    """    def adapter_owned(capability: str) -> bool:
        return capability.startswith(('local-file:', 'backend:', 'node:'))

    # These namespaces are observations owned by this adapter. Caller claims
    # cannot turn an unverified file, backend transition or partial schema into
    # false presence or false absence.
    observed = {item for item in slot['capabilities'] if not adapter_owned(item)}
    absent = {item for item in slot['known_absent_capabilities']
              if not adapter_owned(item)}
    candidates: list[dict] = []
""",
    'adapter-owned live capability projection',
)

replace(
    'tests/test_setup_context_compatibility.py',
    "from studio_workflow import setup_context_compatibility as L\n",
    "from studio_workflow import setup_context_compatibility as L\nfrom studio_workflow import source_compatibility as S\n",
    'source bridge test import',
)
replace(
    'tests/test_setup_context_compatibility.py',
    """    return {
        'format': 'studio.setup-source-candidate/v1',
        'context_sha256': SOURCE_CONTEXT,
""",
    """    result = {
        'format': S.REPORT_FORMAT,
        'context_sha256': SOURCE_CONTEXT,
""",
    'sealed source fixture start',
)
replace(
    'tests/test_setup_context_compatibility.py',
    """        'notice': 'retained evidence only',
    }


def context(**updates):
""",
    """        'notice': 'retained evidence only',
    }
    result['context_sha256'] = S.candidate_report_digest(result)
    return result


def context(**updates):
""",
    'sealed source fixture return',
)
replace(
    'tests/test_setup_context_compatibility.py',
    """    def test_live_context_cannot_contradict_declared_slot_runtime_or_capabilities(self):
        with self.assertRaisesRegex(ValueError, 'runtime'):
            L.evaluate(request(target=slot(runtime='other-runtime')))
        target = slot(known_absent_capabilities=['node:LoraLoader'])
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            L.evaluate(request(target=target))
""",
    """    def test_live_context_runtime_conflict_refuses_but_projected_claims_are_context_owned(self):
        with self.assertRaisesRegex(ValueError, 'runtime'):
            L.evaluate(request(target=slot(runtime='other-runtime')))
        target = slot(known_absent_capabilities=['node:LoraLoader'])
        result = L.evaluate(request(target=target))
        self.assertEqual(row(result)['status'], 'recommended')
""",
    'live context ownership expectation',
)

replace(
    'tests/test_setup_source_evidence.py',
    "self.assertEqual(result['format'], 'studio.setup-source-candidate/v1')",
    "self.assertEqual(result['format'], S.REPORT_FORMAT)",
    'source bridge format assertion',
)
replace(
    'tests/test_setup_source_evidence.py',
    """        self.assertEqual(value, before)
        self.assertEqual(result['format'], S.REPORT_FORMAT)
""",
    """        self.assertEqual(value, before)
        self.assertEqual(result['format'], S.REPORT_FORMAT)
        self.assertEqual(result['context_sha256'], S.candidate_report_digest(result))
""",
    'source report self-verification assertion',
)

replace_all(
    'docs/bundle-studio/SETUP-SOURCE-EVIDENCE.md',
    'studio.setup-source-candidate/v1',
    'studio.setup-source-candidate/v2',
    2,
    'source evidence contract documentation',
)
replace(
    'docs/bundle-studio/SETUP-SOURCE-EVIDENCE.md',
    """A successful `studio.setup-source-candidate/v2` result contains:
""",
    """A successful `studio.setup-source-candidate/v2` result contains a reproducible
fingerprint over every retained field trusted by downstream compatibility. Editing
candidate facts, evidence, diagnostics, provider claims or authority flags without
regenerating the reviewed report is refused.

It contains:
""",
    'source fingerprint documentation',
)

print('Setup-context integrity fixes applied.')
