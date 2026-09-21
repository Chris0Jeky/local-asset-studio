// Collection-only inert DOM fixture; real HTTP/SQLite and browser checks are separate.
'use strict';
const vm=require('node:vm'),crypto=require('node:crypto');
function setup(){
  const elements=new Map(),writes=[],reads=[],timers=new Map();let approve=false,requests=0,timerId=0;
  const el=id=>{
    if(!elements.has(id))elements.set(id,{value:'',open:false,disabled:false,hidden:false,textContent:'',events:{},classList:{toggle(){}},
      addEventListener(name,fn){(this.events[name]??=[]).push(fn);},emit(name,event={}){for(const fn of this.events[name]||[])fn(event);},
      showModal(){this.open=true;},close(){this.open=false;this.emit('close');},focus(){}});
    return elements.get(id);
  };
  const context=vm.createContext({console,AbortController,Set,JSON,Date,crypto:crypto.webcrypto,$:el,
    window:{confirm(){requests++;return approve;}},setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);},
    api(url,options={}){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
      const record={url,options,resolve,reject};(options.method==='POST'?writes:reads).push(record);
      options.signal?.addEventListener('abort',()=>{const e=Error('aborted');e.name='AbortError';reject(e);});return promise;},
    assetMessage(){},refreshAssets:async()=>{}});
  const run=code=>vm.runInContext(code,context);
  run("let assetState={workspace_id:'1'.repeat(32),collections:[]},assetScope='all',assetSelection=new Set(),collectionEditing=null;function setAssetScope(value){assetScope=value;}");
  return {el,run,writes,reads,timers,payload:index=>JSON.parse(writes[index].options.body),confirmations:()=>requests,approve(value){approve=value;}};
}
const canonical=value=>JSON.stringify(value,function(key,item){return item&&typeof item==='object'&&!Array.isArray(item)?Object.fromEntries(Object.keys(item).sort().map(k=>[k,item[k]])):item;});
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
function collectionReceipt(p,createId='a'.repeat(32)){
  const result={id:p.id||createId,name:p.name||'Deleted',description:p.description||'',revision:p.action==='create'?1:p.expected_revision+1,deleted:p.action==='delete'};
  const receipt={format:'studio.collection-receipt/v1',workspace_id:p.workspace_id,request_id:p.request_id,action:p.action,status:'committed',
    request_sha256:hash(canonical(p)),result,affected_asset_count:0};
  const receipt_json=canonical(receipt);
  return {format:'studio.collection-result/v1',workspace_id:p.workspace_id,request_id:p.request_id,status:'committed',receipt,receipt_json,
    receipt_sha256:hash(receipt_json),replayed:false,current:result.deleted?null:{id:result.id,name:result.name,description:result.description,revision:result.revision},generation_submitted:false};
}
module.exports={setup,collectionReceipt};
