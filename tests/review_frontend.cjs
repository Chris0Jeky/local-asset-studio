'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {cropFromPercent,cropPixels,optionalInteger,artifactPath}=require('../app/static/review.js');
assert.deepEqual(cropFromPercent(['0','0','100','100']),[0,0,10000,10000]);
assert.deepEqual(cropFromPercent(['12.34','0.01','99.99','87.65']),[1234,1,9999,8765]);
for(const bad of [[0,0,0,100],[1,2,3],['',0,10,10],[false,0,10,10],[0,-0.001,100,100],[0,0,100.001,100],[NaN,0,10,10]])assert.throws(()=>cropFromPercent(bad));
assert.deepEqual(cropPixels([3333,3333,6667,6667],3,7),[0,2,3,5]);
assert.equal(optionalInteger('',0,86400),null);assert.equal(optionalInteger('0',0,86400),0);assert.equal(optionalInteger('1e2',0,86400),100);
for(const bad of [true,null,undefined,'1.2','-1','Infinity','NaN','86401'])assert.throws(()=>optionalInteger(bad,0,86400));
const project='a'.repeat(32),url=`/api/production/${project}/files/reviews/${'b'.repeat(32)}/preview-A.png`;
assert.equal(artifactPath(url,project),url);
for(const bad of ['https://evil.invalid/x',url+'?next=evil',url.replace('preview-A.png','../plan.json'),url.replace('/preview','//preview'),url.replace(project,'c'.repeat(32))])assert.throws(()=>artifactPath(bad,project));
// Exercise the actual Experiments entry point without reproducing its renderer.
const nodes=new Map();const $=selector=>{if(!nodes.has(selector))nodes.set(selector,{innerHTML:'',classList:{toggle(){}},value:'',checked:false});return nodes.get(selector);};
const sandbox={$,esc:String};vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(require.resolve('../app/static/production.js'),'utf8'),sandbox);
function rendered(status,desk=false,kind='comparison'){
  const plan={id:project,name:'Study',kind,state:{status,message:'fixture',review:desk?{desk_url:'/review.html'}:{}},budget:{reserved:2,allowance:2},stages:[{label:'A',job:{status:'completed',outputs:[{asset_id:'d'.repeat(32),media_type:'image'}]}}],values:[1]};
  sandbox.fixture=plan;vm.runInContext('productionPlans=[fixture];productionId=fixture.id;renderProduction();',sandbox);return $('#productionDetail').innerHTML;
}
assert.match(rendered('awaiting_review'),/Open review desk/);assert.match(rendered('failed'),/Open review desk/);
assert.match(rendered('awaiting_review'),/data-choose-candidate/);
assert.doesNotMatch(rendered('reviewed',true),/data-choose-candidate|id="productionNotes"/);
assert.doesNotMatch(rendered('running'),/Open review desk/);
assert.doesNotMatch(rendered('completed',false,'native'),/Open review desk/);
console.log('Review frontend contracts passed: helpers, source URL scope and existing Experiments rendering');
