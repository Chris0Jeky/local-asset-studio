// Execute both real browser modules, controlling only DOM/transport scheduling.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
class Element {
 constructor(tag='div'){Object.assign(this,{tag,value:'',textContent:'',hidden:false,disabled:false,checked:false,files:[],children:[],listeners:{},dataset:{}});}
 addEventListener(type,handler){this.listeners[type]=handler;}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=children;}
 setAttribute(name,value){this[name]=value;}
 removeAttribute(name){delete this[name];}
 after(node){this.error=node;}
 focus(){}
 querySelector(selector){return walk(this,x=>x.tag===selector);}
 querySelectorAll(){return [];}
 fire(type){return this.listeners[type]?.({target:this});}
}
function walk(node,test){for(const child of node.children){if(test(child))return child;const result=walk(child,test);if(result)return result;}return null;}
const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const events={};const doc={getElementById:el,createElement:tag=>new Element(tag),createTextNode:t=>Object.assign(new Element('text'),{textContent:t}),
 addEventListener:(type,fn)=>{events[type]=fn;},dispatchEvent:event=>events[event.type]?.(),body:new Element()};
let calls=[],resolvePreview;const response=value=>({ok:true,json:async()=>value});
const context=vm.createContext({document:doc,window:{addEventListener(){}},CustomEvent:class{constructor(type){this.type=type;}},
 crypto:require('node:crypto').webcrypto,URL:{createObjectURL:()=> 'blob:fixture',revokeObjectURL(){}},
 btoa:text=>Buffer.from(text,'binary').toString('base64'),fetch:async(url,options)=>{
  if(url==='/api/prompt/profiles')return response({profiles:[]});
  const body=JSON.parse(options.body);calls.push({url,body});
  if(url.endsWith('/inspect'))return response({format:'studio.reference-review/v1',analysis:fixture.report,review:fixture.review,
    inference_submitted:false,generation_submitted:false,execution_authorized:false});
  return new Promise(resolve=>{resolvePreview=(failed=false)=>resolve(failed?{ok:false,json:async()=>({error:'Preview refused'})}:response({format:'studio.reference-transfer-preview/v1',base_intent:body.intent,
    intent:{...body.intent,references:fixture.report.request.references},reference_draft:{source_report_sha256:fixture.report.report_sha256,review:body.review},changes:[],
    inference_submitted:false,generation_submitted:false,execution_authorized:false}));});
 }});
