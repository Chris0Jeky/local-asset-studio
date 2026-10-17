'use strict';
// shapeSize + applyTune contracts: sliced from app/static/make.js by function markers with node:vm.
// Never edit app/static/make.js; this file only reads it.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, '../app/static/make.js'), 'utf8');
function slice(start, end) {
  const s = src.indexOf(start);
  assert.ok(s >= 0, 'missing start marker: ' + start);
  const e = src.indexOf(end, s + start.length);
  assert.ok(e > s, 'missing end marker: ' + end);
  return src.slice(s, e);
}
const shapeSrc = slice('  function shapeSize(preset,look,shape){', '\n  const shapeDefault=');
const applySrc = slice('  function applyTune(controls,look,t){', '\n  function renderTune(){');
const scaleSrc = slice('  const scaleOf=t=>t?.scale??100', '\n  function paintScale(t){');
const tokenSrc = slice('  const hasToken=(text,word)=>', '\n  const freeSlot=');

function env(presetsList, knowledge) {
  const context = {PRESETS: presetsList, knowledge};
  vm.createContext(context);
  vm.runInContext(
    'const presets=()=>PRESETS;\n' +
    "const SLOTS=['lora','lora2','lora3','lora4','lora5','lora6'];\n" +
    "const NAMED=k=>k+'_name';\n" +
    'const bound=(p,k)=>!!(p?.[k]||p?.bindings_extra?.[k]);\n' +
    'const byId=id=>presets().find(p=>p.id===id);\n' +
    'const presetFor=look=>presets().find(p=>p.id===look?.body?.preset_id);\n' +
    "const kb=()=>typeof knowledge!=='undefined'&&knowledge||{};\n" +
    'const entry=name=>name&&kb().loras?.[name]||null;\n' +
    scaleSrc + '\n' + tokenSrc + '\n' + shapeSrc + '\n' + applySrc,
    context
  );
  return {
    shapeSize(preset, look, shape) {
      context._preset = preset;
      context._look = look;
      context._shape = shape;
      return JSON.parse(vm.runInContext('JSON.stringify(shapeSize(_preset,_look,_shape))', context));
    },
    apply(controls, look, tune) {
      context.controls = controls;
      context.look = look;
      context.tune = tune;
      const id = vm.runInContext('applyTune(controls,look,tune)', context);
      return {id, controls: JSON.parse(vm.runInContext('JSON.stringify(controls)', context))};
    },
  };
}

function basePreset(over = {}) {
  return {
    id: 'base', family: 'Anima',
    defaults: {width: 832, height: 1216}, dimension_multiple: 64,
    lora: ['1', 'lora'], lora_name: ['1', 'text'],
    lora2: ['1', 'lora'], lora2_name: ['1', 'text'],
    steps: ['1', 'steps'], sampler: ['1', 'sampler'], negative: ['1', 'text'], seed: ['1', 'seed'],
    ...over,
  };
}
const otherPreset = () => basePreset({id: 'other'});
const lookFor = (presetId, controls) => ({id: 'look-1', body: {preset_id: presetId, controls: {...controls}}});
const tuneFor = (presetId, rows, extra = {}) => ({
  preset: presetId, rows, cleared: [], steps: null, sampler: '', negative: null, scale: 100, reseed: true, ...extra,
});
const KNOWLEDGE = {
  loras: {
    'fern-style.safetensors': {trigger: 'fern, moss', trigger_position: 'end', family: 'Anima'},
    'dawn-style.safetensors': {trigger: 'sunlit', trigger_position: 'start', family: 'Anima'},
  },
};

// shapeSize

test('design returns the authored width and height verbatim', () => {
  const h = env([basePreset()], {});
  assert.deepEqual(h.shapeSize(basePreset(), lookFor('base', {width: 832, height: 1216}), 'design'), [832, 1216]);
});

