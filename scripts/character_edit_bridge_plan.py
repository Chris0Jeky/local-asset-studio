"""Pure preparation and native-binding contracts for controlled Studio edits.

Preparation verifies files and writes a new local handoff; it makes no HTTP calls.
"""
from __future__ import annotations
import copy
from pathlib import Path
from PIL import Image
from scripts.character_edit_bridge_io import (
    HEX, canonical, digest, hashed, decode, read, relative, local, bytes_of,
    artifact, save_new, image_info, require,
)
ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_REFERENCE_ROLES = ('costume', 'style', 'pose')


def preset_contract(preset):
    """Ignore server-derived fields; pin the selected authored catalog entry."""
    require(isinstance(preset, dict) and preset.get('id') in ('qwen-2ref', 'qwen-3ref'), 'Unsupported native preset')
    return copy.deepcopy({k:v for k,v in preset.items() if k not in ('defaults', 'runtime_block', 'missing_loras', 'continuation_capability')})


def compile_instruction(changes):
    instruction = '\n'.join(c['instruction'] for c in changes)
    prompt = (instruction + '\nReturn one edited image of the current source crop (Picture 1), at the same framing and scale. '
              'Keep identity from the identity reference; do not copy its pose or background. '
              'Preserve details not requested to change. Do not add text or panels.')
    require(0 < len(prompt) <= 8000, 'Combined brief exceeds the Studio limit of 8000 characters; nothing is truncated')
    return prompt


def projected_graph(template, preset, request):
    """Independent bounded projection for the supported Qwen graphs, not a runner.

    Verify native preview pixels/roles against the *prepared* bindings. A catalog
    swap during the HTTP calls must not become its own self-consistent baseline.
    Unknown native rewrites fail comparison rather than being silently trusted.
    """
    graph=copy.deepcopy(template)
    def bind(binding, value):
        require(isinstance(binding,list) and len(binding)==2, 'Invalid pinned control binding')
        node,field=map(str,binding)
        require(node in graph and field in graph[node].get('inputs',{}), 'Pinned binding absent from template')
        graph[node]['inputs'][field]=copy.deepcopy(value)
    for name,value in request['controls'].items():
        require(name in ('positive','seed','width','height'), 'Unsupported projected control')
        bindings=([preset[name]] if preset.get(name) else [])+preset.get('bindings_extra',{}).get(name,[])
        require(bool(bindings),'Pinned control is unavailable')
        for binding in bindings: bind(binding,value)
    slots=preset.get('reference_slots',[]); refs=request['references']
    require(len(slots)==len(refs), 'Pinned reference count differs')
    for slot,ref in zip(slots,refs): bind(slot['binding'],ref['file'])
    guidance='\n'.join(f"Picture {i+1} — {r['role']}: use {r['contribution'].strip() or 'the assigned visual role'}. Avoid transferring: {r['avoid'].strip() or 'unrequested details'}." for i,r in enumerate(refs))
    bind(preset['positive'],guidance+'\n\nRequested result:\n'+request['controls']['positive'])
    return graph


