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
startup(true).then(() => startup(false)).catch(error => { console.error(error); process.exitCode = 1; });
