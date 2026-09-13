/* Persistence state only. Shared graphs remain owned by WorkflowStudio. */
(function (root) {
  'use strict';
  const KEY = 'studio.workflow.pending-save.v1', PREFIX = '/api/workflow-studio/documents';
  const clone = x => JSON.parse(JSON.stringify(x));
  function signature(doc) { if (!doc) return ''; const value = clone(doc); delete value.revision; const sorted = x => Array.isArray(x) ? x.map(sorted) : x && typeof x === 'object' ? Object.fromEntries(Object.keys(x).sort().map(k => [k, sorted(x[k])])) : x; return JSON.stringify(sorted(value)); }
  function validatePending(value) {
    if (!value || value.version !== 1 || typeof value.session !== 'string' || typeof value.source !== 'string' ||
        !['save', 'restore'].includes(value.operation) || !value.body || typeof value.body.request_id !== 'string' ||
        !/^[A-Za-z0-9_.-]{1,96}$/.test(value.body.request_id) ||
        !(value.path === PREFIX || /^\/api\/workflow-studio\/documents\/[a-zA-Z0-9_.-]{1,96}\/(commands|restore)$/.test(value.path))) throw Error('Invalid retained save. Export the browser session record for inspection; it was not sent.');
    if (value.path === PREFIX) {
      if (value.operation !== 'save' || !value.body.document || Object.keys(value.body).sort().join(',') !== 'document,request_id') throw Error('Invalid retained create');
    } else {
      if (!Number.isSafeInteger(value.body.expected_revision) || value.body.expected_revision < 1) throw Error('Invalid retained revision');
      if (value.operation === 'restore') {
        if (!value.path.endsWith('/restore') || !Number.isSafeInteger(value.body.revision) || value.body.revision < 1 || Object.keys(value.body).sort().join(',') !== 'expected_revision,request_id,revision') throw Error('Invalid retained restore');
      } else if (!value.path.endsWith('/commands') || Object.keys(value.body).sort().join(',') !== 'commands,expected_revision,request_id' ||
                 !Array.isArray(value.body.commands) || value.body.commands.length !== 1 || value.body.commands[0]?.op !== 'replace' || !value.body.commands[0].document) throw Error('Invalid retained save command');
    }
    return clone(value);
  }
  class State {
    constructor(storage, uuid) {
      this.storage = storage; this.uuid = uuid; this.session = uuid(); this.binding = null; this.pending = null; this.busy = false;
      const raw = storage.getItem(KEY);
      if (raw) { if (raw.length > 3 * 1024 * 1024) throw Error('Retained save exceeds the browser limit'); this.pending = validatePending(JSON.parse(raw)); }
    }
    detach() { this.session = this.uuid(); this.binding = null; }
    attach(result) { this.binding = {id: result.id, revision: result.revision, baseline: signature(result.document), conflict: result.head_revision !== result.revision}; }
    dirty(doc) { return !this.binding || signature(doc) !== this.binding.baseline; }
    begin(doc, copy = false, restoreRevision = null) {
      if (!doc || this.pending || this.busy) throw Error('Resolve the retained save before starting another write.');
      if (!copy && this.binding?.conflict) throw Error('Workflow changed elsewhere. Open current, or save a separate copy.');
      const bound = !copy && this.binding;
      if (restoreRevision !== null && !bound) throw Error('Open a saved workflow before restoring a revision.');
      const request_id = this.uuid(), operation = restoreRevision === null ? 'save' : 'restore';
      const path = bound ? PREFIX + '/' + bound.id + (operation === 'restore' ? '/restore' : '/commands') : PREFIX;
      const body = !bound ? {request_id, document: clone(doc)} : operation === 'restore'
        ? {request_id, expected_revision: bound.revision, revision: restoreRevision}
        : {request_id, expected_revision: bound.revision, commands: [{op: 'replace', document: clone(doc)}]};
      const pending = validatePending({version: 1, path, body, session: this.session, source: signature(doc), operation});
      // No request can leave before its exact identity and payload are retained.
      this.storage.setItem(KEY, JSON.stringify(pending)); this.pending = pending;
      return clone(pending);
    }
    success(result, current) {
      if (!this.pending) throw Error('No pending save to reconcile');
      const pending = this.pending;
      this.storage.removeItem(KEY); this.pending = null;
      if (pending.session !== this.session) return {detached: true, replace: false};
      this.attach(result);
      return {detached: false, replace: pending.operation === 'restore' && !this.binding.conflict && signature(current) === pending.source};
    }
    failure(status) {
      if (![400, 403, 404, 409].includes(status)) return; // Transport/503 outcomes stay retained.
      this.storage.removeItem(KEY); this.pending = null;
      if (status === 409 && this.binding) this.binding.conflict = true;
    }
  }
  const exported = {State, signature, validatePending, KEY, PREFIX};
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  else root.WorkflowProjectState = exported;
})(typeof window !== 'undefined' ? window : globalThis);
