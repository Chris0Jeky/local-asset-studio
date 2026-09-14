"""Multi-image observations and explicit trait selection into a new CreativeIntent.

This is a pure review contract, not a persistent document, model worker or graph
adapter. Metadata recovery stays in recipe_intake; analysis is never provenance.
"""
from __future__ import annotations
import copy
import hashlib
import re
from .schema import canonical, digest, fields, file_bytes, identifier, need, new_brief, strings, text, validate

REQUEST_FORMAT = 'studio.reference-analysis.request/v1'
REPORT_FORMAT = 'studio.reference-analysis.report/v1'
MAX_REFERENCES = 4
IMAGE_FACETS = ('subject', 'action', 'setting', 'composition', 'camera', 'lighting', 'style', 'palette', 'mood')
ROLE_FACETS = {
    'identity': ('subject',), 'costume': ('subject',),
    'pose': ('action', 'composition'), 'style': ('style', 'palette', 'lighting', 'mood'),
    'composition': ('composition', 'camera', 'setting'), 'geometry': ('subject',),
}


def _hash(value):
    need(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value), 'Expected SHA256')


def _bounded(value):
    need(len(canonical(value)) <= 65536, 'Reference analysis exceeds 64 KiB')
    return copy.deepcopy(value)


def validate_request(value):
    fields(value, ('format', 'brief', 'references'))
    need(value['format'] == REQUEST_FORMAT, 'Unsupported reference request')
    text(value['brief'], 4000, empty=True)
    refs = value['references']
    need(type(refs) is list and 1 <= len(refs) <= MAX_REFERENCES, 'Supply one to four image references; never truncate')
    ids = set()
    for ref in refs:
        fields(ref, ('id', 'path', 'sha256', 'role_hint'))
        identifier(ref['id']); need(ref['id'] not in ids, 'Duplicate reference ID'); ids.add(ref['id'])
        _hash(ref['sha256']); text(ref['path'], 500)
        need('\\' not in ref['path'] and ':' not in ref['path'] and
             all(x not in ('', '.', '..') for x in ref['path'].split('/')), 'Unsafe reference path')
        need(type(ref['role_hint']) is str and ref['role_hint'] in ('auto', *ROLE_FACETS), 'Unsupported role hint')
    return _bounded(value)


def new_request(brief, references):
    return validate_request({'format': REQUEST_FORMAT, 'brief': brief, 'references': references})


def validate_answer(request, answer):
    q = validate_request(request)
    fields(answer, ('summary', 'assumptions', 'questions', 'images'))
    text(answer['summary'], 1000); strings(answer['assumptions'], 8, 300); strings(answer['questions'], 3, 300)
    need(type(answer['images']) is list and len(answer['images']) == len(q['references']), 'Describe every reference exactly once')
    for ref, image in zip(q['references'], answer['images']):
        fields(image, ('reference_id', 'suggested_role', 'description', 'tags', 'facets', 'uncertain_facets', 'unknowns'))
        need(image['reference_id'] == ref['id'], 'Reference order/identity differs from request')
        role = image['suggested_role']
        need(type(role) is str and role in ROLE_FACETS, 'Unsupported suggested role')
        need(ref['role_hint'] == 'auto' or role == ref['role_hint'], 'Model changed an explicit role hint')
        text(image['description'], 1000); strings(image['tags'], 20, 80); strings(image['unknowns'], 8, 300)
        fields(image['facets'], (), IMAGE_FACETS)
        for value in image['facets'].values(): text(value, 240)
        strings(image['uncertain_facets'], len(IMAGE_FACETS), 32)
        need(len(set(image['uncertain_facets'])) == len(image['uncertain_facets']) and
             set(image['uncertain_facets']) <= image['facets'].keys(), 'Unknown/duplicate uncertain facet')
    return _bounded(answer)


def make_report(request, answer, analysis_inputs):
    q = validate_request(request); a = validate_answer(q, answer)
    need(type(analysis_inputs) is list and len(analysis_inputs) == len(q['references']), 'Missing analysis input evidence')
    for ref, item in zip(q['references'], analysis_inputs):
        fields(item, ('reference_id', 'source_sha256', 'analysis_sha256', 'analysis_size'))
        need(item['reference_id'] == ref['id'] and item['source_sha256'] == ref['sha256'], 'Analysis source identity changed')
        _hash(item['analysis_sha256']); size = item['analysis_size']
        need(type(size) is list and len(size) == 2 and all(type(x) is int and 1 <= x <= 768 for x in size), 'Invalid analysis dimensions')
    report = _bounded({'format': REPORT_FORMAT, 'request': q, 'answer': a, 'analysis_inputs': analysis_inputs,
                       'authority': 'untrusted_suggestion', 'execution_authorized': False, 'generation_submitted': False})
    report['report_sha256'] = digest(report)
    return report


