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


def guides():
    common = [
        step('Check readiness before spending a run', 'Read the recipe’s model and environment requirements. A connected backend is not proof that this recipe fits memory or has every dependency.', '/#create', '#dependencies'),
        step('Generate only when you choose', 'Review your references, dimensions and variation count. Click Generate yourself when ready. The guide never starts generation or installs models.', '/#create', '#generate'),
        step('Review, keep and reuse', 'Compare at the final intended size. Save a useful result in the Asset library, record what needs work, then reuse it as a reference or export source. Completed is not the same as accepted.', '/#assets', '#assetGrid'),
    ]
    items = [
        dict(id='first-image', title='Make my first image', summary='Idea → recipe → settings → a reviewed image.', steps=[
            step('Start with a recipe, not a model list', 'Open Create and search by the result you need: illustration, portrait, pixel art or product. Choose a recipe in the active environment; do not assume all models share the same settings.', '/#create', '#presetList'),
            step('Describe the result', 'State the subject, action, setting and composition. Use Prompt Lab for a wording proposal; keep your own intent and inspect the proposal before applying it.', '/#create', '#positive'),
            step('Adjust a few meaningful controls', 'Begin with authored defaults. Change size, seed or one family-specific setting at a time. Save a named setup when you find a useful combination.', '/#create', '#controls'),
        ] + common),
        dict(id='reference-edit', title='Edit or preserve a character', summary='References with roles → scoped change → comparison.', steps=[
            step('Choose the editing mechanism', 'Use a reference-edit recipe for semantic changes, or an actual mask/inpaint recipe for a localized repair. A sentence about a pose is not geometric pose control.', '/#create', '#presetSearch'),
            step('Assign what each image contributes', 'On Qwen Atelier recipes, give references identity, pose or style roles. Other recipes expose first/last frame or a single source instead. Keep the original source unchanged.', '/#create', '#roleReferences'),
            step('Write both the change and the invariants', 'Describe what changes and what must remain. For masks, inspect the recipe’s alpha convention; empty or inverted masks do not become correct through prompting.', '/#create', '#positive'),
        ] + common),
        dict(id='compare', title='Find better settings', summary='One question → bounded comparison → keep a winner.', steps=[
            step('Establish the baseline', 'Choose a recipe, references and a fixed brief in Create. Avoid changing model, prompt and sampling settings together when testing one hypothesis.', '/#create', '#selectedPreset'),
            step('Plan a bounded comparison', 'Choose Plan comparison. Select one setting and explicit candidate values, then check the total graph-run allowance and time limit. Preparing is not starting.', '/#create', '#planComparison'),
            step('Start and inspect the plan', 'Open Runs & review, inspect the stages, then explicitly start. Unknown submission outcomes must be reconciled, never blindly retried. Time limits apply between stages.', '/#production', '#productionDetail'),
            step('Make a creative decision', 'Compare candidates and record why a result is useful. A new repair is a deliberate branch with a budget, not an automatic rerun.', '/#production', '#productionDetail'),
        ]),
        dict(id='scene', title='Assemble a scene or dialogue', summary='Accepted assets → scene editor → preview → native handoff.', steps=[
            step('Collect your source assets', 'Select the images, clips and audio you actually want to use. Preserve originals; a scene edit should not regenerate unrelated source artwork.', '/#assets', '#assetGrid'),
            step('Open the Scene editor', 'Build a scene using the supported clip, timing and audio controls. Preview rendering is separate from model generation. Unsupported native-editor effects need a disclosed handoff.', '/av.html'),
            step('Prepare voice takes separately', 'The Voice baseline is a bounded starting point, not a promise of every voice model or expressive control. Audition and review the take before assembling it.', '/voice.html'),
            step('Review the resulting media', 'Check duration, audio alignment, legibility and transitions in the actual preview. Export editable sources alongside delivery files when the adapter supports them.', '/av.html'),
        ]),
        dict(id='game-assets', title='Build an exportable game asset', summary='Target constraints → approved sources → native export.', steps=[
            step('Choose the target first', 'Decide canvas, anchor, filtering, timing and target engine. For 3D also decide units, pivot, geometry budget and materials. A beautiful preview is not an engine acceptance test.', '/#create', '#presetSearch'),
            step('Select a consistent source set', 'Use the Asset library to select matching frames or a reviewed mesh. Sprite frames need a common canvas and anchor; do not trim them independently.', '/#assets', '#assetGrid'),
            step('Prepare the native export', 'Use the selected-assets export controls for an atlas, layered ORA/Krita source or Godot project. Inspect unsupported features rather than assuming lossless interchange.', '/#assets', '#nativeExport'),
            step('Inspect the actual engine result', 'Use Runs & review for export evidence. Check playback, pivots, alpha and timing in the target application before accepting a production pack.', '/#production', '#productionDetail'),
        ]),
        dict(id='workflow', title='Build my own node workflow', summary='Installed nodes → Steps or Nodes → save → review a compatible run.', steps=[
            step('Load the installed node catalog', 'Workflow Studio reads the active backend’s node definitions. Search and add nodes, or import an API-format graph. Loading a catalog never runs a graph.', '/workflow-studio.html#builder', '#nodeSearch'),
            step('Connect and configure', 'Select a node to edit values and connect compatible outputs. Optional inputs have explicit toggles. Disabling a node does not invent a bypass: define a supported passthrough or disconnect its branch.', '/workflow-studio.html#builder', '#nodeInspector'),
            step('Select outputs and check the graph', 'Compilation includes only selected output closures, retaining disconnected drafts in the document. Errors identify nodes and inputs. This is structural checking, not ComfyUI runtime validation.', '/workflow-studio.html#builder', '#compileWorkflow'),
            step('Save the exact workflow', 'Use Save to Workspace to share a revision with agents. Resolve pending saves or unsaved edits before preparing a run. Exporting an API graph does not authorize execution.', '/workflow-studio.html#builder', '#saveSharedWorkflow'),
            step('Prepare, review and run separately', 'For a supported registered image recipe, use Prepare saved revision and review its exact source and controls. Run / recover original uses that saved ticket, not later edits. History is shared with agents. References and arbitrary rewiring still need later execution adapters.', '/workflow-studio.html#builder', '#prepareSavedRun'),
        ]),
        dict(id='agents', title='Run a recipe without a browser', summary='Discover → prepare a pinned ticket → approve once → observe.', steps=[
            step('Start the existing Studio server', 'Use python app/server.py --repo-root . on the configured machine. This starts the existing local service without opening a browser; keep its single worker and configured environments.', '/workflow-studio.html#agents', '#agentCommands'),
            step('Discover and prepare', 'Use python -m studio_workflow capabilities and documents list. The runs prepare command takes a saved document ID, expected revision, preset and retained request ID. Alternatively prepare a registered recipe file. Neither path executes it.', '/workflow-studio.html#agents', '#agentCommands'),
            step('Approve the exact ticket', 'Use runs review PREPARATION_ID, then runs run with the approved record and ticket hashes and --approve. This keeps exact tickets on the server. MCP exposes the same operations. A new preparation is not recovery from an uncertain job.', '/workflow-studio.html#agents', '#agentCommands'),
            step('Observe; never blindly retry', 'Use status JOB_ID or wait JOB_ID. Transport failure after submission means unknown, not failed. Inspect the same ticket/job and retain evidence. Existing recovery and resource limitations remain visible.', '/workflow-studio.html#agents', '#agentCommands'),
        ]),
    ]
    for guide in items:
        assert len(guide['steps']) == len(STAGES[guide['id']])
        # common steps are shared above; copy before assigning per-guide stages.
        guide['steps'] = [dict(item, id=stage_id, check=check) for item, (stage_id, check)
                          in zip(guide['steps'], STAGES[guide['id']])]
    next(g for g in items if g['id'] == 'reference-edit')['steps'][1]['alternatives'] = ['#referenceWrap', '#lastReferenceWrap']
    return {'version': 2, 'guides': items, 'generation_submitted': False,
            'progress_semantics': 'Navigation progress is self-reported, not evidence that a task completed.'}
