'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const S=require('../app/static/setup-compatibility-selector.js');

const authority={
  provider_accessed:false,file_hashed:false,model_downloaded:false,
  installation_authorized:false,backend_switched:false,
  selection_changed:false,generation_submitted:false,
};
const candidate=(id,name,status,extra={})=>({
  id,name,identity:'sha256:'+id.padEnd(64,id[0]),status,
  selectable:['recommended','possible'].includes(status),
  expert_override_required:status==='needs_review',
  recommendation_rank:status==='recommended'?1:null,
  hard_conflicts:status==='incompatible'?[{code:'architecture_mismatch',message:'Architecture does not match.'}]:[],
  unknowns:status==='needs_review'?[{code:'local_file_unverified',message:'Exact local bytes need review.'}]:[],
  limitations:status==='possible'?[{code:'weak_evidence',message:'Evidence does not justify a recommendation.'}]:[],
  evidence_summary:{strong_support:0,strong_contradiction:0,qualifying_gallery_sources:0,qualifying_gallery_observations:0,weaker_support:0},
  ...extra,
});
function fixture(){
  const rows=[
    candidate('alpha','Alpha','recommended'),
    candidate('beta','Beta','possible'),
    candidate('gamma','Gamma','needs_review'),
    candidate('delta','Delta','incompatible'),
  ];
  return {
    format:'studio.setup-context-compatibility-report/v1',
    context_sha256:'a'.repeat(64),
    precondition:{inventory_revision:'b'.repeat(64),schema_revision:'c'.repeat(64),backend_id:'primary',runtime:'comfyui',switching:false},
    compatibility_input:{format:'studio.setup-compatibility-input/v1',slot:{role:'lora'},candidates:rows.map(({id,name,identity})=>({id,name,identity})),evidence:[]},
    compatibility:{format:'studio.setup-compatibility-report/v1',context_sha256:'d'.repeat(64),candidates:rows,diagnostics:[],...authority},
    source_contexts:rows.map(row=>({candidate_id:row.id,context_sha256:'e'.repeat(64),source_context_sha256:'f'.repeat(64),source_coverage_complete:true,review_revision:'sha256:'+'1'.repeat(64)})),
    observations:[],diagnostics:[],notice:'Advice only.',...authority,
  };
}
const option=(value,label,selected=false)=>({value,textContent:label,selected,disabled:false,dataset:{}});
function selector(value='beta'){
  const options=[option('alpha','Alpha'),option('beta','Beta',value==='beta'),option('gamma','Gamma',value==='gamma'),option('delta','Delta',value==='delta'),option('extra','Unreviewed extra',value==='extra')];
  return {options,value,dataset:{},attributes:{},events:[],setAttribute(k,v){this.attributes[k]=String(v);},removeAttribute(k){delete this.attributes[k];},dispatchEvent(event){this.events.push(event.type);}};
}

test('strictly validates report authority and decision semantics',()=>{
  const value=fixture(),before=JSON.stringify(value);
  assert.equal(S.validate(value),value);
  assert.equal(JSON.stringify(value),before);
  for(const mutate of [
    r=>{r.provider_accessed=true;},
    r=>{r.compatibility.candidates[2].expert_override_required=false;},
    r=>{r.compatibility.candidates[3].selectable=true;},
    r=>{r.compatibility.candidates[1].recommendation_rank=2;},
    r=>{r.compatibility.candidates.push({...r.compatibility.candidates[0]});},
    r=>{r.compatibility_input.candidates=r.compatibility_input.candidates.slice(1);},
  ]){
    const changed=fixture();mutate(changed);
    assert.throws(()=>S.validate(changed),/compatibility/i);
  }
});

test('projects the four states without changing evaluator order',()=>{
  const rows=S.project(fixture());
  assert.deepEqual(rows.map(row=>row.id),['alpha','beta','gamma','delta']);
  assert.deepEqual(rows.map(row=>row.label),['Recommended #1 · Alpha','Possible · Beta','Needs review · Gamma','Incompatible · Delta']);
  assert.deepEqual(rows.map(row=>row.normalSelectable),[true,true,false,false]);
  assert.deepEqual(rows.map(row=>row.expertSelectable),[true,true,true,false]);
  assert.match(rows[1].reason,/does not justify/i);
  assert.match(rows[2].reason,/local bytes/i);
  assert.match(rows[3].reason,/architecture/i);
  assert.ok(rows.every(Object.isFrozen));
});

test('decorates existing options without adding choices or changing selection',()=>{
  const select=selector('beta'),status={textContent:'',hidden:true};
  const before=select.options.length;
  const result=S.decorate(select,fixture(),{status,expert:false});
  assert.equal(select.options.length,before);
  assert.equal(select.value,'beta');
  assert.deepEqual(select.events,[]);
  assert.deepEqual(select.options.map(o=>o.disabled),[false,false,true,true,true]);
  assert.deepEqual(select.options.map(o=>o.textContent),[
    'Recommended #1 · Alpha','Possible · Beta','Needs review · Gamma','Incompatible · Delta','Needs review · Unreviewed extra',
  ]);
  assert.equal(select.attributes['aria-invalid'],undefined);
  assert.match(status.textContent,/Possible/i);
  assert.match(status.textContent,/does not justify/i);
  assert.equal(status.hidden,false);
  assert.equal(result.selected.id,'beta');
});

test('expert override exposes only Needs review and never Incompatible',()=>{
  const select=selector('gamma'),status={textContent:'',hidden:true};
  S.decorate(select,fixture(),{status,expert:false});
  assert.equal(select.options[2].disabled,true);
  assert.equal(select.attributes['aria-invalid'],'true');
  assert.match(status.textContent,/explicit expert review/i);

  S.decorate(select,fixture(),{status,expert:true});
  assert.equal(select.options[2].disabled,false);
  assert.equal(select.options[3].disabled,true);
  assert.equal(select.options[4].disabled,true);
  assert.equal(select.attributes['aria-invalid'],undefined);
  assert.match(status.textContent,/Needs review/i);
});

test('a selected incompatible or unreported value remains visible but invalid',()=>{
  for(const value of ['delta','extra']){
    const select=selector(value),status={textContent:'',hidden:true};
    S.decorate(select,fixture(),{status,expert:true});
    assert.equal(select.value,value);
    assert.equal(select.attributes['aria-invalid'],'true');
    assert.match(status.textContent,value==='delta'?/Incompatible/i:/not included/i);
  }
});
