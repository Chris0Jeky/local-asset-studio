'use strict';
// Save a tune as a look (#1847): the shipped Make functions run in node:vm, sliced from app/static/make.js by marker; the Studio, the page and the network are doubles.
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
const listSrc = slice('  const tunedFrom=', '\n  const current=');
const scaleSrc = slice('  const scaleOf=t=>t?.scale??100', '\n  function paintScale(t){');
const tokenSrc = slice('  const hasToken=(text,word)=>', '\n  const freeSlot=');
const applySrc = slice('  function applyTune(controls,look,t){', '\n  function renderTune(){');
const saveSrc = slice('  function tunedLookBody(', '\n  // Compare one setting (#1496)');

const preset = (over = {}) => ({
  id: 'anima', family: 'Anima', name: 'Anima',
  lora: ['1', 'lora'], lora_name: ['1', 'text'], lora2: ['1', 'lora'], lora2_name: ['1', 'text'],
  steps: ['1', 'steps'], sampler: ['1', 'sampler'], negative: ['1', 'text'], seed: ['1', 'seed'], choices: {sampler: ['euler', 'dpmpp']}, ...over,
});
const KNOWLEDGE = {loras: {'dawn.safetensors': {trigger: 'sunlit', trigger_position: 'end', family: 'Anima'}}};
const baseLook = () => ({
  id: 'look-base', name: 'Base look', revision: 3, kind: 'look', usable: true,
  body: {preset_id: 'anima', template: 'masterpiece, {scene}, soft light', negative: 'blurry', scene_example: 'a fox',
    controls: {steps: 30, sampler: 'euler', seed: 5, lora: 0.8, lora_name: 'fern.safetensors'}},
});
const tune = (over = {}) => ({preset: 'anima', rows: [{slot: 'lora', name: 'fern.safetensors', strength: 0.8, on: true}], cleared: [], steps: null, sampler: '', negative: null, seed: null, reseed: true, scale: 100, ...over});

function fixture({privacy = 'regular', refuse = null, installed = null} = {}) {
  const calls = [], els = {};
  for (const id of ['#makeSaveForm', '#makeSaveOpen', '#makeSaveName', '#makeSaveNotes', '#makeSaveMsg', '#makeSaveGo'])
    els[id] = {value: '', textContent: '', hidden: true, disabled: false, isConnected: true, focus() {}, setAttribute() {}};
  let n = 0, release = null;
  const context = {
    structuredClone, Error, String, Object, Array, JSON, PRESETS: [preset()], knowledge: KNOWLEDGE, calls, els, said: [], installedLoras: installed || [],
    state: {looks: [baseLook()], tune: {}, goal: 'character'}, privacyEpoch: 0,
    GOALS: [{id: 'character', name: 'Anime character', looks: ['look-base']}],
    requestPrivacy: () => ({scope: 'regular', privacy}),
    json: async (url, body) => {
      body = JSON.parse(JSON.stringify(body)); calls.push({url, body});
      if (release) await release.promise;
      if (refuse) throw Error(refuse);
      return {id: 'saved-' + (++n), kind: 'look', revision: 0, origin: 'owner', name: body.name, body: body.body, lineage: body.lineage};
    },
    q: s => els[s],
  };
  vm.createContext(context);
  vm.runInContext([
    'const presets=()=>PRESETS;',
    "const SLOTS=['lora','lora2','lora3','lora4','lora5','lora6'];",
    "const NAMED=k=>k+'_name';",
    'const bound=(p,k)=>!!(p?.[k]||p?.bindings_extra?.[k]);',
    'const byId=id=>presets().find(p=>p.id===id);',
    'const presetFor=look=>presets().find(p=>p.id===look?.body?.preset_id);',
    "const kb=()=>typeof knowledge!=='undefined'&&knowledge||{};",
    'const entry=name=>name&&kb().loras?.[name]||null;',
    'const compatible=()=>[];',
    'const goal=()=>GOALS.find(g=>g.id===state.goal);',
    'const current=()=>state.looks.find(l=>l.id===state.look)||null;',
    'const say=text=>{said.push(text);};',
    'const tuneOf=look=>state.tune[look.id];',
    scaleSrc, tokenSrc, applySrc, listSrc, saveSrc,
  ].join('\n'), context);
  const run = code => vm.runInContext(code, context);
  return {
    context, calls, els, run,
    hold() { let resolve; const promise = new Promise(r => { resolve = r; }); release = {promise}; return () => resolve(); },
    // The page's Save press: name and notes typed, then the shipped handler.
    async press(look, tuneValue, name, notes = '') {
      context.state.look = look.id; context.state.tune[look.id] = tuneValue;
      els['#makeSaveName'].value = name; els['#makeSaveNotes'].value = notes;
      return run('saveLookUi("go")');
    },
    ids: () => run('lookList().map(l=>l.id)'),
  };
}

