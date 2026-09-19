'use strict';
const assert = require('node:assert/strict');
const {test} = require('node:test');
const W = require('../app/static/workshop.js');

const defaults = {layout:'focus',skin:'atelier',ambience:'none'};

test('unknown preferences never become CSS selectors or settings', () => {
  assert.deepEqual(W.preferences({layout:'<script>',skin:'url(https://evil.test)',ambience:'javascript:alert(1)',positive:'private'}), defaults);
  for (const input of [null, [], 7, 'studio', {__proto__: {skin:'arcade'}}])
    assert.deepEqual(W.preferences(input), defaults);
});

test('missing, malformed, oversized and unavailable storage are harmless', () => {
  for (const value of [null, '{', 'null', '[]', 'x'.repeat(2049)]) {
    const storage={getItem:key=>key===W.STORAGE_KEY?value:null};
    assert.deepEqual(W.readPreferences(storage), defaults);
  }
  assert.deepEqual(W.readPreferences({getItem(){throw Error('blocked');}}), defaults);
  assert.equal(W.writePreferences({setItem(){throw Error('full');}}, {}), false);
});

test('legacy v1 layout and skin migrate without inventing ambience', () => {
  const storage={getItem:key=>key===W.LEGACY_STORAGE_KEY?JSON.stringify({layout:'studio',skin:'sakura',positive:'private'}):null};
  assert.deepEqual(W.readPreferences(storage), {layout:'studio',skin:'sakura',ambience:'none'});
});

test('jobProblemsHost is created outside the Recent runs disclosure', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const js = fs.readFileSync(path.join(__dirname, '../app/static/workshop.js'), 'utf8');
  const host = js.indexOf("problemsHost.id = 'jobProblemsHost'");
  const results = js.indexOf("disclosure('workshopResults'");
  const append = js.indexOf('create.append(problemsHost, results)');
  assert.ok(host >= 0 && results > host && append > results);
});

test('groupControls leaves the I2V hold note outside two-column fieldsets', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const js = fs.readFileSync(path.join(__dirname, '../app/static/workshop.js'), 'utf8');
  const body = js.slice(js.indexOf('function groupControls()'), js.indexOf('function applyPresentation()'));
  assert.match(body, /if \(label\.querySelector\('#i2vMode'\)\) continue;/);
});

test('only allow-listed presentation preferences are persisted, never prompts', () => {
  let stored;
  const storage={getItem:key=>key===W.STORAGE_KEY?stored:null,setItem:(key,value)=>{assert.equal(key,W.STORAGE_KEY);stored=value;}};
  assert.equal(W.writePreferences(storage,{layout:'immersive',skin:'retro-anime',ambience:'night-shift',positive:'private prompt',source:'private file',checkpoint:'private'}),true);
  assert.deepEqual(JSON.parse(stored),{layout:'immersive',skin:'retro-anime',ambience:'night-shift'});
  assert.deepEqual(W.readPreferences(storage),{layout:'immersive',skin:'retro-anime',ambience:'night-shift'});
});

test('three layouts, four skins and three ambiences round-trip without generation settings', () => {
  assert.deepEqual(Object.keys(W.LAYOUTS), ['focus','studio','immersive']);
  assert.deepEqual(Object.keys(W.SKINS), ['atelier','arcade','sakura','retro-anime']);
  assert.deepEqual(Object.keys(W.AMBIENCES), ['none','night-shift','quiet-morning']);
  for (const layout of Object.keys(W.LAYOUTS)) for (const skin of Object.keys(W.SKINS)) for (const ambience of Object.keys(W.AMBIENCES)) {
    let value;
    const storage={getItem:key=>key===W.STORAGE_KEY?value:null,setItem:(_,next)=>{value=next;}};
    assert.equal(W.writePreferences(storage,{layout,skin,ambience,seed:123,checkpoint:'private'}),true);
    assert.deepEqual(W.readPreferences(storage),{layout,skin,ambience});
  }
});

