"""Read-only, resource-scoped settings explanations. Never prepares or runs a job.

Claims live inside the existing settings KB. Resource hashes below identify
catalog pins, NOT newly hashed installed files. The same evaluator serves HTTP,
offline tests and the CLI; the browser only presents its report.
"""
from __future__ import annotations

import argparse
import copy
from datetime import date
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from .core import canonical, decode, digest, need
from .preset_adapter import CONTROLS, equivalent, graph_inputs

FORMAT = 'studio.settings-guidance/v1'
KINDS = {'creator_documentation', 'local_observation', 'controlled_experiment', 'authored_hypothesis'}
FILE_FIELDS = {'ckpt_name': 'checkpoints', 'unet_name': 'diffusion_models',
               'clip_name': 'text_encoders', 'clip_name1': 'text_encoders', 'clip_name2': 'text_encoders',
               'clip_name3': 'text_encoders', 'vae_name': 'vae', 'lora_name': 'loras',
               'control_net_name': 'controlnet', 'clip_vision_name': 'clip_vision'}
LORA_TYPES = {'LoraLoader', 'LoraLoaderModelOnly'}
MAX_CLAIMS = 128


def text(value, limit=2000):
    return isinstance(value, str) and 0 < len(value) <= limit


def numeric(value):
    return type(value) is int or type(value) is float and math.isfinite(value)


def file_key(value):
    need(text(value, 300) and '\\' not in value and '\x00' not in value, 'Invalid resource path')
    parts = value.split('/')
    need(len(parts) >= 2 and all(p not in ('', '.', '..') and ':' not in p for p in parts)
         and parts[0] in set(FILE_FIELDS.values()), 'Resource must use a model-library relative path')
    return value


def band(value):
    need(isinstance(value, dict), 'A setting band must be an object')
    if set(value) == {'values'}:
        items = value['values']
        need(isinstance(items, list) and 1 <= len(items) <= 32
             and all(numeric(x) or text(x, 200) for x in items), 'Use 1–32 finite numeric or text choices')
        need(all(numeric(x) == numeric(items[0]) for x in items), 'Do not mix text and numeric choices')
    else:
        need(set(value) == {'range'} and isinstance(value['range'], list) and len(value['range']) == 2
             and all(numeric(x) for x in value['range']) and value['range'][0] <= value['range'][1],
             'Use an ordered finite numeric range')
    return value


def contains(constraint, value):
    if 'values' in constraint: return any(equivalent(value, x) for x in constraint['values'])
    return numeric(value) and constraint['range'][0] <= value <= constraint['range'][1]


def overlap(bands):
    """Joint intersection, not merely pairwise overlap; never choose a compromise."""
    choices = next((b['values'] for b in bands if 'values' in b), None)
    if choices is not None: return any(all(contains(b, x) for b in bands) for x in choices)
    return max(b['range'][0] for b in bands) <= min(b['range'][1] for b in bands)


