/* Transport/state boundary for read-only guidance. No setting or workbench writes. */
(function(root){
  'use strict';
  const FORMAT='studio.settings-guidance/v1', PATH='/api/workflow-studio/guidance';
  function bounded(value,depth=0){
    if(depth>48)throw Error('Guidance input is too deeply nested.');
    if(typeof value==='number'&&(!Number.isFinite(value)||(Number.isInteger(value)&&!Number.isSafeInteger(value))))throw Error('Exact finite browser values are required.');
    if(value&&typeof value==='object')for(const [key,item]of Object.entries(value)){
      if(['__proto__','constructor','prototype'].includes(key))throw Error('Invalid guidance object key.');bounded(item,depth+1);
    }
  }
  function payload(snapshot){
    if(!snapshot?.preset||!snapshot.graph)throw Error('Resource inspection is not available yet.');
    const p=snapshot.preset, expected_bindings={};
    const keys=['positive','negative','width','height','seed','steps','cfg','denoise','sampler','scheduler',...['lora','lora2','lora3','lora4','lora5','lora6'].flatMap(k=>[k,k+'_name'])];
    for(const key of keys){const pairs=[...(p[key]?[p[key]]:[]),...(p.bindings_extra?.[key]||[])];if(pairs.length)expected_bindings[key]=pairs;}
    const value={preset_id:p.id,controls:snapshot.controls,expected_graph:snapshot.graph,expected_bindings};bounded(value);
    if(new TextEncoder().encode(JSON.stringify(value)).length>1048576)throw Error('Guidance request exceeds 1 MiB.');
    return JSON.parse(JSON.stringify(value));
  }
  function validate(report,id){
    if(!report||report.format!==FORMAT||report.preset_id!==id||report.generation_submitted!==false||report.authoring_only!==true||!/^([a-f0-9]{64})$/.test(report.context_sha256||''))throw Error('Invalid guidance response; previous advice is not current.');
    for(const key of ['resources','claims','conflicts','uncovered_resources','diagnostics'])if(!Array.isArray(report[key])||report[key].length>4096)throw Error('Invalid guidance list.');
    for(const claim of report.claims)if(!claim||!['applies','unknown','not_applicable'].includes(claim.applicability)||!Array.isArray(claim.checks)||!Array.isArray(claim.reasons)||!claim.source)throw Error('Malformed scoped guidance.');
    bounded(report);return report;
  }
  class Latest {
    constructor(){this.epoch=0;this.current='';this.closed=false;}
    begin(value){if(this.closed)throw Error('Guidance panel closed.');this.current=JSON.stringify(value);return{epoch:++this.epoch,source:this.current};}
    invalidate(){this.epoch++;this.current='';}
    accepts(ticket,value){return!this.closed&&ticket.epoch===this.epoch&&ticket.source===this.current&&ticket.source===JSON.stringify(value);}
    close(){this.closed=true;this.invalidate();}
  }
  const exports={FORMAT,PATH,payload,validate,Latest};
  if(typeof module==='object'&&module.exports)module.exports=exports;else root.BundleGuidanceClient=exports;
})(globalThis);
