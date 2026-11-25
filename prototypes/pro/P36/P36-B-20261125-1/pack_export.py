"""Checked, explicit draft handoff to Lumenfold pack v1; never an Unreal import."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import struct
import sys

# CLI runs keep regenerable bytecode out of the source tree.
if __name__ == '__main__':
    sys.dont_write_bytecode = True

from pipeline import (PipelineError, STAGES, REPO_ROOT, assess, canonical_bytes, decode_json,
                      digest, linked, load_json, require, validate_family,
                      verify_artifact, write_new_runtime)


def verify_family_media(family, asset_root, *, stages=None):
    """Reopen every active artifact and remeasure pixel-labelled observations.

Annotations remain assertions bound to bytes; we do not claim to measure face
geometry or authenticate who annotated or accepted it. No cached score is trusted.
"""
    from consistency import measure_regions
    from PIL import Image
    validate_family(family)
    paths, measured, seen_paths = {}, {}, {}
    for stage in STAGES:
        if stages is not None and stage not in stages: continue
        if stage not in family['heads']: continue
        receipt = family['receipts'][family['heads'][stage]]; payload = receipt['payload']
        by_sha = {}
        for artifact in payload['artifacts']:
            folded = artifact['path'].casefold()
            if folded in seen_paths:
                require(seen_paths[folded] == (artifact['path'], artifact['sha256'], artifact['bytes']),
                        'Conflicting or case-colliding artifact paths')
            seen_paths[folded] = (artifact['path'], artifact['sha256'], artifact['bytes'])
            path = verify_artifact(asset_root, artifact)
            paths[(stage, artifact['key'])] = path
            by_sha[artifact['sha256']] = (path, artifact)
            if artifact['media_type'].startswith('image/'):
                require(artifact['colour_space'] == 'srgb' and artifact['alpha'] in ('opaque', 'straight'),
                        'Unsupported image encoding: normalize to encoded sRGB with straight alpha first')
                with Image.open(path) as image:
                    require(list(image.size) == artifact['dimensions'], 'Image dimensions differ from receipt')
                    require(image.width <= 4096 and image.height <= 4096 and image.width * image.height <= 16*1024*1024,
                            'Identity image exceeds decode bounds')
                    require(not image.info.get('icc_profile'), 'Unsupported embedded colour encoding profile')
                    require(getattr(image, 'n_frames', 1) == 1, 'Animated sheet unsupported')
                    image.verify()
        for view in payload['identity']['sheet']['views']:
            required_names = family['policy']['required'][stage].get(view['id'])
            if required_names is None: continue  # Explicit diagnostics do not satisfy or change required gates.
            require(view['media_sha256'] in by_sha, 'Unbound identity view')
            path, artifact = by_sha[view['media_sha256']]
            features = view['features']
            pixel_names = [name for name, record in features.items()
                           if record.get('provenance') == 'pixel_measured']
            if family['mode'] == 'production':
                require(all(r.get('provenance') != 'fixture_truth' for r in features.values()),
                        'Synthetic annotations cannot qualify production media')
                for name in required_names:
                    if family['policy']['features'][name]['kind'] == 'rgb':
                        require(features[name].get('provenance') == 'pixel_measured',
                                'Production colour evidence must be measured from pixels')
            if pixel_names:
                regions = family['policy'].get('regions', {}).get(stage, {}).get(view['id'], {})
                require(all(name in regions for name in pixel_names), 'Frozen policy lacks measurement regions')
                actual = measure_regions(path, artifact['sha256'], {n: regions[n] for n in pixel_names})
                for name in pixel_names:
                    require(actual[name]['value'] == features[name]['value'],
                            'Stored pixel measurement differs from media: ' + stage + '/' + view['id'] + '/' + name)
                    if stage == 'concept':
                        measurement = (actual[name]['value'], regions[name])
                        old = measured.get((artifact['sha256'], name))
                        require(old is None or old == measurement, 'Ambiguous concept measurement regions')
                        measured[(artifact['sha256'], name)] = measurement
        if family['mode'] == 'production':
            for dimension in ('generation', 'inspection', 'acceptance', 'licence'):
                require(not receipt[dimension].get('evidence_ref', '').startswith('fixture:'),
                        'Synthetic attestations cannot qualify production media')
    if 'concept' in family['heads'] and (stages is None or 'concept' in stages):
        anchor = family['receipts'][family['heads']['concept']]['payload']['identity']['anchor_features']
        for name, record in anchor.items():
            if family['mode'] == 'production' and family['policy']['features'][name]['kind'] == 'rgb':
                require(record['provenance'] == 'pixel_measured', 'Production colour anchor must be pixel measured')
            if record['provenance'] == 'pixel_measured':
                measured_anchor = measured.get((record['media_sha256'], name))
                require(measured_anchor is not None and measured_anchor[0] == record['value'],
                        'Anchor pixel measurement was not reproduced')
            elif family['mode'] == 'production':
                require(record['provenance'] != 'fixture_truth', 'Synthetic anchor cannot qualify production media')
    return paths


def _model_format(artifact, path):
    suffix = path.suffix.lower()
    require(suffix in ('.glb', '.vrm', '.fbx'), 'Expected GLB, VRM or FBX engine model')
    if suffix in ('.glb', '.vrm'):
        with path.open('rb') as handle: header = handle.read(12)
        require(len(header) == 12 and header[:4] == b'glTF', 'Invalid GLB/VRM header')
        version, length = struct.unpack('<II', header[4:])
        require(version == 2 and length == artifact['bytes'], 'Invalid GLB/VRM version or length')
        if suffix == '.vrm':
            with path.open('rb') as handle:
                handle.seek(12); chunk_header = handle.read(8)
                require(len(chunk_header) == 8, 'Missing VRM extension JSON')
                size, kind = struct.unpack('<II', chunk_header)
                require(kind == 0x4e4f534a and 0 < size <= 2*1024*1024 and size <= length-20,
                        'Missing or oversized VRM extension JSON')
                document = decode_json(handle.read(size))
            extensions = document.get('extensions', {}) if type(document) is dict else {}
            require(type(extensions) is dict and any(type(extensions.get(k)) is dict
                    for k in ('VRM', 'VRMC_vrm')), 'A renamed GLB is missing a VRM extension')
    else:
        with path.open('rb') as handle: header = handle.read(80)
        require(header.startswith(b'Kaydara FBX Binary') or b'FBX' in header,
                'Unrecognized FBX header; native qualification is still required')
    return {'.glb': 'glb', '.vrm': 'vrm', '.fbx': 'fbx'}[suffix]


def build_manifest(family, asset_root, metadata, *, release=False, intended_use=None):
    validate_family(family)
    require(type(release) is bool, 'Release gate must be boolean')
    require(not release or family['mode'] == 'production', 'A synthetic family is never releasable')
    gate = assess(family, 'unreal', require_licence=release, intended_use=intended_use)
    require(gate['passed'], 'Export blocked: ' + ', '.join(b['code'] for b in gate['blockers']), 'export_blocked')
    require(type(metadata) is dict and metadata.get('id') == family['character_id'], 'Character metadata mismatch')
    required = ('display_name', 'profile', 'style', 'voice', 'animations', 'versus')
    require(all(k in metadata for k in required), 'Explicit Lumenfold character metadata required')
    allowed = {'id', *required, 'notes', 'combat', 'skeleton', 'ue', 'expressions'}
    require(set(metadata) <= allowed, 'Unknown metadata or legacy pack overlay refused')
    skeleton = metadata.get('skeleton')
    require(skeleton in ('vrm-humanoid', 'ue-mannequin', 'mixamo', 'custom', 'none'), 'Explicit skeleton required')
    if family['mode'] == 'production': require(skeleton != 'none', 'Production character requires a rig')
    paths = verify_family_media(family, asset_root)
    files, file_identity, key_by_asset, image_metadata = {}, {}, {}, {}
    model_candidates = []
    for stage in STAGES:
        receipt = family['receipts'][family['heads'][stage]]
        for artifact in receipt['payload']['artifacts']:
            identity = (artifact['path'], artifact['sha256'], artifact['bytes'])
            key = file_identity.get(identity)
            if key is None:
                key = stage + '-' + artifact['key']
                require(key not in files, 'File key collision')
                licence = artifact['licence']
                files[key] = {'path': artifact['path'], 'sha256': artifact['sha256'], 'bytes': artifact['bytes'],
                              'source': artifact.get('source', 'studio-workspace:' + family['workspace_id'] +
                                                     '/asset/' + artifact['asset_id']),
                              'licence': licence['name'], 'commercial': licence['commercial']}
                if licence.get('restrictions'): files[key]['restrictions'] = licence['restrictions']
                file_identity[identity] = key
                if artifact['media_type'].startswith('image/'):
                    image_metadata[key] = {k: artifact[k] for k in ('dimensions', 'colour_space', 'alpha')}
            key_by_asset[(stage, artifact['key'])] = key
            if artifact['role'] == 'engine-model' and stage == 'toon':
                model_candidates.append((key, artifact, paths[(stage, artifact['key'])]))
    require(len(model_candidates) == 1, 'Exactly one selected toon-stage engine model is required')
    key, model, path = model_candidates[0]; format_name = _model_format(model, path)
    models = {format_name: {'file': key}, 'skeleton': skeleton,
              'ue': {**copy.deepcopy(metadata.get('ue', {})), 'from': format_name}}
    # Joined topology, retargeting and shader behavior are not inferred from a GLB header.
    toon = family['receipts'][family['heads']['toon']]['payload']['artifacts']
    material = [a for a in toon if a['role'] == 'toon-materials']
    require(len(material) <= 1, 'Ambiguous toon material sidecar')
    if material:
        models['toon'] = {'file': key_by_asset[('toon', material[0]['key'])]}
    concept = family['receipts'][family['heads']['concept']]['payload']['artifacts']
    portrait = next((a for a in concept if a['media_type'].startswith('image/')), None)
    require(portrait is not None, 'A concept portrait is required')
    pack = {'schema': 'lumenfold.pack/1', 'id': family['character_id'], 'status': 'draft',
            **{k: copy.deepcopy(metadata[k]) for k in required}, 'files': files, 'models': models,
            'expressions': copy.deepcopy(metadata.get('expressions', {})),
            'portraits': {'neutral': {'file': key_by_asset[('concept', portrait['key'])]}},
            'x-studio-character-pipeline': {
                'schema': 'las.character-pack/1', 'family_sha256': digest(family),
                'concept_receipt': family['heads']['concept'], 'stage_receipts': dict(family['heads']),
                'mode': family['mode'], 'evidence_state': 'implemented',
                'family_sidecar': 'family.json', 'handoff_sidecar': 'handoff.json',
                'generation_submitted': False, 'identity_gate': 'passed',
                'perceptual_identity_verified': False, 'media_bytes_verified': True,
                'release_clearance_checked': release, 'intended_use': intended_use,
                'unreal_import': 'planned', 'image_metadata': image_metadata}}
    for key in ('notes', 'combat'):
        if key in metadata: pack[key] = copy.deepcopy(metadata[key])
    canonical_bytes(pack)
    try:
        import jsonschema
    except ImportError as exc:
        raise PipelineError('Pack schema validation requires jsonschema in the offline Python environment') from exc
    schema_path = Path(__file__).with_name('lumenfold.pack.schema.json')
    schema = load_json(schema_path)
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(pack), key=lambda e: str(list(e.path)))
    require(not errors, 'Lumenfold pack schema rejected output: ' +
            '; '.join('/'.join(map(str, e.path)) + ': ' + e.message for e in errors[:8]))
    # The upstream validator also checks every recursively named `file` reference.
    def check_refs(node):
        if type(node) is dict:
            for name, value in node.items():
                if name == 'file' and type(value) is str: require(value in files, 'Dangling pack file reference')
                elif name != 'files': check_refs(value)
        elif type(node) is list:
            for value in node: check_refs(value)
    check_refs(pack)
    return pack


def export_bundle(family, asset_root, metadata, out, *, release=False, intended_use=None):
    out = Path(out).absolute(); runtime = REPO_ROOT / '.runtime'
    require(out.resolve().is_relative_to(runtime.resolve()), 'Output must be under repository .runtime/')
    require(not any(linked(p) for p in (out, *out.parents)), 'Linked output path refused')
    require(not out.exists(), 'Export destination exists; inspect it before a new explicit export')
    # All validation happens before the destination is created. The completion receipt
    # is written last; interrupted bundles are visibly incomplete and are never retried.
    pack = build_manifest(family, asset_root, metadata, release=release, intended_use=intended_use)
    handoff = {'schema': 'las.character-handoff/1', 'family_sha256': digest(family),
               'pack_sha256': digest(pack), 'concept_receipt': family['heads']['concept'],
               'mode': family['mode'], 'evidence_state': 'implemented', 'unreal_import': 'planned',
               'generation_submitted': False, 'asset_copy_performed': False,
               'assets_verified_at_export': True, 'revalidate_at_import': True}
    try: out.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc: raise PipelineError('Export destination exists') from exc
    write_new_runtime(out / 'family.json', family)
    write_new_runtime(out / 'pack.json', pack)
    write_new_runtime(out / 'handoff.json', handoff)
    return handoff


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family', required=True); parser.add_argument('--asset-root', required=True)
    parser.add_argument('--metadata', required=True); parser.add_argument('--out', required=True)
    parser.add_argument('--release', action='store_true'); parser.add_argument('--intended-use')
    args = parser.parse_args(argv)
    try:
        result = export_bundle(load_json(args.family), args.asset_root, load_json(args.metadata), args.out,
                               release=args.release, intended_use=args.intended_use)
        sys.stdout.buffer.write(canonical_bytes(result)); return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': getattr(exc, 'code', 'invalid_input'), 'message': str(exc),
                          'generation_submitted': False}), file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
