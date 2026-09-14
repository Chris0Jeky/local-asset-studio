"""Authored navigation, not automated actions or evidence of creative acceptance."""

def step(title, detail, route, target=None):
    return dict(title=title, detail=detail, route=route, target=target)


# Stable stage IDs and read-only predicates. IDs survive copy/ordering changes;
# the target IDs remain owned by the existing feature markup, not a second router.
STAGES = {
    'first-image': [('recipe', 'recipe'), ('wording', 'prompt'), ('settings', 'manual'),
                    ('readiness', 'readiness'), ('output', 'output'), ('review', 'review')],
    'reference-edit': [('mechanism', 'reference_recipe'), ('sources', 'references'), ('wording', 'prompt'),
                       ('readiness', 'readiness'), ('output', 'output'), ('review', 'review')],
    'compare': [('baseline', 'recipe'), ('budget', 'manual'), ('inspect', 'manual'), ('decision', 'manual')],
    'scene': [('sources', 'selection'), ('scene', 'manual'), ('voice', 'manual'), ('review', 'manual')],
    'game-assets': [('target', 'manual'), ('sources', 'selection'), ('export', 'manual'), ('engine', 'manual')],
    'workflow': [('nodes', 'schema'), ('connections', 'manual'), ('check', 'graph_check'), ('save', 'saved'), ('run', 'manual')],
    'agents': [('service', 'manual'), ('prepare', 'manual'), ('approve', 'manual'), ('observe', 'manual')],
}
# Catalog IDs offered as a one-click recipe choice on a recipe/reference_recipe step.
# The coach selects through the existing Create picker; it never generates. Validated
# against presets/catalog.json by tests/test_studio_guide.py.
RECOMMENDED = {
    'first-image': ['anima-portrait', 'flux'],
    'reference-edit': ['qwen-1ref', 'qwen-3ref'],
    'compare': ['anima-portrait', 'flux'],
}