def prepare(workspace, plan_name, output, seeds, *, repo=ROOT, max_seconds=1800, campaign=None):
    """Compile a local, reviewed edit to explicit Qwen reference slots. No HTTP."""
    from scripts import character_edit as edit, character_edit_pixels as pixels
    from scripts.character_study import validate_canon, verify_artifact
    root = Path(workspace).resolve(strict=True); plan_path = local(root, plan_name)
    plan = read(plan_path); edit.check_plan(plan)
    require(plan['intent']['operation'] in ('anatomy-repair', 'costume-change', 'local-repaint'),
            'This bridge currently supports single-actor local edits, not scene/interaction generation')
    require(len(plan['document']['actors']) == 1 and len(plan['targets']) == 1,
            'Multi-actor conditioning needs a separate native bridge; no actor references will be dropped')
    require('qwen-edit-local' in plan['candidate_routes'], 'Qwen is excluded by this edit policy')
    require(canonical(plan['catalog']) == canonical(read(Path(repo)/'research/character-consistency/edit-routes.json')),
            'Route evidence changed; recompile the edit plan')
    require(isinstance(seeds, list) and 1 <= len(seeds) <= 4 and all(type(s) is int and 0 <= s <= 2**63-1 for s in seeds)
            and len(set(seeds)) == len(seeds), 'Use one to four distinct integer seeds')
    budget = plan['intent']['budget']
    require(1 <= budget['max_candidates'] <= 16 and len(seeds) + budget['max_repairs'] <= budget['max_candidates'],
            'Primary candidates and reserved repairs must fit the existing Production cap (16)')
    require(type(max_seconds) is int and 60 <= max_seconds <= 14400, 'Invalid time budget')
    campaign_value = None
    if campaign is not None:
        from scripts.character_edit_campaign import validate
        campaign_value = validate(read(local(root, campaign)))
        require(campaign_value['budget_owner'] == plan['budget_owner'], 'Campaign budget owner differs from the edit plan')
        require(budget['max_candidates'] <= campaign_value['max_generation_attempts'], 'Edit allowance exceeds the campaign cap')
    actor = plan['document']['actors'][0]; refs = actor['references']
    require(1 <= len(refs) <= 2 and sum(r['role'] == 'identity' for r in refs) == 1,
            'Use exactly one identity and at most one other reference; this bridge never truncates references')
    require(all(r['role'] == 'identity' or r['role'] in OPTIONAL_REFERENCE_ROLES for r in refs),
            'The optional reference must be costume, style or pose; composition is reserved for the source crop')
    canon = validate_canon(read(verify_artifact(root, actor['canon'])))
    require(canon['approval']['state'] == 'approved', 'An approved canon attestation is required; no owner decision is inferred')
    identity = next(r for r in refs if r['role'] == 'identity')
    require(any(r['role'] == 'identity' and r['sha256'] == identity['image']['sha256'] for r in canon['references']),
            'Actor identity image is not an identity reference of its approved canon')
    prompt = compile_instruction(plan['intent']['changes'])
    source, mask, protection = pixels._inputs(root, plan)
    crop = source.crop(tuple(plan['intent']['context_box'])).convert('RGBA')
    require(crop.getchannel('A').getextrema() == (255, 255),
            'Transparent source crops need an explicit matting/alpha contract; this bridge does not invent one')
    require(not source.info.get('icc_profile'), 'Normalize source ICC explicitly before this neural bridge')
    refs = sorted(refs, key=lambda r: r['role'] != 'identity')
    for r in refs:
        image_info(bytes_of(root, r['image']))
        require(len('; '.join(r['take'])) <= 1500 and len('; '.join(r['ignore'])) <= 1500,
                'Reference guidance exceeds native limit; nothing is truncated')
    expected_preset = f'qwen-{len(refs)+1}ref'
    cat = read(Path(repo)/'presets/catalog.json')
    preset = next((p for p in cat['presets'] if p['id'] == expected_preset), None)
    require(preset is not None and len(preset.get('reference_slots', [])) == len(refs)+1, 'Matching native Qwen preset missing')
    template_path = Path(repo)/preset['graph']
    require(template_path.resolve().is_relative_to((Path(repo)/'workflows/api').resolve()), 'Unexpected native template location')
    template = template_path.read_bytes(); graph = decode(template)
    require(sum(n.get('class_type') == 'LoadImage' for n in graph.values()) == len(refs)+1, 'Unexpected native reference count')
    # Staging is local and exclusive; an incomplete folder is preserved for inspection.
    target = local(root, output, exists=False)
    require(not target.exists() and not target.is_symlink(), 'Choose a new handoff directory')
    target.mkdir(parents=True)
    prepared_name = output + '/prepared'; bundle = pixels.prepare(root, plan, prepared_name)
    context = pixels.png(target/'prepared/context.png').convert('RGBA')
    w, h = context.size
    # The canvas is now an explicit latent bound to width/height, so the padded crop must land on the
    # recipe's own dimension grid. Fail here rather than resampling the candidate afterwards.
    low, high = preset.get('dimension_limits', [64, 1536]); grid = preset.get('dimension_multiple', 8)
    require(low <= w <= high and low <= h <= high and w % grid == 0 and h % grid == 0
            and w*h <= preset.get('max_pixels', 1024*1024),
            f'Crop does not fit native Qwen dimensions ({low}-{high}, multiples of {grid}); no silent resampling')
    # Only alignment padding can be transparent here. Its explicit model matte is black.
    rgb = Image.new('RGB', context.size, (0, 0, 0)); rgb.paste(context, mask=context.getchannel('A'))
    with (target/'model-context.png').open('xb') as stream: rgb.save(stream, format='PNG')
    specs = [{'image': artifact(root, output+'/model-context.png'), 'role': 'composition',
              'contribution': 'Current source crop, camera, pose and surrounding context. Apply only the requested change.',
              'avoid': 'Unrequested redesign, labels or additional figures.'}]
    for r in refs:
        specs.append({'image': copy.deepcopy(r['image']), 'role': r['role'],
                      'contribution': '; '.join(r['take']), 'avoid': '; '.join(r['ignore'])})
    originals = [plan['document']['source'], actor['canon'], plan['intent']['edit_mask']]
    if plan['intent']['protect_mask']: originals.append(plan['intent']['protect_mask'])
    originals += [r['image'] for r in refs]
    for r in canon['references']:
        ref = {'path': r['path'], 'sha256': r['sha256']}; bytes_of(root, ref); originals.append(ref)
    originals += [artifact(root, plan_name), artifact(root, prepared_name+'/bundle.json'),
                  artifact(root, prepared_name+'/context.png'), artifact(root, prepared_name+'/edit-mask.png')]
    handoff = {'schema_version': 1, 'kind': 'character_edit_studio_handoff', 'plan': artifact(root, plan_name),
        'edit_plan_sha256': plan['plan_sha256'], 'document_sha256': plan['intent']['document_sha256'],
        'bundle': prepared_name, 'bundle_sha256': bundle['bundle_sha256'], 'references': specs,
        'originals': list({r['path']: r for r in originals}.values()), 'size': [w, h], 'seeds': seeds,
        'preset_id': expected_preset, 'template_sha256': digest(template),
        'native_preset': preset_contract(preset), 'preset_sha256': hashed(preset_contract(preset)), 'positive': prompt,
        'max_candidates': budget['max_candidates'], 'reserved_repairs': budget['max_repairs'],
        'max_seconds': max_seconds, 'budget_owner': plan['budget_owner'],
        'policy': next(r for r in plan['route_reports'] if r['route_id'] == 'qwen-edit-local'),
        'scope': 'One actor; semantic reference conditioning; write mask applied after generation, not sent as a native pose/inpaint control.',
        'context_conversion': 'Opaque source crop; zero-fill alignment padding explicitly matted to black RGB without resampling.',
        'submits_generation': False}
    if campaign_value is not None:
        handoff.update(schema_version=2, campaign=artifact(root,campaign),
                       campaign_id=campaign_value['campaign_id'], campaign_sha256=campaign_value['campaign_sha256'])
    handoff['sha256'] = hashed(handoff); save_new(target/'handoff.json', handoff)
    return handoff


