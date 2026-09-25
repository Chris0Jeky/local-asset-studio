// Exercises the real import event handlers; optional transport uses the inert Studio HTTP fixture.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {webcrypto,createHash}=require('node:crypto');
const root=path.join(__dirname,'..'),html=fs.readFileSync(path.join(root,'app/static/index.html'),'utf8');
assert.match(html,/id="importCharacterStudy"/,'Runs & review needs the explicit character-case import entry');
assert.match(html,/<script src="\/static\/character-import.js"><\/script>/);
const sha=data=>createHash('sha256').update(data).digest('hex');
const bytes=Buffer.from('synthetic reference'),plan={kind:'character_study_plan',schema_version:1,submits_generation:false,plan_sha256:'a'.repeat(64),
  canon:{approval:{state:'approved',reviewer_kind:'human'},references:[{id:'front',sha256:sha(bytes),role:'identity',path:'front.png'}]},
  request:{study_id:'fixture-study',budget:{max_generation_attempts:2}},
  cases:[{id:'case-1',preset_id:'qwen-1ref',task_id:'portrait',route_id:'qwen',seed:7,reference_ids:['front'],required_checks:['identity']}]};
const handoff={kind:'character_study_handoff',schema_version:1,submits_generation:false,submission_payload:null,plan_sha256:plan.plan_sha256,case_id:'case-1',preset_id:'qwen-1ref',handoff_sha256:'b'.repeat(64),
  proposed_controls:{positive:'Synthetic case',seed:7},upload_requirements:[{...plan.canon.references[0],slot_index:0}]};
