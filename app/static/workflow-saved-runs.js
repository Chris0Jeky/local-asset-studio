/* Saved-revision preparation/history over the shared service. No startup I/O. */
(function () {
  'use strict';
  const C = window.WorkflowSavedRunCore, P = window.WorkflowProject;
  if (!C || !P || !document.querySelector('#builder')) return;
  const $ = s => document.querySelector(s), preset = $('#presetChoice'), API = '/api/workflow-studio/document-runs';
  const el = (tag, text, attrs = {}) => { const n = document.createElement(tag); if (text !== null) n.textContent = text; for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
  const panel = el('section', null, {id: 'workflowSavedRuns', class: 'wf-panel wf-saved-runs', 'aria-labelledby': 'savedRunsTitle'});
  const summary = el('p', '', {id: 'savedRunDraftState'}), message = el('p', 'No run requested. Load history or prepare a saved revision.', {id: 'savedRunMessage', role: 'status'});
  const prepareActions = el('div', null, {class: 'wf-toolbar'}), historyActions = el('div', null, {class: 'wf-toolbar'}), runActions = el('div', null, {class: 'wf-toolbar'});
  const history = el('select', null, {id: 'savedRunHistory', 'aria-label': 'Prepared runs for the open workflow'});
  const pending = el('select', null, {id: 'savedRunPending', 'aria-label': 'Retained preparation requests'});
  const requestId = el('input', null, {id: 'savedRunRequest', maxlength: '96', 'aria-label': 'Original preparation request ID', placeholder: 'Original preparation ID'});
  const metadata = el('p', 'No original run selected.', {id: 'savedRunSource'}), controls = el('pre', '', {id: 'savedRunControls'});
  const identifiers = el('details'), fingerprints = el('pre', '', {id: 'savedRunFingerprints'});
  identifiers.append(el('summary', 'Source IDs and fingerprints'), fingerprints);
  const details = el('details'), fullTicket = el('pre', '', {id: 'savedRunExactTicket'}), jobInfo = el('pre', '', {id: 'savedRunObservation'});
  details.append(el('summary', 'Exact ticket, including fixed recipe identity'), fullTicket);
  panel.append(el('h3', 'Saved runs · recover across tabs and agents', {id: 'savedRunsTitle'}), summary, prepareActions,
    el('p', 'Preparation uses the saved revision only. Save local edits explicitly first; preparation never starts a generation.'),
    historyActions, metadata, runActions, message, el('h4', 'Projected control changes'), controls, identifiers, details, jobInfo,
    el('p', 'Existing tab-local tickets are separate. Loading a saved run does not replace your draft. A missing job is not proof that it never ran.'));
  $('#builder').append(panel);
  let journal = null, busy = false, packet = null, historyOwner = null, before = null, viewToken = 0, projectKey = '';
  const buttons = {}, say = text => { message.textContent = text; };
  function action(host, id, label, fn) {
    const b = el('button', label, {type: 'button', id}); buttons[id] = b;
    b.onclick = async () => {
      if (busy || b.disabled) return; busy = true; sync();
      try { await fn(); } catch (e) { say(e.message); } finally { busy = false; sync(); }
    }; host.append(b);
  }
  async function request(path, body) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(path, {signal: controller.signal, ...(body === undefined ? {} : {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})});
      const raw = await response.text(); if (raw.length > 2 * 1048576) throw Error('Saved-run reply exceeds the browser limit');
      const value = JSON.parse(raw);
      if (!response.ok) { const e = Error(value?.error || 'Saved-run request failed'); e.status = response.status; throw e; }
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('Invalid saved-run reply');
      return value;
    } finally { clearTimeout(timer); }
  }
  function bindingKey() { const p = P.snapshot(); return `${p.id || ''}:${p.revision || ''}`; }
  function currentReady() { const p = P.snapshot(); return !!p.id && !p.blocked && !p.dirty && !p.conflict && !!preset.value; }
  function pendingRefresh() {
    const keep = pending.value, rows = journal.list(); pending.replaceChildren(el('option', 'No retained preparation selected', {value: ''}));
    for (const r of rows) pending.append(el('option', `${r.preset_id} · r${r.expected_revision} · ${r.request_id}`, {value: r.request_id}));
    pending.value = rows.some(r => r.request_id === keep) ? keep : rows[0]?.request_id || '';
    return rows;
  }
  async function selectOriginal(id, expectedSource = null) {
    C.identifier(id); const token = ++viewToken; packet = null; sync();
    const checked = await C.review(await request(API + '/' + encodeURIComponent(id) + '/review'), id, crypto);
    if (expectedSource && !C.same(expectedSource, checked.source)) throw Error('Run selection source changed; no ticket was attached');
    if (token !== viewToken) return;
    packet = checked; requestId.value = id; jobInfo.textContent = '';
    try { journal?.remember(checked.source); } catch (e) { say('Review loaded; browser retention unavailable: ' + e.message); return; }
    say(`Original r${checked.source.revision} reviewed. Run requires separate consent; current draft edits are not included.`);
  }
  async function prepare(value = null) {
    if (!journal) throw Error('Browser retention is unavailable; use the headless saved-run client');
    if (!value) {
      if (!currentReady()) throw Error('Save or reopen the workflow before preparing this revision');
      if (journal.list().length) throw Error('Recover the retained preparation or explicitly remove its local note first');
      const p = P.snapshot(); value = {request_id: crypto.randomUUID(), document_id: p.id, expected_revision: p.revision, preset_id: preset.value};
      journal.retain(value); pendingRefresh();
    }
    const key = bindingKey(); say('Preparing the saved revision; the request identity is retained before sending…');
    await request(API, value);
    // Fetch and verify committed evidence independently. A malformed/lost POST
    // response leaves the retained request available rather than inventing another.
    const checked = await C.review(await request(API + '/' + value.request_id + '/review'), value.request_id, crypto);
    if (!C.same({document_id: value.document_id, revision: value.expected_revision, preset_id: value.preset_id}, checked.source)) throw Error('Committed preparation does not match the retained source');
    journal.remember(checked.source); journal.complete(value); pendingRefresh();
    if (key !== bindingKey()) { say(`Preparation retained as ${value.request_id}. The open workflow changed; use its original ID to review it.`); return; }
    packet = checked; requestId.value = value.request_id; jobInfo.textContent = '';
    say('Saved preparation retained in Workspace. Review this original ticket, then explicitly run.');
  }
  async function loadHistory(more) {
    const p = P.snapshot(); if (!p.id || more && (!before || historyOwner !== bindingKey())) return;
    const key = bindingKey(), cursor = more ? before : null, token = ++viewToken;
    const query = new URLSearchParams({document_id: p.id, limit: '25'}); if (cursor) query.set('before', String(cursor));
    const result = await request(API + '?' + query);
    if (token !== viewToken || key !== bindingKey()) return;
    if (result.document_id !== p.id || !Array.isArray(result.runs) || result.runs.length > 25) throw Error('History belongs to another workflow');
    let previous = cursor || Number.MAX_SAFE_INTEGER;
    for (const row of result.runs) {
      C.identifier(row.request_id); C.revision(row.revision);
      if (row.document_id !== p.id || !Number.isSafeInteger(row.sequence) || row.sequence < 1 || row.sequence >= previous) throw Error('Invalid run history order'); previous = row.sequence;
    }
    if (result.next_before !== null && (!result.runs.length || result.next_before !== previous)) throw Error('Invalid history cursor');
    if (!more) history.replaceChildren(el('option', 'Choose an original prepared run', {value: ''}));
    for (const row of result.runs) history.append(el('option', `${row.preset_id} · r${row.revision} · ${row.request_id}`, {value: row.request_id}));
    before = result.next_before; historyOwner = key; say('Prepared runs loaded. Preparation records are not evidence of completed generation.');
  }
  async function runOriginal() {
    if (!packet || !journal) throw Error('Review an original run before executing');
    const s = C.source(packet.source);
    if (!confirm(`Run or recover ORIGINAL ${s.preset_id}, saved revision ${s.revision}, request ${s.request_id}? Unsaved or later edits are not used. An existing attempt will be observed, not duplicated; an unsubmitted ticket can start generation.`)) return;
    journal.remember(s); say('Contacting Studio for the original saved ticket. A lost reply does not mean it failed.');
    try {
      const result = await request(API + '/' + s.request_id + '/run', {approved: true, record_sha256: s.record_sha256, ticket_sha256: s.ticket_sha256});
      if (!C.same(s, C.source(result.source))) throw Error('Reply belongs to another saved run');
      const d = result.dispatch, status = d?.job?.status || d?.status;
      if ((d?.job?.id || d?.job_id) !== s.job_id || !['completed', 'failed', 'partial', 'cancelled', 'queued', 'waiting', 'submitting', 'running', 'uncertain', 'reconciliation_required'].includes(status)) throw Error('Malformed dispatch evidence');
      say(`Original run: ${status}. Observe the job for updates. No automatic retry or polling.`);
    } catch (e) { throw Error(e.message + ' Outcome may be unknown. Observe or recover this same original run; do not prepare a replacement.'); }
  }
  async function observe() {
    const s = C.source(packet?.source), result = await request(API + '/' + s.request_id + '/observe');
    if (!C.same({request_id: s.request_id, document_id: s.document_id, revision: s.revision, record_sha256: s.record_sha256, document_sha256: s.document_sha256}, result) || result.observation?.job_id !== s.job_id) throw Error('Observation belongs to another saved run');
    const o = result.observation;
    if (o.state === 'observed') {
      if (o.job?.id !== s.job_id || typeof o.job.status !== 'string') throw Error('Invalid linked job');
      jobInfo.textContent = JSON.stringify(o.job, null, 2); say(`Original job: ${o.job.status}. This read did not submit, cancel or resume work.`);
    } else {
      if (!['not_observed', 'workspace_changed', 'evidence_mismatch'].includes(o.state)) throw Error('Invalid observation state');
      jobInfo.textContent = ''; say(`${o.state}: ${o.message || 'Inspect original evidence.'} No submission status was inferred.`);
    }
  }
  function download(name, text) {
    const url = URL.createObjectURL(new Blob([text], {type: 'application/json'})), a = el('a', '', {href: url, download: name});
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  action(prepareActions, 'prepareSavedRun', 'Prepare saved revision', () => prepare());
  prepareActions.append(pending);
  action(prepareActions, 'recoverSavedPreparation', 'Recover preparation', () => {
    const value = journal.list().find(x => x.request_id === pending.value); if (!value) throw Error('Select a retained preparation'); return prepare(value);
  });
  action(prepareActions, 'removePreparationNote', 'Remove local note', () => {
    const value = journal.list().find(x => x.request_id === pending.value); if (!value) return;
    if (confirm(`Remove only the local preparation note ${value.request_id}? Save this ID first. This does not delete its server record or cancel any work. A new preparation is a separate deliberate attempt.`)) { journal.complete(value); pendingRefresh(); say('Local note removed. Existing server evidence is unchanged.'); }
  });
  action(historyActions, 'loadSavedRuns', 'Load run history', () => loadHistory(false));
  action(historyActions, 'moreSavedRuns', 'Older runs', () => loadHistory(true));
  historyActions.append(history, requestId);
  action(historyActions, 'reviewSavedRun', 'Review original run', () => selectOriginal(requestId.value.trim()));
  action(runActions, 'executeSavedRun', 'Run / recover original', runOriginal);
  action(runActions, 'observeSavedRun', 'Observe original job', observe);
  action(runActions, 'downloadSavedTicket', 'Download exact ticket', () => download('saved-run-ticket.json', packet.ticket_json));
  action(runActions, 'downloadSavedRecord', 'Download source record', () => download('saved-run-record.json', packet.record_json));
  history.onchange = () => { requestId.value = history.value; packet = null; sync(); };
  requestId.oninput = () => { packet = null; viewToken++; sync(); }; pending.onchange = () => sync();
  function sync() {
    const p = P.snapshot(), key = bindingKey();
    if (key !== projectKey) { projectKey = key; viewToken++; before = null; historyOwner = null; history.replaceChildren(el('option', 'Load history for the open workflow', {value: ''})); }
    summary.textContent = !p.id ? 'Open or save a Workspace workflow to prepare a persisted run.' : `Workspace r${p.revision} · ${p.blocked ? 'save unresolved' : p.conflict ? 'conflict; reopen current' : p.dirty ? 'unsaved edits — save first' : 'saved revision ready for preparation'}`;
    buttons.prepareSavedRun.disabled = busy || !journal || !currentReady();
    pending.hidden = buttons.recoverSavedPreparation.hidden = buttons.removePreparationNote.hidden = !pending.value;
    buttons.recoverSavedPreparation.disabled = buttons.removePreparationNote.disabled = busy || !journal || !pending.value;
    buttons.loadSavedRuns.disabled = busy || !p.id; buttons.moreSavedRuns.disabled = busy || !before || historyOwner !== key;
    buttons.reviewSavedRun.disabled = busy || !requestId.value.trim();
    buttons.executeSavedRun.disabled = busy || !packet || !journal;
    for (const id of ['observeSavedRun', 'downloadSavedTicket', 'downloadSavedRecord']) buttons[id].disabled = busy || !packet;
    history.disabled = requestId.disabled = pending.disabled = busy;
    metadata.textContent = packet ? `${packet.source.preset_id} · original saved revision ${packet.source.revision}. ${packet.source_is_current ? 'Current at last review.' : `Newer head r${packet.head_revision} exists.`} ${p.id !== packet.source.document_id || p.revision !== packet.source.revision || p.dirty ? 'The editor differs; Run uses this ORIGINAL source only.' : ''}` : 'Review a preparation to see its original source. Your editor is not replaced.';
    fingerprints.textContent = packet ? `Document: ${packet.source.document_id}\nPreparation: ${packet.source.request_id}\nJob: ${packet.source.job_id}\nRecord SHA-256: ${packet.source.record_sha256}\nTicket SHA-256: ${packet.source.ticket_sha256}` : '';
    controls.textContent = packet?.controls_json || ''; fullTicket.textContent = packet?.ticket_json || '';
    identifiers.hidden = details.hidden = !packet; jobInfo.hidden = !jobInfo.textContent;

  }
  try { journal = new C.Journal(localStorage); pendingRefresh(); const old = journal.previous(); if (old) { requestId.value = old.request_id; say('Original run reference restored. Review or observe it explicitly; nothing was sent on load.'); } }
  catch (e) { journal = null; say('Browser retention unavailable: ' + e.message + '. History and review remain read-only options.'); }
  document.addEventListener('workflow:project', sync); document.addEventListener('workflow:render', sync);
  preset.addEventListener('change', sync); window.addEventListener('storage', () => { try { if (journal) pendingRefresh(); } catch (e) { journal = null; say(e.message); } sync(); });
  sync();
})();