def validate_report(report):
    fields(report, ('format', 'request', 'answer', 'analysis_inputs', 'authority',
                    'execution_authorized', 'generation_submitted', 'report_sha256'))
    expected = make_report(report['request'], report['answer'], report['analysis_inputs'])
    need(canonical(report) == canonical(expected), 'Changed or invalid reference report')
    return expected


def review_template(report):
    """A proposal to review, not acceptance. Uncertain facets/tags are opt-in."""
    report = validate_report(report)
    return {'report_sha256': report['report_sha256'], 'selections': [
        {'reference_id': image['reference_id'], 'role': image['suggested_role'],
         'facets': sorted(set(image['facets']) & set(ROLE_FACETS[image['suggested_role']]) - set(image['uncertain_facets'])),
         'overrides': {}, 'tags': []} for image in report['answer']['images']]}


def draft(report, review, root=None, *, source_bytes=None):
    """Explicit selection creates a NEW intent; never overwrites an existing one.

    Supply either a file root or exact in-memory originals. Analysis of yesterday's
    pixels cannot silently attach today's replacement. Staging must check again.
    """
    report = validate_report(report); fields(review, ('report_sha256', 'selections'))
    need(review['report_sha256'] == report['report_sha256'], 'Stale reference review')
    _bounded(review)
    q = report['request']; answer = report['answer']; choices = review['selections']
    need(type(choices) is list and len(choices) == len(q['references']), 'Review every reference; do not silently omit images')
    need((root is not None) != (source_bytes is not None), 'Supply one source workspace or exact in-memory originals')
    if source_bytes is not None:
        need(type(source_bytes) is dict and set(source_bytes) == {ref['id'] for ref in q['references']},
             'Supply every original exactly once')
    intent = new_brief(q['brief'] if q['brief'].strip() else answer['summary'])
    transfers = []; parts = {}; unknowns = []
    for ref, image, choice in zip(q['references'], answer['images'], choices):
        fields(choice, ('reference_id', 'role', 'facets', 'overrides', 'tags'))
        need(choice['reference_id'] == ref['id'], 'Review reference identity/order changed')
        role = choice['role']; need(type(role) is str and role in ROLE_FACETS, 'Unsupported selected role')
        strings(choice['facets'], len(IMAGE_FACETS), 32)
        selected = choice['facets']
        need(len(set(selected)) == len(selected) and set(selected) <= set(ROLE_FACETS[role]), 'Selection crosses reference-role boundary')
        fields(choice['overrides'], (), selected)
        strings(choice['tags'], 20, 80)
        need(len(set(choice['tags'])) == len(choice['tags']) and set(choice['tags']) <= set(image['tags']), 'Unknown/duplicate selected tags')
        if source_bytes is None: file_bytes(root, ref, 8 * 1024 * 1024)
        else:
            raw = source_bytes[ref['id']]
            need(type(raw) is bytes and 0 < len(raw) <= 8 * 1024 * 1024, 'Reference size limit exceeded')
            need(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Reference bytes changed')
        takes = []
        for facet in selected:
            edited = facet in choice['overrides']
            need(edited or facet in image['facets'], 'Selected facet has no observation or user description')
            need(edited or facet not in image['uncertain_facets'], 'An uncertain facet needs an explicit user description')
            value = choice['overrides'][facet] if edited else image['facets'][facet]
            text(value, 240)
            parts.setdefault(facet, []).append(ref['id'] + ': ' + value)
            takes.append(facet + ': ' + value)
            transfers.append({'reference_id': ref['id'], 'source_sha256': ref['sha256'], 'field': facet,
                              'value': value, 'origin': 'user_edit' if edited else 'selected_visual_observation'})
        for tag in choice['tags']:
            if tag not in intent['tags']: intent['tags'].append(tag)
            transfers.append({'reference_id': ref['id'], 'source_sha256': ref['sha256'], 'field': 'tags',
                              'value': tag, 'origin': 'selected_visual_tag'})
        intent['references'].append({'id': ref['id'], 'role': role, 'kind': 'image', 'path': ref['path'],
                                     'sha256': ref['sha256'], 'take': takes, 'ignore': []})
        unknowns.extend({'reference_id': ref['id'], 'text': value} for value in image['unknowns'])
    intent['facets'] = {key: '; '.join(values) for key, values in parts.items()}
    validate(intent)  # Enforce the existing compiler's caps; do not truncate a constraint.
    result = {'format': 'studio.reference-draft/v1', 'intent': intent, 'source_report_sha256': report['report_sha256'],
              'review': copy.deepcopy(review), 'transfers': transfers, 'unknowns': unknowns,
              'brief_origin': 'user' if q['brief'].strip() else 'reviewed_analysis_summary',
              'assumptions': answer['assumptions'], 'unresolved_questions': answer['questions'],
              'execution_authorized': False, 'generation_submitted': False,
              'limits': ['A new editable intent, not a bound recipe or an approval of artwork.',
                         'Semantic role labels do not enforce pose geometry or exact protected pixels.',
                         'Select a compatible registered route; four analysis images do not imply four native model slots.']}
    result = _bounded(result); result['draft_sha256'] = digest(result)
    return result