test('the save carries the base look and the exact tuned controls, and never the scene', async () => {
  const f = fixture();
  const t = tune({rows: [{slot: 'lora', name: 'fern.safetensors', strength: 1.2, on: true}, {slot: 'lora2', name: 'dawn.safetensors', strength: 0.5, on: true, added: true}], steps: 18, sampler: 'dpmpp', negative: 'extra fingers', reseed: false, seed: 77});
  await f.press(f.context.state.looks[0], t, '  Fern at full  ', 'More leaf detail');
  assert.equal(f.calls.length, 1);
  const {url, body} = f.calls[0];
  assert.equal(url, '/api/looks');
  assert.equal(body.action, 'create'); assert.equal(body.kind, 'look'); assert.equal(body.name, 'Fern at full');
  assert.deepEqual(body.body.controls, {steps: 18, sampler: 'dpmpp', seed: 77, lora: 1.2, lora_name: 'fern.safetensors', lora2: 0.5, lora2_name: 'dawn.safetensors'});
  assert.equal(body.body.preset_id, 'anima');
  assert.equal(body.body.template, 'masterpiece, {scene}, soft light, sunlit', 'an added LoRA’s trigger joins the wording; the scene stays a slot');
  assert.equal(body.body.template.split('{scene}').length, 2);
  assert.equal(body.body.negative, 'extra fingers'); assert.equal(body.body.notes, 'More leaf detail'); assert.equal(body.body.scene_example, 'a fox');
  assert.equal('positive' in body.body.controls, false);
  assert.deepEqual(body.lineage.map(({role, tuned_from, tuned_root}) => ({role, tuned_from, tuned_root})), [{role: 'evidence', tuned_from: 'look-base', tuned_root: 'look-base'}]);
  assert.match(f.els['#makeSaveMsg'].textContent + f.context.said.join(), /Saved .Fern at full./);
});

test('two tunes of one base saved under two names come back as two picker entries for the goal', async () => {
  const f = fixture(), base = f.context.state.looks[0];
  await f.press(base, tune({steps: 12}), 'Quick');
  await f.press(base, tune({steps: 40, rows: [{slot: 'lora', name: 'fern.safetensors', strength: 0.3, on: true}]}), 'Slow and soft');
  assert.deepEqual(f.ids(), ['look-base', 'saved-1', 'saved-2']);
  const [quick, slow] = f.context.state.looks.slice(1);
  assert.equal(quick.body.controls.steps, 12); assert.equal(slow.body.controls.steps, 40);
  assert.equal(quick.body.controls.lora, 0.8); assert.equal(slow.body.controls.lora, 0.3);
  // A tune of a saved look still lists in the root's goal.
  await f.press(quick, {...tune({steps: 8}), preset: 'anima'}, 'Quicker');
  assert.equal(f.calls[2].body.lineage[0].tuned_from, 'saved-1'); assert.equal(f.calls[2].body.lineage[0].tuned_root, 'look-base');
  assert.deepEqual(f.ids(), ['look-base', 'saved-1', 'saved-2', 'saved-3']);
  // A put-away saved look leaves the picker.
  f.context.state.looks.find(l => l.id === 'saved-2').trashed_at = 1;
  assert.deepEqual(f.ids(), ['look-base', 'saved-1', 'saved-3']);
});

test('saving sends no job and no prepare request', async () => {
  const f = fixture();
  await f.press(f.context.state.looks[0], tune({steps: 12}), 'Quick');
  assert.deepEqual(f.calls.map(c => c.url), ['/api/looks']);
});

test('a refusal, a name clash, a blank name and a private creation each give a plain message and a look is only added when saved', async () => {
  const refused = fixture({refuse: 'Look controls must be an object of up to 40 settings'});
  await refused.press(refused.context.state.looks[0], tune(), 'Whatever');
  assert.equal(refused.els['#makeSaveMsg'].textContent, 'Look controls must be an object of up to 40 settings');
  assert.equal(refused.context.state.looks.length, 1); assert.equal(refused.els['#makeSaveGo'].disabled, false);

  const clash = fixture();
  await clash.press(clash.context.state.looks[0], tune(), ' base LOOK ');
  assert.match(clash.els['#makeSaveMsg'].textContent, /already exists/); assert.equal(clash.calls.length, 0);

  const blank = fixture();
  await blank.press(blank.context.state.looks[0], tune(), '   ');
  assert.equal(blank.els['#makeSaveMsg'].textContent, 'Name the look.'); assert.equal(blank.calls.length, 0);

  const hidden = fixture({privacy: 'private'});
  await hidden.press(hidden.context.state.looks[0], tune(), 'Secret');
  assert.match(hidden.els['#makeSaveMsg'].textContent, /private creation cannot save one/); assert.equal(hidden.calls.length, 0);
});

test('a second press while a save is in flight sends nothing', async () => {
  const f = fixture(), done = f.hold(), base = f.context.state.looks[0];
  const first = f.press(base, tune({steps: 12}), 'Quick');
  const second = f.press(base, tune({steps: 12}), 'Quick');
  await second; done(); await first;
  assert.equal(f.calls.length, 1);
  assert.equal(f.context.state.looks.length, 2);
});

test('an added LoRA that is no longer installed is left out of the saved look, and the owner is told', async () => {
  const f = fixture({installed: ['fern.safetensors', 'dawn.safetensors']});
  const t = tune({rows: [{slot: 'lora', name: 'fern.safetensors', strength: 0.8, on: true}, {slot: 'lora2', name: 'gone.safetensors', strength: 0.6, on: true, added: true}]});
  await f.press(f.context.state.looks[0], t, 'Without the missing one');
  const {controls} = f.calls[0].body.body;
  assert.deepEqual(Object.keys(controls).filter(k => k.startsWith('lora')).sort(), ['lora', 'lora_name']);
  assert.ok(!JSON.stringify(f.calls[0].body).includes('gone.safetensors'));
  assert.match(f.context.said.join(), /Left out gone from the saved look: no longer installed/);
  assert.ok(f.context.said.join().includes('Saved'));
});
