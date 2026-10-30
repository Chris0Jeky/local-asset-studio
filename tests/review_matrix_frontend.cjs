'use strict';
// Execute the shipped Review desk with a small DOM and a controllable HTTP seam.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),listeners={},pending=[],requests=[],all=[];
let active=null;
function matches(node,selector){
  if(selector.startsWith('#'))return node.id===selector.slice(1);
  if(selector==='[data-grid-candidate]')return node.dataset.gridCandidate!==undefined;
  if(selector==='[data-crop]')return node.dataset.crop!==undefined;
  return node.tagName.toLowerCase()===selector;
}
class Node {
  constructor(tag='div',id=''){this.tagName=tag.toUpperCase();this.id=id;this.children=[];this.dataset={};this.attributes={};this.value='';this.hidden=false;this.disabled=false;this.textContent='';this.parentElement=null;this.events={};this.width=this.height=384;this.classList={toggle(){},add(){},remove(){}};all.push(this);if(id)nodes.set(id,this);}
  append(...children){for(const node of children){if(node.parentElement)node.parentElement.children=node.parentElement.children.filter(c=>c!==node);node.parentElement=this;this.children.push(node);}}
  replaceChildren(...children){for(const node of this.children)node.parentElement=null;this.children=[];this.append(...children);}
  setAttribute(key,value){this.attributes[key]=String(value);}
  getAttribute(key){return this.attributes[key]??null;}
  removeAttribute(key){delete this.attributes[key];}
  querySelectorAll(selector){return this.children.flatMap(c=>[...(matches(c,selector)?[c]:[]),...c.querySelectorAll(selector)]);}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  closest(selector){return matches(this,selector)?this:this.parentElement?.closest(selector)||null;}
  contains(node){return node===this||this.children.some(c=>c.contains(node));}
  addEventListener(type,listener){this.events[type]=listener;}
  focus(){if(!this.disabled)active=this;}
  scrollIntoView(){}
  getContext(){return {fillRect(){},drawImage(){}};}
  click(){this.focus();const event={target:this,preventDefault(){}};if(this.onclick)this.onclick(event);let node=this;while(node){node.events.click?.(event);node=node.parentElement;}}
}
const html=fs.readFileSync(require.resolve('../app/static/review.html'),'utf8');
for(const match of html.matchAll(/<([a-z0-9]+)\b[^>]*\bid="([^"]+)"[^>]*>/g))new Node(match[1],match[2]);
const $=id=>nodes.get(id)||all.find(node=>node.id===id);
for(const id of ['cropRight','cropBottom'])$(id).value='100';
for(const id of ['cropLeft','cropTop'])$(id).value='0';
$('background').value='dark';$('mode').value='pair';
const project='a'.repeat(32),session='b'.repeat(32),location={search:'?project='+project,href:'http://127.0.0.1/review.html?project='+project};
const document={querySelector:selector=>$(selector.slice(1))||null,querySelectorAll:selector=>all.filter(n=>selector.split(',').some(s=>matches(n,s))),
  createElement:tag=>new Node(tag),get activeElement(){return active;},addEventListener:(name,fn)=>{listeners[name]=fn;}};
const sandbox={document,location,URLSearchParams,URL,Blob,console,setTimeout,clearTimeout,confirm:()=>true,
  history:{replaceState(_state,_title,url){location.href=String(url);location.search=new URL(url,location.href).search;}},
  window:{addEventListener:(name,fn)=>{listeners[name]=fn;}},
  Image:class {constructor(){this.naturalWidth=192;this.naturalHeight=256;}decode(){return Promise.resolve();}},
  fetch:(url,options)=>new Promise(resolve=>{const body=JSON.parse(options.body);requests.push({url,body});pending.push(resolve);})};