def guides():
    common = [
        step('Check readiness before running', 'Read this recipe’s model and environment requirements. A connected backend is not proof that it fits memory or has every dependency.', '/#create', '#dependencies'),
        step('Generate, then pick the run', 'Press Generate yourself when the settings look right, then choose that run below to inspect its outputs.', '/#create', '#generate'),
        step('Review, keep and reuse', 'Compare at the final intended size, then save what works to the Asset library and record what needs work. A finished render is not acceptance.', '/#assets', '#assetGrid'),
    ]
    items = [
        dict(id='first-image', title='Make my first image', summary='Idea → recipe → settings → a reviewed image.', steps=[
            step('Start from a recipe', 'Search Create by the result you want: illustration, portrait, pixel art or product. Recipes carry their own settings; model names do not.', '/#create', '#presetList'),
            step('Describe the result', 'State subject, action, setting and composition in the prompt field. Prompt Lab can propose wording; read it before you apply it.', '/#create', '#positive'),
            step('Change one control at a time', 'Start from the authored defaults and adjust size, seed or one family setting. Save a named setup once a combination works.', '/#create', '#controls'),
        ] + common),
        dict(id='reference-edit', title='Edit or preserve a character', summary='References with roles → scoped change → comparison.', steps=[
            step('Pick a reference recipe', 'Qwen Atelier 1-3 References keeps identity, pose or style from your images. Text-only recipes cannot preserve a source.', '/#create', '#presetSearch'),
            step('Assign each image a role', 'Give every reference its identity, pose or style role, or attach the single source the recipe asks for. Leave the original file unchanged.', '/#create', '#roleReferences'),
            step('Write the change and invariants', 'Describe what changes and what must stay the same. For mask recipes, check the alpha convention; prompting cannot fix an inverted mask.', '/#create', '#positive'),
        ] + common),
        dict(id='compare', title='Find better settings', summary='One question → bounded comparison → keep a winner.', steps=[
            step('Set the baseline', 'Choose the recipe, references and brief you will test against in Create. Vary one thing later, not model, prompt and sampler together.', '/#create', '#selectedPreset'),
            step('Plan a bounded comparison', 'Open Plan comparison, pick one setting and its candidate values, then set the run allowance and time limit. Preparing is not starting.', '/#create', '#planComparison'),
            step('Start and inspect the plan', 'Open Runs & review, read the stages, then start the plan yourself. Reconcile an uncertain submission; never retry it blindly.', '/#production', '#productionDetail'),
            step('Choose a winner', 'Compare the candidates and record why one is useful. A repair is a deliberate new branch with its own budget, not an automatic rerun.', '/#production', '#productionDetail'),
        ]),
        dict(id='scene', title='Assemble a scene or dialogue', summary='Accepted assets → scene editor → preview → native handoff.', steps=[
            step('Select your source assets', 'Pick the images, clips and audio you actually want in the scene. Keep the originals; a scene edit should not regenerate artwork.', '/#assets', '#assetGrid'),
            step('Build the scene', 'Assemble clips, timing and audio in the Scene editor. Preview rendering is not model generation, and unsupported effects need a native handoff.', '/av.html'),
            step('Record voice takes separately', 'Audition a take in Voice baseline before you place it. The baseline is a starting point, not every voice model or expressive control.', '/voice.html'),
            step('Review the finished media', 'Play the preview and check duration, audio alignment, legibility and transitions. Export editable sources beside delivery files where supported.', '/av.html'),
        ]),
        dict(id='game-assets', title='Build an exportable game asset', summary='Target constraints → approved sources → native export.', steps=[
            step('Decide the target constraints', 'Fix canvas, anchor, filtering, timing and engine first; for 3D also units, pivot, budget and materials. A good preview is not an engine test.', '/#create', '#presetSearch'),
            step('Select a consistent source set', 'Choose matching frames or a reviewed mesh in the Asset library. Sprite frames need one shared canvas and anchor, so do not trim them separately.', '/#assets', '#assetGrid'),
            step('Prepare the native export', 'Use the selected-asset export controls for an atlas, layered source or Godot project. Read the unsupported-feature notes before relying on it.', '/#assets', '#nativeExport'),
            step('Test it in the engine', 'Open Runs & review for the export evidence, then check playback, pivots, alpha and timing in the target application itself.', '/#production', '#productionDetail'),
        ]),
        dict(id='workflow', title='Build my own node workflow', summary='Installed nodes → Steps or Nodes → save → review a compatible run.', steps=[
            step('Load the installed nodes', 'Workflow Studio reads the active backend’s node definitions. Search and add nodes, or import an API-format graph; loading never runs one.', '/workflow-studio.html#builder', '#nodeSearch'),
            step('Connect and configure nodes', 'Select a node to edit its values and wire compatible outputs. Disabling a node is not a bypass: add a supported passthrough or disconnect the branch.', '/workflow-studio.html#builder', '#nodeInspector'),
            step('Check the graph', 'Select your outputs and run Check connections; errors name the node and input. This is structural checking, not ComfyUI runtime validation.', '/workflow-studio.html#builder', '#compileWorkflow'),
            step('Save the exact workflow', 'Use Save to Workspace to share a revision with agents. Clear pending saves and unsaved edits before you prepare a run.', '/workflow-studio.html#builder', '#saveSharedWorkflow'),
            step('Prepare, review, then run', 'Prepare a saved revision for a registered image recipe and read its exact source and controls. Run / recover uses that ticket, not your later edits.', '/workflow-studio.html#builder', '#prepareSavedRun'),
        ]),
        dict(id='agents', title='Run a recipe without a browser', summary='Discover → prepare a pinned ticket → approve once → observe.', steps=[
            step('Start the Studio server', 'Run python app/server.py --repo-root . on the configured machine. This starts the existing local service without opening a browser.', '/workflow-studio.html#agents', '#agentCommands'),
            step('Discover, then prepare a ticket', 'Run python -m studio_workflow capabilities and documents list. Then runs prepare with a document ID, revision, preset and request ID; preparing never executes.', '/workflow-studio.html#agents', '#agentCommands'),
            step('Approve the exact ticket', 'Run runs review PREPARATION_ID, then runs run with the approved record, ticket hashes and --approve. A new preparation is not recovery.', '/workflow-studio.html#agents', '#agentCommands'),
            step('Observe; never blindly retry', 'Use status JOB_ID or wait JOB_ID and keep the evidence. Transport failure after submission means unknown, not failed.', '/workflow-studio.html#agents', '#agentCommands'),
        ]),
    ]
    for guide in items:
        assert len(guide['steps']) == len(STAGES[guide['id']])
        # common steps are shared above; copy before assigning per-guide stages.
        guide['steps'] = [dict(item, id=stage_id, check=check) for item, (stage_id, check)
                          in zip(guide['steps'], STAGES[guide['id']])]
        if guide['id'] in RECOMMENDED: guide['recommended'] = list(RECOMMENDED[guide['id']])
    next(g for g in items if g['id'] == 'reference-edit')['steps'][1]['alternatives'] = ['#referenceWrap', '#lastReferenceWrap']
    return {'version': 2, 'guides': items, 'generation_submitted': False,
            'progress_semantics': 'Navigation progress is self-reported, not evidence that a task completed.'}
