"""Synthetic dispatch contexts using real Workspace and Production preparation APIs."""
from __future__ import annotations

from pathlib import Path

import authority_fixtures
from admission_fixtures import semantic_inputs
import pipeline as p


def make_dispatch_case(root):
    root = Path(root)
    p.require(root.resolve().is_relative_to((p.REPO_ROOT / '.runtime').resolve()),
              'Dispatch fixtures belong under .runtime/')
    from production_intent_fixtures import make_production_case
    context = authority_fixtures.make_workspace(root / 'authority', through='concept')
    context['semantic_policy'], context['annotations'] = semantic_inputs(context)
    prepared = make_production_case(root / 'studio', experiments=context['experiments'],
                                   family_id=context['family']['family_id'], stage='turnaround')
    context.update(intent=prepared['intent'], studio_root=prepared['studio_root'],
                   production=prepared, ledger_path=root / 'attempts.sqlite3',
                   simulation_path=root / 'simulated-comfy.sqlite3')
    return context


def parameters(context):
    return {key: context[key] for key in ('experiments', 'family', 'binding', 'asset_root',
                                          'semantic_policy', 'annotations', 'intent', 'studio_root')}


def write_context(path, context):
    values = parameters(context)
    values = {key: str(value) if isinstance(value, Path) else value for key, value in values.items()}
    p.write_new_runtime(path, values)
