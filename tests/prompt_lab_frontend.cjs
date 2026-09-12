// Run the actual page startup, including asynchronous profile response handling.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function startup(ok) {
  const elements = new Map(), requests = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', textContent: '', children: [],
      addEventListener() {}, append(child) { this.children.push(child); },
    });
    return elements.get(id);
  }
  const context = vm.createContext({
    document: {getElementById: element, createElement: () => ({})},
    fetch: async url => {
      requests.push(url);
      return {ok, json: async () => ok
        ? {profiles: [{id: 'sdxl-prose-v1', name: 'SDXL prose', tasks: ['image']}]}
        : {error: 'Profile registry unavailable'}};
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/prompt-lab.js'), 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(requests, ['/api/prompt/profiles'], 'Page startup must not submit generation');
  if (ok) {
    assert.equal(element('profile').children.length, 1, 'Successful response populates target profiles');
    assert.equal(element('profile').children[0].value, 'sdxl-prose-v1');
    assert.equal(element('status').textContent, '');
  } else {
    assert.equal(element('profile').children.length, 0);
    assert.match(element('status').textContent, /Profile registry unavailable/);
  }
}
async function metadataResponses() {
  const elements = new Map(), pending = [], requests = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', textContent: '', children: [], listeners: {},
      addEventListener(type, fn) { this.listeners[type] = fn; },
      append(child) { this.children.push(child); },
    });
    return elements.get(id);
  }
  const context = vm.createContext({
    document: {getElementById: element, createElement: () => ({})},
    btoa: s => Buffer.from(s, 'binary').toString('base64'),
    fetch: (url, options) => {
      requests.push({url, options});
      if (url === '/api/prompt/profiles') return Promise.resolve({ok: true, json: async () => ({profiles: []})});
      return new Promise(resolve => pending.push(resolve));
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/prompt-lab.js'), 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  const choose = (text, size = 10) => element('png-file').listeners.change({target: {files: [
    {size, arrayBuffer: async () => Uint8Array.from(Buffer.from(text)).buffer},
  ]}});
  const older = choose('old'), newer = choose('new');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(pending.length, 2);
  assert.equal(JSON.parse(requests[2].options.body).media_base64, Buffer.from('new').toString('base64'));
  pending[1]({ok: true, json: async () => ({marker: 'newer', workflow_executed: false})});
  await newer;
  pending[0]({ok: true, json: async () => ({marker: 'older'})});
  await older;
  assert.equal(JSON.parse(element('metadata').textContent).marker, 'newer', 'Late response must not replace newer evidence');
  const lateError = choose('broken');
  await new Promise(resolve => setImmediate(resolve));
  await choose('too large', 650001);
  const errorText = element('metadata').textContent;
  assert.match(errorText, /650 KB/);
  pending[2]({ok: false, json: async () => ({error: 'late parse failure'})});
  await lateError;
  assert.equal(element('metadata').textContent, errorText, 'Late error must not replace current selection feedback');
  assert.deepEqual(requests.map(r => r.url), ['/api/prompt/profiles', ...Array(3).fill('/api/prompt/metadata')]);
  assert.equal(pending.length, 3, 'Oversize selection must not upload');
}
// Terminal line: its absence is how the Python wrapper tells a stalled chain from a completed run.
startup(true).then(() => startup(false)).then(metadataResponses)
  .then(() => console.log('Prompt Lab frontend contracts passed: profile startup, HTTP failure reporting and metadata selection.'))
  .catch(error => { console.error(error); process.exitCode = 1; });
