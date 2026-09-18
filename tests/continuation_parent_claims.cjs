const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(require.resolve('../app/static/app.js'), 'utf8');

function functionSource(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} must remain available to the Create lineage owner`);
  const brace = app.indexOf('{', start);
  let depth = 0;
  for (let index = brace; index < app.length; index += 1) {
    if (app[index] === '{') depth += 1;
    else if (app[index] === '}' && --depth === 0) return app.slice(start, index + 1);
  }
  throw new Error(`Could not read ${name}`);
}

function harness(withSlots = true) {
  const context = vm.createContext({});
  vm.runInContext([
    'let parentAssets=[],parentByInput={},attached=[];',
    `const selected={reference_slots:${withSlots ? '[{}]' : '[]'}};`,
    'const attachedReferencePayload=()=>attached;',
    functionSource('parentClaimed'),
    functionSource('releaseParentAsset'),
    functionSource('releaseInputParent'),
    functionSource('claimInputParent'),
    'this.claim=(input,id)=>claimInputParent(input,id);',
    'this.attach=value=>{attached=value};',
    'this.release=id=>releaseParentAsset(id);',
    'this.releaseInput=input=>releaseInputParent(input);',
    'this.snapshot=()=>JSON.stringify({parentAssets,parentByInput});',
  ].join('\n'), context);
  return {
    claim: context.claim,
    attach: context.attach,
    release: context.release,
    releaseInput: context.releaseInput,
    snapshot: () => JSON.parse(context.snapshot()),
  };
}

test('a board continuation source survives clearing a same-asset role slot', () => {
  const state = harness(true);
  state.claim('lastReference', 'asset-a');
  assert.deepEqual(state.snapshot(), {
    parentAssets: ['asset-a'],
    parentByInput: {lastReference: 'asset-a'},
  });

  state.attach([{file: 'board.png', missing: false, parent_asset: 'asset-a'}]);
  state.attach([]);
  state.release('asset-a');
  assert.deepEqual(state.snapshot(), {
    parentAssets: ['asset-a'],
    parentByInput: {lastReference: 'asset-a'},
  }, 'the distinct continuation source still owns the lineage claim');

  state.releaseInput('lastReference');
  assert.deepEqual(state.snapshot(), {parentAssets: [], parentByInput: {}});
});

test('a role-slot reference continues to use the slot record as its claim', () => {
  const state = harness(true);
  state.claim('reference', 'asset-a');
  assert.deepEqual(state.snapshot(), {parentAssets: ['asset-a'], parentByInput: {}});
  state.release('asset-a');
  assert.deepEqual(state.snapshot(), {parentAssets: [], parentByInput: {}});
});

test('slot-less inputs retain their existing named claims', () => {
  const state = harness(false);
  state.claim('reference', 'asset-a');
  state.claim('lastReference', 'asset-b');
  assert.deepEqual(state.snapshot(), {
    parentAssets: ['asset-a', 'asset-b'],
    parentByInput: {reference: 'asset-a', lastReference: 'asset-b'},
  });
});