for(const name of ['prompt-lab.js','reference-review.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8'),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 el('brief').value='Keep my instruction';
 el('rr-analysis').files=[{size:128*1024+1}];await el('rr-analysis').fire('change');
 assert.equal(el('rr-analysis')['aria-invalid'],'true');
 assert.equal(el('rr-analysis')['aria-describedby'],'rr-analysis-error');
 assert.equal(el('rr-analysis').error.id,'rr-analysis-error');
 assert.equal(el('rr-analysis').error.textContent,'Choose an analysis JSON no larger than 128 KiB.');
 assert.equal(el('rr-status').textContent,'Choose an analysis JSON no larger than 128 KiB.');
 assert.equal(el('rr-change-summary')['role'],'status');
 assert.equal(el('rr-change-summary')['aria-live'],'polite');
 el('rr-analysis').files=[{size:100,text:async()=>JSON.stringify(fixture.report)}];await el('rr-analysis').fire('change');
 assert.equal(el('rr-analysis')['aria-invalid'],undefined);
 assert.equal(el('rr-analysis')['aria-describedby'],undefined);
 assert.equal(el('rr-analysis').error.hidden,true);
 assert.equal(el('rr-analysis').error.textContent,'');
 el('rr-originals').files=[{size:0}];await el('rr-originals').fire('change');
 assert.equal(el('rr-originals')['aria-invalid'],'true');
 assert.equal(el('rr-originals')['aria-describedby'],'rr-originals-error');
 assert.equal(el('rr-originals').error.id,'rr-originals-error');
 assert.equal(el('rr-originals').error.textContent,'Choose one to four exact original images, each at most 8 MiB.');
 assert.equal(el('rr-status').textContent,'Choose one to four exact original images, each at most 8 MiB.');
 el('rr-adopt').fire('change');
 assert.equal(el('rr-originals').error.textContent,'Choose one to four exact original images, each at most 8 MiB.','Unrelated status messages must not replace the input error');
 el('rr-originals').files=fixture.images.map((row,i)=>{const bytes=Buffer.from(row.media_base64,'base64');return{size:bytes.length,name:'renamed-'+i+'.png',arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};});
 await el('rr-originals').fire('change');assert.equal(el('rr-originals')['aria-invalid'],undefined);assert.equal(el('rr-preview').disabled,false);
 assert.equal(el('rr-originals')['aria-describedby'],undefined);assert.equal(el('rr-originals').error.hidden,true);
 assert.equal(el('rr-source-status')['role'],'status');
 assert.equal(el('rr-source-status')['aria-live'],'polite');
 assert.match(el('rr-source-status').textContent,/originals matched by SHA-256/);
 const card=walk(el('rr-cards'),x=>x.dataset.reference==='picture-1'),trait=walk(card,x=>x.dataset.facet==='style');
 const role=walk(card,x=>x.tag==='select');
 assert.equal(role['aria-label'],'Use this picture for Picture 1 role');
 const legends=[];(function collect(node){for(const child of node.children||[]){if(child.tag==='legend')legends.push(child.textContent);collect(child);}})(card);
 assert.deepEqual(legends,['Traits to transfer','Suggested tags and unknowns']);
 const traitGroup=walk(card,x=>x.tag==='fieldset'&&x.children[0]?.textContent==='Traits to transfer');
 const tagGroup=walk(card,x=>x.tag==='fieldset'&&x.children[0]?.textContent==='Suggested tags and unknowns');
 assert.ok(walk(traitGroup,x=>x.tag==='input'),'Trait controls belong to their named fieldset');
 assert.ok(walk(tagGroup,x=>x.tag==='input'),'Tag controls belong to their named fieldset');
 let sourceWrites=0,sourceText=el('rr-source-status').textContent;
 Object.defineProperty(el('rr-source-status'),'textContent',{get:()=>sourceText,set:value=>{sourceWrites++;sourceText=value;}});
 await el('rr-originals').fire('change');assert.equal(sourceWrites,0,'Unchanged source match text must not be announced again');
 const text=trait.querySelector('textarea'),check=trait.querySelector('input');text.value='bold ink';await text.fire('input');
 check.checked=false;await check.fire('change');check.checked=true;await check.fire('change');
 const request=el('rr-preview').fire('click');await tick();
 const payload=calls.at(-1).body;
 assert.equal(payload.review.selections[0].overrides.style,'bold ink','Reselecting an edited trait must send the description still displayed');
 const count=calls.length;
 el('brief').value='A newer instruction';await el('brief').fire('input');
 assert.equal(el('rr-preview').disabled,true,'A changed draft cannot create parallel validation while an old request is in flight');
 await el('rr-preview').fire('click');assert.equal(calls.length,count);
 resolvePreview();await request;
 assert.equal(el('rr-apply').disabled,true,'Late preview cannot arm apply after a draft change');
 assert.equal(el('brief').value,'A newer instruction');assert.equal(el('rr-preview').disabled,false);
 let next=el('rr-preview').fire('click');await tick();resolvePreview();await next;
 let summaryWrites=0,summaryText=el('rr-change-summary').textContent;
 Object.defineProperty(el('rr-change-summary'),'textContent',{get:()=>summaryText,set:value=>{summaryWrites++;summaryText=value;}});
 next=el('rr-preview').fire('click');await tick();resolvePreview();await next;
 assert.equal(summaryWrites,0,'An unchanged preview count must not be announced again');
 next=el('rr-preview').fire('click');await tick();resolvePreview(true);await next;
 assert.equal(el('rr-change-summary').textContent,'','A refused preview must clear the prior count');
 assert.equal(el('rr-apply').disabled,true);
 console.log('Reference panel selection and single-flight guards passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
