/* Per-tab metadata recovery only. Reading this journal never performs network I/O. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioAssetRecovery=api;})(globalThis,function(){
  'use strict';
  const PREFIX='studio.asset-recovery.v1.', LIMIT=512*1024;
  const workspace=value=>typeof value==='string' && /^[0-9a-f]{32}$/.test(value);
  const object=value=>value && typeof value==='object' && !Array.isArray(value);
  const form=value=>object(value) && ['title','tags','review','notes'].every(k=>typeof value[k]==='string');
  function operation(value){
    const c=value?.command;
    if(!object(c) || typeof value.body!=='string' || value.body.length>128*1024 ||
       typeof c.request_id!=='string' || !/^[A-Za-z0-9_-]{16,128}$/.test(c.request_id) ||
       !['edit','trash','restore','add_collection','remove_collection'].includes(c.action) ||
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
    if(slot==='library')return operation(value.operation) && Array.isArray(value.selection) && value.selection.every(id=>typeof id==='string');
    const m=value.metadata;
    return slot==='detail' && typeof value.id==='string' && object(m) && m.id===value.id &&
      Number.isSafeInteger(m.metadata_revision) && m.metadata_revision>=0 && typeof m.title==='string' &&
      typeof m.notes==='string' && typeof m.review==='string' && typeof m.favorite==='boolean' &&
      Array.isArray(m.tags) && m.tags.every(t=>typeof t==='string') && form(value.baseline) && form(value.draft) &&
      (!value.operation || (operation(value.operation) && JSON.stringify(value.operation.command.ids)===JSON.stringify([value.id]) &&
        ['details','favorite','trash'].includes(value.operation.kind) && form(value.operation.snapshot))) &&
      (!value.conflict || (object(value.conflict) && Array.isArray(value.conflict.current)));
  }
  function create(storage){
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
      return JSON.parse(raw);
    }
    function clear(slot){
      try{const store=target();store.removeItem(key(slot));if(store.getItem(key(slot))!==null)throw Error();}
      catch(_){throw Error('The save recovery record could not be cleared. Check its receipt again before another save.');}
    }
    return {read,write,clear};
  }
  return {create,PREFIX,workspace};
});
