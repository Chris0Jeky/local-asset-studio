// Run the actual page startup, including asynchronous profile response handling.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const StudioUX = require('../app/static/studio-core.js');

const SOURCE = fs.readFileSync(path.join(__dirname, '../app/static/prompt-lab.js'), 'utf8');
const PROFILES = JSON.parse(fs.readFileSync(path.join(__dirname, '../research/prompt-studio/profiles.json'), 'utf8')).profiles;

// Node stub with only the surface the page actually touches, so a missing guard fails loudly.
function makeNode(tag = 'div') {
  return {
    tag, value: '', textContent: '', className: '', hidden: false, disabled: false, children: [], listeners: {},
    addEventListener(type, fn) { this.listeners[type] = fn; },
    append(...nodes) { for (const child of nodes) this.children.push(child); },
    replaceChildren(...nodes) { this.children = [...nodes]; },
    querySelectorAll() { return []; },
    get text() { return [this.textContent, ...this.children.map(c => c.text ?? '')].join(' '); },
  };
}

function makeStorage(initial = {}) {
  const data = {...initial};
  return {
    getItem: k => (k in data ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v); },
    removeItem: k => { delete data[k]; },
    _data: data,
  };
}

function harness({profiles = PROFILES, compile = null, ok = true, timers = false, storage = null} = {}) {
  const elements = new Map(), requests = [];
  const element = id => { if (!elements.has(id)) elements.set(id, makeNode()); return elements.get(id); };
  const context = vm.createContext({
    ...(timers ? {setTimeout, clearTimeout} : {}),
    ...(storage ? {localStorage: storage} : {}),
    StudioUX,
    document: {getElementById: element, createElement: makeNode},
    btoa: s => Buffer.from(s, 'binary').toString('base64'),
    fetch: async (url, options) => {
      requests.push({url, options});
      if (url === '/api/prompt/profiles') return {ok, json: async () => ok ? {profiles} : {error: 'Profile registry unavailable'}};
      if (url === '/api/prompt/compile') return {ok: true, json: async () => compile(JSON.parse(options.body))};
      throw Error('Unexpected route ' + url);
    },
  });
  vm.runInContext(SOURCE, context);
  return {element, requests, elements, storage, run: code => vm.runInContext(code, context)};
}

const compiled = (overrides = {}) => body => ({
  schema_version: 1, kind: 'compiled_creative_intent', state: overrides.errors?.length ? 'blocked' : 'review_required',
  fields: {positive: 'An observatory keeper', negative: 'blur'}, intent: body.intent, profile: PROFILES.find(p => p.id === body.profile_id),
  intent_sha256: 'b'.repeat(64), profile_sha256: 'c'.repeat(64), coverage: [{source: 'brief', destination: 'description'}],
  errors: [], diagnostics: [], generation_submitted: false, ...overrides,
});

async function startup(ok) {
  const {element, requests} = harness({ok, compile: compiled()});
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(requests.every(r => !r.url.includes('/api/jobs')), 'Page startup must not submit generation');
  if (ok) {
    assert.deepEqual(requests.map(r => r.url), ['/api/prompt/profiles', '/api/prompt/compile'],
      'A loaded registry builds the prompt once, and reads nothing else');
    assert.equal(JSON.parse(requests[1].options.body).profile_id, PROFILES[0].id);
    assert.equal(element('profile').children.length, PROFILES.length, 'Successful response populates target profiles');
    assert.equal(element('profile').children[0].value, 'sdxl-prose-v1');
    assert.match(element('profile-summary').textContent, /reference images/, 'The chosen profile explains itself before anything is typed');
    assert.equal(element('status').textContent, 'No generation submitted.');
    assert.match(element('state').textContent, /Built/);
    assert.match(element('fields').textContent, /observatory keeper/);
    assert.match(element('identity').textContent, /bbbbbbbbbbbb/, 'The brief fingerprint is shown in readable form');
    assert.equal(element('coverage').children[0].text.replace(/\s+/g, ' ').trim(), 'Your brief → positive prompt', 'Coverage reads as a sentence, not JSON');
    assert.match(element('trace').textContent, /"intent_sha256"/, 'The raw trace is kept for agents');
  } else {
    assert.deepEqual(requests.map(r => r.url), ['/api/prompt/profiles'], 'An unavailable registry compiles nothing');
    assert.equal(element('profile').children.length, 0);
    assert.match(element('status').textContent, /Profile registry unavailable/);
  }
}

