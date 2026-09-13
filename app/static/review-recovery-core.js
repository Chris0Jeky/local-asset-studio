/* A tab-local recovery journal, never authority for saved metadata or execution. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioReviewRecovery=api;})(typeof globalThis==='object'?globalThis:this,()=>{
  'use strict';
  const KEY='studio.asset-review-recovery.v1', MAX_COUNT=8, MAX_BYTES=256*1024, MAX_RECORD_BYTES=96*1024;
  const reviews=['unreviewed','selected','needs_work','rejected'];
  const clone=value=>JSON.parse(JSON.stringify(value));
  const plain=value=>value!==null && typeof value==='object' && !Array.isArray(value);
  const exact=(value,keys)=>plain(value) && Object.keys(value).length===keys.length && keys.every(k=>Object.hasOwn(value,k));
  const text=(value,max)=>typeof value==='string' && value.length<=max;
  const identity=value=>typeof value==='string' && /^[0-9a-f]{32}$/.test(value);
  const assetId=value=>typeof value==='string' && /^[a-zA-Z0-9_-]{1,128}$/.test(value);
  const revision=value=>Number.isSafeInteger(value) && value>=0;
  const size=value=>new TextEncoder().encode(value).length;
  const requireValid=valid=>{if(!valid)throw Error('Invalid asset review recovery data; original local record retained.');};
  function form(value){
    requireValid(exact(value,['title','tags','review','notes']) && text(value.title,300) && text(value.tags,8192) &&
      text(value.notes,20000) && reviews.includes(value.review));
  }
  function metadata(value,id){
    requireValid(exact(value,['id','title','notes','tags','favorite','review','trashed_at','metadata_revision']) && value.id===id &&
      text(value.title,300) && text(value.notes,20000) && Array.isArray(value.tags) && value.tags.length<=100 &&
      value.tags.every(t=>text(t,100)) && typeof value.favorite==='boolean' && reviews.includes(value.review) &&
      (value.trashed_at===null || typeof value.trashed_at==='number' && Number.isFinite(value.trashed_at)) && revision(value.metadata_revision));
  }
  function validate(value){
    // Check bytes before traversing user-controlled fields. UTF-8, not character count.
    if(size(JSON.stringify(value))>MAX_RECORD_BYTES)throw Error('Asset review recovery record exceeds its byte limit.');
    requireValid(exact(value,['version','workspace','asset','opened','draft','pending']) && value.version===1 && identity(value.workspace) && assetId(value.asset));
    metadata(value.opened,value.asset);form(value.draft);
    if(value.pending!==null){
      requireValid(exact(value.pending,['body','snapshot']) && text(value.pending.body,MAX_RECORD_BYTES));form(value.pending.snapshot);
      let command;try{command=JSON.parse(value.pending.body);}catch{requireValid(false);}
      const keys=['action','ids','request_id','expected_revisions','workspace_id'];
      requireValid(plain(command) && command.workspace_id===value.workspace && ['edit','trash','restore'].includes(command.action) && identity(command.request_id) &&
        Array.isArray(command.ids) && command.ids.length===1 && command.ids[0]===value.asset &&
        exact(command.expected_revisions,[value.asset]) && command.expected_revisions[value.asset]===value.opened.metadata_revision);
      const fields=['title','notes','tags','favorite','review'];
      requireValid(Object.keys(command).every(k=>keys.includes(k) || command.action==='edit' && fields.includes(k)));
      requireValid(keys.every(k=>Object.hasOwn(command,k)));
      if(command.action==='edit'){
        requireValid(fields.some(k=>Object.hasOwn(command,k)));
        for(const field of fields)if(Object.hasOwn(command,field)){
          requireValid(field==='favorite'?typeof command[field]==='boolean':field==='review'?reviews.includes(command[field]):
            field==='tags'?Array.isArray(command[field]) && command[field].length<=100 && command[field].every(t=>text(t,100)):
            text(command[field],field==='title'?300:20000));
        }
      }
    }
    return value;
  }
  function journal(storage){
    function read(){
      const raw=storage.getItem(KEY);
      if(raw===null)return {version:1,entries:[]};
      if(typeof raw!=='string' || size(raw)>MAX_BYTES)throw Error('Asset review journal exceeds its byte limit.');
      let data;try{data=JSON.parse(raw);}catch{throw Error('Invalid asset review journal; original local data retained.');}
      if(data?.version!==1)throw Error('Unsupported asset review recovery version; original local data retained.');
      requireValid(exact(data,['version','entries']) && Array.isArray(data.entries));
      if(data.entries.length>MAX_COUNT)throw Error('Asset review journal exceeds its count limit.');
      const seen=new Set();for(const entry of data.entries){validate(entry);const key=entry.workspace+':'+entry.asset;requireValid(!seen.has(key));seen.add(key);}
      return data;
    }
    function write(data){const raw=JSON.stringify(data);if(size(raw)>MAX_BYTES)throw Error('Asset review journal exceeds its byte limit.');storage.setItem(KEY,raw);}
    return Object.freeze({
      list(workspace){requireValid(identity(workspace));return read().entries.filter(e=>e.workspace===workspace);},
      get(workspace,asset){requireValid(identity(workspace) && assetId(asset));return read().entries.find(e=>e.workspace===workspace && e.asset===asset)||null;},
      put(entry,{resolved=false}={}){
        validate(entry);const data=read(),index=data.entries.findIndex(e=>e.workspace===entry.workspace && e.asset===entry.asset);
        if(index>=0 && data.entries[index].pending && !resolved && JSON.stringify(data.entries[index].pending)!==JSON.stringify(entry.pending))
          throw Error('An unconfirmed save identity cannot be replaced or forgotten implicitly.');
        if(index<0){if(data.entries.length===MAX_COUNT)throw Error('Asset review journal count limit reached; no entries were evicted.');data.entries.push(clone(entry));}
        else data.entries[index]=clone(entry);
        write(data);
      },
      remove(workspace,asset,{resolved=false}={}){
        requireValid(identity(workspace) && assetId(asset));const data=read(),entry=data.entries.find(e=>e.workspace===workspace && e.asset===asset);
        if(entry?.pending && !resolved)throw Error('An unconfirmed save identity cannot be forgotten implicitly.');
        if(entry){data.entries=data.entries.filter(e=>e!==entry);write(data);}
      }
    });
  }
  return Object.freeze({KEY,MAX_COUNT,MAX_BYTES,MAX_RECORD_BYTES,journal,validate});
});