def validate_handoff_contract(value, plan=None, campaign=None):
    """Validate embedded JSON only; never resolve client workspace paths."""
    require(isinstance(value, dict) and value.get('kind') == 'character_edit_studio_handoff'
            and type(value.get('schema_version')) is int and value['schema_version'] in (1,2), 'Invalid handoff')
    require(value.get('sha256') == hashed({k: v for k, v in value.items() if k != 'sha256'}), 'Handoff hash mismatch')
    require(all(isinstance(value.get(k), str) and HEX.fullmatch(value[k]) for k in ('edit_plan_sha256','document_sha256','bundle_sha256')), 'Invalid identity digest')
    relative(value['bundle'])
    require(value['submits_generation'] is False and value['policy']['eligible_by_preference'] is True, 'Invalid handoff claim/policy')
    require(value['preset_id'] in ('qwen-2ref', 'qwen-3ref') and HEX.fullmatch(value['template_sha256']), 'Unsupported native profile')
    require(canonical(preset_contract(value['native_preset']))==canonical(value['native_preset'])
            and value['native_preset']['id']==value['preset_id'] and hashed(value['native_preset'])==value['preset_sha256'], 'Native preset contract hash mismatch')
    refs = value['references']
    require(isinstance(refs, list) and len(refs) == int(value['preset_id'][5])
            and all(isinstance(r, dict) for r in refs) and refs[0].get('role') == 'composition', 'Wrong reference projection')
    require(refs[1].get('role') == 'identity', 'The second binding must be the identity reference')
    require(len(refs) == 2 or refs[2].get('role') in OPTIONAL_REFERENCE_ROLES,
            'The optional reference must be costume, style or pose; composition is reserved for the source crop')
    seeds = value['seeds']
    require(isinstance(seeds, list) and 1 <= len(seeds) <= 4 and all(type(s) is int and 0 <= s <= 2**63-1 for s in seeds)
            and len(set(seeds)) == len(seeds), 'Invalid seed budget')
    require(type(value['max_candidates']) is int and 1 <= value['max_candidates'] <= 16
            and type(value['reserved_repairs']) is int and 0 <= value['reserved_repairs'] <= 3
            and len(seeds)+value['reserved_repairs'] <= value['max_candidates'], 'Invalid candidate allowance')
    require(type(value['max_seconds']) is int and 60 <= value['max_seconds'] <= 14400, 'Invalid time budget')
    require(isinstance(value['positive'], str) and 0 < len(value['positive']) <= 8000, 'Invalid compiled brief')
    for ref in [value['plan'], *value['originals'], *(r['image'] for r in refs)]:
        require(isinstance(ref,dict) and set(ref)=={'path','sha256'}
                and isinstance(ref['sha256'],str) and HEX.fullmatch(ref['sha256']), 'Invalid artifact descriptor')
        relative(ref['path'])
    for ref in refs:
        require(isinstance(ref['contribution'], str) and len(ref['contribution']) <= 1500
                and isinstance(ref['avoid'], str) and len(ref['avoid']) <= 1500, 'Invalid reference guidance')
    w,h=value['size']; require(type(w) is int and type(h) is int and 64<=w<=1536 and 64<=h<=1536 and w%8==h%8==0 and w*h<=1024**2, 'Invalid native crop size')
    if value['schema_version']==2:
        from scripts import character_edit as edit, character_edit_campaign as campaigns
        edit.check_plan(plan); campaign=campaigns.validate(campaign)
        require(set(value['campaign'])=={'path','sha256'} and isinstance(value['campaign']['sha256'],str)
                and HEX.fullmatch(value['campaign']['sha256']), 'Invalid campaign artifact')
        relative(value['campaign']['path'])
        require(value['campaign_id']==campaign['campaign_id'] and value['campaign_sha256']==campaign['campaign_sha256'], 'Campaign identity differs')
        require(value['edit_plan_sha256']==plan['plan_sha256'] and value['document_sha256']==plan['intent']['document_sha256'], 'Handoff document/plan identity differs')
        require(value['budget_owner']==plan['budget_owner']==campaign['budget_owner'], 'Handoff budget owner differs')
        require(value['max_candidates']==plan['intent']['budget']['max_candidates']
                and value['reserved_repairs']==plan['intent']['budget']['max_repairs']
                and value['max_candidates']<=campaign['max_generation_attempts'], 'Handoff candidate allowance differs')
        require(len(plan['document']['actors'])==len(plan['targets'])==1
                and plan['intent']['operation'] in ('anatomy-repair','costume-change','local-repaint')
                and 'qwen-edit-local' in plan['candidate_routes'], 'Unsupported campaign edit plan')
        expected_policy=next(r for r in plan['route_reports'] if r['route_id']=='qwen-edit-local')
        require(canonical(value['policy'])==canonical(expected_policy)
                and value['positive']==compile_instruction(plan['intent']['changes']), 'Handoff policy/instruction differs from the edit plan')
        actor_refs=sorted(plan['document']['actors'][0]['references'],key=lambda r:r['role']!='identity')
        require(len(actor_refs)+1==len(refs), 'Handoff actor reference count differs')
        for actual,expected in zip(refs[1:],actor_refs):
            require(actual=={'image':expected['image'],'role':expected['role'],
                             'contribution':'; '.join(expected['take']),'avoid':'; '.join(expected['ignore'])},
                    'Handoff actor reference differs from the edit plan')
    return value


def validate_handoff(root, value):
    plan=campaign=None
    if isinstance(value,dict) and value.get('schema_version')==2:
        plan=decode(bytes_of(root,value['plan'])); campaign=decode(bytes_of(root,value['campaign']))
    validate_handoff_contract(value,plan,campaign)
    for ref in value['originals']: bytes_of(root, ref)
    bytes_of(root, value['plan'])
    for index,ref in enumerate(value['references']):
        im = image_info(bytes_of(root, ref['image']))
        if index==0: require(list(im.size) == value['size'] and im.getchannel('A').getextrema() == (255,255), 'Model context changed')
    return value
