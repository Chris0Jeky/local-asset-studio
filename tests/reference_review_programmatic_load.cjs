// A programmatic review load must disarm prior mutation evidence before awaiting inspection.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const referenceRecords=fixture.report.request.references.map((reference,index)=>({
  id:reference.id,
  role:fixture.review.selections[index].role,
  kind:'image',
  path:reference.path,
  sha256:reference.sha256,
  take:[],
  ignore:[],
}));

class Element {
  constructor(tag='div'){
    Object.assign(this,{tag,value:'',textContent:'',hidden:false,disabled:false,checked:false,
      files:[],children:[],listeners:{},dataset:{},className:''});
  }
  addEventListener(type,handler){this.listeners[type]=handler;}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  setAttribute(name,value){this[name]=value;}
  focus(){}
  querySelector(selector){return walk(this,node=>node.tag===selector);}
  querySelectorAll(){return [];}
  fire(type){return this.listeners[type]?.({target:this});}
}
function walk(node,test){
  for(const child of node.children){
    if(test(child))return child;
    const result=walk(child,test);if(result)return result;
  }
  return null;
}
const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const events={};
const document={
  getElementById:el,
  createElement:tag=>new Element(tag),
  createTextNode:text=>Object.assign(new Element('text'),{textContent:text}),
  addEventListener:(type,handler)=>{events[type]=handler;},
  dispatchEvent:event=>events[event.type]?.(event),
  body:new Element(),
};
const response=value=>({ok:true,json:async()=>value});
let inspectGate=null;
const context=vm.createContext({
  document,
  window:{addEventListener(){}},
  CustomEvent:class{constructor(type){this.type=type;}},
  crypto:require('node:crypto').webcrypto,
  URL:{createObjectURL:()=> 'blob:fixture',revokeObjectURL(){}},
  btoa:text=>Buffer.from(text,'binary').toString('base64'),
  fetch:async(url,options)=>{
    if(url==='/api/prompt/profiles')return response({profiles:[]});
    const body=JSON.parse(options.body);
    if(url.endsWith('/inspect')){
      if(inspectGate)await inspectGate;
      return response({
        format:'studio.reference-review/v1',analysis:fixture.report,review:fixture.review,
        inference_submitted:false,generation_submitted:false,execution_authorized:false,
      });
    }
    if(url.endsWith('/preview'))return response({
      format:'studio.reference-transfer-preview/v1',
      base_intent:body.intent,
      intent:{...body.intent,facets:{...body.intent.facets,style:'reviewed ink'},references:referenceRecords},
      reference_draft:{source_report_sha256:fixture.report.report_sha256,review:body.review},
      changes:[{field:'facets.style',before:null,after:'reviewed ink'}],
      inference_submitted:false,generation_submitted:false,execution_authorized:false,
    });
    throw Error('Unexpected request '+url);
  },
});
for(const name of ['prompt-lab.js','reference-review.js']){
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8'),context);
}

const originalFiles=()=>fixture.images.map((row,index)=>{
  const bytes=Buffer.from(row.media_base64,'base64');
  return {size:bytes.length,name:'renamed-'+index+'.png',
    arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};
});

(async()=>{
  el('brief').value='Keep my instruction';
  await context.StudioReferenceReview.load(fixture.report,originalFiles());
  await el('rr-preview').fire('click');
  assert.equal(el('rr-apply').disabled,false,'A verified preview must arm Apply');
  el('rr-apply').fire('click');
  assert.equal(el('rr-undo').disabled,false,'The applied review must expose its undo ticket');
  assert.equal(el('rr-export').disabled,false,'The applied review must expose its receipt');

  let releaseInspect;
  inspectGate=new Promise(resolve=>{releaseInspect=resolve;});
  const loading=context.StudioReferenceReview.load(fixture.report,[]);
  assert.equal(el('rr-undo').disabled,true,
    'Programmatic load must immediately disarm the prior undo ticket');
  assert.equal(el('rr-export').disabled,true,
    'Programmatic load must immediately disarm the prior receipt');
  releaseInspect();
  await loading;
  console.log('Programmatic reference-review load disarmed prior mutation evidence');
})().catch(error=>{console.error(error);process.exitCode=1;});
