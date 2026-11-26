"""Guard a draft export without authorizing Lumenfold's current direct importer.

The retained upstream exporter deduplicates artifact path/hash/size before copying
provenance into pack v1. This wrapper refuses conflicting facts before that loss
can occur. It reads source bytes through the upstream gate and writes no files.

The consumer declaration is a proposed admission contract, not an implemented
Lumenfold gate. Current import_packs.py does not enforce it and must not receive
these drafts directly. Studio's caller must separately check live authority.
"""
from __future__ import annotations

from pack_export import build_manifest as _build_manifest
from pipeline import STAGES, canonical_bytes, digest, require, validate_family


CONSUMER_REVISION = '19d86763944e842cbce6a3b6ae13f7abc1464b37'


def _check_reused_artifact_facts(family):
    """Compare all facts for repeated active paths, without merging declarations.

An explicit source is compared as written. An omitted source uses the exact
Workspace/asset locator that the upstream exporter would emit. The complete
licence object is compared, including the terms source and any extra recorded
facts, rather than only the three fields projected into pack v1.
"""
    seen = {}
    for stage in STAGES:
        if stage not in family['heads']:
            continue
        receipt = family['receipts'][family['heads'][stage]]
        for artifact in receipt['payload']['artifacts']:
            identity = (artifact['path'], artifact['sha256'], artifact['bytes'])
            source = artifact.get('source', 'studio-workspace:' + family['workspace_id'] +
                                  '/asset/' + artifact['asset_id'])
            require(type(source) is str and bool(source), 'Artifact source must be a nonempty string')
            facts = canonical_bytes({'source': source, 'licence': artifact['licence']})
            folded = artifact['path'].casefold()
            previous = seen.get(folded)
            if previous is not None:
                prior_identity, prior_facts, prior_stage = previous
                require(identity == prior_identity,
                        'Reused artifact path has conflicting bytes or case: ' + artifact['path'],
                        'artifact_content_conflict')
                require(facts == prior_facts,
                        'Reused artifact has conflicting provenance or licence facts: ' +
                        artifact['path'] + ' (' + prior_stage + ', ' + stage + ')',
                        'artifact_provenance_conflict')
            else:
                seen[folded] = (identity, facts, stage)


def build_guarded_manifest(family, asset_root, metadata, *, release=False, intended_use=None):
    """Return a pack-v1 draft, refusing lossy reuse before upstream deduplication.

All upstream identity, ancestry, byte-integrity and intended-use checks still
apply. Neither a schema pass nor this declaration proves native compatibility,
authenticates owner decisions, or permits use of the current direct importer.
"""
    validate_family(family)
    _check_reused_artifact_facts(family)
    pack = _build_manifest(family, asset_root, metadata, release=release, intended_use=intended_use)
    require(pack['status'] == 'draft', 'Guarded exports must remain draft')
    extension = pack['x-studio-character-pipeline']
    require(extension['family_sha256'] == digest(family), 'Exporter changed the source family binding')
    require(extension['concept_receipt'] == family['heads']['concept'] and
            extension['stage_receipts'] == family['heads'], 'Exporter changed the selected ancestry')
    extension['consumer_admission'] = {
        'schema': 'las.lumenfold-consumer-admission/1',
        'state': 'staged_validation_required',
        'pack_status': 'draft',
        'current_direct_import_allowed': False,
        'staged_validator_required': True,
        'native_import_state': 'not_executed_by_exporter',
        'joined_topology': 'unverified',
        'rig_compatibility': 'unverified',
        'source_family_sha256': digest(family),
        'source_metadata_sha256': digest(metadata),
        'provenance_reuse_policy': 'exact_source_and_complete_licence_facts',
        'inspected_consumer': {
            'repository': 'Chris0Jeky/lumenfold',
            'revision': CONSUMER_REVISION,
            'entrypoint': 'games/world3d/tools/import_packs.py',
        },
        'required_checks': [
            'current_workspace_authority_and_selected_ancestry',
            'pack_schema_and_actual_source_bytes',
            'decoded_model_rig_expression_and_material_compatibility',
            'candidate_staging_and_transactional_promotion',
            'separate_native_receipt_and_owner_acceptance',
        ],
    }
    canonical_bytes(pack)
    return pack
