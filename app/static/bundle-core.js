/* Read-only recipe projection. No network, DOM, model loading or generation. */
(function(root,factory){const core=factory();if(typeof module==='object'&&module.exports)module.exports=core;else root.StudioBundles=core;})(globalThis,function(){
  'use strict';
  const SLOTS=['lora','lora2','lora3','lora4','lora5','lora6'];
  const KEYS=['positive','negative','seed','steps','cfg','width','height','denoise','frames','fps','sampler','scheduler',...SLOTS,...SLOTS.map(k=>k+'_name')];
  const own=(o,k)=>!!o&&Object.hasOwn(o,k);
  const bound=(p,k)=>own(p,k)&&!!p[k]||!['positive','negative'].includes(k)&&own(p.bindings_extra,k)&&!!p.bindings_extra[k];
  const object=o=>!!o&&typeof o==='object'&&!Array.isArray(o);
  const text=v=>typeof v==='string'?v:'';
  function canonical(value){if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';if(object(value))return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';return JSON.stringify(value);}
  function links(values){return(Array.isArray(values)?values:[]).filter(u=>{try{const x=new URL(u);return x.protocol==='https:'&&!x.username&&!x.password;}catch{return false;}});}
  function limits(p,k){
    if(SLOTS.includes(k))return[0,2,0.05];
    if(['width','height'].includes(k))return[p.dimension_limits?.[0]||64,p.dimension_limits?.[1]||1536,p.dimension_multiple||8];
    return({seed:[0,Number.MAX_SAFE_INTEGER,1],steps:[1,150,1],cfg:[0,30,0.1],denoise:[0,1,0.01],frames:[5,365,p.frame_grid||1],fps:[1,60,1]})[k]||null;
  }
  function value(p,k,v){
    if(!KEYS.includes(k)||!bound(p,k))throw Error('Unsupported recipe control: '+k);
    if(typeof v!=='string'&&typeof v!=='number')throw Error('Invalid value for '+k);
    if(typeof v==='number'&&!Number.isFinite(v))throw Error('Non-finite value for '+k);
    const range=limits(p,k);
    // Some legacy presets use `lora` for a filename, not a strength.
    if(range&&!(k==='lora'&&typeof p.defaults?.lora==='string'&&!bound(p,'lora_name'))){
      if(String(v).trim()===''||!Number.isFinite(Number(v)))throw Error(k+' needs a finite number');
      const n=Number(v);if(n<range[0]||n>range[1])throw Error(k+' must be between '+range[0]+' and '+range[1]);
      if(['seed','steps','width','height','frames','fps'].includes(k)&&!Number.isSafeInteger(n))throw Error(k+' needs a safe integer');
      if(['width','height'].includes(k)&&n%range[2]!==0)throw Error(k+' must be a multiple of '+range[2]);
      return n;
    }
    if(String(v).length>20000)throw Error(k+' is too long');return String(v);
  }
  function resolve(p,recipe,overrides={}){
    if(!object(p)||!object(recipe)||p.id!==recipe.preset_id)throw Error('The exact preset is unavailable');
    if(!object(recipe.controls)||!object(overrides))throw Error('Recipe controls must be an object');
    const result={};
    // Always start from graph defaults, never from the current workbench.
    for(const k of KEYS)if(bound(p,k)&&own(p.defaults,k))result[k]=value(p,k,p.defaults[k]);
    for(const source of [recipe.controls,overrides])for(const [k,v]of Object.entries(source))result[k]=value(p,k,v);
    return result;
  }
  function diff(before,after){return[...new Set([...Object.keys(before),...Object.keys(after)])].sort().filter(k=>String(before[k]??'')!==String(after[k]??'')).map(key=>({key,before:before[key]??null,after:after[key]??null}));}
  function guidance(kb,p){const family=kb?.family_aliases?.[p.family]||p.family;return{family,updated:kb?.updated||null,entry:kb?.families?.[family]||null};}
  function adapters(p,controls,kb){return SLOTS.filter(k=>bound(p,k+'_name')).map(key=>{const file=text(controls[key+'_name']);const entry=kb?.loras?.[file]||{};return{key,file,strength:controls[key],active:Number(controls[key])!==0,label:text(entry.label)||file,trigger:text(entry.trigger),position:text(entry.trigger_position),role:text(entry.role)||'purpose unrecorded',family:text(entry.family),range:Array.isArray(entry.strength)?entry.strength.filter(Number.isFinite):[],sha256:/^[a-f0-9]{64}$/i.test(entry.sha256||'')?entry.sha256:null,sources:links([...(Array.isArray(entry.sources)?entry.sources:[]),entry.source]),note:Array.isArray(entry.notes)?entry.notes.filter(n=>typeof n==='string').join(' '):text(entry.notes)||text(entry.note)};});}
  function evidence(recipe){const e=recipe.evidence;return{recorded:recipe.status==='executed',detail:typeof e==='string'?e:object(e)?[e.prompt_id?'Prompt '+e.prompt_id:'',Number.isFinite(e.seconds)?e.seconds+' seconds (recorded trial)':'',text(e.note)].filter(Boolean).join(' · '):'',label:recipe.status==='executed'?'Execution recorded':'Not executed here'};}
  function sample(record){
    // Only packaged local previews; no external images/tracking, path traversal or data URLs.
    if(!object(record)||!/^\/api\/examples\/[a-zA-Z0-9_-]+\/[a-zA-Z0-9_-]+\.(jpg|png|webp)$/.test(record.url||''))return null;
    if(!text(record.prompt_id)||!text(record.caption)||!text(record.receipt))return null;
    return{...record,label:'Recorded local example',notice:'Selected historical trial, not a representative benchmark or a guaranteed reproduction.'};
  }
  function resources(p,controls,graph){
    if(!object(graph))return[];const copy=JSON.parse(JSON.stringify(graph));
    for(const [k,v]of Object.entries(controls)){
      const extra=p.bindings_extra?.[k]||[];const pairs=[...(Array.isArray(p[k])?[p[k]]:[]),...extra];
      for(const pair of pairs)if(Array.isArray(pair)&&copy[pair[0]]?.inputs)copy[pair[0]].inputs[pair[1]]=v;
    }
    const roles={ckpt_name:'Checkpoint',unet_name:'Diffusion model',clip_name:'Text encoder',clip_name1:'Text encoder',clip_name2:'Text encoder',clip_name3:'Text encoder',vae_name:'VAE / decoder',lora_name:'Adapter',control_net_name:'ControlNet',clip_vision_name:'Image encoder'};
    const rows=[];
    for(const [node,n]of Object.entries(copy))for(const [field,v]of Object.entries(n.inputs||{}))if(typeof v==='string'&&/\.(safetensors|gguf|pth|pt|onnx|patch)$/i.test(v)){
      const strengths=['strength_model','strength_clip','strength'].filter(k=>own(n.inputs,k));
      const off=field==='lora_name'&&strengths.length>0&&strengths.every(k=>n.inputs[k]===0);
      rows.push({node,field,file:v,role:roles[field]||'Graph resource',active:!off});
    }
    return rows;
  }
  function editable(p,key){return bound(p,key)&&(['positive','negative','seed','steps','cfg','width','height'].includes(key)||SLOTS.includes(key));}
  return{SLOTS,KEYS,bound,canonical,links,limits,value,resolve,diff,guidance,adapters,evidence,sample,resources,editable};
});
