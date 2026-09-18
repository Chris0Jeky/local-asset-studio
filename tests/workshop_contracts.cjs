'use strict';
const assert = require('node:assert/strict');
const {test} = require('node:test');
const W = require('../app/static/workshop.js');

test('unknown preferences never become CSS selectors or settings', () => {
  assert.deepEqual(W.preferences({layout:'<script>',skin:'url(https://evil.test)',positive:'private'}), {layout:'focus',skin:'atelier'});
  for (const input of [null, [], 7, 'studio', {__proto__: {skin:'arcade'}}])
    assert.deepEqual(W.preferences(input), {layout:'focus',skin:'atelier'});
});
test('missing, malformed, oversized and unavailable storage are harmless', () => {
  for (const value of [null, '{', 'null', '[]', 'x'.repeat(2049)])
    assert.deepEqual(W.readPreferences({getItem:()=>value}), {layout:'focus',skin:'atelier'});
  assert.deepEqual(W.readPreferences({getItem(){throw Error('blocked');}}), {layout:'focus',skin:'atelier'});
  assert.equal(W.writePreferences({setItem(){throw Error('full');}}, {}), false);
});
test('only allow-listed presentation preferences are persisted, never prompts', () => {
  let stored;
  const storage={getItem:()=>stored,setItem:(key,value)=>{assert.equal(key,W.STORAGE_KEY);stored=value;}};
  assert.equal(W.writePreferences(storage,{layout:'focus',skin:'atelier',positive:'private prompt',source:'private file'}),true);
  assert.deepEqual(JSON.parse(stored),{layout:'focus',skin:'atelier'});
  assert.deepEqual(W.readPreferences(storage),{layout:'focus',skin:'atelier'});
});
