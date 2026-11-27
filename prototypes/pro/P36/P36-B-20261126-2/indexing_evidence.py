"""Deterministic software proof of real Studio output-index provenance binding.

The baseline is only the former raw stored-source/output dictionary equality,
not a replay of the former authority implementation. All records and media are
synthetic fixtures; this summary makes no generation or owner art-review claim.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pipeline as p
from test_studio_authority import IndexedOutputAuthorityTests


def _capture(case, context, name):
    report = case.capture(context)
    return {'name': name, 'current_capture_passed': report['passed'],
            'blocker_codes': sorted({row['code'] for row in report['blockers']})}


def prove_indexing(out: Path) -> dict:
    """Create ten disjoint runtime fixtures and return stable names/results only."""
    out = Path(out).absolute()
    runtime = p.REPO_ROOT / '.runtime'
    p.require(out.resolve().is_relative_to(runtime.resolve()) and out != runtime,
              'Indexing proof must remain under repository .runtime')
    p.safe_relative(out.relative_to(runtime).as_posix())
    p.require(not any(p.linked(path) for path in (out, *out.parents)), 'Linked proof output refused')
    p.require(not out.exists() or out.is_dir() and not any(out.iterdir()), 'Proof output must be new or empty')
    out.mkdir(parents=True, exist_ok=True)

    # setUp would allocate a separate TemporaryDirectory. The caller instead
    # owns every fixture beneath the explicit output directory supplied here.
    IndexedOutputAuthorityTests.setUpClass()
    case = IndexedOutputAuthorityTests('test_actual_generated_indexed_output_has_current_authority')
    case.root, case.counter = out, 0
    controls = []
    for name, options in (
        ('generated_normal', {}),
        ('generated_without_advisory', {'advise': False}),
        ('generated_quiet_wall', {'quiet_wall': True}),
        ('imported_image', {'operation': 'asset.import'}),
    ):
        context = case.indexed(**options)
        asset = context['workspace'].get(context['asset_id'])
        raw_equal = asset['source'] == context['job']['outputs'][asset['output_index']]
        row = _capture(case, context, name)
        row['raw_equality_baseline_matches'] = raw_equal
        case.assertFalse(raw_equal, name + ': real indexing must expose the former raw-equality mismatch')
        case.assertTrue(row['current_capture_passed'], name + ': current authority must pass')
        case.assertEqual(row['blocker_codes'], [], name)
        controls.append(row)

    mutations = []
    for name in ('wrong_output_asset_id', 'changed_stored_source_filename', 'changed_uploaded_file',
                 'changed_prompt_id', 'unknown_provenance_field', 'wrong_deterministic_output_index'):
        context = case.indexed('asset.import' if name == 'changed_uploaded_file' else 'generated')
        output = context['job']['outputs'][0]
        if name == 'wrong_output_asset_id':
            output['asset_id'] = 'f' * 32
        elif name == 'changed_stored_source_filename':
            source = context['workspace'].get(context['asset_id'])['source']
            source['filename'] = 'different-stored-source.png'
            with context['workspace'].connection() as db:
                db.execute('UPDATE assets SET source=? WHERE id=?',
                           (p.canonical_bytes(source).decode(), context['asset_id']))
        elif name == 'changed_uploaded_file':
            output['uploaded_file'] = 'other-upload.png'
        elif name == 'changed_prompt_id':
            output['prompt_id'] = 'another-prompt'
            # Keep the settled-job gate valid; rejection must come from the
            # changed output provenance, not an incomplete prompt inventory.
            context['job']['prompt_ids'] = ['another-prompt']
            context['job']['submissions'][0]['prompt_id'] = 'another-prompt'
        elif name == 'unknown_provenance_field':
            output['new_meaningful_field'] = 'unrecorded-source'
        else:
            duplicate = copy.deepcopy(output)
            duplicate.pop('asset_id')
            context['job']['outputs'].append(duplicate)
            with context['workspace'].connection() as db:
                db.execute('UPDATE assets SET output_index=1 WHERE id=?', (context['asset_id'],))
        # Refresh the explicit state digest so stale-file rejection cannot
        # accidentally make a provenance mutation appear covered.
        case.save_job(context)
        row = _capture(case, context, name)
        case.assertFalse(row['current_capture_passed'], name + ': changed provenance must fail')
        case.assertEqual(row['blocker_codes'], ['job_output_unbound'], name)
        mutations.append(row)

    return {'controls': controls, 'mutations': mutations, 'counts': {
        'valid_controls': len(controls),
        'raw_equality_baseline_valid_refusals': sum(not row['raw_equality_baseline_matches'] for row in controls),
        'current_valid_passes': sum(row['current_capture_passed'] for row in controls),
        'provenance_mutations': len(mutations),
        'current_mutation_refusals': sum(not row['current_capture_passed'] for row in mutations),
    }}