// Every blocked build states the reason and the action in words, and keeps the code for agents.
async function blockedBuildExplainsItself() {
  const {element} = harness({compile: compiled({
    errors: [{code: 'REFERENCE_COUNT', message: 'This profile reads 0..0 reference images and 1 are attached; none were silently discarded'}],
    diagnostics: [{code: 'PARAMETER_HANDOFF', message: 'language needs an executor binding'}],
  })});
  await new Promise(resolve => setImmediate(resolve));
  assert.match(element('state').textContent, /Not usable yet/);
  const [blocker, note] = element('diagnostics').children;
  assert.equal(blocker.className, 'pl-issue pl-blocking');
  assert.match(blocker.children[0].textContent, /^Blocked: The SDXL \/ descriptive baseline profile reads no reference images/);
  assert.match(blocker.children[1].textContent, /Remove the reference, or switch to a profile that reads reference images\./);
  assert.equal(note.className, 'pl-issue', 'A diagnostic is not presented as a blocker');
  assert.match(note.children[0].textContent, /^Worth knowing:/);
  const codes = blocker.children.map(c => c.textContent).filter(t => t.startsWith('REFERENCE_COUNT'));
  assert.equal(codes.length, 1, 'The raw code stays visible for agents');
  assert.match(codes[0], /none were silently discarded/, 'The compiler message is kept alongside the plain sentence');
  assert.equal(element('export-result').disabled, false, 'A blocked build is still an exportable record');
  assert.match(element('export-reason').textContent, /unresolved items/);
}

// A one-click repair is offered only when a real profile fits the references already attached.
async function repairsAreOfferedOnlyWhenTheyFit() {
  const {element, run} = harness({compile: compiled({
    errors: [{code: 'REFERENCE_COUNT', message: 'This profile reads 0..0 reference images and 1 are attached'}],
  })});
  await new Promise(resolve => setImmediate(resolve));
  const buttons = box => box.children.filter(c => c.tag === 'button').map(b => b.textContent);
  assert.deepEqual(buttons(element('diagnostics').children[0]), [],
    'With nothing attached the current profile already fits, so no switch is invented');
  // Record one reference the way the file picker does, then rebuild.
  run("intent.references.push({id:'ref-a',role:'identity',kind:'image',path:'a.png',sha256:'a'.repeat(64),take:[],ignore:[]});build();");
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(buttons(element('diagnostics').children[0]), ['Switch to Qwen Image Edit 2511 / 1–3 reference images'],
    'One attached reference makes the reference-reading profile a one-click switch');
  run("document.getElementById('diagnostics').children[0].children.find(c=>c.tag==='button').listeners.click();");
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(element('profile').value, 'qwen-edit2511-three-v1');
  assert.equal(run('intent.task'), 'edit', 'The switch also moves the brief to the task that profile accepts');
  assert.match(element('status').textContent, /Nothing you typed was changed\./);
}