const clone=value=>JSON.parse(JSON.stringify(value));
async function httpTransport(base,url,options){
  // Node fetch ignores a supplied Host. Match the production loopback headers on
  // our ephemeral test listener with http.request, as the Python HTTP fixtures do.
  const body=options.body instanceof Blob?Buffer.from(await options.body.arrayBuffer()):Buffer.from(options.body||'');
  return new Promise((resolve,reject)=>{
    const request=require('node:http').request(base+url,{method:options.method||'GET',headers:{Host:'127.0.0.1:8191',Origin:'http://127.0.0.1:8191','Content-Length':body.length,...options.headers}},response=>{
      const chunks=[];response.on('error',reject);response.on('data',part=>chunks.push(part));response.on('end',()=>{
        try{const data=JSON.parse(Buffer.concat(chunks));if(response.statusCode>=400){const error=Error(data.error);error.status=response.statusCode;reject(error);}else resolve(data);}catch(error){reject(error);}
      });
    });
    request.setTimeout(10000,()=>request.destroy(Error('Inert HTTP fixture timed out')));request.on('error',reject);request.end(body);
  });
}
function harness(fixture={plan,handoff,references:[{bytes:bytes.toString('base64'),type:'image/png'}]},base=null){
  const elements=new Map(),requests=[],messages=[];
  const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,hidden:false,files:[],classList:{toggle(){}},showModal(){this.open=true;},close(){this.open=false;}});return elements.get(selector);};
  const id=sha('character-primary:'+fixture.plan.plan_sha256+':'+fixture.handoff.case_id).slice(0,32);
  const project={id,name:'Saved fixture case',kind:'comparison',state:{status:'planned'},budget:{allowance:2,reserved:0},root_id:'character-study:'+fixture.plan.plan_sha256,
    plan:{character_source:{kind:'character_primary_import',study_plan:fixture.plan,handoff:fixture.handoff,case_id:fixture.handoff.case_id}}};
  const transport={saved:false,drop:false,uploadFail:false,unconfirmed:false};
  const api=async(url,options={})=>{
    const method=options.method||'GET';requests.push({url,method,body:options.body});
    if(base)return httpTransport(base,url,options);
    if(url==='/api/production'&&method==='GET')return transport.saved?[project]:[];
    if(url==='/api/production/'+id)return project;
    if(url==='/api/upload'){if(transport.uploadFail)throw Error('inert upload failure');return {file:'f'.repeat(32)+'_'+options.headers['X-Filename']+'.png'};}
    if(url==='/api/production'&&method==='POST'){if(transport.unconfirmed)throw Error('inert unconfirmed request');transport.saved=true;if(transport.drop)throw Error('inert lost reply');return project;}
    throw Error('Unexpected request: '+method+' '+url);
  };
  const context=vm.createContext({$,esc:value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),crypto:webcrypto,TextEncoder,Uint8Array,AbortController,
    api,post:(url,data)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),
    refreshProduction:async()=>{},showView(){},productionId:null,productionMessage:(...args)=>messages.push(args)});
  vm.runInContext(fs.readFileSync(path.join(root,'app/static/character-import.js'),'utf8'),context);
  const load=async(p=fixture.plan,h=fixture.handoff)=>{
    $('#importCharacterStudy').onclick();$('#characterPlanFile').files=[new File([p===fixture.plan&&fixture.plan_text?fixture.plan_text:JSON.stringify(p)],'plan.json')];
    $('#characterHandoffFile').files=[new File([h===fixture.handoff&&fixture.handoff_text?fixture.handoff_text:JSON.stringify(h)],'handoff.json')];
    await $('#readCharacterCase').onclick();
  };
  const references=()=>fixture.references.forEach((ref,i)=>{$('#characterReference'+i).files=[new File([Buffer.from(ref.bytes,'base64')],'source.png',{type:ref.type})];});
  const submit=()=>$('#characterImportForm').onsubmit({preventDefault(){}});
  return {$,requests,messages,transport,context,project,load,references,submit};
}
(async()=>{
  if(process.argv[2]==='--http'){
    const fixture=JSON.parse(fs.readFileSync(process.argv[3],'utf8')),h=harness(fixture,process.argv[4]);
    await h.load();assert.equal(h.requests.length,0);h.references();await h.submit();
    assert.equal(h.context.productionId,h.project.id,h.$('#characterImportStatus').textContent);assert.equal(h.requests.filter(r=>r.method==='POST'&&r.url==='/api/production').length,1);
    await h.load();h.references();await h.submit();
    assert.equal(h.requests.filter(r=>r.method==='POST'&&r.url==='/api/production').length,1,'Reopening a saved case must not import twice');
    assert.equal(h.requests.filter(r=>r.url==='/api/upload').length,fixture.references.length);
    assert.ok(h.requests.every(r=>!r.url.includes('/start')&&!r.url.includes('/jobs')));
    console.log('Character import real HTTP path preserves one case and zero generation requests.');return;
  }
  let h=harness();assert.equal(h.requests.length,0);await h.load();assert.equal(h.requests.length,0,'Reading files stays local');
  assert.match(h.$('#characterCaseSummary').textContent,/portrait/);assert.match(h.$('#characterCaseSummary').textContent,/2/);
  await h.submit();assert.equal(h.requests.length,0,'Missing reference must fail before any transport');
  h.$('#characterReference0').files=[new File(['wrong'],'wrong.png',{type:'image/png'})];await h.submit();assert.equal(h.requests.length,0,'Wrong bytes must fail before transport');
  h.references();await Promise.all([h.submit(),h.submit()]);
  assert.equal(h.requests.filter(r=>r.url==='/api/production'&&r.method==='POST').length,1);
  const sent=JSON.parse(h.requests.find(r=>r.url==='/api/production'&&r.method==='POST').body);
  assert.deepEqual(Object.keys(sent).sort(),['character_handoff','character_plan','max_seconds','name','uploads']);
  assert.deepEqual(sent.uploads,[{reference_id:'front',file:'f'.repeat(32)+'_front.png'}]);assert.equal(sent.max_seconds,1800);
  assert.equal(h.context.productionId,h.project.id);assert.ok(!h.requests.some(r=>/\/(start|resume|jobs)$/.test(r.url)));
  const decimal=clone(handoff);decimal.reference_policy={weight:1};
  h=harness({plan,handoff:decimal,handoff_text:JSON.stringify(decimal).replace('"weight":1','"weight":1.0'),references:[{bytes:bytes.toString('base64'),type:'image/png'}]});
  await h.load();h.references();await h.submit();
  assert.match(h.requests.find(r=>r.url==='/api/production'&&r.method==='POST').body,/"weight":1\.0/,'Original numeric representations must survive the browser; Python contract hashes distinguish 1.0 from 1');
  for(const mutate of [p=>p.canon.approval.state='draft',p=>p.cases[0].id='another-case',p=>p.cases[0].reference_ids=['different'],p=>p.cases[0].seed=8]){
    h=harness();const p=clone(plan);mutate(p);await h.load(p);assert.equal(h.$('#characterCaseFields').hidden,true);assert.equal(h.requests.length,0);
  }
  h=harness();const changed=clone(handoff);changed.upload_requirements[0].slot_index=1;await h.load(plan,changed);assert.equal(h.$('#characterCaseFields').hidden,true);
  h=harness();await h.load();h.references();h.transport.drop=true;await h.submit();await h.submit();
  assert.equal(h.requests.filter(r=>r.url==='/api/production'&&r.method==='POST').length,1,'A lost response is reconciled read-only');
  assert.equal(h.context.productionId,h.project.id);
  h=harness();await h.load();h.references();h.transport.saved=true;await h.submit();assert.equal(h.requests.filter(r=>r.method==='POST').length,0,'Existing case is opened without another upload/import');
  h=harness();await h.load();h.references();h.transport.unconfirmed=true;await h.submit();await h.submit();
  assert.equal(h.requests.filter(r=>r.method==='POST'&&r.url==='/api/production').length,1,'An absent saved case after a lost reply must not trigger another import');
  assert.match(h.$('#characterImportStatus').textContent,/No import was repeated/);
  h=harness();await h.load();h.references();h.transport.saved=true;
  h.project.plan.character_source={...h.project.plan.character_source,handoff:{...handoff,handoff_sha256:'c'.repeat(64)}};
  await h.submit();assert.equal(h.requests.filter(r=>r.method==='POST').length,0);assert.match(h.$('#characterImportStatus').textContent,/different handoff/);
  const pairPlan=clone(plan),pairHandoff=clone(handoff),back=Buffer.from('second synthetic reference');
  pairPlan.canon.references.push({id:'back',role:'identity',path:'back.png',sha256:sha(back)});pairPlan.cases[0].reference_ids.push('back');
  pairHandoff.upload_requirements.push({...pairPlan.canon.references[1],slot_index:1});
  h=harness({plan:pairPlan,handoff:pairHandoff,references:[{bytes:bytes.toString('base64'),type:'image/png'},{bytes:back.toString('base64'),type:'image/png'}]});
  await h.load();h.references();h.$('#characterReference1').files=[new File(['wrong'],'wrong.png',{type:'image/png'})];await h.submit();
  assert.equal(h.requests.length,0,'A bad later reference must not upload the valid earlier one');
  h.references();await h.submit();assert.deepEqual(JSON.parse(h.requests.find(r=>r.url==='/api/production'&&r.method==='POST').body).uploads.map(u=>u.reference_id),['front','back']);
  h=harness();await h.load();h.references();h.$('#characterImportMinutes').value='0';await h.submit();assert.equal(h.requests.length,0);
  h.$('#characterImportMinutes').value='30';h.$('#characterPlanFile').onchange();await h.submit();assert.equal(h.requests.length,0,'Changing plan files invalidates the prepared case');
  {
    const second=Buffer.from('second synthetic reference'),pairPlan=clone(plan),pairHandoff=clone(handoff);
    pairPlan.canon.references.push({id:'back',role:'identity',path:'back.png',sha256:sha(second)});pairPlan.cases[0].reference_ids.push('back');
    pairHandoff.upload_requirements.push({...pairPlan.canon.references[1],slot_index:1});
    h=harness({plan:pairPlan,handoff:pairHandoff,references:[{bytes:bytes.toString('base64'),type:'image/png'},{bytes:second.toString('base64'),type:'image/png'}]});
    await h.load();h.references();
    let started=0,cancelDisabledDuringLoop=null,hadSignal=false;const inner=h.context.api;
    h.context.api=async(url,options={})=>{
      if(url==='/api/upload'){if(started===0){cancelDisabledDuringLoop=h.$('#cancelCharacterImport').disabled;hadSignal=!!(options&&options.signal);h.$('#cancelCharacterImport').onclick();}started++;}
      return inner(url,options);
    };
    await h.submit();
    assert.equal(cancelDisabledDuringLoop,false,'Cancel must stay enabled during the reference read/hash/upload loop');
    assert.equal(hadSignal,true,'The in-flight upload must receive an AbortController signal');
    assert.equal(started,1,'Cancel during the loop must stop further uploads');
    assert.match(h.$('#characterImportStatus').textContent,/Import cancelled after 1 of 2 pictures/i,'Cancelling must report how many pictures were uploaded');
    assert.match(h.$('#characterImportStatus').textContent,/Nothing was imported/i,'Cancelling before the final commit must commit nothing and say so');
    assert.equal(h.requests.filter(r=>r.url==='/api/production'&&r.method==='POST').length,0,'A cancelled import must not register the case');
    assert.equal(h.$('#cancelCharacterImport').disabled,false,'Cancel must be usable after the cancelled import');
  }
  console.log('Character import controls preserve reference order, exact bytes, explicit import and no duplicate submission.');
})().catch(error=>{console.error(error);process.exitCode=1;});
