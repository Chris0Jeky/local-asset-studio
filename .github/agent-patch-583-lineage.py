from __future__ import annotations

import argparse
from pathlib import Path

SOURCE = Path('app/static/app.js')
TEST = Path('tests/continuation_parent_claims.cjs')

TEST_CONTENT = r'''const assert = require('node:assert/strict');
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
'''

OLD_COMMENT = "// Lineage is attributed per attachment point. A slot-less input records its source in parentByInput;\n// a role slot records it on the reference record itself (parent_asset, supplied by\n"
NEW_COMMENT = "// Lineage is attributed per attachment point. A slot-less input and a board's distinct lastReference\n// source record their claim in parentByInput; a role slot records it on its reference record (parent_asset, supplied by\n"
OLD_FUNCTION = "function claimInputParent(input, id) { releaseInputParent(input); if(!id)return; if(!selected?.reference_slots?.length)parentByInput[input]=id; if(!parentAssets.includes(id))parentAssets=[...parentAssets,id]; }"
NEW_FUNCTION = "function claimInputParent(input, id) { releaseInputParent(input); if(!id)return; if(!selected?.reference_slots?.length||input==='lastReference')parentByInput[input]=id; if(!parentAssets.includes(id))parentAssets=[...parentAssets,id]; }"


def add_test() -> None:
    if not TEST.exists():
        TEST.write_text(TEST_CONTENT.rstrip() + '\n', encoding='utf-8')


def add_implementation() -> None:
    source = SOURCE.read_text(encoding='utf-8')
    if NEW_FUNCTION in source:
        return
    if source.count(OLD_FUNCTION) != 1 or source.count(OLD_COMMENT) != 1:
        raise SystemExit('lineage source marker changed')
    source = source.replace(OLD_COMMENT, NEW_COMMENT).replace(OLD_FUNCTION, NEW_FUNCTION)
    SOURCE.write_text(source, encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-only', action='store_true')
    parser.add_argument('--implementation', action='store_true')
    args = parser.parse_args()
    if args.test_only == args.implementation:
        raise SystemExit('choose exactly one mode')
    add_test()
    if args.implementation:
        add_implementation()


if __name__ == '__main__':
    main()
