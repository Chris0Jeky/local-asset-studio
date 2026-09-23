'use strict';
const assert=require('node:assert/strict');
const C=require('../app/static/continuation-core.js');

const capability={
  version:1,
  consumes_source:true,
  operation:'combine',
  prompt_role:'instruction',
  reference_count:2,
  source_input:'last_reference',
  board_min:1,
  template_sha256:'a'.repeat(64)
};
const source={preset_id:'flux-edit'};
const sourcePreset={id:'flux-edit',name:'FLUX edit',family:'FLUX.2 Klein 4B'};
const four={id:'combine-klein',name:'Combine with Klein 4B',family:'FLUX.2 Klein 4B',continuation_capability:capability};
const nine={id:'combine-klein-9b',name:'Combine with Klein 9B',family:'FLUX.2 Klein 9B',continuation_capability:capability};
const depth={id:'combine-klein-9b-depth',name:'Combine with Klein 9B depth',family:'FLUX.2 Klein 9B',continuation_capability:capability};

assert.deepEqual(
  C.destinations('combine',[sourcePreset,four,nine],source).map(item=>item.id),
  ['combine-klein-9b','combine-klein'],
  'the declared 9B pose-following route must lead even when the source came from the 4B family'
);

assert.deepEqual(
  C.destinations('combine',[sourcePreset,four,nine,depth],source).map(item=>item.id),
  ['combine-klein-9b-depth','combine-klein-9b','combine-klein'],
  'the newer depth lead must keep the pose-first 9B route ahead of the 4B family fallback'
);

const copypose={id:'combine-klein-9b-copypose',name:'Combine with Klein 9B Copy Pose',family:'FLUX.2 Klein 9B',continuation_capability:capability};
const skeleton={id:'combine-klein-9b-skeleton',name:'Combine with a drawn skeleton',family:'FLUX.2 Klein 9B',continuation_capability:capability};
assert.deepEqual(
  C.destinations('combine',[sourcePreset,four,nine,depth,skeleton,copypose],source).map(item=>item.id),
  ['combine-klein-9b-copypose','combine-klein-9b-skeleton','combine-klein-9b-depth','combine-klein-9b','combine-klein'],
  'Copy Pose leads the Combine route (owner decision q-28, 23 September 2026): Copy Pose keeps the character look and background best, the drawn skeleton is the most reliable pose'
);

const replace={id:'combine-klein-9b-replace',name:'Combine with Klein 9B replace',family:'FLUX.2 Klein 9B',continuation_capability:capability};
for(const from of [sourcePreset,{id:'nine-source',name:'Nine source',family:'FLUX.2 Klein 9B'}]){
  assert.deepEqual(
    C.destinations('combine',[from,four,nine,depth,skeleton,copypose,replace],{preset_id:from.id}).map(item=>item.id),
    ['combine-klein-9b-copypose','combine-klein-9b-skeleton','combine-klein-9b-depth','combine-klein-9b-replace','combine-klein-9b','combine-klein'],
    'the whole declared order holds whether the source came from the 4B or the 9B family (replace sits before pose-first 9B and the 4B fallback)'
  );
}

assert.deepEqual(
  C.destinations('combine',[sourcePreset,four,{...nine,runtime_block:'Unavailable in this runtime'}],source).map(item=>item.id),
  ['combine-klein','combine-klein-9b'],
  'a runtime-blocked preferred route must not displace an available fallback'
);

console.log('Continuation route lead contracts passed: 6');