test('immersive presentation exposes local ambience, visual skin and read-only guidance seams', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const js = fs.readFileSync(path.join(__dirname, '../app/static/workshop.js'), 'utf8');
  for (const marker of ['workshopAmbience','workshopSkinChoice','wk-immersive-hero','wk-setup-rail','wk-guidance','workshopGuidanceAction'])
    assert.ok(js.includes(marker), marker+' missing');
  assert.doesNotMatch(js, /workshopGuidanceAction[^\n]+click\(\)/);
});

test('Studio shell loads the read-only context boundary before the workshop adapter', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const shell = fs.readFileSync(path.join(__dirname, '../app/static/studio-shell.js'), 'utf8');
  assert.match(shell, /context\.src='\/static\/presentation-context\.js'/);
  assert.match(shell, /context\.onload=/);
});

test('workshop guidance projects immutable intents and dispatches only through the semantic adapter', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const js = fs.readFileSync(path.join(__dirname, '../app/static/workshop.js'), 'utf8');
  assert.match(js, /Context\.project\(/);
  assert.match(js, /Context\.createActionAdapter\(/);
  assert.match(js, /presentationView/);
  assert.match(js, /dispatchIntent/);
  assert.doesNotMatch(js, /guidanceAction\.dataset\.action/);
});

test('the offline prototype loads the context boundary before workshop.js', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const html = fs.readFileSync(path.join(__dirname, '../docs/workshop/prototype.html'), 'utf8');
  const context = html.indexOf('presentation-context.js');
  const workshop = html.indexOf('workshop.js');
  assert.ok(context >= 0 && workshop > context);
});

test('the workshop bridge consumes the reference model and re-derives none of it', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const js = fs.readFileSync(path.join(__dirname, '../app/static/workshop.js'), 'utf8');
  assert.match(js, /StudioReferenceModel\.live\(/);
  // Every reference semantic belongs to reference-model.js; a second copy here is what #610 items 1 and 3 were.
  for (const derived of ['reference_slots', 'reference_board', 'last_reference_label', 'referenceRecords', 'lastUploaded', 'referencePending'])
    assert.ok(!js.includes(derived), derived + ' is re-derived in workshop.js');
  const references = fs.readFileSync(path.join(__dirname, '../app/static/references.js'), 'utf8');
  assert.match(references, /function referencesReady\(\)\{return referenceProjection\(\)\.ready;\}/);
});

test('the source intent focuses the slot the projection reports outstanding, and still only focuses', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const js = fs.readFileSync(path.join(__dirname, '../app/static/workshop.js'), 'utf8');
  const body = js.slice(js.indexOf('function revealSources()'), js.indexOf('function openResults()'));
  assert.match(body, /bridge\.referenceSlots\?\.\(\)/);
  assert.match(body, /slot\.required && !slot\.staged/);
  // The outstanding slot must be tried before the fixed page order, or a filled board picture wins again.
  assert.ok(body.indexOf('outstanding') < body.indexOf("q('#roleReferences input[type=file]')"));
  assert.ok(!/\.click\(|submit|generate/i.test(body), 'the source intent must never do more than focus');
});

test('every page and prototype that runs workshop.js loads the reference model first', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const read = name => fs.readFileSync(path.join(__dirname, name), 'utf8');
  const index = read('../app/static/index.html');
  assert.ok(index.indexOf('/static/reference-model.js') >= 0);
  assert.ok(index.indexOf('/static/reference-model.js') < index.indexOf('/static/references.js'));
  const prototype = read('../docs/workshop/prototype.html');
  assert.ok(prototype.indexOf('reference-model.js') >= 0);
  assert.ok(prototype.indexOf('reference-model.js') < prototype.indexOf('workshop.js'));
  const driver = read('workshop_browser_core.py');
  assert.ok(driver.indexOf("app/static/reference-model.js") < driver.indexOf("app/static/workshop.js"));
});

