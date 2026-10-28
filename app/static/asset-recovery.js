/* Per-tab metadata recovery only. Reading this journal never performs network I/O. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioAssetRecovery=api;})(globalThis,function(){
  'use strict';
  const PREFIX='studio.asset-recovery.v1.', LIMIT=512*1024;
  const workspace=value=>typeof value==='string' && /^[0-9a-f]{32}$/.test(value);
  const object=value=>value && typeof value==='object' && !Array.isArray(value);
  function scopedStorage(storage,privacy='regular'){
    if(!['regular','private','all'].includes(privacy))throw Error('Invalid recovery privacy scope.');
    const prefix=privacy==='regular'?'':'studio.privacy.'+privacy+'.',target=()=>typeof storage==='function'?storage():storage;
    const names=()=>{const store=target(),out=[];for(let i=0;i<store.length;i++){const key=store.key(i);if(typeof key!=='string')continue;if(prefix?key.startsWith(prefix):!key.startsWith('studio.privacy.'))out.push(prefix?key.slice(prefix.length):key);}return out;};
    return {getItem:key=>target().getItem(prefix+key),setItem:(key,value)=>target().setItem(prefix+key,value),removeItem:key=>target().removeItem(prefix+key),
      get length(){return names().length;},key:index=>names()[index]??null};
  }
  const form=value=>object(value) && ['title','tags','review','notes'].every(k=>typeof value[k]==='string');
  const refusalCode=value=>typeof value==='string' && /^[A-Za-z0-9_-]{1,64}$/.test(value);
  function validRefusal(value,pending,scope){
    const fields=['version','workspace_id','request_id','status','message','observed_at'],command=pending?.command;
    return object(value) && Object.keys(value).every(k=>fields.includes(k)||k==='code') && fields.every(k=>Object.hasOwn(value,k)) &&
      value.version===1 && workspace(scope) && command?.workspace_id===scope && value.workspace_id===scope && value.request_id===command.request_id &&
      typeof value.request_id==='string' && /^[A-Za-z0-9_-]{16,128}$/.test(value.request_id) &&
      Number.isInteger(value.status) && value.status>=400 && value.status<500 &&
      // At most 1,000 Unicode code points also bounds UTF-8 to 4,000 bytes.
      typeof value.message==='string' && value.message.length>0 && value.message.length<=2000 && [...value.message].length<=1000 &&
      Number.isSafeInteger(value.observed_at) && value.observed_at>=0 && value.observed_at<=8640000000000000 &&
      (!Object.hasOwn(value,'code') || refusalCode(value.code));
  }
  function samePending(left,right){return operation(left) && operation(right) && left.body===right.body &&
    left.command.workspace_id===right.command.workspace_id && left.command.request_id===right.command.request_id;}
  function lastRefusal(value,pending){
    return value?.version===2 && samePending(value.operation,pending) && validRefusal(value.last_refusal,pending,value.workspace_id)?JSON.parse(JSON.stringify(value.last_refusal)):null;
  }
  function operation(value){
    const c=value?.command;
    if(!object(c) || typeof value.body!=='string' || value.body.length>128*1024 ||
       typeof c.request_id!=='string' || !/^[A-Za-z0-9_-]{16,128}$/.test(c.request_id) ||
       !['edit','trash','restore','archive','unarchive','add_collection','remove_collection'].includes(c.action) ||
       !Array.isArray(c.ids) || !c.ids.length || c.ids.length>200 || new Set(c.ids).size!==c.ids.length ||
       !object(c.expected_revisions) || Object.keys(c.expected_revisions).length!==c.ids.length ||
       c.ids.some(id=>typeof id!=='string' || !id || !Number.isSafeInteger(c.expected_revisions[id]) || c.expected_revisions[id]<0))return false;
    try{return JSON.stringify(JSON.parse(value.body))===JSON.stringify(c);}catch(_){return false;}
  }
  function valid(slot,value){
    if(!object(value) || ![1,2].includes(value.version))return false;
    if(value.version===2 && (!workspace(value.workspace_id) ||
       (value.operation && value.operation.command?.workspace_id!==value.workspace_id) ||
       (slot==='detail' && value.metadata?.workspace_id!==value.workspace_id) ||
       (value.conflict && (value.conflict.workspace_id!==value.workspace_id || !Array.isArray(value.conflict.current) || value.conflict.current.some(m=>m.workspace_id!==value.workspace_id)))))return false;
    if(Object.hasOwn(value,'last_refusal') && (value.version!==2 || !validRefusal(value.last_refusal,value.operation,value.workspace_id)))return false;
    if(slot==='library')return operation(value.operation) && Array.isArray(value.selection) && value.selection.every(id=>typeof id==='string');
    const m=value.metadata;
    return slot==='detail' && typeof value.id==='string' && object(m) && m.id===value.id &&
      Number.isSafeInteger(m.metadata_revision) && m.metadata_revision>=0 && typeof m.title==='string' &&
      typeof m.notes==='string' && typeof m.review==='string' && typeof m.favorite==='boolean' &&
      Array.isArray(m.tags) && m.tags.every(t=>typeof t==='string') && form(value.baseline) && form(value.draft) &&
      (!value.operation || (operation(value.operation) && JSON.stringify(value.operation.command.ids)===JSON.stringify([value.id]) &&
        ['details','favorite','trash','archive'].includes(value.operation.kind) && form(value.operation.snapshot))) &&
      (!value.conflict || (object(value.conflict) && Array.isArray(value.conflict.current)));
  }
  function create(storage){
    let checkpoint=null;
    const notify=(slot,value)=>{if(checkpoint?.changed)checkpoint.changed(slot,value);};
    const target=()=>typeof storage==='function'?storage():storage;
    const key=slot=>{if(!['detail','library'].includes(slot))throw Error('Unknown save recovery record.');return PREFIX+slot;};
    function read(slot){
      let raw;try{raw=target().getItem(key(slot));}catch(_){throw Error('Browser save recovery is unavailable. Keep this tab open; no new save can be sent.');}
      if(raw===null)return null;
      try{if(raw.length>LIMIT)throw Error();const value=JSON.parse(raw);if(!valid(slot,value))throw Error();return value;}
      catch(_){throw Error('The retained save cannot be read safely. It is preserved in this tab; no new save can be sent.');}
    }
    function write(slot,value){
      if(!valid(slot,value))throw Error('The draft could not be retained safely. No new save was sent.');
      const raw=JSON.stringify(value);if(raw.length>LIMIT)throw Error('This draft is too large for save recovery. Keep a copy before leaving this tab.');
      try{const store=target();store.setItem(key(slot),raw);if(store.getItem(key(slot))!==raw)throw Error();}
      catch(_){throw Error('Could not retain this draft for reload recovery. Keep this tab open; no new save can be sent.');}
      const retained=JSON.parse(raw);notify(slot,retained);return retained;
    }
    function clear(slot){
      try{const store=target();store.removeItem(key(slot));if(store.getItem(key(slot))!==null)throw Error();}
      catch(_){throw Error('The save recovery record could not be cleared. Check its receipt again before another save.');}
      notify(slot,null);
    }
    function recordRefusal(slot,pending,error,{current=()=>true,observedAt=Date.now()}={}){
      if(!current() || !operation(pending) || !Number.isInteger(error?.status) || error.status<400 || error.status>=500 ||
        typeof error.message!=='string' || !error.message.trim())return null;
      const command=pending.command,data=error.data;
      if(!workspace(command.workspace_id) || data?.code==='asset_workspace_conflict' ||
        object(data) && (Object.hasOwn(data,'workspace_id') && data.workspace_id!==command.workspace_id ||
          Object.hasOwn(data,'request_id') && data.request_id!==command.request_id))return null;
      const retained=read(slot);if(retained?.version!==2 || !samePending(retained.operation,pending))return null;
      const points=[...error.message.trim()],message=points.length>1000?points.slice(0,999).join('')+'…':points.join('');
      const explanation={version:1,workspace_id:command.workspace_id,request_id:command.request_id,status:error.status,message,observed_at:observedAt};
      if(refusalCode(data?.code))explanation.code=data.code;
      if(!validRefusal(explanation,pending,retained.workspace_id) || !current())return null;
      return write(slot,{...retained,last_refusal:explanation});
    }
    function dispatch(slot,operation,send,current=()=>true){
      if(!checkpoint?.prepare)return send();
      const retained=read(slot);
      if(!retained?.operation || retained.operation.body!==operation.body)throw Error('The pending command differs from its retained recovery; no write was sent.');
      return Promise.resolve().then(()=>checkpoint.prepare(slot,retained)).then(()=>{
        if(!current() || read(slot)?.operation?.body!==operation.body)throw Error('Recovery context changed while persisting; no write was sent.');
        return send();
      });
    }
    function connect(value){checkpoint=value;}
    return {read,write,clear,dispatch,connect,recordRefusal};
  }
  return {create,PREFIX,workspace,validRefusal,lastRefusal,scopedStorage};
});