test('portrait keeps a portrait authored size; landscape swaps it', () => {
  const h = env([basePreset()], {});
  const preset = basePreset();
  assert.deepEqual(h.shapeSize(preset, lookFor('base', {width: 832, height: 1216}), 'portrait'), [832, 1216]);
  assert.deepEqual(h.shapeSize(preset, lookFor('base', {width: 832, height: 1216}), 'landscape'), [1216, 832]);
});

test('portrait swaps a landscape authored size; landscape keeps it', () => {
  const h = env([basePreset()], {});
  const preset = basePreset();
  assert.deepEqual(h.shapeSize(preset, lookFor('base', {width: 1216, height: 832}), 'portrait'), [832, 1216]);
  assert.deepEqual(h.shapeSize(preset, lookFor('base', {width: 1216, height: 832}), 'landscape'), [1216, 832]);
});

test('square rounds sqrt(area) to the model multiple', () => {
  const h = env([basePreset()], {});
  assert.deepEqual(h.shapeSize(basePreset(), lookFor('base', {width: 832, height: 1216}), 'square'), [1024, 1024]);
});

test('square-authored portrait synthesizes a 3:2 pair on the grid', () => {
  const h = env([basePreset()], {});
  const preset = basePreset();
  const portrait = h.shapeSize(preset, lookFor('base', {width: 1000, height: 1000}), 'portrait');
  const landscape = h.shapeSize(preset, lookFor('base', {width: 1000, height: 1000}), 'landscape');
  assert.deepEqual(portrait, [832, 1216]);
  assert.deepEqual(landscape, [1216, 832]);
});

test('a custom dimension_multiple changes the rounding grid', () => {
  const h = env([basePreset()], {});
  const preset = basePreset({dimension_multiple: 16});
  assert.deepEqual(h.shapeSize(preset, lookFor('base', {width: 1000, height: 1000}), 'portrait'), [816, 1232]);
});

test('missing widths fall back to 1024 with a 64 grid', () => {
  const h = env([{id: 'bare'}], {});
  assert.deepEqual(h.shapeSize({id: 'bare'}, lookFor('bare', {}), 'design'), [1024, 1024]);
  assert.deepEqual(h.shapeSize(null, lookFor('bare', {}), 'design'), [1024, 1024]);
});

test('tiny pictures clamp up to one grid cell; unknown shapes order like landscape', () => {
  const h = env([basePreset()], {});
  assert.deepEqual(h.shapeSize(basePreset(), lookFor('base', {width: 8, height: 8}), 'square'), [64, 64]);
  assert.deepEqual(h.shapeSize(basePreset(), lookFor('base', {width: 832, height: 1216}), 'panorama'), [1216, 832]);
});

// applyTune

test('a tuned adapter strength and filename land in the controls', () => {
  const h = env([basePreset()], KNOWLEDGE);
  const {id, controls} = h.apply(
    {lora: 0, lora_name: '', positive: 'a garden'},
    lookFor('base', {lora: 0.8, lora_name: 'orig.safetensors'}),
    tuneFor('base', [{slot: 'lora', name: 'orig.safetensors', strength: 0.9, on: true}])
  );
  assert.equal(id, 'base');
  assert.equal(controls.lora, 0.9);
  assert.equal(controls.lora_name, 'orig.safetensors');
});

test('style scale multiplies the sent strength; a switched-off row sends 0', () => {
  const h = env([basePreset()], KNOWLEDGE);
  const scaled = h.apply(
    {lora: 0, positive: 'a garden'},
    lookFor('base', {}),
    tuneFor('base', [{slot: 'lora', name: 'orig.safetensors', strength: 1, on: true}], {scale: 150})
  );
  assert.equal(scaled.controls.lora, 1.5);
  const off = h.apply(
    {lora: 0.8, positive: 'a garden'},
    lookFor('base', {}),
    tuneFor('base', [{slot: 'lora', name: 'orig.safetensors', strength: 1, on: false}])
  );
  assert.equal(off.controls.lora, 0);
});

test('tuned steps land when bound; null steps leave the prepared value alone', () => {
  const h = env([basePreset()], KNOWLEDGE);
  const set = h.apply({steps: 30}, lookFor('base', {}), tuneFor('base', [], {steps: 40}));
  assert.equal(set.controls.steps, 40);
  const kept = h.apply({steps: 30}, lookFor('base', {}), tuneFor('base', [], {steps: null}));
  assert.equal(kept.controls.steps, 30);
});

