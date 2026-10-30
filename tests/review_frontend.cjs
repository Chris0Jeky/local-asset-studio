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

// Run the shipped desk against DOM/canvas boundaries; only the initial inspect is stubbed.
const test=require('node:test');
async function holdDesk({delayB=false}={}){
  const nodes=new Map(),all=[],requests=[],listeners={document:{},window:{}};let active=null,decodeB;
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
  const state={exists:true,revision:0,revealed:false,finalized:false,selected:null,notes:'',crop:[2500,2500,7500,7500],background:'dark',history:[],export:null,grid:null,
    candidates:[...'ABC'].map(alias=>({alias,preview_url:url.replace('preview-A.png',alias+'.png'),assessment:{verdict:'unreviewed',notes:'',observations:{},cleanup_seconds:null,preference:null}}))};
  const document={querySelector:s=>$(s.slice(1)),querySelectorAll:s=>all.filter(n=>matches(n,s)),createElement:tag=>new Node(tag),get activeElement(){return active;},addEventListener:(type,fn)=>(listeners.document[type]??=[]).push(fn)};
  const sandbox={document,location:{search:'?project='+project},URLSearchParams,console,
    window:{addEventListener:(type,fn)=>(listeners.window[type]??=[]).push(fn)},
    Image:class {decode(){this.naturalWidth=this.src.endsWith('/B.png')?400:200;this.naturalHeight=this.naturalWidth*2;return delayB&&this.src.endsWith('/B.png')?new Promise(resolve=>{decodeB=resolve;}):Promise.resolve();}},
    fetch:async(url,options)=>{requests.push({url,options});assert.equal(requests.length,1,'Hold interactions must never fetch or POST');return {ok:true,json:async()=>state};}};
  const source=process.env.REVIEW_TEST_REF?require('node:child_process').execFileSync('git',['show',process.env.REVIEW_TEST_REF+':app/static/review.js'],{encoding:'utf8'}):fs.readFileSync(require.resolve('../app/static/review.js'),'utf8');
  vm.runInNewContext(source,sandbox);await tick();
  return {$,emit,tick,document,requests,Node,decodeB:()=>decodeB(),draw:side=>$(side+'Canvas').draws.at(-1)};
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
    for(const target of [$('cropLeft'),$('notes'),$('mode'),editable,child]){assert.equal(down({target}).prevented,false);await tick();shown('left','A');}
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
