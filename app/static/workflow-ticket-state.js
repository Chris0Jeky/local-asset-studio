/* Retained run intent only. The server owns dispatch, jobs and uncertainty. */
(function (root) {
  'use strict';
  const KEY = 'studio.workflow.run-ticket.v1', LIMIT = 3 * 1024 * 1024;
  const HASH = /^[0-9a-f]{64}$/, UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  const TERMINAL = ['completed', 'failed', 'partial', 'cancelled'];
  const STATUSES = [...TERMINAL, 'queued', 'waiting', 'submitting', 'running', 'uncertain'];
  const need = (ok, message) => { if (!ok) throw Error(message); };
  const object = x => !!x && typeof x === 'object' && !Array.isArray(x);
  const clone = x => JSON.parse(JSON.stringify(x));
  function safe(value, depth = 0) {
    need(depth <= 48, 'Run record is too deeply nested');
    if (typeof value === 'number') need(Number.isFinite(value) && (!Number.isInteger(value) || Number.isSafeInteger(value)), 'Use the Python client for integers outside the exact browser range');
    if (value && typeof value === 'object') for (const [key, child] of Object.entries(value)) {
      need(!['__proto__', 'constructor', 'prototype'].includes(key), 'Reserved record key'); safe(child, depth + 1);
    }
  }
  function signature(value) {
    safe(value);
    const sorted = x => Array.isArray(x) ? x.map(sorted) : object(x) ? Object.fromEntries(Object.keys(x).sort().map(k => [k, sorted(x[k])])) : x;
    return JSON.stringify(sorted(value));
  }
  function validateReport(r) {
    safe(r);
    need(object(r) && r.format === 'studio.preset-projection/v1' && r.generation_submitted === false, 'Invalid projection report');
    const t = r.ticket;
    need(object(t) && t.format === 'studio.run-ticket/v1' && UUID.test(t.request_id) && UUID.test(r.job_id), 'Invalid retained ticket identity');
    need(object(t.recipe) && object(r.recipe) && typeof t.recipe.preset_id === 'string' && t.recipe.preset_id.length > 0 &&
      t.recipe.batch_count === 1 && signature(t.recipe) === signature(r.recipe), 'Ticket and report recipes differ');
    need(object(t.pins) && t.generation_submitted === false && typeof t.notice === 'string' &&
      Object.keys(t).sort().join(',') === 'format,generation_submitted,notice,pins,recipe,request_id', 'Invalid ticket fields');
    for (const field of ['ticket_sha256', 'document_sha256', 'authored_graph_sha256', 'prepared_graph_sha256']) need(HASH.test(r[field]), 'Missing report fingerprint');
    need(t.pins.graph_sha256 === r.prepared_graph_sha256, 'Prepared graph fingerprint differs');
    need(object(r.changed_bindings), 'Missing binding report');
    return clone(r);
  }
  function validateRecord(record) {
    need(object(record) && record.version === 1 && ['prepared', 'attempted'].includes(record.phase) &&
      typeof record.source === 'string' && record.source.length <= LIMIT, 'Invalid retained run record; preserve storage for inspection');
    validateReport(record.report);
    need(record.last_status === null || STATUSES.includes(record.last_status) || record.last_status === 'reconciliation_required', 'Invalid retained job status');
    need(record.phase !== 'prepared' || record.last_status === null, 'Invalid unsubmitted state');
    return clone(record);
  }
  class State {
    constructor(storage) {
      this.storage = storage; this.record = null;
      const raw = storage.getItem(KEY);
      if (raw) { need(raw.length <= LIMIT, 'Retained run record is too large'); this.record = validateRecord(JSON.parse(raw)); }
    }
    commit(next) {
      const checked = validateRecord(next), raw = JSON.stringify(checked);
      need(raw.length <= LIMIT, 'Run record exceeds browser storage budget');
      this.storage.setItem(KEY, raw); this.record = checked;
    }
    accept(report, source, preset) {
      need(!this.record, 'Resolve or explicitly clear the retained ticket first');
      const checked = validateReport(report);
      need(source && checked.recipe.preset_id === preset, 'Prepared recipe does not match the selected recipe');
      this.commit({version: 1, phase: 'prepared', source: signature(source), report: checked, last_status: null});
    }
    matches(source, preset) { return !!this.record && this.record.source === signature(source) && this.record.report.recipe.preset_id === preset; }
    begin(source, preset, recovery = false) {
      need(this.record, 'Prepare a ticket first');
      if (recovery) need(this.record.phase === 'attempted', 'Recovery requires a retained dispatch attempt');
      else need(this.record.phase === 'prepared' && this.matches(source, preset), 'Draft or recipe changed; do not run a stale ticket');
      // Persist intent BEFORE the caller sends a request capable of generation.
      this.commit({...this.record, phase: 'attempted'});
      return clone(this.record.report.ticket);
    }
    observe(job) {
      need(this.record && object(job) && job.id === this.record.report.job_id && STATUSES.includes(job.status), 'Job reply is malformed or belongs to another ticket');
      this.commit({...this.record, phase: 'attempted', last_status: job.status});
      return job.status;
    }
    dispatched(result) {
      need(this.record?.phase === 'attempted' && object(result), 'Invalid dispatch reply; retain the same ticket');
      if (object(result.job)) return this.observe(result.job);
      need(result.status === 'reconciliation_required' && result.job_id === this.record.report.job_id, 'Dispatch outcome is unknown; retain the same ticket');
      this.commit({...this.record, last_status: 'reconciliation_required'});
      return 'reconciliation_required';
    }
    canClear() { return !!this.record && (this.record.phase === 'prepared' || TERMINAL.includes(this.record.last_status)); }
    clear() {
      need(this.canClear(), 'Unresolved or active work must retain its ticket; observe it instead');
      this.storage.removeItem(KEY); this.record = null;
    }
  }
  const api = {State, KEY, signature, validateReport, validateRecord};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.WorkflowTicketState = api;
})(typeof window !== 'undefined' ? window : globalThis);