def validate_claim(value):
    need(isinstance(value, dict) and set(value) == {'id', 'title', 'runtime', 'resources', 'when',
         'settings', 'source', 'rationale', 'review_after'}, 'Invalid guidance claim fields')
    need(text(value['id'], 96) and re.fullmatch(r'[a-z0-9][a-z0-9_.-]*', value['id']), 'Invalid claim ID')
    need(text(value['title'], 160) and text(value['rationale'], 3000), 'Claim title and rationale required')
    need(value['runtime'] == 'comfyui', 'Only ComfyUI claims are supported')
    resources = value['resources']
    need(isinstance(resources, list) and 1 <= len(resources) <= 12, 'Use 1–12 exact resource pins')
    files = set()
    for resource in resources:
        need(isinstance(resource, dict) and set(resource) == {'file', 'sha256'}, 'Invalid claim pin')
        key = file_key(resource['file'])
        need(key not in files, 'Duplicate resource scope'); files.add(key)
        need(isinstance(resource['sha256'], str) and re.fullmatch(r'[a-f0-9]{64}', resource['sha256']), 'SHA-256 scope required')
    conditions = value['when']
    need(isinstance(conditions, list) and len(conditions) <= 16, 'Too many prerequisites')
    for condition in conditions:
        need(isinstance(condition, dict), 'Invalid prerequisite')
        if set(condition) == {'resource', 'state'}:
            file_key(condition['resource'])
            need(condition['resource'] in files, 'Prerequisite resource needs an exact scope pin')
            need(condition['state'] in ('active', 'inactive'), 'Invalid resource-state prerequisite')
        elif set(condition) == {'adapters'}:
            need(condition['adapters'] == 'none_active', 'Unknown adapter prerequisite')
        else:
            need(set(condition) == {'control', 'values'} and condition['control'] in CONTROLS, 'Invalid control prerequisite')
            band({'values': condition['values']})
    settings = value['settings']
    need(isinstance(settings, list) and 1 <= len(settings) <= 16, 'Use 1–16 scoped settings')
    for setting in settings:
        need(isinstance(setting, dict) and set(setting) == {'target', 'recommended', 'tested'}, 'Invalid setting claim')
        target = setting['target']
        need(isinstance(target, dict), 'Setting target required')
        if set(target) == {'control', 'node_types'}:
            need(target['control'] in CONTROLS, 'Unknown setting control')
        else:
            need(set(target) == {'resource', 'input', 'node_types'} and target['resource'] in files
                 and target['input'] in ('strength_model', 'strength_clip'), 'Invalid resource input target')
        need(isinstance(target['node_types'], list) and 1 <= len(target['node_types']) <= 8
             and all(text(x, 120) for x in target['node_types']), 'Exact target node types required')
        need(setting['recommended'] is not None or setting['tested'] is not None, 'Empty setting evidence')
        for key in ('recommended', 'tested'):
            if setting[key] is not None: band(setting[key])
    source = value['source']
    need(isinstance(source, dict) and set(source) == {'kind', 'locator', 'url', 'revision', 'retrieved_at'}, 'Invalid source record')
    need(source['kind'] in KINDS and text(source['locator'], 1000), 'Source kind and locator required')
    need(source['revision'] is None or text(source['revision'], 160), 'Invalid source revision')
    if source['url'] is not None:
        need(text(source['url'], 2000), 'Invalid source URL')
        url = urlsplit(source['url'])
        need(url.scheme == 'https' and url.hostname and not url.username and not url.password, 'Use a credential-free HTTPS source')
    for stamp in (source['retrieved_at'], value['review_after']):
        if stamp is not None:
            need(isinstance(stamp, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', stamp), 'Dates must use YYYY-MM-DD')
            date.fromisoformat(stamp)
    if source['kind'] == 'local_observation':
        need(all(s['recommended'] is None for s in settings), 'A historical observation is not a recommendation')
    return copy.deepcopy(value)


def bindings(preset):
    extras = preset.get('bindings_extra') or {}
    need(isinstance(extras, dict), 'Invalid companion bindings')
    result = {}
    for control in CONTROLS:
        primary = [preset[control]] if preset.get(control) else []
        extra = extras.get(control, [])
        need(isinstance(extra, list), 'Invalid companion bindings')
        pairs = primary + extra
        if not pairs: continue
        need(all(isinstance(x, list) and len(x) == 2 and all(text(t, 120) for t in x) for x in pairs), 'Invalid control binding')
        result[control] = pairs
    return result


def project(preset, template, controls):
    """Apply only declared scalar edits for explanation, not runtime preparation."""
    need(preset.get('modality') == 'image' and not any(preset.get(k) for k in
         ('reference', 'last_reference', 'reference_slots', 'requires_rgba_mask')), 'Guidance currently covers non-reference image presets')
    need(isinstance(template, dict) and 0 < len(template) <= 256, 'Invalid registered graph')
    need(isinstance(controls, dict), 'Controls must be an object')
    mapped = bindings(preset); need(set(controls) <= set(mapped), 'Unsupported guidance controls')
    graph = copy.deepcopy(template); effective = {}; assigned = {}
    for control, pairs in mapped.items():
        for node, field in pairs:
            need(node in graph and isinstance(graph[node].get('inputs'), dict)
                 and field in graph[node]['inputs'], 'Missing catalog binding: ' + control)
        current = graph[pairs[0][0]]['inputs'][pairs[0][1]]
        effective[control] = current
        if control not in controls: continue
        value = controls[control]
        need((numeric(value) and numeric(current)) or (isinstance(value, str) and isinstance(current, str)
             and len(value) <= 8000), 'Use a finite scalar with the bound input type: ' + control)
        for node, field in pairs:
            key = (node, field)
            need(key not in assigned or equivalent(assigned[key], value), 'Conflicting companion controls')
            need(not isinstance(template[node]['inputs'][field], (dict, list)), 'Cannot replace a connection')
            assigned[key] = value; graph[node]['inputs'][field] = value
        effective[control] = value
    return graph, effective, mapped


def resource_context(graph, manifest):
    need(isinstance(manifest, dict) and isinstance(manifest.get('assets'), list), 'Model pin registry unavailable')
    pins = {}
    for item in manifest['assets']:
        if isinstance(item, dict): pins.setdefault(item.get('file'), []).append(item)
    rows = []
    for node, data in graph.items():
        for field, folder in FILE_FIELDS.items():
            name = data.get('inputs', {}).get(field)
            if not isinstance(name, str) or not name: continue
            try: path = file_key(folder + '/' + name)
            except ValueError: continue
            candidates = pins.get(path, [])
            hashes = {p.get('sha256') for p in candidates if isinstance(p.get('sha256'), str)
                      and re.fullmatch(r'[a-f0-9]{64}', p['sha256'])}
            known = len(hashes) == 1 and len(candidates) == 1
            active = True
            if field == 'lora_name':
                strengths = [data['inputs'][k] for k in ('strength_model', 'strength_clip') if k in data['inputs']]
                active = any(x != 0 for x in strengths) if data.get('class_type') in LORA_TYPES and strengths and all(numeric(x) for x in strengths) else None
            rows.append({'node': node, 'input': field, 'file': path, 'active': active,
                         'pin_sha256': next(iter(hashes)) if known else None,
                         'identity': 'catalog_pin' if known else 'ambiguous_pin' if candidates else 'unknown_file'})
    return rows


def targets(target, graph, mapped, resources):
    pairs = mapped.get(target['control'], []) if 'control' in target else [
        [r['node'], target['input']] for r in resources if r['file'] == target['resource'] and r['active'] is not False]
    if not pairs: return []
    result = []
    for node, field in pairs:
        data = graph[node]
        if data.get('class_type') not in target['node_types'] or field not in data['inputs']: return []
        result.append({'key': node + '.' + field, 'node': node, 'input': field,
                       'control': next((k for k, ps in mapped.items() if [node, field] in ps), None),
                       'current': data['inputs'][field]})
    return result


def explain(preset, template, controls, kb, manifest, today=None):
    graph, effective, mapped = project(preset, template, controls)
    resources = resource_context(graph, manifest); by_file = {}
    for row in resources: by_file.setdefault(row['file'], []).append(row)
    guidance = kb.get('guidance', {}) if isinstance(kb, dict) else {}
    need(isinstance(guidance, dict) and guidance.get('version', 1) == 1
         and isinstance(guidance.get('claims', []), list) and len(guidance.get('claims', [])) <= MAX_CLAIMS, 'Unsupported or oversized guidance library')
    now = date.fromisoformat(today) if today else date.today()
    claims, diagnostics, groups, covered = [], [], {}, set()
    ids = [r.get('id') for r in guidance.get('claims', []) if isinstance(r, dict) and isinstance(r.get('id'), str)]
    for raw in guidance.get('claims', []):
        try:
            claim = validate_claim(raw)
            need(ids.count(claim['id']) == 1, 'Duplicate claim ID: ' + claim['id'])
        except (ValueError, TypeError) as exc:
            diagnostics.append(str(exc)); continue
        if not any(r['file'] in by_file for r in claim['resources']): continue
        reasons, state = [], 'applies'
        for pin in claim['resources']:
            rows = by_file.get(pin['file'], [])
            if not rows: reasons.append('Required resource is not selected: ' + pin['file']); state = 'not_applicable'
            elif any(r['pin_sha256'] is None for r in rows):
                reasons.append('Resource identity is unknown or ambiguous: ' + pin['file'])
                if state == 'applies': state = 'unknown'
            elif any(r['pin_sha256'] != pin['sha256'] for r in rows):
                reasons.append('Catalog file version differs from this claim: ' + pin['file']); state = 'not_applicable'
        for condition in claim['when']:
            if 'resource' in condition:
                rows = by_file.get(condition['resource'], [])
                current = True if any(r['active'] is True for r in rows) else None if any(r['active'] is None for r in rows) else False
                ok = None if current is None else current == (condition['state'] == 'active')
                why = condition['resource'] + ' must be ' + condition['state']
            elif 'adapters' in condition:
                rows = [r for r in resources if r['input'] == 'lora_name']
                ok = False if any(r['active'] is True for r in rows) else None if any(r['active'] is None for r in rows) else True
                why = 'every authored adapter must be inactive'
            else:
                current = effective.get(condition['control'])
                ok = contains({'values': condition['values']}, current) if condition['control'] in effective else None
                why = condition['control'] + ' must be one of ' + json.dumps(condition['values'])
            if ok is not True:
                reasons.append('Prerequisite: ' + why)
                if ok is False: state = 'not_applicable'
                elif state == 'applies': state = 'unknown'
        checks = []
        for setting in claim['settings']:
            resolved = targets(setting['target'], graph, mapped, resources)
            if not resolved:
                reasons.append('The target input or required node type is unavailable')
                if state == 'applies': state = 'unknown'
            for target in resolved:
                checks.append({**target, 'recommended': setting['recommended'], 'tested': setting['tested'],
                               'assessment': 'observation_only' if setting['recommended'] is None else
                               'within' if contains(setting['recommended'], target['current']) else 'outside'})
        due = claim['review_after'] is not None and now > date.fromisoformat(claim['review_after'])
        report = {**claim, 'applicability': state, 'reasons': reasons, 'checks': checks, 'review_due': due}
        claims.append(report)
        if state == 'applies':
            covered.update(r['file'] for r in claim['resources'])
            for check in checks:
                if check['recommended'] is not None: groups.setdefault(check['key'], []).append((claim['id'], check['recommended']))
    conflicts = [{'target': key, 'claims': sorted({c for c, _ in entries})}
                 for key, entries in groups.items() if not overlap([b for _, b in entries])]
    uncovered = sorted({r['file'] for r in resources if r['active'] is not False and r['file'] not in covered})
    return {'format': FORMAT, 'preset_id': preset['id'], 'generation_submitted': False, 'authoring_only': True,
            'evaluated_on': now.isoformat(), 'context_sha256': digest({'preset': preset, 'graph': graph, 'kb': kb, 'manifest': manifest}),
            'resources': resources, 'claims': claims, 'conflicts': conflicts, 'uncovered_resources': uncovered,
            'diagnostics': diagnostics, 'notice': 'Claims match catalog pins and authored inputs, not newly verified installed bytes. '
            'No setting was changed. This is not runtime validation, image-quality evidence or permission to generate.'}


def read_json(path):
    with path.open('rb') as stream: raw = stream.read(1048577)
    return decode(raw)


def request(value, studio):
    need(isinstance(value, dict) and set(value) == {'preset_id', 'controls', 'expected_graph', 'expected_bindings'}, 'Supply the captured preset, controls, graph and bindings')
    need(text(value['preset_id'], 96), 'Preset ID required')
    expected = value['expected_graph']
    need(isinstance(expected, dict) and 0 < len(expected) <= 256 and all(
        isinstance(n, dict) and isinstance(n.get('class_type'), str) and isinstance(n.get('inputs'), dict)
        for n in expected.values()), 'Invalid captured graph')
    with studio.lock:
        preset = copy.deepcopy(studio.preset(value['preset_id']))
        template, _ = studio.graph_for(preset)
    need(equivalent(graph_inputs(template), graph_inputs(value['expected_graph']))
         and equivalent(bindings(preset), value['expected_bindings']), 'Recipe graph or bindings changed; select the bundle again')
    return explain(preset, template, value['controls'], read_json(studio.root / 'presets/settings-kb.json'),
                   read_json(studio.root / 'models/library.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--preset', required=True)
    parser.add_argument('--controls', default='{}', help='JSON control object; no job or file is written')
    args = parser.parse_args(); root = args.repo_root.resolve()
    try:
        presets = read_json(root / 'presets/catalog.json')['presets']
        preset = next((p for p in presets if p['id'] == args.preset), None)
        need(preset is not None, 'Unknown preset')
        path = (root / preset['graph']).resolve(); need(path.is_relative_to(root), 'Graph path escapes repository')
        result = explain(preset, read_json(path), decode(args.controls), read_json(root / 'presets/settings-kb.json'),
                         read_json(root / 'models/library.json'))
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError) as exc: parser.exit(2, str(exc) + '\n')


if __name__ == '__main__': main()
