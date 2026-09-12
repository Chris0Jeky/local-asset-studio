// Exercise the real readiness UI while startup catalog loading is still pending.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const elements = new Map(), healthRequests = [], requests = [];
const element = selector => {
  if (!elements.has(selector)) elements.set(selector, {
    value: '', files: [], textContent: '', className: '', disabled: false,
    classList: {toggle() {}}, addEventListener() {},
  });
  return elements.get(selector);
};
const context = vm.createContext({
  document: {querySelector: element, querySelectorAll: () => [], addEventListener() {}},
  URL, Blob, location: {hash: ''}, setInterval() {},
  fetch: (url, options = {}) => {
    if (url === '/api/catalog') return new Promise(() => {});
    if (url === '/api/health') return new Promise((resolve, reject) => healthRequests.push({resolve, reject}));
    if (options.method === 'POST') requests.push({url, options});
    return Promise.resolve({ok: true, json: async () => url.startsWith('/api/inspect/') ? {requirements: [], nodes: [], graph: {}} : {}});
  },
});

const state = () => JSON.parse(vm.runInContext('JSON.stringify({online,schemaAvailable,healthError:typeof healthError===\'undefined\'?false:healthError,disabled:$(\'#generate\').disabled,text:$(\'#health\').textContent,className:$(\'#health\').className})', context));
const respondHealth = async payload => {
  const request = healthRequests.shift();
  assert.ok(request, 'health request is pending');
  request.resolve({ok: true, json: async () => payload});
};

(async () => {
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8'), context);
  vm.runInContext("selected={id:'ready'};updateReady();", context);
  assert.deepEqual(state(), {online: null, schemaAvailable: false, healthError: false, disabled: true, text: 'Checking ComfyUI…', className: 'pill '}, 'pending startup is neutral and cannot submit');

  let pending = vm.runInContext('health()', context); await Promise.resolve();
  await respondHealth({online: true, schema_available: true, missing_models: {}}); await pending;
  assert.deepEqual(state(), {online: true, schemaAvailable: true, healthError: false, disabled: false, text: 'ComfyUI connected', className: 'pill ready'}, 'online health response enables a ready preset');

  pending = vm.runInContext('health()', context); await Promise.resolve();
  await respondHealth({online: false, schema_available: false, missing_models: {}}); await pending;
  assert.deepEqual(state(), {online: false, schemaAvailable: false, healthError: false, disabled: true, text: 'ComfyUI offline', className: 'pill offline'}, 'known offline remains explicit and blocked');

  pending = vm.runInContext('health()', context); await Promise.resolve();
  const failed = healthRequests.shift(); assert.ok(failed, 'failed health request is pending'); failed.reject(Error('network unavailable')); await pending;
  assert.deepEqual(state(), {online: null, schemaAvailable: false, healthError: true, disabled: true, text: 'Readiness unavailable', className: 'pill offline'}, 'request failure is unavailable, not a false offline claim');

  pending = vm.runInContext('health()', context); await Promise.resolve();
  await respondHealth({online: true, schema_available: true, missing_models: {}}); await pending;
  assert.equal(state().disabled, false, 'a later healthy response recovers readiness');

  pending = vm.runInContext('health()', context); await Promise.resolve();
  await respondHealth({online: true, schema_available: false, missing_models: {}}); await pending;
  assert.equal(state().disabled, true, 'missing node schema still blocks generation');
  assert.equal(state().text, 'Checking node readiness');

  pending = vm.runInContext('health()', context); await Promise.resolve();
  await respondHealth({online: true, schema_available: true, missing_models: {ready: ['required-model.safetensors']}}); await pending;
  assert.equal(state().disabled, true, 'missing recipe models still block generation');
  assert.equal(state().text, 'Recipe needs models');
  assert.equal(requests.some(request => request.url === '/api/jobs'), false, 'readiness checks never submit a job');
  console.log('Readiness status distinguishes pending, offline, unavailable, and ready states without job submission.');
})().catch(error => { console.error(error); process.exitCode = 1; });
