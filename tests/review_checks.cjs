'use strict';
// #1203: quick yes/no review checks. Pure policy: which checks fit a recipe route, how a press cycles an answer
// through the asset's tags, and the per-engine counts. Absent is "not checked", never "no" (K14).
const assert=require('node:assert/strict');
const R=require('../app/static/review-checks.js');
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
const combine={id:'combine-klein',continuation_capability:{operation:'combine'}},create={id:'anima-portrait'},refine={id:'krea-refine',continuation_capability:{operation:'image-to-image'}};
test('the check set follows the recipe route: Combine judges the transfer, Create judges the picture',()=>{
  assert.deepEqual(R.forPreset(combine),['pose','face','outfit','style','clean']);
  assert.deepEqual(R.forPreset(create),['style','anatomy','composition','clean']);
  assert.deepEqual(R.forPreset(refine),['style','anatomy','composition','clean']);
  assert.deepEqual(R.forPreset(null),['style','anatomy','composition','clean']);
  const presets=[combine,create];
  assert.deepEqual(R.forAsset({media_type:'image',preset_id:'combine-klein'},presets),R.COMBINE);
  assert.deepEqual(R.forAsset({media_type:'image',preset_id:'gone'},presets),R.CREATE);
  for(const media of ['video','audio','model'])assert.deepEqual(R.forAsset({media_type:media,preset_id:'combine-klein'},presets),[]);
  assert.ok(R.COMBINE.length<=5&&R.CREATE.length<=5,'at most five checks, so number keys 1-5 reach every one');
});
test('answers read only well-formed tags; a contradiction or a missing tag is not checked',()=>{
  assert.deepEqual(R.answers(['hero','face','check:pose=yes','check:face=no','check:hair=yes','check:style=maybe']),{pose:true,face:false});
  assert.deepEqual(R.answers(['check:pose=yes','check:pose=no']),{});
  assert.deepEqual(R.answers(undefined),{});
  assert.equal(R.answer(['check:clean=no'],'clean'),false);assert.equal(R.answer([],'clean'),null);
});
test('one press cycles not checked -> yes -> no -> not checked, and leaves every other tag in place',()=>{
  let tags=['hero','face','check:pose=yes'];
  tags=R.cycle(tags,'face');assert.deepEqual(tags,['hero','face','check:pose=yes','check:face=yes']);
  tags=R.cycle(tags,'face');assert.deepEqual(tags,['hero','face','check:pose=yes','check:face=no']);
  tags=R.cycle(tags,'face');assert.deepEqual(tags,['hero','face','check:pose=yes']);
  assert.throws(()=>R.cycle(tags,'hair'),/Unknown check/);
  // A contradictory pair (typed by hand) collapses to one answer on the next press rather than being kept.
  assert.deepEqual(R.cycle(['check:pose=yes','check:pose=no'],'pose'),['check:pose=yes']);
});
test('counts are per check over owner answers only; trashed and unanswered pictures are left out',()=>{
  const assets=[{tags:['check:pose=yes','check:face=no']},{tags:['check:pose=yes']},{tags:['check:pose=no','check:face=no']},{tags:[]},{tags:['check:pose=yes'],trashed_at:5}];
  assert.deepEqual(R.tally(assets,R.COMBINE),{pose:{yes:2,checked:3},face:{yes:0,checked:2},outfit:{yes:0,checked:0},style:{yes:0,checked:0},clean:{yes:0,checked:0}});
  assert.equal(R.summary(assets,R.COMBINE),'pose 2/3 · face 0/2');
  assert.equal(R.summary([{tags:['hero']}],R.COMBINE),'');
  assert.equal(R.summary([],R.COMBINE),'');
});
test('chips name their state and their key in words, and escape through the caller',()=>{
  const html=R.chipsHTML({tags:['check:pose=yes','check:face=no'],names:R.COMBINE,attr:'data-ux-check',asset:'a"1',escape:v=>String(v).replace(/"/g,'&quot;')});
  assert.equal((html.match(/<button /g)||[]).length,5);
  assert.match(html,/class="review-check is-yes" data-ux-check="pose" data-asset="a&quot;1" aria-label="pose: yes\. Key 1 changes it\."[^>]*>✓ pose</);
  assert.match(html,/class="review-check is-no" data-ux-check="face"[^>]*aria-label="face: no\. Key 2 changes it\."[^>]*>✗ face</);
  assert.match(html,/class="review-check" data-ux-check="outfit"[^>]*aria-label="outfit: not checked\. Key 3 changes it\."[^>]*>outfit</);
  assert.ok(!/disabled/.test(html));
  assert.match(R.chipsHTML({tags:[],names:['pose'],attr:'data-x',disabled:true,escape:String}),/ disabled/);
  assert.equal(R.chipsHTML({tags:[],names:[],attr:'data-x',escape:String}),'');
});
test('number keys 1-5 pick a check; anything else, or a modified key, does not',()=>{
  assert.equal(R.keyIndex({key:'1'}),0);assert.equal(R.keyIndex({key:'5'}),4);
  for(const e of [{key:'0'},{key:'6'},{key:'k'},{key:'1',ctrlKey:true},{key:'2',altKey:true},{key:'3',metaKey:true}])assert.equal(R.keyIndex(e),-1);
});
console.log('Review check contracts passed ('+count+')');
