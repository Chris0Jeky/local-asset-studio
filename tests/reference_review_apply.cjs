// Execute the real Prompt Lab and reference-review modules around a successful Apply.
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
async function previewAndApply(){
  el('rr-originals').files=originalFiles();
  await el('rr-originals').fire('change');
  await el('rr-preview').fire('click');
  assert.equal(el('rr-apply').disabled,false,'A verified preview must arm Apply');
  const retainedDiff=el('rr-diff').children[0];
  el('rr-apply').fire('click');
  assert.equal(el('style').value,'reviewed ink');
  assert.equal(el('rr-diff').children.length,1,'Apply must not clear its own reviewed diff');
  assert.equal(el('rr-diff').children[0],retainedDiff,'Apply must retain the exact reviewed diff nodes');
  assert.match(el('rr-change-summary').textContent,/applied/i,'The summary must describe the applied state');
  assert.doesNotMatch(el('rr-change-summary').textContent,/Nothing is applied yet/);
  assert.equal(el('rr-undo').disabled,false,'The successful application must remain undoable');
  assert.equal(el('rr-export').disabled,false,'The successful application must remain exportable');
  assert.match(el('rr-status').textContent,/Applied to this brief/);
}

(async()=>{
  el('brief').value='Keep my instruction';
  const analysisFile={size:100,text:async()=>JSON.stringify(fixture.report)};
  el('rr-analysis').files=[analysisFile];
  await el('rr-analysis').fire('change');
  await previewAndApply();

  // Programmatic load is also a review-context transition. The previous
  // analysis's mutation ticket and receipt must be unusable before any async
  // inspection or source hashing can finish.
  let releaseInspect;
  inspectGate=new Promise(resolve=>{releaseInspect=resolve;});
  const loading=context.StudioReferenceReview.load(fixture.report,[]);
  assert.equal(el('rr-undo').disabled,true,'Programmatic load must immediately disarm the prior undo ticket');
  assert.equal(el('rr-export').disabled,true,'Programmatic load must immediately disarm the prior receipt');
  releaseInspect();
  await loading;
  inspectGate=null;

  // Re-establish one applied review so the file-input transition remains
  // covered independently of the programmatic path above.
  await previewAndApply();
  el('rr-analysis').files=[analysisFile];
  await el('rr-analysis').fire('change');
  assert.equal(el('rr-undo').disabled,true,'Opening another analysis must disarm the prior undo ticket');
  assert.equal(el('rr-export').disabled,true,'Opening another analysis must disarm the prior receipt');
  console.log('Reference review apply diff and context reset passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
