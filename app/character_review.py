"""Character-check attestations shared by Review Desk and the read-only collector.

Local reviewer names are declarations, not authenticated human identities.
"""
import copy

from scripts import character_study as study
from app.review_media import digest

require = study.require


def context(plan):
    source = plan.get('character_source') or {}
    if source.get('kind') != 'character_primary_import': return None
    study_plan = source['study_plan']; study.check_plan(study_plan)
    case = study.get_case(study_plan, source['case_id'])
    return {'schema_version': 1, 'plan_sha256': study_plan['plan_sha256'], 'case_id': case['id'],
            'required_checks': {key: study_plan['canon']['checks'][key] for key in case['required_checks']}}


def observations(value, scope):
    require(isinstance(value, dict) and set(value) == set(scope['required_checks']), 'Character review must cover exactly the required checks')
    require(all(isinstance(v, str) and v in study.OBSERVATIONS for v in value.values()), 'Unknown character review observation')
    return copy.deepcopy(value)


def unobserved(scope):
    return {key: 'uncertain' for key in scope['required_checks']}


def validate_record(review, scope, output_sha256):
    study.keys(review, {'reviewer', 'reviewer_kind', 'decision', 'checks', 'note', 'output_sha256'})
    require(review['reviewer'] in ('local-user', 'local-agent'), 'Unknown character reviewer declaration')
    require(review['reviewer_kind'] == ('human' if review['reviewer'] == 'local-user' else 'agent'), 'Character reviewer kind differs')
    require(review['decision'] in ('selected', 'accepted'), 'Choose a character selection or acceptance')
    require(review['decision'] != 'accepted' or review['reviewer'] == 'local-user', 'Only an explicit local-user human declaration can accept a character result')
    require(review['output_sha256'] == output_sha256, 'Character review refers to different output bytes')
    checks = observations(review['checks'], scope)
    require(all(value == 'pass' for value in checks.values()), 'Every required character check must pass before selection or acceptance')
    study.text(review['note'], 'character decision note', 8000)
    return copy.deepcopy(review)


def receipt(document, candidate, decision, reviewer, notes):
    scope = context(document['evidence']['plan'])
    require(scope is not None and candidate is not None, 'Choose an imported character candidate before recording a character decision')
    review = {'reviewer': reviewer, 'reviewer_kind': 'human' if reviewer == 'local-user' else 'agent',
              'decision': decision, 'checks': candidate.get('character_checks', unobserved(scope)),
              'note': notes, 'output_sha256': candidate['sha256']}
    validate_record(review, scope, candidate['sha256'])
    return {'schema_version': 1, 'kind': 'character_case_review', 'plan_sha256': scope['plan_sha256'],
            'case_id': scope['case_id'], 'asset_id': candidate['asset_id'],
            'review_revision': document['revision'] + 1, 'evidence_sha256': document['evidence_sha256'], 'review': review}


def collected_review(project, asset, job):
    """Validate a saved receipt against the same project/output already checked by collection."""
    saved = project.get('review_desk') or {}; document = saved.get('document') or {}
    value = document.get('character_review')
    summary = project['state'].get('review') or {}
    if value is None and summary.get('character_review') is None: return None
    require(isinstance(value, dict) and asset is not None, 'Character review is missing its completed output or saved document')
    study.keys(value, {'schema_version', 'kind', 'plan_sha256', 'case_id', 'asset_id', 'review_revision', 'evidence_sha256', 'review'})
    scope = context(project['plan'])
    require(scope is not None and type(value['schema_version']) is int and value['schema_version'] == 1
            and value['kind'] == 'character_case_review', 'Unknown saved character review contract')
    require(value['plan_sha256'] == scope['plan_sha256'] and value['case_id'] == scope['case_id']
            and value['asset_id'] == asset['id'], 'Character review case or asset differs')
    review = validate_record(value['review'], scope, asset['sha256'])
    revision = value['review_revision']; current = document.get('revision')
    require(type(revision) is int and type(current) is int and 1 <= revision <= current
            and saved.get('revision') == current and document.get('finalized') is True
            and document.get('finalized_by') == review['reviewer'], 'Character review finalization differs')
    require(summary.get('character_review') == value and summary.get('revision') == current
            and summary.get('asset_id') == asset['id'] and summary.get('status') == 'selected', 'Character review summary differs from its document')
    evidence = document.get('evidence') or {}
    require(evidence.get('plan') == project['plan'] and digest(evidence) == document.get('evidence_sha256') == value['evidence_sha256'],
            'Character review execution evidence differs')
    stages = evidence.get('stages'); candidates = document.get('candidates'); captured = evidence.get('candidates')
    require(isinstance(stages, list) and len(stages) == 1 and isinstance(candidates, list) and len(candidates) == 1
            and isinstance(captured, list) and len(captured) == 1, 'Character review must bind the single primary output')
    stage = stages[0]; candidate = candidates[0]
    require(stage.get('job_id') == job['id'] and stage.get('status') == 'completed'
            and stage.get('prompt_ids') == job['prompt_ids']
            and stage.get('attempt') == project['state']['attempts']['0']
            and stage.get('graph_sha256') == project['plan']['stages'][0]['graph_sha256'], 'Character review job, prompt or graph differs')
    for item in (candidate, captured[0]):
        require(item.get('asset_id') == asset['id'] and item.get('sha256') == asset['sha256']
                and item.get('bytes') == asset['bytes'] and item.get('stage') == 0 and item.get('output_index') == 0,
                'Character review candidate provenance differs')
    require(candidate.get('alias') == document.get('selected') and candidate.get('character_checks') == review['checks']
            and candidate.get('assessment', {}).get('verdict') == 'keep'
            and candidate['assessment'].get('observations', {}).get('constraints') == 'pass', 'Character review selected assessment differs')
    event = saved.get('finalization_event') or {}; details = event.get('details') or {}
    require(event.get('action') == 'finalize' and event.get('revision') == revision and event.get('reviewer') == review['reviewer']
            and details.get('character_review') == value and details.get('character_decision') == review['decision']
            and details.get('selected') == document['selected'] and details.get('notes') == review['note'],
            'Character review finalization event differs')
    return review
