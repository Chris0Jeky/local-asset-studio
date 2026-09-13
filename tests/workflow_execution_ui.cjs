/* Execute the real UI wiring with a small DOM/transport fixture; not a browser. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const T = require('../app/static/workflow-ticket-state.js');
const clone = x => JSON.parse(JSON.stringify(x));
const hash = 'a'.repeat(64), recipe = {preset_id: 'example', controls: {seed: 42}, batch_count: 1};
const report = {format: 'studio.preset-projection/v1', generation_submitted: false, recipe, document_sha256: hash,
  authored_graph_sha256: hash, prepared_graph_sha256: hash, ticket_sha256: hash, changed_bindings: {},
  job_id: '22222222-2222-5222-8222-222222222222', ticket: {format: 'studio.run-ticket/v1',
    request_id: '11111111-1111-4111-8111-111111111111', recipe, pins: {graph_sha256: hash}, generation_submitted: false, notice: 'Test'}};
function fixture(raw = null) {
  const ids = new Map(), events = new Map(), calls = [], downloads = [];
  class Element {
    constructor(tag) {this.tag = tag; this.children = []; this.disabled = false; this.textContent = ''; this.listeners = {}; this.value = '';}
    setAttribute(k, v) {this[k] = v; if (k === 'id') ids.set(v, this);}
    append(...nodes) {this.children.push(...nodes);}
    addEventListener(k, fn) {this.listeners[k] = fn;}
    remove() {}
    click() {if (this.tag === 'a') downloads.push(this.download); return this.disabled ? undefined : this.onclick?.();}
  }
  const body = new Element('body'), builder = new Element('section'), preset = new Element('select');
  ids.set('builder', builder); ids.set('presetChoice', preset); preset.value = 'example';
  let doc = {format: 'studio.workflow/v1', name: 'Example', revision: 1, backend_id: 'primary', schema_sha256: hash, nodes: {}};
  let epoch = 1, schema = {backend_id: 'primary', schema_sha256: hash}, answer = true, reply;
  const storage = {raw, fail: false, getItem() {return this.raw;}, setItem(k, v) {if (this.fail) throw Error('storage refused'); this.raw = v;}, removeItem() {if (this.fail) throw Error('storage refused'); this.raw = null;}};
  const W = {snapshot: () => clone(doc), epoch: () => epoch, schema: () => clone(schema), validate: () => {}};
  const document = {body, querySelector: s => ids.get(s.slice(1)), createElement: tag => new Element(tag),
    addEventListener: (name, fn) => {const list = events.get(name) || []; list.push(fn); events.set(name, list);}};
  const dispatch = name => (events.get(name) || []).forEach(fn => fn());
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname, '../app/static/workflow-execution.js'), 'utf8'), {
    window: {WorkflowStudio: W, WorkflowTicketState: T}, document, sessionStorage: storage,
    confirm: () => answer, Blob, URL: {createObjectURL: () => 'blob:test', revokeObjectURL: () => {}}, setTimeout: () => {}, clearTimeout: () => {}, AbortController,
    fetch: async (path, options) => {calls.push({path, options}); return reply(path, options);}, console
  });
  reply = async path => ({ok: true, json: async () => path.endsWith('prepare-document') ? clone(report) : path.endsWith('/run')
    ? {job: {id: report.job_id, status: 'queued'}} : {id: report.job_id, status: 'completed'}});
  return {ids, calls, storage, downloads, click: id => ids.get(id).click(),
    setReply: fn => {reply = fn;}, consent: b => {answer = b;}, edit: () => {doc.name += ' edit'; epoch++; dispatch('workflow:render');},
    wideSchema: () => {schema.nodes = {KSampler: {seed: {max: 2**64 - 1}}};},
    schema: () => {schema.schema_sha256 = 'b'.repeat(64); dispatch('workflow:render');},
    choose: () => {preset.value = 'another'; preset.listeners.change();}};
}
let count = 0;
async function test(name, fn) {await fn(); console.log('PASS ' + name); count++;}
(async () => {
  await test('startup and restored intent make no requests', async () => {
    const f = fixture(); assert.equal(f.calls.length, 0); await f.click('prepareWorkflowRun');
    const reload = fixture(f.storage.raw); assert.equal(reload.calls.length, 0); assert.ok(reload.ids.get('downloadWorkflowTicket'));
  });
  await test('prepare, download, decline and run are separate actions', async () => {
    const f = fixture(); await f.click('prepareWorkflowRun'); assert.equal(f.calls.length, 1);
    assert.equal(JSON.parse(f.storage.raw).phase, 'prepared'); await f.click('downloadWorkflowTicket'); assert.deepEqual(f.downloads, ['studio-run-ticket.json']);
    f.consent(false); await f.click('runWorkflowTicket'); assert.equal(f.calls.length, 1);
    f.consent(true); await f.click('runWorkflowTicket'); assert.equal(f.calls[1].path, '/api/workflow-studio/run');
    assert.equal(JSON.parse(f.storage.raw).last_status, 'queued'); assert.equal(f.ids.get('clearWorkflowTicket').disabled, true);
  });
  await test('intent is persisted at fetch boundary and double clicks are inert', async () => {
    const f = fixture(); await f.click('prepareWorkflowRun'); let done;
    f.setReply(async () => {assert.equal(JSON.parse(f.storage.raw).phase, 'attempted'); return new Promise(r => {done = r;});});
    const pending = f.click('runWorkflowTicket'); await f.click('runWorkflowTicket'); assert.equal(f.calls.length, 2);
    done({ok: true, json: async () => ({job: {id: report.job_id, status: 'queued'}})}); await pending;
  });
  await test('wide installed-schema bounds do not block an exact small user seed', async () => {
    const f = fixture(); f.wideSchema(); await f.click('prepareWorkflowRun');
    assert.equal(f.calls.length, 1); assert.equal(JSON.parse(f.storage.raw).report.recipe.controls.seed, 42);
    assert.equal(f.ids.get('runWorkflowTicket').disabled, false);
  });
  await test('post-prepare edit and schema changes disable run', async () => {
    for (const change of ['edit', 'schema', 'choose']) {const f = fixture(); await f.click('prepareWorkflowRun'); f[change](); await f.click('runWorkflowTicket'); assert.equal(f.calls.length, 1);}
  });
  await test('late preparation cannot attach after draft, schema or recipe changes', async () => {
    for (const change of ['edit', 'schema', 'choose']) {
      const f = fixture(); let done; f.setReply(async () => new Promise(r => {done = r;}));
      const pending = f.click('prepareWorkflowRun'); f[change](); done({ok: true, json: async () => clone(report)}); await pending;
      assert.equal(f.storage.raw, null); assert.match(f.ids.get('workflowRunStatus').textContent, /Late ticket discarded/);
    }
  });
  await test('storage failures before preparation or dispatch produce no run request', async () => {
    const f = fixture(); f.storage.fail = true; await f.click('prepareWorkflowRun'); assert.equal(f.storage.raw, null); assert.equal(f.calls.length, 1);
    f.storage.fail = false; await f.click('prepareWorkflowRun'); f.storage.fail = true; await f.click('runWorkflowTicket');
    assert.equal(f.calls.length, 2); assert.equal(JSON.parse(f.storage.raw).phase, 'prepared');
  });
  await test('transport loss retains exact ticket; recovery ignores later draft', async () => {
    const f = fixture(); await f.click('prepareWorkflowRun');
    f.setReply(async () => {throw Error('lost response');}); await f.click('runWorkflowTicket');
    const original = f.calls[1].options.body; assert.equal(JSON.parse(f.storage.raw).phase, 'attempted');
    f.edit(); await f.click('prepareWorkflowRun'); assert.equal(f.calls.length, 2);
    f.setReply(async () => ({ok: true, json: async () => ({job: {id: report.job_id, status: 'uncertain'}})}));
    await f.click('recoverWorkflowTicket'); assert.equal(f.calls[2].options.body, original); assert.equal(f.ids.get('clearWorkflowTicket').disabled, true);
  });
  await test('malformed and error run replies never imply no submission', async () => {
    for (const value of [null, {job: null}, {job: {id: 'wrong', status: 'completed'}}]) {
      const f = fixture(); await f.click('prepareWorkflowRun'); f.setReply(async () => ({ok: true, json: async () => value}));
      await f.click('runWorkflowTicket'); assert.equal(JSON.parse(f.storage.raw).phase, 'attempted'); assert.equal(f.ids.get('clearWorkflowTicket').disabled, true);
    }
    const f = fixture(); await f.click('prepareWorkflowRun'); f.setReply(async () => ({ok: false, json: async () => ({error: 'server exception'})}));
    await f.click('runWorkflowTicket'); assert.equal(JSON.parse(f.storage.raw).phase, 'attempted');
  });
  await test('observation is GET only and terminal work may be cleared explicitly', async () => {
    const f = fixture(); await f.click('prepareWorkflowRun'); await f.click('runWorkflowTicket'); await f.click('observeWorkflowTicket');
    assert.equal(f.calls[2].path, '/api/jobs/' + report.job_id); assert.equal(f.calls[2].options.method, undefined); assert.equal(f.calls[2].options.body, undefined);
    assert.equal(f.ids.get('clearWorkflowTicket').disabled, false); await f.click('clearWorkflowTicket'); assert.equal(f.storage.raw, null);
  });
  console.log(`${count} actual-UI wiring contracts passed`);
})().catch(error => {console.error(error); process.exitCode = 1;});