test('production guidance advertises only actions its current capture can emit', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const js = fs.readFileSync(path.join(__dirname, '../app/static/workshop.js'), 'utf8');
  assert.doesNotMatch(js, /draftDirty/, 'IIFE-private draft state must not be presented as a live bridge');
  const start = js.indexOf('actions:{');
  const end = js.indexOf('\n      }\n    });', start);
  assert.ok(start >= 0 && end > start, 'production action map not found');
  const map = js.slice(start, end);
  for (const reachable of ['REVIEW_READINESS','REVIEW_SOURCES','FOCUS_GENERATE','OPEN_RESULTS'])
    assert.match(map, new RegExp('Context\\.ACTIONS\\.'+reachable));
  for (const unavailable of ['INSPECT_OPERATION','RESOLVE_DRAFT_CONFLICT'])
    assert.doesNotMatch(map, new RegExp('Context\\.ACTIONS\\.'+unavailable));
});

test('workshop documentation describes the shipped boundary and reachable production actions', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const read = name => fs.readFileSync(path.join(__dirname, name), 'utf8');
  const context = read('../docs/workshop/PRESENTATION-CONTEXT.md');
  assert.doesNotMatch(context, /production shell does not load it yet/i);
  assert.doesNotMatch(context, /follow-on stacked PR must load the module/i);
  assert.match(context, /production-reachable actions/i);
  const readme = read('../docs/workshop/README.md');
  const design = read('../docs/workshop/DESIGN.md');
  assert.match(readme, /Review sources/);
  assert.match(design, /Review sources/);
  const spec = read('../docs/superpowers/specs/2026-09-18-workshop-context-guidance-design.md');
  assert.match(spec, /Production currently maps/i);
  for (const plan of ['../docs/superpowers/plans/2026-09-18-presentation-context.md','../docs/superpowers/plans/2026-09-18-workshop-context-guidance.md'])
    assert.doesNotMatch(read(plan), /- \[ \]/, plan+' still claims delivered work is pending');
});

test('Studio shell loads ambience policy and adapter around the workshop presentation', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const shell = fs.readFileSync(path.join(__dirname, '../app/static/studio-shell.js'), 'utf8');
  assert.match(shell, /context\.onload=.*workshop-ambience-policy\.js.*ambience\.onload=loadWorkshop/);
  assert.match(shell, /loadWorkshop=.*workshop\.js.*workshop\.onload=.*workshop-ambience\.js/);
  assert.match(shell, /ambience\.onerror=loadWorkshop/);
});

test('ambience adapter mounts the controller without execution or network authority', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const js = fs.readFileSync(path.join(__dirname, '../app/static/workshop-ambience.js'), 'utf8');
  const A = require('../app/static/workshop-ambience.js');
  assert.equal(typeof A.mount, 'function');
  assert.match(js, /AmbiencePolicy\.createController\(/);
  assert.match(js, /workshopAmbienceStatus/);
  assert.match(js, /__workshopAmbience/);
  assert.doesNotMatch(js, /(?:fetch\(|serviceWorker|\.click\(\))/);
});

test('fixtures load context policy workshop and ambience adapter in order', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  for (const relative of ['../docs/workshop/prototype.html','workshop_fixture.html']) {
    const text = fs.readFileSync(path.join(__dirname, relative), 'utf8');
    const context = text.indexOf('presentation-context.js');
    const policy = text.indexOf('workshop-ambience-policy.js');
    const workshop = text.indexOf('workshop.js');
    const adapter = text.indexOf('workshop-ambience.js');
    assert.ok(context >= 0 && policy > context && workshop > policy && adapter > workshop, relative);
  }
});

test('effective token and suspended modes suppress only decorative poster art', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const css = fs.readFileSync(path.join(__dirname, '../app/static/workshop-ambience.css'), 'utf8');
  assert.match(css, /data-workshop-ambience-render="tokens"/);
  assert.match(css, /data-workshop-ambience-render="suspended"/);
  assert.match(css, /background-image\s*:\s*none/);
});
