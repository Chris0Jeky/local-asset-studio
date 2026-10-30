// #1728: the Prompt Lab -> Create banner names its recipe on the button and offers matching recipes as chips.
// Slices the real banner region out of studio-workbench.js (no helper outside it) and runs it against a fake DOM.
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const read = name => fs.readFileSync(path.join(__dirname, '../app/static', name), 'utf8');
const workbench = read('studio-workbench.js');
const slice = (start, end) => {
  const a = workbench.indexOf(start), b = workbench.indexOf(end, a);
  assert.ok(a !== -1 && b > a, `missing marker ${start}`);
  return workbench.slice(a, b);
};
const region = slice("  const transfer=element('section','panel ux-transfer')", "  const jobInspector=element('dialog'");
const U = (() => { const m = { exports: {} }; vm.runInNewContext(read('studio-core.js'), { module: m, exports: m.exports, window: {} }); return m.exports; })();

const PRESETS = [{ id: 'a-one', name: 'Alpha <b>one</b>', positive: true, negative: true }, { id: 'b-two', name: 'Beta two', positive: true }];
function page({ recipes = ['a-one', 'b-two'], selectedId = 'b-two', presets = PRESETS } = {}) {
  const nodes = {}, announcements = [], network = [], stored = new Map();
  const node = () => ({ hidden: false, textContent: '', children: [], dataset: {}, attrs: {}, value: '', onclick: null,
    setAttribute(k, v) { this.attrs[k] = v; }, replaceChildren(...c) { this.children = c; }, after() {}, closest() { return this; } });
  const context = {
    q: sel => nodes[sel] || (nodes[sel] = node()),
    element: tag => node(), U, catalog: { presets }, selected: null, announce: (m, e) => announcements.push([m, !!e]),
    createHeading: { after() {} }, saveDraft() {}, syncReady() {}, renderDraftNotice() {}, showView: v => { context.shown = v; },
    api: async url => { network.push(url); return { workspace: 'w' }; }, post: (...a) => network.push(a), fetch: (...a) => network.push(a),
    sessionStorage: { getItem: k => stored.get(k) ?? null, removeItem: k => stored.delete(k) },
    setTimeout: () => 0, draftDirty: false, draftPrefix: '',
  };
  context.globalThis = context; vm.createContext(context);
  vm.runInContext([
    'function after(name,cb){const o=globalThis[name];globalThis[name]=function(...a){const r=o.apply(this,a);cb(...a);return r;};}',
    "function selectPreset(id){const next=catalog.presets.find(p=>p.id===id);if(!next)throw Error('This preset is unavailable.');selected=next;}",
    `selectPreset(${JSON.stringify(selectedId)});`,
    region,
    'this.run=initializeDrafts;',
  ].join('\n'), context);
  const handoff = { workspace: 'w', createdAt: Date.now(), transfer: { positive: 'A lantern', negative: 'blur', profile: 'p', recipes } };
  stored.set('studio-prompt-handoff', JSON.stringify(handoff));
  return { context, nodes, announcements, network, ready: context.run() };
}
const chips = p => p.nodes['#uxTransferRecipes'].children;

test('the apply button names the selected recipe, escaped as plain text', async () => {
  const p = page({ selectedId: 'a-one' }); await p.ready;
  assert.equal(p.nodes['#uxApplyPrompt'].textContent, 'Apply to Alpha <b>one</b>');
  assert.equal(chips(p)[0].textContent, 'Alpha <b>one</b>', 'names go through textContent, never markup');
  assert.doesNotMatch(region, /innerHTML=[^;]*\.name/, 'recipe names are never concatenated into innerHTML');
});

test('matching recipes are chips and the selected one is pressed', async () => {
  const p = page(); await p.ready;
  assert.deepEqual(chips(p).map(c => c.textContent), ['Alpha <b>one</b>', 'Beta two']);
  assert.deepEqual(chips(p).map(c => c.attrs['aria-pressed']), ['false', 'true']);
  assert.equal(p.nodes['#uxTransferRecipes'].hidden, false);
  assert.equal(p.nodes['#uxApplyPrompt'].textContent, 'Apply to Beta two');
});

test('a chip switches Create through the existing selectPreset and moves the pressed state and label', async () => {
  const p = page(); await p.ready;
  p.nodes['#uxTransferRecipes'].onclick({ target: { closest: () => chips(p)[0] } });
  assert.equal(p.context.selected.id, 'a-one');
  assert.deepEqual(chips(p).map(c => c.attrs['aria-pressed']), ['true', 'false']);
  assert.equal(p.nodes['#uxApplyPrompt'].textContent, 'Apply to Alpha <b>one</b>');
  assert.equal(vm.runInContext('transfer.hidden', p.context), false, 'the banner stays open until applied');
  assert.deepEqual(p.network, ['/api/identity'], 'switching a recipe sends no request');
});

test('the selected chip does nothing, and an unavailable recipe is announced instead of thrown', async () => {
  const p = page({ recipes: ['b-two', 'gone'] }); await p.ready;
  let calls = 0; const wrapped = p.context.selectPreset; p.context.selectPreset = (...a) => { calls++; return wrapped(...a); };
  p.nodes['#uxTransferRecipes'].onclick({ target: { closest: () => chips(p)[0] } });
  assert.equal(calls, 0, 'the active chip does not reset the form');
  p.nodes['#uxTransferRecipes'].onclick({ target: { closest: () => chips(p)[1] } });
  assert.deepEqual(p.announcements, [['This preset is unavailable.', true]]);
  assert.equal(p.context.selected.id, 'b-two');
});

test('no recipes named means no chip row', async () => {
  const p = page({ recipes: [] }); await p.ready;
  assert.equal(p.nodes['#uxTransferRecipes'].hidden, true);
});

test('the compiler/executor wording is gone and the generate safety stays', async () => {
  const p = page(); await p.ready;
  const shown = p.nodes['#uxTransferNotice'].textContent;
  assert.match(shown, /Nothing is generated until you press Generate/);
  for (const text of [shown, region, fs.readFileSync(path.join(__dirname, '../app/static/studio-core.js'), 'utf8')]) {
    assert.doesNotMatch(text, /executor bindings|compiler settings|selects nothing/i);
  }
});

test('applying and switching never submit a job or fetch anything', async () => {
  const p = page(); await p.ready;
  p.nodes['#uxTransferRecipes'].onclick({ target: { closest: () => chips(p)[0] } });
  p.nodes['#positive'] = { value: '' }; p.nodes['#negative'] = { value: '' };
  p.nodes['#uxApplyPrompt'].onclick();
  assert.equal(p.nodes['#positive'].value, 'A lantern');
  assert.deepEqual(p.network, ['/api/identity']);
});

test('a keyboard chip switch keeps focus on the newly chosen chip after the row is rebuilt', async () => {
  const p = page(); await p.ready;
  const focused = [];p.context.document = { activeElement: { closest: sel => sel === '#uxTransferRecipes' } };
  p.context.element = () => { const n = { hidden: false, textContent: '', children: [], dataset: {}, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, focus() { focused.push(this.dataset.recipe); } }; return n; };
  p.nodes['#uxTransferRecipes'].onclick({ target: { closest: () => ({ dataset: { recipe: 'a-one' } }) } });
  assert.deepEqual(focused, ['a-one']);
  p.context.document = { activeElement: { closest: () => false } };focused.length = 0;
  p.nodes['#uxTransferRecipes'].onclick({ target: { closest: () => ({ dataset: { recipe: 'b-two' } }) } });
  assert.deepEqual(focused, [], 'focus is not stolen when it was elsewhere');
});
