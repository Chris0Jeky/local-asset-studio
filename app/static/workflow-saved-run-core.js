/* Exact-text review and per-request preparation notes; never owns execution. */
(function (root) {
  'use strict';
  const PREFIX = 'studio.workflow.saved-preparation.v1.', LAST = 'studio.workflow.saved-run-reference.v1';
  const HASH = /^[0-9a-f]{64}$/, ID = /^[A-Za-z0-9_.-]{1,96}$/;
  const need = (ok, text) => { if (!ok) throw Error(text); };
  const clone = x => JSON.parse(JSON.stringify(x));
  function identifier(x) { need(typeof x === 'string' && ID.test(x) && !['.', '..', '__proto__', 'constructor', 'prototype'].includes(x), 'Invalid saved-run identity'); return x; }
  function revision(x) { need(Number.isSafeInteger(x) && x >= 1 && x <= 1024, 'Invalid saved revision'); return x; }
  function source(value) {
    need(value && typeof value === 'object', 'Missing saved-run source');
    for (const key of ['request_id', 'document_id', 'preset_id', 'job_id']) identifier(value[key]);
    revision(value.revision);
    for (const key of ['document_sha256', 'record_sha256', 'ticket_sha256']) need(typeof value[key] === 'string' && HASH.test(value[key]), 'Invalid ' + key);
    return Object.fromEntries(['request_id', 'document_id', 'revision', 'preset_id', 'job_id', 'document_sha256', 'record_sha256', 'ticket_sha256'].map(k => [k, value[k]]));
  }
  function request(value) {
    need(value && Object.keys(value).sort().join(',') === 'document_id,expected_revision,preset_id,request_id', 'Invalid preparation note');
    for (const key of ['request_id', 'document_id', 'preset_id']) identifier(value[key]);
    revision(value.expected_revision); return clone(value);
  }
  const same = (a, b) => Object.keys(a).every(k => a[k] === b?.[k]);
  async function sha(text, crypto) {
    need(typeof text === 'string' && text.length <= 1048576, 'Exact review text exceeds limit');
    const bytes = new TextEncoder().encode(text); need(bytes.length <= 1048576, 'Exact review bytes exceed limit');
    return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
  }
  async function review(packet, expected, crypto) {
    const s = source(packet?.source); identifier(expected); need(s.request_id === expected, 'Review belongs to another preparation');
    need(packet.dispatch_attempted === false && revision(packet.head_revision) >= s.revision &&
      packet.source_is_current === (packet.head_revision === s.revision), 'Invalid review head');
    const [recordHash, ticketHash] = await Promise.all([sha(packet.record_json, crypto), sha(packet.ticket_json, crypto)]);
    need(recordHash === s.record_sha256 && ticketHash === s.ticket_sha256, 'Exact review fingerprint mismatch');
    // Parse metadata only. Never serialize parsed tickets back into a run/export:
    // seeds may already have lost precision, even though exact source text has not.
    const record = JSON.parse(packet.record_json), ticket = JSON.parse(packet.ticket_json), r = record.report;
    need(record.format === 'studio.document-run/v1' && same(request(record.request), {
      request_id: s.request_id, document_id: s.document_id, expected_revision: s.revision, preset_id: s.preset_id}), 'Record source differs');
    need(r?.ticket_sha256 === s.ticket_sha256 && r.document_sha256 === s.document_sha256 && r.job_id === s.job_id &&
      r.recipe?.preset_id === s.preset_id && ticket.recipe?.preset_id === s.preset_id && ticket.recipe.batch_count === 1 &&
      r.ticket?.request_id === ticket.request_id && ticket.format === 'studio.run-ticket/v1' &&
      ticket.pins?.graph_sha256 === packet.prepared_graph_sha256 && ticket.pins.backend_id === packet.backend_id, 'Ticket source differs');
    need(typeof packet.controls_json === 'string' && packet.controls_json.length <= 1048576 &&
      JSON.stringify(JSON.parse(packet.controls_json)) === JSON.stringify(r.recipe.controls), 'Displayed controls differ');
    return {...packet, source: s};
  }
  class Journal {
    constructor(storage) { this.storage = storage; }
    list() {
      const values = [];
      for (let i = 0; i < this.storage.length; i++) {
        const key = this.storage.key(i); if (!key?.startsWith(PREFIX)) continue;
        const raw = this.storage.getItem(key); need(raw && raw.length <= 1024, 'Invalid retained preparation; preserve browser storage for inspection');
        const value = request(JSON.parse(raw)); need(key === PREFIX + value.request_id, 'Preparation key differs'); values.push(value);
      }
      need(values.length <= 32, 'Resolve retained preparations before creating more');
      return values.sort((a, b) => a.request_id.localeCompare(b.request_id));
    }
    retain(value) {
      value = request(value); const key = PREFIX + value.request_id, raw = JSON.stringify(value), old = this.storage.getItem(key);
      need(old === null || old === raw, 'Preparation identity already has different content');
      need(old !== null || this.list().length < 32, 'Resolve retained preparations before creating more');
      this.storage.setItem(key, raw); need(this.storage.getItem(key) === raw, 'Preparation note could not be retained'); return value;
    }
    complete(value) {
      value = request(value); const key = PREFIX + value.request_id, old = this.storage.getItem(key);
      need(old !== null && same(request(JSON.parse(old)), value), 'Retained preparation changed'); this.storage.removeItem(key);
    }
    remember(value) { const s = source(value), raw = JSON.stringify(s); this.storage.setItem(LAST, raw); need(this.storage.getItem(LAST) === raw, 'Run reference could not be retained'); }
    previous() { const raw = this.storage.getItem(LAST); need(raw === null || raw.length <= 2048, 'Invalid saved-run reference'); return raw === null ? null : source(JSON.parse(raw)); }
  }
  const exported = {Journal, review, source, request, identifier, revision, same, PREFIX, LAST};
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  else root.WorkflowSavedRunCore = exported;
})(typeof window !== 'undefined' ? window : globalThis);
