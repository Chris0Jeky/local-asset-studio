/* Pure bundle-to-document projection and receipt checks. No storage or execution. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.BundleWorkflowCore=api;})(globalThis,function(){
  'use strict';
  const SLOTS=['lora','lora2','lora3','lora4','lora5','lora6'];
  const KEYS=['positive','negative','width','height','seed','steps','cfg','denoise','style_weight','pose_strength','sampler','scheduler',...SLOTS,...SLOTS.map(k=>k+'_name')];
  const RESERVED=new Set(['__proto__','constructor','prototype']);
  const ID=/^[A-Za-z0-9_.-]{1,96}$/;
  const own=(o,k)=>!!o&&Object.hasOwn(o,k);
  const object=o=>o!==null&&typeof o==='object'&&!Array.isArray(o);
  const need=(ok,message)=>{if(!ok)throw Error(message);};
  function check(value,depth=0){
    need(depth<=48,'Workflow nesting exceeds the supported limit.');
    if(Array.isArray(value))value.forEach(x=>check(x,depth+1));
    else if(object(value))for(const [k,v]of Object.entries(value)){need(!RESERVED.has(k),'Reserved object key: '+k);check(v,depth+1);}
    else if(typeof value==='number')need(Number.isFinite(value)&&(!Number.isInteger(value)||Number.isSafeInteger(value)),'Unsafe or non-finite number. Use the exact-integer SDK instead.');
    else need(value===null||['string','boolean'].includes(typeof value),'Only JSON values are supported.');
  }
  const clone=v=>JSON.parse(JSON.stringify(v));
  function signature(value){check(value);const sorted=v=>Array.isArray(v)?v.map(sorted):object(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;return JSON.stringify(sorted(value));}
  function graphInputs(nodes){need(object(nodes),'A source node map is required.');return Object.fromEntries(Object.entries(nodes).map(([id,n])=>{need(ID.test(id)&&object(n)&&typeof n.class_type==='string'&&object(n.inputs),'Invalid source node: '+id);return[id,{class_type:n.class_type,inputs:n.inputs}];}));}
  function bindings(p,key){
    const extras=p.bindings_extra||{};need(object(extras),'Invalid companion bindings.');
    const extra=extras[key]||[];need(Array.isArray(extra),'Invalid companion bindings: '+key);
    const pairs=[...(p[key]?[p[key]]:[]),...extra];
    return pairs.map(pair=>{need(Array.isArray(pair)&&pair.length===2&&pair.every(v=>typeof v==='string'&&v.length>0&&!RESERVED.has(v)),'Invalid binding: '+key);return [...pair];});
  }
  function label(key){const slot=SLOTS.findIndex(k=>key===k||key===k+'_name');return slot>=0?'Adapter '+(slot+1)+(key.endsWith('_name')?' file':' strength'):({positive:'Describe the result',negative:'What to avoid',cfg:'Guidance (CFG)',seed:'Seed',steps:'Sampling steps',width:'Canvas width',height:'Canvas height',denoise:'Denoise',style_weight:'Style weight',pose_strength:'Pose strength',sampler:'Sampler',scheduler:'Schedule'})[key]||key;}
  function groupFor(keys,node,outputs,id){
    if(keys.some(k=>['positive','negative'].includes(k)))return 'idea';
    if(keys.some(k=>['style_weight','pose_strength'].includes(k)||SLOTS.some(s=>k===s||k===s+'_name')))return 'appearance';
    if(keys.length)return 'sampling';
    if(outputs.includes(id)||['VAEDecode','VAEDecodeTiled'].includes(node.class_type))return 'output';
    if(['CheckpointLoaderSimple','UNETLoader','CLIPLoader','DualCLIPLoader','TripleCLIPLoader','VAELoader'].includes(node.class_type))return 'resources';
    return 'other';
  }
  function steps(nodes,outputs,exposed){
    const titles={idea:['Idea & conditioning','Prompt inputs and their actual graph bindings.'],appearance:['Appearance & adapters','Model and text-encoder strengths remain separate native inputs.'],sampling:['Canvas & sampling','Canvas, seed and sampling controls.'],resources:['Resource loaders','Fixed resource choices retained from the registered graph.'],output:['Decode & output','Decode and output nodes; destinations remain unchanged.'],other:['Other graph nodes','Unclassified nodes are preserved without guessing their purpose.']};
    const groups=Object.fromEntries(Object.keys(titles).map(k=>[k,[]]));
    for(const [id,node]of Object.entries(nodes))groups[groupFor((exposed[id]||[]).map(x=>x.key),node,outputs,id)].push(id);
    const result=[];
    for(const [kind,ids]of Object.entries(groups)){
      let chunk=null,index=0;
      for(const id of ids){
        const controls=(exposed[id]||[]).map(({key,input,companion})=>({name:label(key)+(companion?' · companion':''),node:id,input}));
        need(controls.length<=32,'This node has too many exposed controls; use the native builder.');
        if(!chunk||chunk.controls.length+controls.length>32){chunk={id:'bundle-'+kind+'-'+(++index),name:titles[kind][0]+(index>1?' '+index:''),description:titles[kind][1],nodes:[],controls:[]};result.push(chunk);}
        chunk.nodes.push(id);chunk.controls.push(...controls);
      }
    }
    need(result.length<=64,'The named-step limit would be exceeded.');return result;
  }
  function build(snapshot,base,name){
    check(snapshot);check(base);
    need(object(snapshot)&&object(snapshot.preset)&&object(snapshot.recipe)&&object(snapshot.controls),'Choose a complete bundle draft.');
    const {preset:p,recipe:r,controls}=snapshot;
    need(typeof p.id==='string'&&p.id===r.preset_id,'The recipe belongs to a different preset.');
    need((p.modality||'image')==='image'&&!['reference','last_reference','reference_slots','requires_rgba_mask'].some(k=>Array.isArray(p[k])?p[k].length:!!p[k]),'Reference and non-image bundles need their existing lineage-aware handoff.');
    need(base.format==='studio.workflow/v1'&&base.source?.preset_id===p.id,'The returned workflow is not this registered preset.');
    need(base.backend_id===(p.backend_id||'primary'),'Model environment changed. Refresh and explicitly choose it again.');
    need(typeof base.schema_sha256==='string'&&/^[a-f0-9]{64}$/.test(base.schema_sha256),'A schema identity is required.');
    need(Array.isArray(base.disabled)&&base.disabled.length===0,'The registered template contains disabled nodes.');
    need(object(base.bypass)&&!Object.keys(base.bypass).length,'A registered template cannot supply bypass edits.');
    need(Object.keys(base.nodes||{}).length>0&&Object.keys(base.nodes).length<=256,'The workflow must have 1–256 nodes.');
    need(!Object.values(base.nodes).some(n=>n.class_type==='LoadImage'),'Image inputs require an explicit asset-lineage handoff.');
    need(signature(graphInputs(base.nodes))===signature(graphInputs(snapshot.graph)),'The registered graph changed since inspection. Re-select the bundle.');
    need(typeof name==='string'&&name.trim().length>0&&name.trim().length<=160,'Give this workflow a name of 1–160 characters.');
    need(Array.isArray(base.outputs)&&base.outputs.length>0&&base.outputs.every(id=>own(base.nodes,id))&&new Set(base.outputs).size===base.outputs.length,'No complete registered output selection is available.');
    const doc=clone(base),writes=new Map(),exposed={};
    for(const [key,value]of Object.entries(controls)){
      need(KEYS.includes(key),'Unsupported bundle control: '+key);
      need(['string','number'].includes(typeof value),'A bundle control must be scalar: '+key);
      const pairs=bindings(p,key);need(pairs.length>0,'Unbound bundle control: '+key);
      need(own(p.defaults,key),'The catalog default is unavailable: '+key);
      const first=pairs[0];
      need(own(base.nodes[first[0]]?.inputs,first[1])&&signature(base.nodes[first[0]].inputs[first[1]])===signature(p.defaults[key]),'Catalog and graph defaults differ: '+key);
      for(const [index,[id,input]]of pairs.entries()){
        need(own(doc.nodes[id]?.inputs,input),'Missing graph binding: '+key);
        const old=doc.nodes[id].inputs[input];
        need(['string','number'].includes(typeof old)&&typeof old===typeof value,'Do not replace a connection or change a native input type: '+key);
        const identity=id+'\u0000'+input;
        need(!writes.has(identity)||writes.get(identity)===value,'Conflicting controls target the same input: '+key);
        if(!writes.has(identity)){(exposed[id]??=[]).push({key,input,companion:index>0});writes.set(identity,value);}
        doc.nodes[id].inputs[input]=value;
      }
    }
    doc.name=name.trim();doc.revision=0;doc.steps=steps(doc.nodes,doc.outputs,exposed);
    // This is a new authoring document, not an assertion of execution or a server fork.
    doc.source={preset_id:p.id,authoring_only:true,bundle:{format:'studio.bundle-source/v1',recipe_id:r.id,recipe_name:r.name,controls:clone(controls),evidence:'Unexecuted workflow draft; historical recipe evidence does not certify it.'}};
    check(doc);need(new TextEncoder().encode(JSON.stringify(doc)).length<=900*1024,'The workflow is too large for the retained-save envelope.');
    return {document:doc,controls:Object.keys(controls).length,bindings:writes.size,steps:doc.steps.length};
  }
  function sameDocument(a,b){const left=clone(a),right=clone(b);delete left.revision;delete right.revision;return signature(left)===signature(right);}
  async function expectedId(requestId,cryptoImpl=globalThis.crypto){
    need(typeof requestId==='string'&&ID.test(requestId),'Invalid document request identity.');
    const namespace='0943b1d33a9c4de4a1b7b59b8d7fa86d',name=new TextEncoder().encode(requestId),bytes=new Uint8Array(16+name.length);
    for(let i=0;i<16;i++)bytes[i]=parseInt(namespace.slice(i*2,i*2+2),16);bytes.set(name,16);
    const hash=new Uint8Array(await cryptoImpl.subtle.digest('SHA-1',bytes));hash[6]=(hash[6]&15)|80;hash[8]=(hash[8]&63)|128;
    const h=[...hash.slice(0,16)].map(x=>x.toString(16).padStart(2,'0')).join('');return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20);
  }
  async function receipt(result,pending){
    check(result);check(pending);
    need(pending.path==='/api/workflow-studio/documents'&&pending.operation==='save'&&pending.body?.document?.source?.bundle?.format==='studio.bundle-source/v1','Resolve this retained request in Workflow builder.');
    need(result?.id===await expectedId(pending.body.request_id)&&result.revision===1&&Number.isSafeInteger(result.head_revision)&&result.head_revision>=1&&result.head_revision<=1024,'Unexpected workflow receipt. Retain the same save request.');
    need(result.generation_submitted===false&&result.document?.revision===1&&typeof result.replayed==='boolean'&&/^[a-f0-9]{64}$/.test(result.document_sha256||''),'Incomplete workflow receipt. Retain the same save request.');
    need(sameDocument(result.document,pending.body.document),'The saved document differs from the requested snapshot. Retain the request.');
    return result;
  }
  return {build,signature,check,bindings,expectedId,receipt,sameDocument};
});
