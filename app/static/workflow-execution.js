/* Explicit prepare/run/recover controls over the ordinary Studio ticket service. */
(function () {
  'use strict';
  const W = window.WorkflowStudio, T = window.WorkflowTicketState;
  if (!W || !T) return;
  const $ = s => document.querySelector(s), preset = $('#presetChoice');
  if (!preset || !$('#builder')) return;
  const el = (tag, text, attrs = {}) => { const n = document.createElement(tag); if (text !== null) n.textContent = text; for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
  const panel = el('section', null, {class: 'wf-panel', 'aria-labelledby': 'workflowRunTitle', id: 'workflowExecution'});
  const message = el('p', 'No run ticket. Preparation does not start generation.', {role: 'status', id: 'workflowRunStatus'});
  const summary = el('pre', 'Choose the registered recipe above and prepare its compatible draft.', {id: 'workflowTicketSummary'});
  const actions = el('div', null, {class: 'wf-toolbar'});
  panel.append(el('h3', 'Run a compatible recipe', {id: 'workflowRunTitle'}),
    el('p', 'Prompt, dimensions, sampling and LoRA edits can run when they still match the chosen image recipe. Added nodes, rewiring, reference workflows and output subsets need a later execution adapter.'),
    actions, message, summary, el('p', 'Download the ticket and source report before closing this tab. Recovery uses that original request, never your later draft. Observing is not cancellation.'));
  $('#builder').append(panel);
  let state = null, busy = false;
  function say(text) { message.textContent = text; }
  function schemaMatches(doc) { const live = W.schema(); return !live || (doc && live.backend_id === doc.backend_id && live.schema_sha256 === doc.schema_sha256); }
  function schemaIdentity() { const live = W.schema(); return JSON.stringify(live ? [live.backend_id, live.schema_sha256] : null); }
  const buttons = {};
  function action(id, label, fn) {
    const b = el('button', label, {type: 'button', id}); buttons[id] = b;
    b.onclick = async () => {
      if (busy || !state || b.disabled) return;
      busy = true; sync();
      try { await fn(); } catch (error) { say(error.message + (state.record?.phase === 'attempted' ? ' Keep this ticket; observe or recover the same request.' : '')); }
      finally { busy = false; sync(); }
    }; actions.append(b);
  }
  async function request(path, body) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const options = body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)};
      const response = await fetch(path, {...options, signal: controller.signal});
      const result = await response.json();
      if (!response.ok) throw Error(typeof result?.error === 'string' ? result.error : 'Studio request failed');
      W.validate(result); return result;
    } finally { clearTimeout(timeout); }
  }
  async function prepare() {
    if (state.record) throw Error('Resolve or clear the existing ticket first');
    const source = W.snapshot(), epoch = W.epoch(), id = preset.value, live = schemaIdentity();
    if (!source || !id) throw Error('Load a workflow and choose its registered recipe above');
    say('Checking the entire draft against the chosen recipe…');
    const report = await request('/api/workflow-studio/prepare-document', {document: source, preset_id: id});
    if (epoch !== W.epoch() || id !== preset.value || schemaIdentity() !== live) throw Error('Draft, recipe or schema changed during preparation. Late ticket discarded; nothing ran.');
    state.accept(report, source, id);
    say('Ticket prepared and retained in this tab. Review the controls below, then explicitly run.');
  }
  async function run(recovery) {
    if (!recovery && !schemaMatches(W.snapshot())) throw Error('Installed schema changed. Review and prepare again.');
    const record = state.record;
    if (!record) throw Error('No retained ticket');
    if (!confirm(recovery ? 'Recover the ORIGINAL ticket? If the first request never reached Studio, this can dispatch it once. Later draft edits are not used.' : 'Run this prepared recipe once? This starts generation using the ticket shown, not any future edits.')) return;
    const ticket = state.begin(W.snapshot(), preset.value, recovery);
    say('Dispatch intent retained. Contacting Studio with the same request identity…');
    const result = await request('/api/workflow-studio/run', {ticket, approved: true});
    const status = state.dispatched(result);
    say(`Original ticket status: ${status}. Use Observe job for an update; no automatic polling or resubmission.`);
  }
  async function observe() {
    const id = state.record?.report.job_id;
    if (!id) throw Error('No retained job identity');
    const status = state.observe(await request('/api/jobs/' + encodeURIComponent(id)));
    say(`Job ${id}: ${status}. This was observation only.`);
  }
  function download(name, value) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2) + '\n'], {type: 'application/json'}));
    const a = el('a', '', {href: url, download: name}); document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  action('prepareWorkflowRun', 'Prepare run ticket', prepare);
  action('downloadWorkflowTicket', 'Download ticket', () => download('studio-run-ticket.json', state.record.report.ticket));
  action('downloadWorkflowReport', 'Download source report', () => download('studio-projection-report.json', state.record.report));
  action('runWorkflowTicket', 'Run prepared recipe', () => run(false));
  action('recoverWorkflowTicket', 'Recover same request', () => run(true));
  action('observeWorkflowTicket', 'Observe job', observe);
  action('clearWorkflowTicket', 'Clear finished / unsubmitted ticket', () => {
    if (confirm('Clear this tab’s ticket? Download it first. This does not cancel work or delete server records.')) { state.clear(); say('Ticket cleared locally. A new preparation is a new deliberate attempt.'); }
  });
  function sync() {
    if (!state) { Object.values(buttons).forEach(b => b.disabled = true); return; }
    const r = state.record, doc = W.snapshot();
    buttons.prepareWorkflowRun.disabled = busy || !!r || !doc || !preset.value;
    buttons.downloadWorkflowTicket.disabled = buttons.downloadWorkflowReport.disabled = busy || !r;
    buttons.runWorkflowTicket.disabled = busy || !r || r.phase !== 'prepared' || !state.matches(doc, preset.value) || !schemaMatches(doc);
    buttons.recoverWorkflowTicket.disabled = busy || !r || r.phase !== 'attempted';
    buttons.observeWorkflowTicket.disabled = busy || !r;
    buttons.clearWorkflowTicket.disabled = busy || !state.canClear();
    if (r) summary.textContent = `${r.report.recipe.preset_id} · ${r.phase} · ${r.last_status || 'not observed'}\nRequest: ${r.report.ticket.request_id}\nJob: ${r.report.job_id}\nTicket SHA-256: ${r.report.ticket_sha256}\nSource: ${r.report.document_sha256}\nControls: ${JSON.stringify(r.report.recipe.controls, null, 2)}\n${r.phase === 'prepared' && !state.matches(doc, preset.value) ? 'Draft changed: Run is disabled. Clear this unsubmitted ticket and prepare deliberately.' : 'One graph invocation; the recipe may produce multiple outputs.'}`;
    else summary.textContent = 'No retained ticket. Nothing is queued by opening or editing this page.';
  }
  try { state = new T.State(sessionStorage); if (state.record) say('A ticket was retained from this tab. Nothing was sent. Inspect it before any run or recovery.'); }
  catch (error) { say('Run controls unavailable: ' + error.message); }
  document.addEventListener('workflow:render', sync); document.addEventListener('workflow:replace', sync);
  preset.addEventListener('change', sync);
  sync(); // Deliberately no startup request, generation, restoration or polling.
})();
