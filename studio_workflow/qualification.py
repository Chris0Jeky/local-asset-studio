"""Offline recipe qualification inputs, derived from existing owners; never runs work.

Usage: python -m studio_workflow.qualification --root . --preset anime
A successful inspection is not a qualified route, runtime preflight or permission.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

from .core import MAX_BYTES, canonical, decode, digest, need
from .guidance import bindings, resource_context
from studio_prompt.graph_provenance import inspect_graph

FORMAT = 'studio.route-qualification-inspection/v1'
MAX_ROUTES = 16
MAX_REPORT_BYTES = 8 * MAX_BYTES
FIXED_INPUTS = ('presets/catalog.json', 'models/library.json',
                'research/prompt-studio/profiles.json')
EVIDENCE_STAGES = ('source_reviewed', 'installed', 'executed', 'visually_reviewed', 'accepted')


def _snapshot(value):
    """The pure API has the same finite-JSON boundary as the file/CLI adapter."""
    try:
        return decode(canonical(value))
    except (TypeError, RecursionError, UnicodeError) as exc:
        raise ValueError('Expected bounded finite JSON') from exc


def _profiles(document, preset, graph_sha256):
    need(isinstance(document, dict) and type(document.get('schema_version')) is int
         and document['schema_version'] == 1,
         'Unknown prompt-profile document')
    rows = document.get('profiles')
    need(isinstance(rows, list) and len(rows) <= 256, 'Invalid prompt-profile list')
    seen, result = set(), []
    mapped = bindings(preset)
    for profile in rows:
        need(isinstance(profile, dict) and isinstance(profile.get('id'), str)
             and profile['id'] and profile['id'] not in seen, 'Invalid or duplicate prompt profile')
        seen.add(profile['id'])
        recipes = profile.get('recipes')
        need(isinstance(recipes, list) and all(isinstance(x, str) for x in recipes),
             'Invalid profile recipe association')
        if preset['id'] not in recipes:
            continue
        match, scope = None, 'recipe_association_only'
        if 'template_bindings' in profile:
            templates = profile['template_bindings']
            need(isinstance(templates, list) and all(isinstance(x, dict) for x in templates),
                 'Invalid profile template bindings')
            matches = [x for x in templates if x.get('preset_id') == preset['id']]
            match = False
            if len(matches) == 1:
                contract = matches[0]
                expected = contract.get('bindings')
                match = (isinstance(expected, dict) and set(expected) == {'positive', 'negative'}
                         and contract.get('graph_sha256') == graph_sha256
                         and all(mapped.get(role) == [pair] for role, pair in expected.items()))
            scope = 'exact_local_template_declaration'
        result.append({'id': profile['id'], 'profile_sha256': digest(profile), 'scope': scope,
                       'template_match': match, 'declaration': copy.deepcopy(profile)})
    return sorted(result, key=lambda x: x['id'])


def inspect_route(preset: dict, graph: dict, manifest: dict, profiles: dict) -> dict:
    """Project one catalog configuration, without installed-model or source access.

    Resource activity and graph reachability are static declarations, not tensor
    evaluation. The whole graph is retained in the identity, including disabled
    adapters and disconnected nodes. No caller-provided 'verified' flag grants
    any evidence stage or execution authority.
    """
    preset, graph, manifest, profiles = map(_snapshot, (preset, graph, manifest, profiles))
    need(isinstance(preset, dict) and isinstance(preset.get('id'), str)
         and re.fullmatch(r'[a-z][a-z0-9_-]{0,95}', preset['id']), 'Invalid preset identity')
    need(isinstance(manifest, dict) and isinstance(manifest.get('assets'), list)
         and len(manifest['assets']) <= 4096, 'Invalid model library')
    need(all(isinstance(a, dict) and isinstance(a.get('file'), str) and a['file']
             for a in manifest['assets']), 'Invalid model declaration')
    graph_report = inspect_graph(graph)
    graph_sha = graph_report['graph_sha256']
    components = resource_context(graph, manifest, preset)
    diagnostics = []
    for row in components:
        candidates = [a for a in manifest['assets'] if a.get('file') == row['file']]
        declaration = candidates[0] if row['identity'] == 'catalog_pin' else None
        if declaration is not None and not (
                isinstance(declaration.get('id'), str) and declaration['id']
                and type(declaration.get('bytes')) is int and declaration['bytes'] > 0):
            row.update(identity='invalid_catalog_pin', pin_sha256=None)
            declaration = None
        row['library_declaration'] = copy.deepcopy(declaration)
        # Ambiguity refuses resolution, not retention of the conflicting evidence.
        row['library_candidates'] = sorted(copy.deepcopy(candidates), key=canonical)
        row['activity_scope'] = 'declared_graph_inputs_not_loaded_tensors'
        if declaration is None:
            diagnostics.append({'code': 'unresolved_component_identity', 'file': row['file'],
                                'identity': row['identity']})
    components.sort(key=lambda x: x['file'])
    profile_rows = _profiles(profiles, preset, graph_sha)
    if not any(p['template_match'] is True for p in profile_rows):
        diagnostics.append({'code': 'no_matching_exact_prompt_template'})
    slots = preset.get('reference_slots', [])
    need(isinstance(slots, list) and len(slots) <= 16
         and all(isinstance(s, dict) for s in slots), 'Invalid catalog reference slots')
    mapped = bindings(preset)
    settings = []
    for control, pairs in sorted(mapped.items()):
        for node, field in pairs:
            need(node in graph and field in graph[node]['inputs'], 'Missing catalog control target')
            settings.append({'control': control, 'node': node, 'input': field,
                             'value': copy.deepcopy(graph[node]['inputs'][field]),
                             'scope': 'authored_template_default'})
    # Include selected declarations/profiles, but not unrelated library additions.
    identity = {'preset': preset, 'graph': graph, 'components': components,
                'prompt_profiles': profile_rows}
    result = {
        'format': FORMAT, 'preset_id': preset['id'], 'configuration_sha256': digest(identity),
        'preset_sha256': digest(preset), 'graph_sha256': graph_sha,
        'authority': 'repository_declarations_only', 'generation_submitted': False,
        'qualification_complete': False,
        'components': components, 'settings': settings, 'prompt_profiles': profile_rows,
        'graph_inspection': graph_report,
        'references': {
            'catalog_slots': copy.deepcopy(slots),
            'catalog_slot_count': len(slots) if 'reference_slots' in preset else None,
            'other_source_declarations': {key: copy.deepcopy(preset[key]) for key in
                                          ('reference', 'last_reference', 'requires_rgba_mask') if key in preset},
            'crop_policy_declaration': copy.deepcopy(preset.get('reference_policy')),
            'native_slot_maximum': None, 'order_sensitivity_measured': None,
            'role_leakage_measured': None, 'reference_drift_measured': None,
            'actual_source_hashes_and_transforms': None,
        },
        'runtime': {'fingerprint': None, 'loaded_component_hashes': None,
                    'custom_node_revisions': None, 'precision_verified': None,
                    'prediction_type_verified': None,
                    'node_classes_declared': sorted({n['class_type'] for n in graph.values()})},
        'evidence': {'discovered': True, **{stage: None for stage in EVIDENCE_STAGES}},
        'historical_catalog_claims': {key: copy.deepcopy(preset[key]) for key in
                                     ('verified', 'execution_status', 'execution_note', 'history') if key in preset},
        'results': {
            'hard_constraints': {'state': 'unobserved', 'findings': None},
            'visual_quality': {'state': 'unobserved', 'reviewer': None, 'findings': None},
            'acceptance': {'state': 'unobserved', 'accepted': None, 'owner_decision': None},
            'effort': {'state': 'unobserved', 'attempts': None, 'operator_seconds': None},
            'resources': {key: None for key in (
                'cold_start_seconds', 'warm_generation_seconds', 'model_switch_seconds',
                'peak_vram_bytes', 'peak_host_rss_bytes', 'peak_host_commit_bytes',
                'cleanup_seconds', 'restart_required', 'failure_class')},
        },
        'diagnostics': diagnostics,
        'warning': 'No installation, source authentication, execution, visual acceptance, licence clearance '
                   'or runtime suitability is established. Null means unobserved, not failure or zero. '
                   'Reference counts describe the catalog, not native model capacity. '
                   'Configuration identity is not an execution ticket or atomic filesystem snapshot.',
    }
    need(len(canonical(result)) <= MAX_REPORT_BYTES, 'Qualification report exceeds byte budget')
    return result


def _read(root: Path, relative: str):
    need(isinstance(relative, str) and relative and '\\' not in relative and ':' not in relative,
         'Invalid repository-relative input path')
    path = PurePosixPath(relative)
    need(not path.is_absolute() and all(p not in ('', '.', '..') for p in relative.split('/')),
         'Input path must remain within the repository')
    target = root.joinpath(*path.parts)
    for candidate in (target, *target.parents):
        if candidate == root:
            break
        need(not candidate.is_symlink() and not
             (hasattr(candidate, 'is_junction') and candidate.is_junction()), 'Linked input path refused')
    need(target.resolve().is_relative_to(root), 'Input escaped the repository')
    with target.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    value = decode(raw)
    return value, {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def inspect_repository(root: str | Path, preset_ids: list[str]) -> dict:
    """Read fixed repository metadata and explicitly selected catalog API graphs."""
    need(isinstance(preset_ids, list) and 1 <= len(preset_ids) <= MAX_ROUTES
         and all(isinstance(p, str) for p in preset_ids), 'Select 1..16 recipe IDs')
    need(len(set(preset_ids)) == len(preset_ids), 'Duplicate recipe selection')
    root = Path(root).resolve()
    inputs, identities = [], []
    for path in FIXED_INPUTS:
        value, identity = _read(root, path)
        inputs.append(value); identities.append(identity)
    catalog, manifest, profiles = inputs
    need(isinstance(catalog, dict) and isinstance(catalog.get('presets'), list), 'Invalid catalog')
    rows = catalog['presets']
    need(all(isinstance(p, dict) and isinstance(p.get('id'), str) for p in rows), 'Invalid catalog recipe')
    need(len({p['id'] for p in rows}) == len(rows), 'Duplicate catalog recipe')
    by_id = {p['id']: p for p in rows}
    need(all(pid in by_id for pid in preset_ids), 'Unknown recipe selection')
    routes = []
    graphs = {}
    for pid in preset_ids:
        preset = by_id[pid]
        graph_path = preset.get('graph')
        need(isinstance(graph_path, str) and graph_path.startswith('workflows/api/'),
             'Qualification requires a catalog-owned API graph')
        if graph_path not in graphs:
            graph, identity = _read(root, graph_path)
            graphs[graph_path] = graph; identities.append(identity)
        routes.append(inspect_route(preset, graphs[graph_path], manifest, profiles))
    report = {'format': FORMAT, 'generation_submitted': False, 'qualification_complete': False,
              'input_files': identities, 'routes': routes}
    need(len(canonical(report)) <= MAX_REPORT_BYTES, 'Qualification report exceeds byte budget')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--preset', action='append', required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_repository(args.root, args.preset)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2))
        return 0
    except (ValueError, OSError, RecursionError) as exc:
        print(json.dumps({'error': str(exc), 'generation_submitted': False,
                          'qualification_complete': False}, ensure_ascii=True))
        return 2


if __name__ == '__main__':
    sys.exit(main())
