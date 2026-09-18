'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');

const MODULE_PATH = path.resolve(__dirname, '../app/static/workshop-ambience-policy.js');
function policy() {
  assert.equal(fs.existsSync(MODULE_PATH), true, 'workshop ambience policy module must exist');
  delete require.cache[MODULE_PATH];
  return require(MODULE_PATH);
}

const available = patch => ({
  requested:'night-shift',
  assetState:'available',
  visibility:'visible',
  forcedColors:false,
  reducedMotion:false,
  saveData:false,
  userPaused:false,
  executionState:'ready',
  internetState:'unknown',
  backendState:'unknown',
  ...patch
});

test('local poster eligibility is independent from internet and backend reachability', () => {
  const P = policy();
  const offline = P.project(available({internetState:'offline', backendState:'ready'}));
  const backendDown = P.project(available({internetState:'online', backendState:'down'}));
  assert.equal(offline.renderMode, 'poster');
  assert.equal(backendDown.renderMode, 'poster');
  assert.deepEqual(
    {renderMode:offline.renderMode, assetId:offline.assetId, heroVisible:offline.heroVisible},
    {renderMode:backendDown.renderMode, assetId:backendDown.assetId, heroVisible:backendDown.heroVisible}
  );
});

test('none removes ambience without reserving a decorative surface', () => {
  const P = policy();
  const result = P.project(available({requested:'none'}));
  assert.equal(result.renderMode, 'none');
  assert.equal(result.assetId, null);
  assert.equal(result.heroVisible, false);
});

test('hidden documents suspend optional art without changing the request', () => {
  const P = policy();
  const result = P.project(available({visibility:'hidden', requested:'quiet-morning'}));
  assert.equal(result.requested, 'quiet-morning');
  assert.equal(result.renderMode, 'suspended');
  assert.equal(result.heroVisible, true);
  assert.match(result.status, /hidden|suspend/i);
});

test('forced colours preserve theme structure but suppress illustration', () => {
  const P = policy();
  const result = P.project(available({forcedColors:true}));
  assert.equal(result.renderMode, 'tokens');
  assert.equal(result.heroVisible, true);
  assert.match(result.reason, /forced/i);
});

test('missing and unknown local assets fall back to tokens', () => {
  const P = policy();
  for (const assetState of ['missing','unknown']) {
    const result = P.project(available({assetState}));
    assert.equal(result.renderMode, 'tokens');
    assert.equal(result.assetId, null);
    assert.equal(result.heroVisible, true);
  }
});

test('accessibility economy pause and runtime pressure retain an available static poster', () => {
  const P = policy();
  const cases = [
    {reducedMotion:true},
    {saveData:true},
    {userPaused:true},
    {executionState:'running'},
    {executionState:'uncertain'},
    {executionState:'unknown'}
  ];
  for (const patch of cases) {
    const result = P.project(available(patch));
    assert.equal(result.renderMode, 'poster');
    assert.equal(result.motionEligible, false);
    assert.equal(result.assetId, 'night-shift');
  }
});

test('malformed values fail closed to no requested ambience', () => {
  const P = policy();
  const result = P.project({
    requested:'https://provider.example/loop.mp4',
    assetState:{url:'private'},
    visibility:'sideways',
    executionState:'submit-now'
  });
  assert.equal(result.requested, 'none');
  assert.equal(result.renderMode, 'none');
  assert.equal(result.heroVisible, false);
  assert.doesNotMatch(JSON.stringify(result), /provider|private|submit-now/);
});

test('policy decisions are immutable and carry no execution authority', () => {
  const P = policy();
  const result = P.project(available());
  assert.equal(Object.isFrozen(result), true);
  assert.equal(Object.isFrozen(result.commands), true);
  assert.equal(result.authorizesExecution, false);
  assert.deepEqual(result.commands, []);
  assert.equal(result.motionEligible, false);
  assert.throws(() => { result.renderMode = 'video'; }, TypeError);
});
