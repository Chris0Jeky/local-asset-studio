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
assert.match(rendered('failed'),/Open review desk/);
assert.match(rendered('awaiting_review'),/data-choose-candidate/);
assert.doesNotMatch(rendered('reviewed',true),/data-choose-candidate|id="productionNotes"/);
assert.doesNotMatch(rendered('running'),/Open review desk/);
assert.doesNotMatch(rendered('completed',false,'native'),/Open review desk/);
console.log('Review frontend contracts passed: helpers, source URL scope and existing Experiments rendering');

// #1730: render and click the real Compare & review page, with only the existing API and Library hooks stubbed.
const {test}=require('node:test');
function comparisonPage(){
  const elements=new Map(),requests=[],opened=[];let current,refusal=null,libraryReads=0;
  const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',classList:{toggle(){}}});return elements.get(selector);};
  const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const context=vm.createContext({$,esc,api:async url=>{requests.push({url});return [current];},
    post:async(url,data)=>{requests.push({url,data:JSON.parse(JSON.stringify(data))});if(refusal)throw Error(refusal);current.state={...current.state,status:'reviewed',review:{status:data.asset_id?'selected':'needs_work',...data}};return current;},
    refreshAssets:async()=>{libraryReads++;},openAsset:id=>opened.push(id)});
  vm.runInContext(fs.readFileSync(require.resolve('../app/static/production.js'),'utf8'),context);
  const plan={id:project,name:'Study',kind:'comparison',state:{status:'awaiting_review',message:'Finished'},budget:{reserved:2,allowance:2},values:[1,2],
    stages:['A','B'].map(label=>({label,job:{status:'completed',outputs:[{asset_id:'asset-'+label,media_type:'image'}]}}))};
  const render=(value=plan)=>{current=structuredClone(value);context.fixture=current;vm.runInContext('productionPlans=[fixture];productionId=fixture.id;renderProduction();',context);};
  const click=(selector,dataset)=>$('#productionDetail').onclick({target:{closest:s=>s===selector?{dataset}:null}});
  return {$,plan,render,click,requests,opened,refuse:message=>{refusal=message;},libraryReads:()=>libraryReads};
}
test('awaiting study has one primary Review link to its existing desk',()=>{
  const page=comparisonPage();page.render();
  const html=page.$('#productionList').innerHTML+page.$('#productionDetail').innerHTML;
  assert.equal((html.match(/href="\/review\.html\?project=/g)||[]).length,1);
  assert.match(html,new RegExp('<a class="primary [^"]*" href="/review.html\\?project='+project+'">Review</a>'));
  assert.doesNotMatch(html,/Review now|Open review desk/);
  assert.equal(page.requests.length,0,'rendering never sends a request');
});
test('Review is hidden with zero candidates, including stages with no saved asset',()=>{
  const page=comparisonPage();
  for(const stages of [[],[{label:'A'}],[{label:'A',job:{status:'failed',outputs:[]}}],[{label:'A',job:{outputs:[{media_type:'image'}]}}]]){
    page.render({...page.plan,stages});
    assert.doesNotMatch(page.$('#productionList').innerHTML+page.$('#productionDetail').innerHTML,/href="\/review\.html\?project=/);
  }
});
test('Quick pick folds Choose and submits the unchanged review command',async()=>{
  const page=comparisonPage();page.render();
  const html=page.$('#productionDetail').innerHTML;
  const picks=[...html.matchAll(/<details[^>]*><summary>Quick pick<\/summary>([\s\S]*?)<\/details>/g)];
  assert.equal(picks.length,2);
  for(const [i,label] of ['A','B'].entries())assert.match(picks[i][1],new RegExp('data-choose-candidate="asset-'+label+'">Choose '+label+'</button>'));
  assert.equal((html.match(/data-choose-candidate=/g)||[]).length,2,'no unfolded duplicate Choose controls');
  page.$('#productionNotes').value='Keep the silhouette & light';
  await page.click('[data-choose-candidate]',{chooseCandidate:'asset-B'});
  assert.deepEqual(page.requests,[{url:'/api/production/'+project+'/review',data:{asset_id:'asset-B',notes:'Keep the silhouette & light',reviewer:'local-user'}},{url:'/api/production'}]);
  assert.equal(page.libraryReads(),0,'Choose does not write or reload Library metadata');
});
test('successful quick pick shows an escaped winner and Library action at the chosen candidate',async()=>{
  const page=comparisonPage();page.plan.stages[0].label='A <b>"&';page.render();
  assert.doesNotMatch(page.$('#productionDetail').innerHTML,/Winner:/,'no result before success');
  await page.click('[data-choose-candidate]',{chooseCandidate:'asset-A'});
  let html=page.$('#productionDetail').innerHTML;
  const articles=[...html.matchAll(/<article class="candidate">([\s\S]*?)<\/article>/g)].map(m=>m[1]);
  assert.match(articles[0],/<details[^>]* open><summary>Quick pick<\/summary>[\s\S]*?<p[^>]*role="status"[^>]*>Winner: A &lt;b&gt;&quot;&amp; \u00b7 <button[^>]*data-candidate-open="asset-A"[^>]*>Open in Library<\/button><\/p>[\s\S]*?<\/details>/);
  assert.doesNotMatch(articles[0],/Winner: A <b>/);
  assert.doesNotMatch(articles[1],/Winner:/,'the result belongs to the chosen candidate');
  assert.equal((html.match(/Winner:/g)||[]).length,1);
  page.render({...page.plan,state:{status:'reviewed',message:'Saved',review:{asset_id:'asset-A',status:'selected'}}});
  assert.match(page.$('#productionDetail').innerHTML,/Winner: A &lt;b&gt;&quot;&amp;/,'the saved result survives another render');
  await page.click('[data-candidate-open]',{candidateOpen:'asset-A'});
  assert.deepEqual(page.opened,['asset-A']);assert.equal(page.libraryReads(),1,'reuse the existing open-asset hook');
});
test('refused inline pick has no winner, and desk reviews keep legacy picks hidden',async()=>{
  const page=comparisonPage();page.render();page.refuse('Save refused');
  await page.click('[data-choose-candidate]',{chooseCandidate:'asset-A'});
  assert.doesNotMatch(page.$('#productionDetail').innerHTML,/Winner:/);
  assert.equal(page.$('#productionMessage').textContent,'Save refused');
  page.render({...page.plan,state:{status:'reviewed',message:'Desk',review:{desk_url:'/review.html',asset_id:'asset-A'}}});
  assert.doesNotMatch(page.$('#productionDetail').innerHTML,/Quick pick|data-choose-candidate|id="productionNotes"/);
});
