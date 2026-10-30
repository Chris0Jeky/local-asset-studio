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

// Run the shipped desk against DOM/canvas boundaries; only the initial inspect is stubbed.
const test=require('node:test');
async function holdDesk({delayB=false,saves=false,finalized=false,setup}={}){
  const nodes=new Map(),all=[],requests=[],listeners={document:{},window:{}},gate=[];let active=null,decodeB;
  const matches=(node,selector)=>selector.split(',').some(s=>s.startsWith('#')?node.id===s.slice(1):s==='[contenteditable]'?node.contentEditable==='true':node.tagName.toLowerCase()===s);
  class Node {
    constructor(tag,id=''){this.tagName=tag.toUpperCase();this.id=id;this.children=[];this.dataset={};this.attributes={};this.value='';this.hidden=false;this.disabled=false;this.textContent='';this.parentElement=null;this.events={};this.width=this.height=768;this.draws=[];this.classList={toggle(){}};all.push(this);}
    append(...children){for(const child of children){child.parentElement=this;this.children.push(child);}}
    replaceChildren(...children){this.children=[];this.append(...children);}
    setAttribute(key,value){this.attributes[key]=String(value);}
    getAttribute(key){return this.attributes[key]??null;}
    querySelectorAll(selector){return this.children.flatMap(c=>[...(matches(c,selector)?[c]:[]),...c.querySelectorAll(selector)]);}
    closest(selector){return matches(this,selector)?this:this.parentElement?.closest(selector)||null;}
    addEventListener(type,fn){(this.events[type]??=[]).push(fn);}
    focus(){active=this;this.onfocus?.();emit('document','focusin',{target:this});}
    getContext(){return {fillRect(){},drawImage:(...args)=>this.draws.push(args)};}
  }
  const html=fs.readFileSync(require.resolve('../app/static/review.html'),'utf8');
  for(const m of html.matchAll(/<([a-z0-9]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)){const node=new Node(m[1],m[2]);for(const a of m[0].matchAll(/([\w-]+)="([^"]*)"/g))node.setAttribute(a[1],a[2]);nodes.set(m[2],node);}
  const $=id=>nodes.get(id)||all.find(n=>n.id===id),tick=()=>new Promise(resolve=>setImmediate(resolve));
  function emit(surface,type,extra={}){const event={target:$('leftCanvas'),key:' ',button:0,prevented:false,preventDefault(){this.prevented=true;},...extra};for(const fn of (typeof surface==='string'?listeners[surface]:surface.events)[type]||[])fn(event);if(typeof surface!=='string')surface['on'+type]?.(event);return event;}
  for(const [id,value] of Object.entries({cropLeft:'25',cropTop:'25',cropRight:'75',cropBottom:'75',background:'dark',mode:'pair'}))$(id).value=value;
  const state={exists:true,revision:0,revealed:false,finalized,selected:null,notes:'',crop:[2500,2500,7500,7500],background:'dark',history:[],export:null,grid:null,
    candidates:[...'ABC'].map(alias=>({alias,preview_url:url.replace('preview-A.png',alias+'.png'),assessment:{verdict:'unreviewed',notes:'',observations:{},cleanup_seconds:null,preference:null}}))};
  setup?.(state);
  const document={querySelector:s=>$(s.slice(1)),querySelectorAll:s=>all.filter(n=>matches(n,s)),createElement:tag=>new Node(tag),get activeElement(){return active;},addEventListener:(type,fn)=>(listeners.document[type]??=[]).push(fn)};
  const sandbox={document,location:{search:'?project='+project},URLSearchParams,console,
    window:{addEventListener:(type,fn)=>(listeners.window[type]??=[]).push(fn)},
    Image:class {decode(){this.naturalWidth=this.src.endsWith('/B.png')?400:200;this.naturalHeight=this.naturalWidth*2;return delayB&&this.src.endsWith('/B.png')?new Promise(resolve=>{decodeB=resolve;}):Promise.resolve();}},
    fetch:async(url,options)=>{requests.push({url,options});if(!saves||requests.length===1){assert.equal(requests.length,1,'Hold interactions must never fetch or POST');return {ok:true,json:async()=>state};}return new Promise(resolve=>gate.push(resolve));}};
  const source=process.env.REVIEW_TEST_REF?require('node:child_process').execFileSync('git',['show',process.env.REVIEW_TEST_REF+':app/static/review.js'],{encoding:'utf8'}):fs.readFileSync(require.resolve('../app/static/review.js'),'utf8');
  vm.runInNewContext(source,sandbox);await tick();
  // A save stays in flight until answered; the reply is the saved review one revision on, as the server returns it.
  const answer=async()=>{const body=JSON.parse(requests.at(-1).options.body),saved=structuredClone(state);saved.revision=body.expected_revision+1;saved.candidates.find(c=>c.alias===body.alias).assessment=body.assessment;gate.shift()({ok:true,json:async()=>saved});await tick();await tick();};
  // Answer the oldest in-flight request with make(body,state), then let the continuation (the next request) run.
  const respond=async make=>{gate.shift()(make(JSON.parse(requests.at(-1).options.body),state));for(let i=0;i<4;i++)await tick();};
  return {$,emit,tick,document,requests,Node,answer,respond,state,decodeB:()=>decodeB(),draw:side=>$(side+'Canvas').draws.at(-1)};
}
test('Review desk hold-to-compare',async t=>{
  const {$,emit,tick,document,requests,Node,draw}=await holdDesk();
  const down=(extra={})=>emit('document','keydown',extra),up=()=>emit('document','keyup');
  const shown=(side,alias)=>assert.ok(draw(side)[0].src.endsWith('/'+alias+'.png'),side+' draws '+alias);
  await t.test('Space swaps the primary canvas using the shared crop and restores on keyup',async()=>{
    shown('left','A');const caption=$('leftCaption').textContent;
    assert.equal(down().prevented,true);await tick();shown('left','B');shown('right','B');
    assert.deepEqual(draw('left').slice(1),[100,200,200,400,192,0,384,768]);assert.equal($('leftCaption').textContent,caption);
    assert.equal($('holdCompare').getAttribute('aria-pressed'),'true');up();await tick();shown('left','A');
    assert.deepEqual(draw('left').slice(1),[50,100,100,200,192,0,384,768]);assert.equal($('holdCompare').getAttribute('aria-pressed'),'false');
  });
  await t.test('focused right canvas and single views use the other candidate',async()=>{
    $('rightCanvas').focus();down();await tick();shown('left','A');shown('right','A');up();await tick();shown('right','B');
    for(const mode of ['left','right']){$('mode').value=mode;$('mode').onchange();down();await tick();shown(mode,mode==='left'?'B':'A');up();await tick();shown(mode,mode==='left'?'A':'B');}
    $('mode').value='pair';$('mode').onchange();$('leftCanvas').focus();
  });
  await t.test('pointer release, cancellation and leaving restore without a click toggle',async()=>{
    for(const end of ['pointerup','pointercancel','pointerleave']){
      emit($('holdCompare'),'pointerdown',{target:$('holdCompare')});await tick();shown('left','B');
      emit($('holdCompare'),end,{target:$('holdCompare')});await tick();shown('left','A');assert.equal($('holdCompare').getAttribute('aria-pressed'),'false');
    }
    for(const extra of [{button:2},{ctrlKey:true},{shiftKey:true},{metaKey:true},{altKey:true}]){emit($('holdCompare'),'pointerdown',extra);await tick();shown('left','A');assert.equal($('holdCompare').getAttribute('aria-pressed'),'false');}
  });
  await t.test('blur and visibility changes always release',async()=>{
    for(const [surface,type] of [['window','blur'],['document','visibilitychange']]){down();await tick();shown('left','B');emit(surface,type);await tick();shown('left','A');assert.equal($('holdCompare').getAttribute('aria-pressed'),'false');}
  });
  await t.test('candidate changes restore, including assessment and side selection',async()=>{
    down();await tick();$('candidate').value='B';$('candidate').onchange();await tick();shown('left','A');assert.equal($('holdCompare').getAttribute('aria-pressed'),'false');
    for(const side of ['left','right']){down();await tick();$(side).value='C';$(side).onchange();await tick();shown('left',side==='left'?'C':'A');shown('right',side==='right'?'C':'B');assert.equal($('holdCompare').getAttribute('aria-pressed'),'false');$(side).value=side==='left'?'A':'B';$(side).onchange();await tick();}
    down();await tick();$('swap').onclick();await tick();shown('left','B');shown('right','A');assert.equal($('holdCompare').getAttribute('aria-pressed'),'false');$('swap').onclick();await tick();
  });
  await t.test('typing, modifiers, repeats and other keys do nothing',async()=>{
    const editable=new Node('div');editable.contentEditable='true';const child=new Node('span');editable.append(child);
    for(const target of [$('cropLeft'),$('notes'),$('mode'),editable,child,$('swap')]){assert.equal(down({target}).prevented,false);await tick();shown('left','A');}
    for(const extra of [{altKey:true},{ctrlKey:true},{metaKey:true},{shiftKey:true},{repeat:true},{isComposing:true},{key:'s'}]){assert.equal(down(extra).prevented,false);await tick();shown('left','A');}
    down();await tick();emit('document','focusin',{target:$('notes')});await tick();shown('left','A');
  });
  await t.test('blind captions stay stable and holds perform no requests',async()=>{
    const captions=[$('leftCaption').textContent,$('rightCaption').textContent];down();await tick();shown('left','B');
    assert.deepEqual([$('leftCaption').textContent,$('rightCaption').textContent],captions);assert.match(captions[0],/^Candidate A .*settings hidden$/);assert.match(captions[1],/^Candidate B .*settings hidden$/);
    up();await tick();assert.equal(requests.length,1);assert.equal(JSON.parse(requests[0].options.body).action,'inspect');assert.equal(document.querySelector('#message').textContent,'Saved review loaded. No generation performed.');
  });
  await t.test('release wins over a pending image decode',async()=>{
    const desk=await holdDesk({delayB:true});
    desk.emit('document','keydown');desk.emit('document','keyup',{target:desk.$('notes'),ctrlKey:true});desk.decodeB();await desk.tick();
    assert.ok(desk.$('leftCanvas').draws.every(args=>args[0].src.endsWith('/A.png')));assert.ok(desk.draw('right')[0].src.endsWith('/B.png'));assert.equal(desk.$('holdCompare').getAttribute('aria-pressed'),'false');assert.equal(desk.requests.length,1);
  });
});

// #1752: K/W/X in Pair and single views save the candidate on show through the Grid's own save path.
test('Review desk Pair-view K/W/X',async t=>{
  const press=(desk,key,extra={})=>desk.emit('document','keydown',{key,...extra}),saved=desk=>desk.requests.slice(1).map(r=>JSON.parse(r.options.body));
  await t.test('loading never saves; K saves the left candidate by default with the Grid request shape',async()=>{
    const desk=await holdDesk({saves:true});assert.equal(desk.requests.length,1);
    assert.equal(press(desk,'k').prevented,true);await desk.tick();
    const [body]=saved(desk);assert.equal(desk.requests.length,2);assert.equal(JSON.parse(desk.requests[0].options.body).action,'inspect');
    assert.deepEqual(Object.keys(body).sort(),['action','alias','assessment','expected_revision']);
    assert.deepEqual([body.action,body.alias,body.expected_revision,body.assessment.verdict],['rate','A',0,'keep']);
    assert.deepEqual(Object.keys(body.assessment).sort(),['cleanup_seconds','notes','observations','preference','verdict']);
    assert.equal(desk.$('message').textContent,'Saving…');await desk.answer();
    assert.equal(desk.$('message').textContent,'Saved. No generation performed.');
    assert.deepEqual([desk.$('left').value,desk.$('right').value,desk.$('mode').value],['A','B','pair'],'the layout stays as the owner left it');
    assert.match(desk.$('progress').children[0].children[1].textContent,/Keep/);
  });
  await t.test('the focused or pressed preview is the one saved; W and X map to Needs work and Not this',async()=>{
    const desk=await holdDesk({saves:true});
    desk.$('rightCanvas').focus();press(desk,'w');await desk.tick();await desk.answer();
    desk.emit(desk.$('leftCanvas'),'pointerdown',{});press(desk,'X');await desk.tick();
    assert.deepEqual(saved(desk).map(b=>[b.alias,b.assessment.verdict,b.expected_revision]),[['B','needs_work',0],['A','reject',1]]);
  });
  await t.test('Left only and Right only save the side on show, whichever preview was last focused',async()=>{
    const desk=await holdDesk({saves:true});
    desk.$('rightCanvas').focus();desk.$('mode').value='left';desk.$('mode').onchange();press(desk,'k');await desk.tick();await desk.answer();
    desk.$('leftCanvas').focus();desk.$('mode').value='right';desk.$('right').value='C';desk.$('mode').onchange();await desk.tick();press(desk,'x');await desk.tick();
    assert.deepEqual(saved(desk).map(b=>[b.alias,b.assessment.verdict]),[['A','keep'],['C','reject']]);
  });
  await t.test('an unsaved draft of the shown candidate is saved with the verdict',async()=>{
    const desk=await holdDesk({saves:true});
    desk.$('check-constraints').value='pass';desk.$('notes').value='Lantern glow holds';desk.emit(desk.$('assessmentForm'),'input',{target:desk.$('check-constraints')});
    press(desk,'k');await desk.tick();const [body]=saved(desk);
    assert.deepEqual([body.alias,body.assessment.verdict,body.assessment.observations.constraints,body.assessment.notes],['A','keep','pass','Lantern glow holds']);
  });
  await t.test('typing, modifiers, repeats, composition and other keys never save',async()=>{
    const desk=await holdDesk({saves:true}),editable=new desk.Node('div');editable.contentEditable='true';const child=new desk.Node('span');editable.append(child);
    for(const target of [desk.$('notes'),desk.$('cropLeft'),desk.$('mode'),desk.$('candidate'),editable,child])assert.equal(press(desk,'k',{target}).prevented,false);
    for(const extra of [{altKey:true},{ctrlKey:true},{metaKey:true},{shiftKey:true},{repeat:true},{isComposing:true}])assert.equal(press(desk,'w',extra).prevented,false);
    for(const other of ['s','Enter','ArrowDown'])assert.equal(press(desk,other).prevented,false);
    await desk.tick();assert.equal(desk.requests.length,1);
  });
  await t.test('nothing saves while a save is in flight',async()=>{
    const desk=await holdDesk({saves:true});press(desk,'k');await desk.tick();assert.equal(desk.requests.length,2);
    assert.equal(press(desk,'x').prevented,false);await desk.tick();assert.equal(desk.requests.length,2);
    await desk.answer();press(desk,'x');await desk.tick();assert.deepEqual(saved(desk).map(b=>[b.alias,b.assessment.verdict,b.expected_revision]),[['A','keep',0],['A','reject',1]]);
  });
  await t.test('while Space is held the shown image is the other candidate, so the key is refused',async()=>{
    const desk=await holdDesk({saves:true});desk.emit('document','keydown');await desk.tick();
    assert.equal(desk.$('holdCompare').getAttribute('aria-pressed'),'true');
    assert.equal(press(desk,'k').prevented,true);await desk.tick();assert.equal(desk.requests.length,1);
    assert.match(desk.$('message').textContent,/^Release Space first/);
    desk.emit('document','keyup');await desk.tick();press(desk,'k');await desk.tick();assert.equal(saved(desk).length,1);assert.equal(saved(desk)[0].alias,'A');
  });
  await t.test('a preview still loading is never rated: the key waits for the shown candidate',async()=>{
    const desk=await holdDesk({saves:true,delayB:true});desk.$('swap').onclick();await desk.tick();
    assert.equal(desk.$('left').value,'B');assert.equal(press(desk,'k').prevented,true);await desk.tick();
    assert.equal(desk.requests.length,1,'no rating while the left canvas still shows A');assert.match(desk.$('message').textContent,/^Wait for Candidate B/);
    desk.decodeB();await desk.tick();await desk.tick();press(desk,'k');await desk.tick();assert.deepEqual(saved(desk).map(b=>b.alias),['B']);
  });
  await t.test('a recorded decision is never reopened by a shortcut',async()=>{
    const desk=await holdDesk({saves:true,finalized:true});
    assert.equal(press(desk,'k').prevented,true);await desk.tick();assert.equal(desk.requests.length,1,'no rating request');
    assert.match(desk.$('message').textContent,/^The decision is recorded/);
  });
  await t.test('blind captions keep their candidate letters and hidden settings',async()=>{
    const desk=await holdDesk({saves:true});press(desk,'k');await desk.tick();await desk.answer();
    assert.match(desk.$('leftCaption').textContent,/^Candidate A .*settings hidden$/);assert.match(desk.$('rightCaption').textContent,/^Candidate B .*settings hidden$/);
    assert.doesNotMatch(desk.$('message').textContent,/engine|seed/i);
  });
});

// #1752: the winner path. The click is the human declaration of the constraints check; nothing else sets it, and Reveal stays separate.
test('Review desk Choose as winner',async t=>{
  const desk=setup=>holdDesk({saves:true,setup(state){
    state.revealed=true;state.evidence={stages:[{status:'completed'},{status:'completed'},{status:'failed'}]};
    state.candidates.forEach((c,i)=>{c.source={filename:c.alias+'.png',stage:i,sha256:'0'.repeat(64),transform:{oriented_size:[200,400]}};c.assessment={verdict:['keep','keep','reject'][i],notes:'note '+c.alias,cleanup_seconds:30,preference:4,
      observations:{constraints:'not_assessed',identity:'pass',pose_contact:'not_assessed',composition:'fail',detail:'not_assessed'}};});
    setup?.(state);}});
  // review_desk.change: a rating reopens the decision; finalize records it.
  const serve=(body,state)=>{
    state.revision=body.expected_revision+1;
    if(body.action==='rate'){state.candidates.find(c=>c.alias===body.alias).assessment=body.assessment;state.finalized=false;state.selected=null;}
    else{state.finalized=true;state.selected=body.selected;state.notes=body.notes;}
    const saved=structuredClone(state);return {ok:true,json:async()=>saved};
  };
  const refuse=error=>()=>({ok:false,json:async()=>({error})});
  const choose=(d,alias)=>{d.$('selected').value=alias;d.$('selected').onchange();};
  const sent=d=>d.requests.slice(1).map(r=>JSON.parse(r.options.body)),actions=d=>d.requests.map(r=>JSON.parse(r.options.body).action);
  const click=async d=>{d.$('chooseWinner').onclick();await d.tick();};
  await t.test('names its reason while it cannot act, and is ready for a kept, completed candidate',async()=>{
    const d=await desk();assert.equal(d.$('decision').hidden,false);
    assert.equal(d.$('chooseWinner').disabled,true);assert.match(d.$('chooseWinnerHint').textContent,/^Choose a kept candidate under Selected result/);
    choose(d,'C');assert.match(d.$('chooseWinnerHint').textContent,/^Candidate C is not kept/);
    choose(d,'A');assert.equal(d.$('chooseWinner').disabled,false);assert.equal(d.$('chooseWinnerHint').textContent,'');
    assert.equal(d.$('chooseWinner').textContent,'Candidate A meets the stated constraints — choose as winner');
    assert.equal(d.requests.length,1,'looking never writes');
  });
  await t.test('the click marks constraints Pass through rate, keeps the rest, then finalizes the same candidate with the notes',async()=>{
    const d=await desk();choose(d,'A');d.$('summary').value='Keeps the silhouette';d.$('summary').oninput();
    await click(d);assert.equal(d.requests.length,2);
    assert.deepEqual(sent(d)[0],{action:'rate',alias:'A',expected_revision:0,assessment:{verdict:'keep',notes:'note A',cleanup_seconds:30,preference:4,
      observations:{constraints:'pass',identity:'pass',pose_contact:'not_assessed',composition:'fail',detail:'not_assessed'}}});
    assert.equal(d.$('message').textContent,'Saving…');await d.respond(serve);
    assert.deepEqual(sent(d)[1],{action:'finalize',selected:'A',notes:'Keeps the silhouette',expected_revision:1});
    await d.respond(serve);
    assert.deepEqual(actions(d),['inspect','rate','finalize'],'no reveal, no extra rating');
    assert.equal(d.$('message').textContent,'Candidate A: stated constraints marked Pass and recorded as the winner. No generation performed.');
    assert.equal(d.$('phase').textContent,'Decision recorded');assert.equal(d.state.candidates[0].assessment.observations.constraints,'pass');
  });
  await t.test('an already passed candidate is finalized without a second rating',async()=>{
    const d=await desk(s=>{s.candidates[0].assessment.observations.constraints='pass';});choose(d,'A');
    await click(d);assert.deepEqual(sent(d).map(b=>[b.action,b.selected,b.expected_revision]),[['finalize','A',0]]);await d.respond(serve);
    assert.equal(d.$('message').textContent,'Candidate A recorded as the winner. No generation performed.');
  });
  await t.test('a failed precondition sends nothing and says why',async()=>{
    const cases=[
      ['nothing selected',null,'',/^Choose a kept candidate/],
      ['unreviewed candidate',s=>{s.candidates[2].assessment.verdict='unreviewed';},'A',/^Record a verdict for every candidate/],
      ['not kept',s=>{s.candidates[1].assessment.verdict='needs_work';},'B',/^Candidate B is not kept/],
      ['incomplete stage',s=>{s.evidence.stages[1].status='failed';},'B',/^An incomplete execution/],
    ];
    for(const [name,setup,alias,reason] of cases){
      const d=await desk(setup||undefined);choose(d,alias);assert.equal(d.$('chooseWinner').disabled,true,name);
      await click(d);assert.equal(d.requests.length,1,name+' sends nothing');assert.match(d.$('message').textContent,reason,name);
    }
    const d=await desk(s=>{s.revealed=false;});assert.equal(d.$('decision').hidden,true);await click(d);assert.equal(d.requests.length,1,'blind review: no declaration, no reveal');
  });
  await t.test('unsaved assessments and crop drafts block it with no request',async()=>{
    const d=await desk();choose(d,'A');d.$('notes').value='half typed';d.emit(d.$('assessmentForm'),'input',{target:d.$('notes')});
    assert.equal(d.$('chooseWinner').disabled,true);assert.match(d.$('chooseWinnerHint').textContent,/^Save candidate assessments/);
    await click(d);assert.equal(d.requests.length,1);assert.match(d.$('message').textContent,/^Save candidate assessments/);
    const e=await desk();choose(e,'A');e.$('cropLeft').value='10';e.$('cropForm').oninput();
    await click(e);assert.equal(e.requests.length,1,'an unsaved crop blocks it too');
  });
  await t.test('nothing is sent while a save is in flight',async()=>{
    const d=await desk();choose(d,'A');await click(d);assert.equal(d.requests.length,2);await click(d);assert.equal(d.requests.length,2);
  });
  await t.test('a refused rating changes nothing and stops before finalizing',async()=>{
    const d=await desk();choose(d,'A');await click(d);await d.respond(refuse('This review changed in another window; reload it'));
    assert.deepEqual(actions(d),['inspect','rate']);assert.match(d.$('message').textContent,/^This review changed in another window/);
    assert.equal(d.state.candidates[0].assessment.observations.constraints,'not_assessed');
  });
  await t.test('a refused decision after a saved mark says the mark was saved and why finalize did not happen',async()=>{
    const d=await desk();choose(d,'A');await click(d);await d.respond(serve);
    assert.deepEqual(actions(d),['inspect','rate','finalize']);await d.respond(refuse('Character acceptance needs an explicit local-user human declaration'));
    assert.match(d.$('message').textContent,/^Candidate A stated constraints were saved as Pass, but the decision was not recorded\. Character acceptance/);
    assert.equal(d.state.candidates[0].assessment.observations.constraints,'pass');assert.equal(d.state.finalized,false);assert.equal(d.requests.length,3);
  });
  await t.test('a character case sends the chosen candidate\'s own saved checks and the usual character decision',async()=>{
    const d=await desk(s=>{s.character_context={required_checks:{face:'Face matches'}};s.character_review=null;s.candidates[0].character_checks={face:'pass'};s.candidates[1].character_checks={face:'uncertain'};s.candidates[2].character_checks={face:'fail'};});
    choose(d,'B');await click(d);assert.deepEqual(sent(d)[0].character_checks,{face:'uncertain'},'not the form values of the candidate on show');
    await d.respond(serve);assert.deepEqual([sent(d)[1].action,sent(d)[1].selected,sent(d)[1].character_decision,sent(d)[1].reviewer],['finalize','B','selected','local-user']);
  });
});

// #1730: render and click the real Compare & review page, with only the existing API and Library hooks stubbed.
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
