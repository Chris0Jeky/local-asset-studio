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
