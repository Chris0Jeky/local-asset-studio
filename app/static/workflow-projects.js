/* Saved workflows and named Steps over the existing editor and shared reducer. */
(function () {
  'use strict';
  const W = window.WorkflowStudio, P = window.WorkflowProjectState;
  if (!W || !P) return;
  const $ = s => document.querySelector(s), clone = x => JSON.parse(JSON.stringify(x));
  const el = (tag, text, attrs = {}) => { const n = document.createElement(tag); if (text !== null) n.textContent = text; for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
  const btn = (text, action, id) => { const n = el('button', text, {type: 'button'}); if (id) n.id = id; n.onclick = guard(action); return n; };
  const uuid = () => crypto.randomUUID();
  let applying = false, readToken = 0, reduceToken = 0, state, mode = 'nodes', historyOwner = null;
  const panel = el('section', null, {class: 'wf-panel wf-shared', 'aria-label': 'Saved workflows'});
  panel.append(el('h3', 'Saved workflows · shared with agents'));
  const actions = el('div', null, {class: 'wf-toolbar'}), choice = el('select', null, {id: 'sharedWorkflowChoice', 'aria-label': 'Saved workflow'});
  choice.append(el('option', 'Refresh saved workflows', {value: ''})); actions.append(choice);
  const message = el('p', 'Save drafts to Workspace to share them with agents. Nothing runs when you save.', {role: 'status', id: 'sharedWorkflowStatus'});
  function say(text) { message.textContent = text; }
  function guard(fn) { return async () => { try { await fn(); } catch (error) { say(error.message); } finally { sync(); } }; }
  async function request(path, value) {
    const r = await fetch(path, value === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(value)});
    const result = await r.json();
    if (!r.ok) { const e = Error(result.error || 'Workflow request failed'); e.status = r.status; throw e; }
    W.validate(result); return result;
  }
  async function refresh() {
    const token = ++readToken, result = await request(P.PREFIX), selected = choice.value;
    if (token !== readToken) return;
    choice.replaceChildren(el('option', 'Choose saved workflow', {value: ''}));
    for (const item of result.documents) choice.append(el('option', `${item.name} · r${item.revision}`, {value: item.id}));
    choice.value = selected;
  }
  function load(result) {
    applying = true; try { W.load(result.document); } finally { applying = false; }
    state.attach(result); history.replaceChildren(el('option', 'Load revision history', {value: ''})); sync();
  }
  async function open() {
    if (state.pending || state.busy) throw Error('Resolve the retained save before opening another workflow.');
    if (!choice.value) throw Error('Choose a saved workflow.');
    if (W.snapshot() && !confirm('Open saved workflow? Export the current local draft first to keep unsaved changes.')) return;
    const token = ++readToken, epoch = W.epoch(), result = await request(P.PREFIX + '/' + choice.value);
    if (state.pending || state.busy) throw Error('A save began while opening. Nothing was replaced; open again after the save resolves.');
    if (token !== readToken || epoch !== W.epoch()) throw Error('The draft changed while opening. Nothing was replaced.');
    load(result); say(`Opened ${result.document.name} at server revision ${result.revision}.`);
  }
  async function sendPending() {
    if (!state.pending || state.busy) return;
    state.busy = true; sync();
    const pending = clone(state.pending);
    try {
      const result = await request(pending.path, pending.body);
      const outcome = state.success(result, W.snapshot());
      if (outcome.replace) load(result);
      say(outcome.detached ? `Retained save resolved as ${result.id}, r${result.revision}. Current draft was not replaced; Refresh to open it.`
        : state.binding.conflict ? `Save receipt recovered at r${result.revision}, but head is r${result.head_revision}. Your draft is retained. Open current or save a copy.`
        : `Workspace revision ${result.revision} saved. ${state.dirty(W.snapshot()) ? 'Later local edits remain unsaved.' : 'Agents can now read this exact revision.'}`);
    } catch (error) {
      state.failure(error.status);
      say(error.status === 409 ? 'An agent or another window changed this workflow. Local edits are retained. Open current or save a separate copy.'
        : error.message + (state.pending ? ' The exact request is retained; use Retry retained save, not a new save.' : ''));
    } finally { state.busy = false; sync(); }
  }
  async function save(copy = false) { state.begin(W.snapshot(), copy); await sendPending(); }
  const history = el('select', null, {id: 'workflowRevisionChoice', 'aria-label': 'Historical revision'});
  history.append(el('option', 'Load revision history', {value: ''}));
  async function historyLoad() {
    if (!state.binding) throw Error('Open a saved workflow first.');
    const key = state.binding.id, result = await request(P.PREFIX + '/' + key + '/history');
    if (state.binding?.id !== key) return;
    historyOwner = key;
    history.replaceChildren(el('option', 'Choose revision to restore', {value: ''}));
    for (const item of result.revisions) history.append(el('option', `r${item.revision} · ${item.kind} · ${new Date(item.created_at * 1000).toLocaleString()}`, {value: item.revision}));
    say(`Saved history has ${result.revisions.length} revisions. Restore appends a new revision; it never deletes history.`);
  }
  async function restore() {
    if (!history.value || historyOwner !== state.binding?.id) throw Error('Load history for the current saved workflow, then choose a revision.');
    if (!confirm('Restore this saved revision as a new revision? Export any unsaved local edits first.')) return;
    state.begin(W.snapshot(), false, Number(history.value)); await sendPending();
  }
  actions.append(btn('Refresh saved', refresh), btn('Open current', open, 'openSharedWorkflow'), btn('Save to Workspace', () => save(), 'saveSharedWorkflow'), btn('Save separate copy', () => save(true), 'copySharedWorkflow'), btn('Retry retained save', sendPending, 'retrySharedWorkflow'));
  const historyActions = el('div', null, {class: 'wf-toolbar'});
  historyActions.append(btn('Load revision history', historyLoad, 'loadWorkflowHistory'), history, btn('Restore revision', restore, 'restoreSharedWorkflow'));
  const stateLabel = el('p', 'Local draft', {id: 'sharedWorkflowState', 'aria-live': 'polite'});
  panel.append(actions, stateLabel, message, historyActions);
  $('#builder .wf-toolbar').before(panel);
  try { state = new P.State(sessionStorage, uuid); if (state.pending) say('A save request survived this tab’s reload. Retry its exact retained request to reconcile it; it will not overwrite the current draft.'); }
  catch (error) { say('Shared saving is unavailable: ' + error.message); }
  let publishedProject = '';
  function projectSnapshot() {
    return {id: state?.binding?.id || null, revision: state?.binding?.revision || null,
      dirty: !state || state.dirty(W.snapshot()), blocked: !state || !!state.pending || state.busy,
      conflict: !!state?.binding?.conflict};
  }
  window.WorkflowProject = Object.freeze({snapshot: projectSnapshot});
  function sync() {
    const next = JSON.stringify(projectSnapshot());
    if (next !== publishedProject) { publishedProject = next; document.dispatchEvent(new Event('workflow:project')); }
    if (!state) { panel.querySelectorAll('button').forEach(n => n.disabled = true); return; }
    // A copy can attach a new document without calling load(). History belongs
    // to its source identity, never merely to an integer revision.
    if (historyOwner !== state.binding?.id) {
      historyOwner = null;
      history.replaceChildren(el('option', 'Load revision history', {value: ''}));
    }
    const blocked = !!state.pending || state.busy, has = !!W.snapshot();
    stateLabel.textContent = state.pending ? 'Save pending · retain this request' : state.binding ? `Workspace r${state.binding.revision} · ${state.binding.conflict ? 'conflict — local draft retained' : state.dirty(W.snapshot()) ? 'unsaved local changes' : 'saved'}` : 'Local draft · not attached to a saved workflow';
    $('#saveSharedWorkflow').disabled = blocked || !has || !!state.binding?.conflict || (!!state.binding && !state.dirty(W.snapshot()));
    $('#copySharedWorkflow').disabled = blocked || !has;
    $('#openSharedWorkflow').disabled = blocked;
    $('#retrySharedWorkflow').disabled = !state.pending || state.busy;
    $('#loadWorkflowHistory').disabled = !state.binding || state.busy;
    $('#restoreSharedWorkflow').disabled = blocked || !state.binding || !!state.binding.conflict || !history.value || historyOwner !== state.binding.id;
  }
  history.onchange = sync;
  document.addEventListener('workflow:replace', () => { readToken++; if (!applying && state) { state.detach(); history.replaceChildren(el('option', 'Load revision history', {value: ''})); say('Local draft loaded. Save a new Workspace copy, or open a saved workflow to edit its revisions.'); } });
  // Steps use the same pure reducer as saved commands, without committing a revision.
  const stepsPanel = el('section', null, {id: 'workflowSteps', class: 'wf-steps', 'aria-label': 'Workflow steps'}); stepsPanel.hidden = true;
  const viewbar = el('div', null, {class: 'wf-toolbar'}), nodesPanel = $('#builder .wf-builder');
  const nodesButton = btn('Nodes view', () => view('nodes'), 'showWorkflowNodes'), stepsButton = btn('Steps view', () => view('steps'), 'showWorkflowSteps');
  nodesButton.setAttribute('aria-controls', 'workflowNodePanels'); stepsButton.setAttribute('aria-controls', 'workflowSteps'); nodesPanel.id = 'workflowNodePanels';
  viewbar.append(nodesButton, stepsButton, btn('Create named step', () => configure(), 'createWorkflowStep'));
  nodesPanel.before(viewbar, $('#workflowDiagnostics'), stepsPanel);
  document.addEventListener('workflow:inspect', () => view('nodes'));
  function view(value) { mode = value; stepsPanel.hidden = value !== 'steps'; nodesPanel.hidden = value !== 'nodes'; nodesButton.setAttribute('aria-pressed', String(value === 'nodes')); stepsButton.setAttribute('aria-pressed', String(value === 'steps')); renderSteps(); }
  async function reduce(commands) {
    const source = W.snapshot(), epoch = W.epoch(), token = ++reduceToken;
    if (!source) throw Error('Load or create a workflow first.');
    const result = await request(P.PREFIX + '/reduce', {document: source, commands});
    if (token !== reduceToken || epoch !== W.epoch()) throw Error('Draft changed while applying the step command. Nothing was replaced; try the deliberate edit again.');
    W.change(result.document); say('Step edit applied to the local draft. Save to Workspace to share it; nothing was queued.');
  }
  const dialog = el('dialog', null, {class: 'wf-step-dialog', 'aria-labelledby': 'stepDialogTitle'}); document.body.append(dialog);
  let dialogEpoch = null, opener = null;
  function configure(existing = null) {
    const doc = W.snapshot(); if (!doc) throw Error('Load or create a workflow first.');
    dialogEpoch = W.epoch(); opener = document.activeElement; dialog.replaceChildren();
    const form = el('form'), title = el('h2', existing ? 'Edit named step' : 'Create a named step', {id: 'stepDialogTitle'});
    const label = el('label', 'Step name'), name = el('input', null, {required: '', maxlength: '120', 'aria-label': 'Step name'}); name.value = existing?.name || ''; label.append(name);
    const descLabel = el('label', 'What does this step do?'), description = el('textarea', null, {maxlength: '2000'}); description.value = existing?.description || ''; descLabel.append(description);
    const members = el('fieldset'); members.append(el('legend', 'Choose its nodes'));
    const controls = el('fieldset'); controls.append(el('legend', 'Expose inputs as step settings'));
    const occupied = new Set((doc.steps || []).filter(x => x.id !== existing?.id).flatMap(x => x.nodes)), live = W.schema();
    const nodeChecks = [], fieldChecks = [];
    for (const [id, node] of Object.entries(doc.nodes)) {
      if (occupied.has(id)) continue;
      const row = el('label', null, {class: 'wf-check'}), input = el('input', null, {type: 'checkbox'}); input.checked = !!existing?.nodes.includes(id); row.append(input, document.createTextNode(`${id} · ${node.class_type}`)); members.append(row); nodeChecks.push([id, input]);
      const specs = new Map((live?.nodes[node.class_type]?.inputs || []).filter(x => !x.hidden).map(x => [x.name, x.name]));
      for (const old of existing?.controls || []) if (old.node === id) specs.set(old.input, old.name);
      for (const [field, title] of specs) {
        const row = el('label', null, {class: 'wf-check'}), check = el('input', null, {type: 'checkbox'});
        check.checked = !!existing?.controls.some(x => x.node === id && x.input === field); row.append(check, document.createTextNode(`${id}.${field}`));
        const friendly = el('input', null, {type: 'text', maxlength: '120', 'aria-label': `${id}.${field} setting label`}); friendly.value = title;
        const group = el('div'); group.append(row, friendly); controls.append(group); fieldChecks.push([id, field, friendly, check]);
      }
    }
    const note = el('p', '', {role: 'status'}), submit = el('button', 'Apply step to draft', {type: 'submit'});
    form.append(title, label, descLabel, members, controls, el('p', 'Only inputs from selected nodes are exposed. Values remain in the graph. Load installed nodes for all available fields.'), note, submit, btn('Cancel', () => dialog.close()));
    form.onsubmit = async e => {
      e.preventDefault(); if (dialogEpoch !== W.epoch()) { note.textContent = 'The draft changed. Close and reopen this dialog before applying.'; return; }
      const nodes = nodeChecks.filter(x => x[1].checked).map(x => x[0]);
      const step = {id: existing?.id || uuid(), name: name.value, description: description.value, nodes,
        controls: fieldChecks.filter(x => x[3].checked && nodes.includes(x[0])).map(([node, input, name]) => ({node, input, name: name.value}))};
      submit.disabled = true;
      try { await reduce([{op: 'put_step', step}]); dialog.close(); view('steps'); } catch (error) { note.textContent = error.message; } finally { submit.disabled = false; }
    };
    dialog.append(form); dialog.showModal(); name.focus();
  }
  dialog.addEventListener('close', () => { if (opener?.isConnected) opener.focus(); });
  async function duplicate(step) {
    const name = prompt('Name the copy. External input connections stay shared; copied outputs are not selected.', step.name + ' copy'); if (!name) return;
    const doc = W.snapshot(), used = new Set(Object.keys(doc.nodes)), mapping = {}; let index = 1;
    for (const key of step.nodes) { while (used.has(String(index))) index++; mapping[key] = String(index); used.add(String(index++)); }
    await reduce([{op: 'duplicate_step', id: step.id, new_id: uuid(), name, node_ids: mapping}]);
  }
  async function moveStep(step, direction) {
    const doc = W.snapshot(), steps = doc?.steps || [], index = steps.findIndex(item => item.id === step.id);
    if (index < 0) throw Error('This step is no longer in the current draft.');
    if (direction === 'up' && index === 0 || direction === 'down' && index === steps.length - 1) return;
    const before = direction === 'up' ? steps[index - 1].id : steps[index + 2]?.id ?? null;
    await reduce([{op: 'move_step', id: step.id, before}]);
    const card = [...stepsPanel.querySelectorAll('[data-step-id]')].find(item => item.dataset.stepId === step.id);
    const preferred = card?.querySelector(`[data-step-move="${direction}"]:not(:disabled)`);
    const available = card?.querySelector('[data-step-move]:not(:disabled)');
    (preferred || available || card)?.focus({preventScroll: true});
    const position = (W.snapshot()?.steps || []).findIndex(item => item.id === step.id) + 1;
    say(`Moved ${step.name} to step ${position}. Save to Workspace to share this order; nothing was queued.`);
  }
  function renderSteps() {
    if (mode !== 'steps') return;
    const doc = W.snapshot(); stepsPanel.replaceChildren(el('p', 'Steps are named groups over the same nodes. Disabling a step never guesses a bypass. Save and check the graph explicitly.'));
    if (!doc?.steps?.length) { stepsPanel.append(el('p', 'No named steps yet. Create one by selecting its nodes and the settings you want to expose.')); return; }
    for (const [index, step] of doc.steps.entries()) {
      const card = el('article', null, {class: 'wf-panel wf-step-card', 'data-step-id': step.id, tabindex: '-1'});
      card.append(el('small', `STEP ${index + 1} · ${step.nodes.length} NODES`), el('h3', step.name), el('p', step.description));
      const label = el('label', null, {class: 'wf-check'}), toggle = el('input', null, {type: 'checkbox', 'aria-label': 'Enable step ' + step.name});
      const count = step.nodes.filter(id => !doc.disabled.includes(id)).length;
      toggle.checked = !!step.nodes.length && count === step.nodes.length; toggle.indeterminate = count > 0 && count < step.nodes.length; toggle.disabled = !step.nodes.length;
      toggle.onchange = guard(() => reduce([{op: 'set_step_enabled', id: step.id, enabled: toggle.checked}])); label.append(toggle, document.createTextNode('Enable this step')); card.append(label);
      for (const c of step.controls) { const setting = el('section', null, {class: 'wf-step-setting', 'aria-label': c.name}); setting.append(el('h4', c.name)); W.field(setting, c.node, c.input); card.append(setting); }
      const actions = el('div', null, {class: 'wf-toolbar'});
      const up = btn('Move up', () => moveStep(step, 'up')), down = btn('Move down', () => moveStep(step, 'down'));
      up.dataset.stepMove = 'up'; down.dataset.stepMove = 'down';
      up.disabled = index === 0; down.disabled = index === doc.steps.length - 1;
      actions.append(up, down, btn('Edit step', () => configure(step)), btn('Duplicate step', () => duplicate(step)), btn('Remove grouping', () => reduce([{op: 'remove_step', id: step.id}])));
      for (const id of step.nodes) actions.append(btn('Inspect node ' + id, () => { view('nodes'); W.inspect(id); }));
      card.append(actions); stepsPanel.append(card);
    }
  }
  document.addEventListener('workflow:render', () => { sync(); renderSteps(); });
  view('nodes'); sync(); // No GET/POST, restoration or model work is started here.
})();
