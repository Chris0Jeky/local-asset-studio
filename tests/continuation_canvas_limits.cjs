'use strict';
const assert=require('node:assert/strict');
const C=require('../app/static/continuation-core.js');

const preset={
  id:'future-restyle',
  width:['10','width'],
  height:['10','height'],
  dimension_multiple:16,
  continuation_capability:{operation:'restyle',keeps_picture:true}
};

assert.deepEqual(
  C.canvasFor({width:32,height:4096},{...preset,dimension_limits:[128,1536]}),
  {width:128,height:1536},
  'declared minimum dimensions must replace the generic 64px floor'
);

assert.deepEqual(
  C.canvasFor({width:1024,height:1024},{...preset,dimension_limits:[64,1536],max_pixels:512*512}),
  {width:512,height:512},
  'a declared pixel budget must reduce a square canvas'
);

const landscape=C.canvasFor(
  {width:1920,height:1080},
  {...preset,dimension_limits:[64,1536],max_pixels:300000}
);
assert.ok(landscape.width*landscape.height<=300000,JSON.stringify(landscape));
assert.equal(landscape.width%16,0);
assert.equal(landscape.height%16,0);
assert.ok(landscape.width>=64&&landscape.height>=64);

assert.equal(
  C.canvasFor({width:1024,height:1024},{...preset,dimension_limits:[512,1536],max_pixels:200000}),
  null,
  'impossible declared bounds must remain unknown rather than prepare an invalid canvas'
);

for(const [source,expected] of [
  [{width:832,height:1216},{width:1040,height:1520}],
  [{width:1216,height:832},{width:1520,height:1040}],
  [{width:4000,height:4000},{width:1248,height:1248}],
  [{width:1920,height:1080},{width:1536,height:864}],
  [{width:1080,height:1920},{width:864,height:1536}]
])assert.deepEqual(C.canvasFor(source,preset),expected,'existing Restyle dimensions must remain stable');

console.log('Continuation canvas limit contracts passed: 9');