const state={exists:true,revision:0,revealed:false,finalized:false,selected:null,notes:'',crop:[0,0,10000,10000],background:'dark',history:[],export:null,
  candidates:[...'ABCDEF'].map(alias=>({alias,preview_url:`/api/production/${project}/files/reviews/${session}/${alias}.png`,assessment:{verdict:'unreviewed',notes:'',cleanup_seconds:null,preference:null,observations:{constraints:'not_assessed',identity:'not_assessed',pose_contact:'not_assessed',composition:'not_assessed',detail:'not_assessed'}}})),
  grid:{rows:[{alias:'R1'},{alias:'R2'},{alias:'R3'}],columns:[{alias:'C1'},{alias:'C2'}],cells:[...'ABCDEF'].map((alias,i)=>({row:'R'+(1+Math.floor(i/2)),column:'C'+(1+i%2),candidates:[alias],runs:[{status:'completed',candidates:[alias]}]}))}};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function respond(value=state,ok=true){assert.ok(pending.length,'An expected review request must exist');pending.shift()({ok,json:async()=>JSON.parse(JSON.stringify(value))});await tick();await tick();}
function key(target,key,extra={}){let prevented=false;const event={target,key,...extra,preventDefault(){prevented=true;}};let node=target;while(node){node.events.keydown?.(event);node=node.parentElement;}listeners.keydown?.(event);return prevented;}
function output(alias){return $('gridTable').querySelectorAll('[data-grid-candidate]').find(n=>n.dataset.gridCandidate===alias);}
async function main(){
  vm.runInNewContext(fs.readFileSync(require.resolve('../app/static/review.js'),'utf8'),sandbox);
  await respond();assert.equal(requests.length,1);assert.equal(requests[0].body.action,'inspect');
  assert.match($('message').textContent,/Saved review loaded/);
  assert.ok($('presentationGrid')?.onclick,'Grid must be reachable inside Review desk');
  $('presentationGrid').click();assert.equal($('gridPanel').hidden,false);assert.equal($('gridTable').querySelectorAll('[data-grid-candidate]').length,6);
  output('D').click();assert.equal($('candidate').value,'D');assert.equal($('left').value,'D');
  $('notes').value='Retain this draft across view changes';$('assessmentForm').oninput({target:$('notes')});
  $('presentationPair').click();$('presentationGrid').click();assert.equal($('notes').value,'Retain this draft across view changes');
  output('E').click();output('D').click();assert.equal($('notes').value,'Retain this draft across view changes');
  output('D').focus();assert.equal(key(output('D'),'w'),true);assert.equal(requests.at(-1).body.action,'rate');
  assert.equal(requests.at(-1).body.alias,'D');assert.equal(requests.at(-1).body.expected_revision,0);
  assert.equal(requests.at(-1).body.assessment.verdict,'needs_work');assert.equal(requests.at(-1).body.assessment.notes,'Retain this draft across view changes');
  await respond({error:'Review conflict'},false);assert.equal($('notes').value,'Retain this draft across view changes');assert.equal($('candidate').value,'D');
  assert.equal(active.dataset.gridCandidate,'D','A failed save must retain the keyboard target');
  const count=requests.length;key($('notes'),'k');key(output('D'),'k',{ctrlKey:true});assert.equal(requests.length,count,'Typing and modified shortcuts never rate');
  assert.equal(key(output('D'),'ArrowUp'),true);assert.equal(active.dataset.gridCandidate,'B');
  $('saveAssessment').click(); // Browser form submission is dispatched explicitly by this small DOM.
  $('assessmentForm').onsubmit({preventDefault(){}});assert.equal(requests.at(-1).body.assessment.verdict,'needs_work');
  state.revision=1;state.candidates[3].assessment=requests.at(-1).body.assessment;await respond();
  assert.equal($('candidate').value,'D');assert.equal($('assessmentStatus').textContent,'Saved');
  $('reveal').click();assert.equal(requests.at(-1).body.action,'reveal');state.revision=2;state.revealed=true;state.evidence={fixture:'recorded'};
  state.evidence_json='{"seed": 9223372036854775807}';
  state.grid.rows.forEach((r,i)=>r.engine=['engine-copper','engine-indigo','engine-jade'][i]);state.grid.columns.forEach((c,i)=>c.seed=['9223372036854775807','915047'][i]);
  await respond();$('presentationPair').click();$('presentationGrid').click();assert.equal($('reveal').disabled,true);
  assert.equal($('evidence').textContent,'{"seed": 9223372036854775807}');
  assert.equal($('gridTable').querySelector('thead').children[0].children[1].textContent,'Seed 9223372036854775807');
  assert.equal($('candidate').value,'D');assert.equal($('phase').textContent,'Settings revealed');
  $('reload').click();state.revealed=false;
  state.grid={rows:[{alias:'R1',label:'Wording A',settings:{positive:'Rain <img src=x> & lantern'}},{alias:'R2',label:'Wording B',settings:{positive:'Lantern in rain'}}],
    columns:[{alias:'C1',seed:'9223372036854775807'}],cells:[{row:'R1',column:'C1',candidates:['A'],runs:[{status:'completed',candidates:['A']}]},{row:'R2',column:'C1',candidates:['B'],runs:[{status:'completed',candidates:['B']}]}]};
  await respond();
  assert.equal($('gridTable').querySelector('caption').textContent,'Comparison grid');
  assert.equal($('gridTable').querySelector('tbody').children[0].children[0].textContent,'R1');
  assert.equal($('gridTable').querySelector('details'),null,'A blind row must not attach hidden wording to the DOM');
  $('reload').click();state.revealed=true;await respond();
  const wording=$('gridTable').querySelector('tbody').children[0].children[0];
  assert.equal(wording.textContent,'Wording A');
  assert.equal(wording.querySelector('summary').textContent,'Settings');
  assert.equal(wording.querySelector('p').textContent,'Wording: Rain <img src=x> & lantern');
  assert.equal(wording.querySelector('img'),null,'Revealed wording stays text, never HTML');
  assert.equal($('gridTable').querySelector('thead').children[0].children[1].textContent,'Seed 9223372036854775807');
  // Repeated runs at one coordinate: a failed run's retained image must be told apart from a completed run's before Reveal.
  $('reload').click();state.revealed=false;state.grid={rows:[{alias:'R1'},{alias:'R2'},{alias:'R3'}],columns:[{alias:'C1'}],cells:[
    {row:'R1',column:'C1',candidates:['A','B'],runs:[{status:'completed',candidates:['A']},{status:'failed',candidates:['B']}]},
    {row:'R2',column:'C1',candidates:['C','D'],runs:[{status:'completed',candidates:['C']},{status:'completed',candidates:['D']}]},
    {row:'R3',column:'C1',candidates:['E'],runs:[{status:'completed',candidates:['E']},{status:'failed',candidates:[]}]}]};
  await respond();
  const cells=[0,1,2].map(i=>$('gridTable').querySelector('tbody').children[i].children[1]),texts=cell=>cell.querySelectorAll('p').map(p=>p.textContent);
  assert.deepEqual(texts(cells[0]),['2 runs','Run 1 · Completed','Run 2 · Failed','2 retained images']);
  assert.deepEqual(texts(cells[1]),['2 runs','Run 1 · Completed','Run 2 · Completed','2 retained images'],'Same-status repeats are counted and told apart');
  assert.deepEqual(texts(cells[2]),['2 runs','Run 1 · Completed','Run 2 · Failed','No retained image','1 retained image']);
  const run=alias=>output(alias).dataset.gridRun;
  assert.deepEqual(['A','B','C','D','E'].map(run),['Run 1 · Completed','Run 2 · Failed','Run 1 · Completed','Run 2 · Completed','Run 1 · Completed']);
  assert.equal(cells[0].querySelectorAll('[data-grid-candidate]').length,2);assert.equal($('gridTable').querySelectorAll('[data-grid-candidate]').length,5);
  assert.doesNotMatch((function walk(n){return n.textContent+n.children.map(walk).join(' ');})($('gridTable')),/engine-|Seed \d/,'Blind runs carry no engine or seed identity');
  output('B').click();assert.equal($('candidate').value,'B','A failed run retained image remains selectable');
  assert.equal(output('B').attributes['aria-pressed'],'true');
  $('reload').click();state.grid=null;await respond();assert.equal($('presentationGrid').disabled,true);assert.equal($('gridPanel').hidden,true);
  assert.match($('gridHint').textContent,/unambiguous saved settings and seeds/);assert.ok(requests.every(r=>r.url.endsWith('/review')));
  console.log('Review matrix interactions passed: selection, drafts, revisioned shortcuts, focus, Reveal and fallback');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
