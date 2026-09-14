// Execute both real browser modules, controlling only DOM/transport scheduling.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
class Element {
 constructor(tag='div'){Object.assign(this,{tag,value:'',textContent:'',hidden:false,disabled:false,checked:false,files:[],children:[],listeners:{},dataset:{}});}
 addEventListener(type,handler){this.listeners[type]=handler;}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=children;}
 setAttribute(name,value){this[name]=value;}
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
  return new Promise(resolve=>{resolvePreview=()=>resolve(response({format:'studio.reference-transfer-preview/v1',base_intent:body.intent,
    intent:{...body.intent,references:fixture.report.request.references},reference_draft:{source_report_sha256:fixture.report.report_sha256,review:body.review},changes:[],
    inference_submitted:false,generation_submitted:false,execution_authorized:false}));});
 }});
for(const name of ['prompt-lab.js','reference-review.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8'),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 el('brief').value='Keep my instruction';
 el('rr-analysis').files=[{size:100,text:async()=>JSON.stringify(fixture.report)}];await el('rr-analysis').fire('change');
 el('rr-originals').files=fixture.images.map((row,i)=>{const bytes=Buffer.from(row.media_base64,'base64');return{size:bytes.length,name:'renamed-'+i+'.png',arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};});
 await el('rr-originals').fire('change');assert.equal(el('rr-preview').disabled,false);
 const card=walk(el('rr-cards'),x=>x.dataset.reference==='picture-1'),trait=walk(card,x=>x.dataset.facet==='style');
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
 console.log('Reference panel selection and single-flight guards passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