test('sampler and negative land when bound; an empty sampler leaves the value alone', () => {
  const h = env([basePreset()], KNOWLEDGE);
  const set = h.apply(
    {sampler: 'dpm', negative: 'old'},
    lookFor('base', {}),
    tuneFor('base', [], {sampler: 'euler', negative: 'blurry'})
  );
  assert.equal(set.controls.sampler, 'euler');
  assert.equal(set.controls.negative, 'blurry');
  const kept = h.apply({sampler: 'dpm'}, lookFor('base', {}), tuneFor('base', [], {sampler: ''}));
  assert.equal(kept.controls.sampler, 'dpm');
});

test('an added end trigger is appended once and a second apply adds nothing', () => {
  const h = env([basePreset()], KNOWLEDGE);
  const tune = tuneFor('base', [{slot: 'lora', name: 'fern-style.safetensors', strength: 0.5, on: true, added: true}]);
  const first = h.apply({lora: 0, positive: 'a garden'}, lookFor('base', {}), structuredClone(tune));
  assert.equal(first.controls.positive, 'a garden, fern, moss');
  const second = h.apply({lora: 0, positive: first.controls.positive}, lookFor('base', {}), structuredClone(tune));
  assert.equal(second.controls.positive, 'a garden, fern, moss');
});

test('a start trigger prepends; a word already present is not repeated', () => {
  const h = env([basePreset()], KNOWLEDGE);
  const start = h.apply(
    {lora: 0, positive: 'a garden'},
    lookFor('base', {}),
    tuneFor('base', [{slot: 'lora', name: 'dawn-style.safetensors', strength: 0.5, on: true, added: true}])
  );
  assert.equal(start.controls.positive, 'sunlit, a garden');
  const deduped = h.apply(
    {lora: 0, positive: 'fern garden'},
    lookFor('base', {}),
    tuneFor('base', [{slot: 'lora', name: 'fern-style.safetensors', strength: 0.5, on: true, added: true}])
  );
  assert.equal(deduped.controls.positive, 'fern garden, moss');
});

test('the look’s own adapter never writes its trigger word', () => {
  const h = env([basePreset()], KNOWLEDGE);
  const {controls} = h.apply(
    {lora: 0, positive: 'a garden'},
    lookFor('base', {}),
    tuneFor('base', [{slot: 'lora', name: 'fern-style.safetensors', strength: 0.5, on: true}])
  );
  assert.equal(controls.positive, 'a garden');
});

test('a cleared row is zeroed on the same model; an uncleared slot is left alone', () => {
  const h = env([basePreset()], KNOWLEDGE);
  const {controls} = h.apply(
    {lora: 0.8, lora2: 0.5},
    lookFor('base', {lora: 0.8, lora2: 0.5}),
    tuneFor('base', [], {cleared: ['lora']})
  );
  assert.equal(controls.lora, 0);
  assert.equal(controls.lora2, 0.5);
});

test('a switched model zeroes every bound slot and returns the new preset id', () => {
  const h = env([basePreset(), otherPreset()], KNOWLEDGE);
  const {id, controls} = h.apply({lora: 0.8, lora2: 0.6}, lookFor('base', {lora: 0.8, lora2: 0.6}), tuneFor('other', []));
  assert.equal(id, 'other');
  assert.equal(controls.lora, 0);
  assert.equal(controls.lora2, 0, 'every bound slot, not only the first');
});

test('applyTune preserves the prepared seed', () => {
  const h = env([basePreset()], KNOWLEDGE);
  const {controls} = h.apply(
    {lora: 0, seed: 123, positive: 'a garden'},
    lookFor('base', {}),
    tuneFor('base', [{slot: 'lora', name: 'orig.safetensors', strength: 0.9, on: true}], {steps: 40})
  );
  assert.equal(controls.seed, 123);
});
