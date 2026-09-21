"""Pure model-specific projections; no graph execution or model inference."""
import copy
import re
from .schema import validate, profiles, need, digest, VERSION, FACETS


def compile_brief(b, profile_id):
    validate(b); registry = profiles(); need(profile_id in registry, 'Unknown model profile; no generic fallback')
    p = registry[profile_id]; errors = []; notes = []; ledger = []; out = {}
    def issue(code, message, error=False):
        (errors if error else notes).append({'code': code, 'message': message})
    def record(source, destination): ledger.append({'source': source, 'destination': destination})
    need(b['task'] in p['tasks'], 'Task does not match model/profile')
    refs = b['references']
    if not p['min_refs'] <= len(refs) <= p['max_refs']:
        issue('REFERENCE_COUNT', f"This profile reads {p['min_refs']}..{p['max_refs']} reference images and {len(refs)} are attached; none were silently discarded", True)
    if any(r['kind'] not in p['reference_kinds'] for r in refs): issue('REFERENCE_KIND', f"This profile reads only {', '.join(p['reference_kinds']) or 'no'} references; the attached kind stays in the brief", True)
    for i, r in enumerate(refs): record(f'references[{i}]', 'reference_map')
    prose = [b['brief']] + [f'{k.capitalize()}: {b["facets"][k]}' for k in FACETS if k in b['facets']]
    record('brief', 'description')
    for k in FACETS:
        if k in b['facets']: record(f'facets.{k}', 'description')
    for i, c in enumerate(b['constraints']):
        if c['mechanism'] == 'prompt': prose.append(c['text']); record(f'constraints[{i}]', 'description + acceptance')
        else:
            record(f'constraints[{i}]', 'required_stage + acceptance')
            issue('STRUCTURAL_CONTROL_REQUIRED', f"{c['id']}: {c['mechanism']} cannot be delivered by prompt text alone", c['priority'] == 'hard')
    dialect = p['dialect']
    if dialect == 'tags':
        if not b['tags']: issue('TAGS_REQUIRED', 'This profile emits only approved tags and none were supplied; the brief is never translated into tags automatically', True)
        out['positive'] = ', '.join(b['tags']); out['negative'] = ', '.join(b['avoid'])
        issue('TAG_COVERAGE_REVIEW', 'Only approved tags are emitted. Review semantic coverage against the preserved brief and constraints.')
        for x in ledger:
            if 'description' in x['destination']: x['destination'] = 'preserved_intent + acceptance / tag coverage review'
        record('tags', 'positive'); record('avoid', 'negative')
    elif dialect in ('prose', 'edit', 'motion', 'sound'):
        if b['tags']: prose.append('Visual descriptors: ' + ', '.join(b['tags']))
        if dialect == 'edit':
            for i, r in enumerate(refs, 1):
                prose.append(f"Picture {i} ({r['role']}): use {'; '.join(r['take']) or 'only the named role'}." +
                             (f" Do not transfer {'; '.join(r['ignore'])}." if r['ignore'] else ''))
        if dialect == 'motion' and not b['facets'].get('motion'):
            issue('MOTION_UNSPECIFIED', 'Specify subject movement, camera movement and what stays fixed; no motion invented.')
        out['positive'] = '\n'.join(prose)
        if p['negative']: out['negative'] = ', '.join(b['avoid'])
        elif b['avoid']: issue('NEGATIVE_REWRITE_REQUIRED', 'This profile has no negative channel, so avoidance terms cannot be sent. Approve positive replacements or keep them as a review note; the words remain in the intent.', True)
        record('tags', 'positive'); record('avoid', 'negative' if p['negative'] else 'review: positive rewrite')
    elif dialect == 'voice':
        out = {'text': b['verbatim'].get('text', ''), 'instruct': '\n'.join(prose), 'language': b['parameters'].get('language', 'Auto')}
        if not out['text'].strip(): issue('SPEECH_TEXT_REQUIRED', 'Provide exact words to speak, separately from performance direction', True)
        record('verbatim.text', 'text: byte-preserving'); record('parameters.language', 'language')
        if out['language'] not in ('Auto','Chinese','English','Japanese','Korean','German','French','Russian','Portuguese','Spanish','Italian'):
            issue('VOICE_LANGUAGE_UNSUPPORTED', 'Language is outside this exact voice profile', True)
    elif dialect == 'music':
        out = {'caption': '\n'.join(prose), 'lyrics': b['verbatim'].get('lyrics', ''), 'instrumental': b['parameters'].get('instrumental', False)}
        if out['instrumental'] and out['lyrics'].strip(): issue('LYRICS_CONFLICT', 'Instrumental request contains lyrics; resolve rather than deleting them', True)
        for a, z in (('bpm', 'bpm'), ('key', 'keyscale'), ('duration_seconds', 'duration')):
            if a in b['parameters']: out[z] = b['parameters'][a]; record('parameters.' + a, z)
        if 'meter' in b['parameters']:
            meter = b['parameters']['meter']; allowed = {'2/4': '2', '3/4': '3', '4/4': '4', '6/8': '6'}
            if meter not in allowed: issue('METER_UNSUPPORTED', 'Meter needs a reviewed adapter mapping', True)
            else: out['timesignature'] = allowed[meter]
            record('parameters.meter', 'timesignature')
        record('verbatim.lyrics', 'lyrics: byte-preserving')
    elif dialect == 'image_input':
        out = {'image_reference_id': refs[0]['id'] if refs else None}
        issue('NO_TEXT_CONDITIONING', 'This image-to-mesh route has no text prompt. Refine/approve the input image or choose a different tool.')
        for x in ledger:
            if 'description' in x['destination']: x['destination'] = 'input-image preparation / acceptance'
    else: raise ValueError('Unsupported profile dialect')
    check = p.get('dialect_check')
    if check in ('anima_aesthetic', 'animagine_opt'):
        for channel in ('positive', 'negative'):
            if re.search(r'(?<!\w)score_[a-z0-9_]+', out.get(channel, ''), re.IGNORECASE):
                issue('MODEL_SCORE_TOKEN_CONFLICT', f'{channel}: score_* tokens need a reviewed rewrite or a different profile; text is retained unchanged', True)
    if check == 'animagine_opt':
        quality = {'masterpiece', 'high score', 'great score', 'absurdres'}
        tail = False
        for tag in out['positive'].split(','):
            is_quality = tag.strip().lower() in quality
            if tail and not is_quality:
                issue('MODEL_TAG_ORDER_CONFLICT', 'Quality terms must form a final tail in this profile; review the existing order, no tags were moved', True)
                break
            tail = tail or is_quality
    consumed_params = {'voice': {'language'}, 'music': {'instrumental', 'duration_seconds', 'bpm', 'key', 'meter'}}.get(dialect, set())
    for k in sorted(b['parameters'].keys() - consumed_params):
        record('parameters.' + k, 'workflow parameter handoff')
        issue('PARAMETER_HANDOFF', f'{k} needs an executor binding; it was not inserted into a text prompt')
    for k in sorted(b['verbatim']):
        if (dialect, k) not in (('voice', 'text'), ('music', 'lyrics')):
            record('verbatim.' + k, 'preserved / unbound'); issue('VERBATIM_UNBOUND', f'No output channel for verbatim.{k}', True)
    if dialect in ('voice', 'music', 'image_input'):
        if b['avoid']: issue('NEGATIVE_UNBOUND', 'This profile has no channel for avoidance terms; they need an explicit supported treatment and were not dropped', True)
        if b['tags']: issue('TAGS_UNBOUND', 'This profile does not read tags; yours are preserved in the intent but unused', True)
    for key, value in out.items():
        cap = p.get('field_limits', {}).get(key, p['max_chars'])
        if isinstance(value, str) and len(value) > cap: issue('PROMPT_TOO_LONG', f'{key} is {len(value)} characters against a reviewed {cap}-character budget; no truncation applied', True)
    if any(c['priority'] == 'hard' for c in b['constraints']):
        issue('ACCEPTANCE_REQUIRED', 'Hard requirements remain acceptance checks; syntactically valid prompting cannot guarantee them.')
    # The complete intent is retained even when the backend cannot consume a field.
    result = {'schema_version': 1, 'kind': 'compiled_creative_intent', 'compiler_version': VERSION,
              'intent': copy.deepcopy(b), 'intent_sha256': digest(b), 'profile': copy.deepcopy(p), 'profile_sha256': digest(p),
              'fields': out, 'reference_map': [{'slot': i, **copy.deepcopy(r)} for i, r in enumerate(refs, 1)],
              'coverage': ledger, 'errors': errors, 'diagnostics': notes,
              'state': 'blocked' if errors else 'review_required', 'generation_submitted': False,
              'token_count': None, 'token_note': 'Character caps are app budgets, not tokenizer measurements.'}
    result['artifact_sha256'] = digest(result)
    return result