// Avoid terms are never deleted: they move into a named review note and can be moved back.
async function avoidTermsAreParkedNotDeleted() {
  const {element, run} = harness({compile: compiled({
    errors: [{code: 'NEGATIVE_REWRITE_REQUIRED', message: 'This profile has no negative channel'}],
  })});
  await new Promise(resolve => setImmediate(resolve));
  element('avoid').value = 'crowd, watermark';
  run('build();');
  await new Promise(resolve => setImmediate(resolve));
  const keep = element('diagnostics').children[0].children.find(c => c.tag === 'button');
  assert.equal(keep.textContent, 'Keep as review note');
  keep.listeners.click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(element('avoid').value, '');
  assert.deepEqual(JSON.parse(run('JSON.stringify(intent.constraints)')), [{id: 'avoid-note-1', text: 'Avoid: crowd, watermark', mechanism: 'verify', priority: 'soft'}]);
  assert.equal(run('intent.avoid.length'), 0, 'The terms left the unsupported channel');
  assert.match(element('status').textContent, /Moved .crowd, watermark. out of Things to avoid/);
  assert.equal(element('notes-section').hidden, false);
  const back = element('notes-list').children[0].children.find(c => c.tag === 'button');
  assert.equal(back.textContent, 'Return to Things to avoid');
  back.listeners.click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(element('avoid').value, 'crowd, watermark', 'The move is reversible in one click');
  assert.equal(run('intent.constraints.length'), 0);
}

// A long avoid list is split across bounded notes, never sliced to fit one (PR #288 review).
async function longAvoidListsAreSplitNotTruncated() {
  const {element, run} = harness({compile: compiled({
    errors: [{code: 'NEGATIVE_REWRITE_REQUIRED', message: 'This profile has no negative channel'}],
  })});
  await new Promise(resolve => setImmediate(resolve));
  const terms = Array.from({length: 12}, (_, i) => ('term' + i).padEnd(120, 'x'));
  element('avoid').value = terms.join(', ');
  run('build();');
  await new Promise(resolve => setImmediate(resolve));
  element('diagnostics').children[0].children.find(c => c.tag === 'button').listeners.click();
  await new Promise(resolve => setImmediate(resolve));
  const kept = JSON.parse(run('JSON.stringify(intent.constraints)'));
  assert.ok(kept.length > 1, 'A list too long for one note becomes several, not a slice');
  assert.ok(kept.every(c => c.text.length <= 500 && c.mechanism === 'verify' && c.priority === 'soft'));
  assert.deepEqual(kept.flatMap(c => c.text.replace(/^Avoid: /, '').split(',').map(t => t.trim())), terms,
    'Every word survives the move, in order');
  assert.match(element('status').textContent, /Every word is kept in the brief/);
  // A term that cannot fit any note refuses the repair instead of cutting it.
  run("intent.constraints.length=0;");
  element('avoid').value = 'z'.repeat(600);
  run('build();');
  await new Promise(resolve => setImmediate(resolve));
  element('diagnostics').children[0].children.find(c => c.tag === 'button').listeners.click();
  assert.equal(run('intent.constraints.length'), 0, 'Nothing is written when nothing fits');
  assert.equal(element('avoid').value, 'z'.repeat(600), 'The text stays exactly where the user typed it');
  assert.match(element('status').textContent, /Nothing was moved or deleted/);
}

// `description` is one ledger word for three fields; the readable trace must not claim the wrong one.
async function coverageNamesTheFieldThisDialectFills() {
  for (const [id, expected] of [['qwen3-voice-design-v1', /performance direction/], ['ace15-music-v1', /caption/], ['sdxl-prose-v1', /positive prompt/]]) {
    const {element, run} = harness({compile: compiled()});
    await new Promise(resolve => setImmediate(resolve));
    run("document.getElementById('profile').value=" + JSON.stringify(id) + ";build();");
    await new Promise(resolve => setImmediate(resolve));
    assert.match(element('coverage').children[0].text, expected, id);
  }
}

// An imported brief brings its own profile; the explanation under the picker has to follow it.
async function importedBriefRefreshesItsExplanation() {
  const {element} = harness({compile: compiled()});
  await new Promise(resolve => setImmediate(resolve));
  const before = element('profile-summary').textContent;
  assert.match(before, /reference images/);
  const brief = {schema_version: 1, id: 'creative-brief', task: 'voice', brief: 'A tired keeper speaks.', facets: {},
    tags: [], avoid: [], constraints: [], references: [], verbatim: {text: 'Hello.'}, parameters: {}, locked: ['verbatim']};
  await element('brief-file').listeners.change({target: {files: [{size: 400, text: async () => JSON.stringify(brief)}]}});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(element('profile').value, 'qwen3-voice-design-v1');
  assert.notEqual(element('profile-summary').textContent, before, 'A stale profile explanation would describe the wrong model');
  assert.match(element('profile-summary').textContent, /byte-for-byte/);
}

