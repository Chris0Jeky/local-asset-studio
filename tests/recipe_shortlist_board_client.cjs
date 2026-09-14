'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const C=require('../app/static/recipe-shortlist.js');

const source={asset_id:'style-0',sha256:'b'.repeat(64),role:'style'};
const query={goal:'reference-image',reference_count:1,limit:6,offset:0,sources:[source]};
const candidate=()=>({
  preset_id:'style-pose-nova',name:'Style + Pose Nova',description:'Fixture',backend_id:'primary',
  operation:'restyle',prompt_role:'description',reference_count:4,template_sha256:'d'.repeat(64),
  reference_board:{minimum:1,slot_count:3,source_input:'last_reference'},status:'unknown',
  checks:[{code:'restyle_source_separate',state:'unknown',message:'Pose source remains separate.'}],requirements:[],
  source_assignments:[{...source,slot:1,binding:['14','image'],role_mode:'style-board'}]
});
const report=()=>({
  format:'studio.recipe-shortlist/v1',goal:'reference-image',reference_count:1,snapshot_sha256:'a'.repeat(64),
  source:null,sources:[{...source,slot:1,title:'Style study',width:32,height:48,bytes_verified:true,staged:false}],
  candidates:[candidate()],total:1,offset:0,next_offset:null,counts:{observed:0,unknown:1,needs_setup:0},
  diagnostics:[],checked_at:123,generation_submitted:false,execution_authorized:false,scope:'Default graph only'
});

test('accepts a proven Restyle board with three visual slots and a separate native source',()=>{
  const value=C.validate(report(),query);
  assert.equal(value.candidates[0].reference_count,4);
  assert.deepEqual(value.candidates[0].reference_board,{minimum:1,slot_count:3,source_input:'last_reference'});
  assert.equal(value.candidates[0].source_assignments[0].role_mode,'style-board');
});

test('rejects four-input candidates without the exact Restyle board contract',()=>{
  const edits=[
    r=>delete r.candidates[0].reference_board,
    r=>r.candidates[0].reference_board.minimum=0,
    r=>r.candidates[0].reference_board.slot_count=2,
    r=>r.candidates[0].reference_board.source_input='reference',
    r=>r.candidates[0].reference_board.extra=true,
    r=>r.candidates[0].operation='instruction-edit',
    r=>r.candidates[0].reference_count=3,
  ];
  for(const edit of edits){const value=report();edit(value);assert.throws(()=>C.validate(value,query));}
});

test('style-board assignment mode is board-only and requires an actual image binding',()=>{
  for(const patch of [{role_mode:'prompt-guidance'},{binding:null}]){
    const value=report();Object.assign(value.candidates[0].source_assignments[0],patch);
    assert.throws(()=>C.validate(value,query));
  }
  const value=report();delete value.candidates[0].reference_board;value.candidates[0].reference_count=1;
  assert.throws(()=>C.validate(value,query));
});
