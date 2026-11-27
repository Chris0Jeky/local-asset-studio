"""Synthetic semantic declarations over the real-Workspace test fixture.

These fictional marks test the admission contract. They are not annotations of
actual character images, model outputs, or owner judgments.
"""
from __future__ import annotations

import copy

from consistency import policy_digest
import pipeline as p
from sheet_identity import semantic_policy_digest


def semantic_inputs(context, *, provenance='fixture_truth'):
    family, binding = context['family'], context['binding']
    root = family['receipts'][family['heads']['concept']]['payload']
    asset = next(a for a in root['artifacts'] if a['asset_id'] == binding['concept_asset_id'])
    concept = {'asset_id': asset['asset_id'], 'media_sha256': asset['sha256'],
               'receipt_digest': family['heads']['concept']}
    metric = {key: family['policy'][key] for key in ('version', 'features', 'required')}
    anchors = {
        'left-iris': {'kind': 'identity', 'value': 'amber', 'vocabulary': ['amber', 'blue']},
        'right-iris': {'kind': 'identity', 'value': 'blue', 'vocabulary': ['amber', 'blue']},
        'braid-side': {'kind': 'identity', 'value': 'subject-left',
                       'vocabulary': ['subject-left', 'subject-right']},
    }
    policy = {'version': 1, 'side_basis': 'subject_anatomical', 'concept': concept,
              'proxy_policy_digest': policy_digest(metric), 'anchors': anchors,
              'contexts': {'base': {}},
              'required': {stage: {view: {'context': 'base',
                            'anchors': ['braid-side'] if 'back' in view else list(anchors)}
                            for view in views}
                           for stage, views in family['policy']['required'].items()}}
    policy_hash = semantic_policy_digest(policy)
    annotations = {}
    for stage in p.STAGES:
        if stage not in family['heads']:
            continue
        sheet = family['receipts'][family['heads'][stage]]['payload']['identity']['sheet']
        annotation = {'version': 1, 'method': 'manual_descriptor_v1',
                      'side_basis': 'subject_anatomical', 'concept': copy.deepcopy(concept),
                      'policy_digest': policy_hash, 'views': []}
        for view in sheet['views']:
            required = policy['required'][stage][view['id']]
            annotation['views'].append({'id': view['id'], 'media_sha256': view['media_sha256'],
                'compared_to': copy.deepcopy(concept), 'context': required['context'],
                'anchors': {name: {'state': 'observed', 'value': anchors[name]['value'],
                                  'provenance': provenance} for name in required['anchors']}})
        annotations[stage] = annotation
    return policy, annotations


def manufactured_production_declarations(context):
    """Reseal synthetic media as explicit test declarations to isolate provenance.

This is an adversarial test setup, not real production evidence or acceptance.
It removes upstream fixture markers so the new semantic fixture veto, rather
than an earlier marker check, is the reason a transition refuses.
"""
    old = context['family']
    family = p.create_family(old['family_id'], old['workspace_id'], old['character_id'],
                             old['policy'], mode='production')
    binding = copy.deepcopy(context['binding'])
    for stage in p.STAGES:
        if stage not in old['heads']:
            continue
        receipt = copy.deepcopy(old['receipts'][old['heads'][stage]])
        payload = receipt['payload']
        payload['mode'] = 'production'
        payload['parents'] = {parent: family['heads'][parent] for parent in p.PARENTS[stage]}
        payload['concept_id'] = None if stage == 'concept' else family['heads']['concept']
        payload['recipe'] = {'route_id': 'test-declaration-only', 'controls': {}}
        for artifact in payload['artifacts']:
            artifact['source'] = 'test:manufactured-source-declaration'
            artifact['licence']['source'] = 'test:manufactured-terms'
        for view in payload['identity']['sheet']['views']:
            for feature in view['features'].values():
                if feature['provenance'] == 'fixture_truth':
                    feature['provenance'] = 'human_annotated'
        for feature in payload['identity'].get('anchor_features', {}).values():
            if feature['provenance'] == 'fixture_truth':
                feature['provenance'] = 'human_annotated'
        for check in payload['quality']:
            check['evidence_ref'] = 'test:manufactured-quality-declaration'
        for dimension, state, actor in [('generation', 'completed', 'test-operator'),
                                        ('inspection', 'inspected', 'test-reviewer'),
                                        ('acceptance', 'accepted', 'owner')]:
            receipt = p.attest(receipt, dimension, state, actor, 'test:manufactured-declaration')
        family = p.record_receipt(family, receipt, asset_root=context['asset_root'])
        binding['stages'][stage]['receipt_id'] = receipt['id']
    return {**context, 'family': family, 'binding': binding}