async function metadataResponses() {
  const elements = new Map(), pending = [], requests = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, makeNode());
    return elements.get(id);
  }
  const context = vm.createContext({
    StudioUX,
    document: {getElementById: element, createElement: makeNode},
    btoa: s => Buffer.from(s, 'binary').toString('base64'),
    fetch: (url, options) => {
      requests.push({url, options});
      if (url === '/api/prompt/profiles') return Promise.resolve({ok: true, json: async () => ({profiles: []})});
      return new Promise(resolve => pending.push(resolve));
    },
  });
  vm.runInContext(SOURCE, context);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(requests.map(r => r.url), ['/api/prompt/profiles'], 'An empty registry builds nothing');
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
async function liveBuildIsDebounced() {
  const {requests, run} = harness({timers: true, compile: () => ({state: 'review_required', fields: {positive: 'x'}, errors: [], diagnostics: [], coverage: [], intent: {}, profile: PROFILES[0], profile_sha256: 'p', intent_sha256: 'i'})});
  await new Promise(resolve => setTimeout(resolve, 600));
  const before = requests.filter(r => r.url === '/api/prompt/compile').length;
  for (let i = 0; i < 5; i++) run('invalidate()');
  assert.equal(requests.filter(r => r.url === '/api/prompt/compile').length, before, 'A keystroke burst sends nothing while the debounce is pending');
  await new Promise(resolve => setTimeout(resolve, 700));
  assert.equal(requests.filter(r => r.url === '/api/prompt/compile').length, before + 1, 'Five edits inside 400 ms build once');
}
// The brief survives a reload: edits debounced through invalidate() persist, then restore.
async function draftIsRestoredAfterReload() {
  const storage = makeStorage();
  const first = harness({timers: true, storage, compile: compiled()});
  await new Promise(resolve => setTimeout(resolve, 600));
  first.element('brief').value = 'A keeper who remembers the storm.';
  first.element('tags').value = 'lantern, night';
  first.run('invalidate()');
  await new Promise(resolve => setTimeout(resolve, 700));
  const raw = storage.getItem('studio.promptLab.draft');
  assert.ok(raw, 'An edit that calls invalidate() persists the draft');
  assert.match(raw, /keeper who remembers/, 'The stored draft holds the typed brief');
  const second = harness({storage, compile: compiled()});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(second.element('brief').value, 'A keeper who remembers the storm.', 'The draft is restored after a simulated reload');
  assert.equal(second.element('tags').value, 'lantern, night');
  assert.ok(second.requests.every(r => !r.url.includes('/api/jobs')), 'Restoring must never submit anything');
  assert.equal(second.element('export-result').disabled, false, 'A restored draft still builds');
}

// A corrupt or wrong-version value is ignored and cleared, never applied.
async function corruptDraftIsIgnored() {
  const storage = makeStorage({'studio.promptLab.draft': '{oops'});
  const first = harness({storage, compile: compiled()});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(first.element('brief').value, '', 'A corrupt stored value is ignored');
  assert.equal(storage.getItem('studio.promptLab.draft'), null, 'A corrupt value is cleared');
  assert.match(first.element('status').textContent, /No generation submitted/);
  storage.setItem('studio.promptLab.draft', JSON.stringify({version: 999, intent: {brief: 'x', task: 'image'}}));
  const second = harness({storage, compile: compiled()});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(second.element('brief').value, '', 'A wrong-version value is ignored');
  assert.equal(storage.getItem('studio.promptLab.draft'), null, 'A wrong-version value is cleared');
}

// Reference bytes never reach storage: only metadata and labels persist.
async function storedDraftExcludesReferenceBytes() {
  const storage = makeStorage();
  const {run} = harness({storage, compile: compiled()});
  await new Promise(resolve => setImmediate(resolve));
  run("intent.references.push({id:'ref-x',role:'identity',kind:'image',path:'a.png',sha256:'a'.repeat(64),take:[],ignore:[],data:'data:image/png;base64,AAAA',bytes:'AAAA',blob:'blob:xxx'});saveDraft();");
  const raw = storage.getItem('studio.promptLab.draft');
  assert.ok(raw, 'The draft was stored');
  assert.doesNotMatch(raw, /data:image\/png/, 'The stored draft excludes reference bytes');
  assert.doesNotMatch(raw, /AAAA/, 'No embedded payload survives');
  const kept = JSON.parse(raw).intent.references[0];
  assert.equal(kept.path, 'a.png', 'Reference metadata survives');
  assert.equal(kept.sha256, 'a'.repeat(64));
  assert.ok(!('data' in kept) && !('bytes' in kept) && !('blob' in kept), 'Payload keys are stripped');
}

// A failed rebuild never leaves the old prompt looking current.
async function failedRebuildMarksStale() {
  let fail = false;
  const ok = compiled();
  const {element, run} = harness({compile: body => { if (fail) throw Error('profile exploded'); return ok(body); }});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(element('export-result').disabled, false, 'A good build is exportable');
  fail = true;
  run('build();');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(element('export-result').disabled, true, 'A failed rebuild leaves Export disabled');
  assert.match(element('state').textContent, /Out of date/, 'The state says the result is out of date');
  assert.match(element('state').textContent, /profile exploded/, 'The stale state keeps the reason');
  assert.match(element('status').textContent, /profile exploded/);
}
// A repair through rebuild() (Keep as review note, Switch profile) persists like a keystroke does.
async function repairPathsPersistTheDraft() {
  const storage = makeStorage();
  const {element, run} = harness({timers: true, storage, compile: compiled()});
  await new Promise(resolve => setTimeout(resolve, 600));
  element('brief').value = 'A repaired brief';
  run("rebuild('Repaired.');");
  await new Promise(resolve => setTimeout(resolve, 700));
  assert.match(storage.getItem('studio.promptLab.draft') || '', /A repaired brief/, 'rebuild() queues a draft save');
}
// A malformed or unsupported stored draft is dropped before it touches the page.
async function malformedDraftLeavesThePageUsable() {
  for (const intent of [{brief: 'x', task: 'image', tags: 'a,b'}, {brief: 'x', task: 'image', facets: []}, {brief: 'x', task: 'no-such-task'}, {brief: 'x', task: 'image', references: [{id: 'r', take: 'nope'}]}]) {
    const storage = makeStorage({'studio.promptLab.draft': JSON.stringify({version: 1, profile: 'missing', intent})});
    const {element} = harness({storage, compile: compiled()});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(element('brief').value, '', 'A malformed draft is not applied: ' + JSON.stringify(intent));
    assert.equal(storage.getItem('studio.promptLab.draft'), null, 'A malformed draft is cleared');
    assert.equal(element('export-result').disabled, false, 'The page still builds after dropping it');
  }
}
// Terminal line: its absence is how the Python wrapper tells a stalled chain from a completed run.
startup(true).then(() => startup(false)).then(blockedBuildExplainsItself).then(repairsAreOfferedOnlyWhenTheyFit)
  .then(avoidTermsAreParkedNotDeleted).then(longAvoidListsAreSplitNotTruncated)
  .then(coverageNamesTheFieldThisDialectFills).then(importedBriefRefreshesItsExplanation).then(metadataResponses).then(liveBuildIsDebounced).then(draftIsRestoredAfterReload).then(corruptDraftIsIgnored).then(storedDraftExcludesReferenceBytes).then(failedRebuildMarksStale).then(repairPathsPersistTheDraft).then(malformedDraftLeavesThePageUsable)
  .then(() => console.log('Prompt Lab frontend contracts passed: profile startup, live build, plain-language blockers, HTTP failure reporting and metadata selection.'))
  .catch(error => { console.error(error); process.exitCode = 1; });
