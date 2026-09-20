/* Optional local review evidence, never an authoritative Workspace or a replay queue. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioAssetRecoveryShelf=api;})(globalThis,function(){
  'use strict';
  const KEY='studio.asset-recovery.shelf.v1',LOCK=KEY+'.lock';
  const LIMITS=Object.freeze({records:20,record:256*1024,total:2*1024*1024,depth:16,keys:20000,string:64*1024,ids:200});
  const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
  const bytes=s=>new TextEncoder().encode(s).byteLength;
  const same=(a,b)=>canonical(a)===canonical(b);
  const fail=message=>{throw Error(message);};
  const id=v=>typeof v==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(v);
  const scope=v=>typeof v==='string'&&/^[0-9a-f]{32}$/.test(v);
  const digest=v=>typeof v==='string'&&/^[0-9a-f]{64}$/.test(v);
  const keys=(v,allowed,required=allowed)=>object(v)&&Object.keys(v).every(k=>allowed.includes(k))&&required.every(k=>Object.hasOwn(v,k));
  const text=(v,max=LIMITS.string)=>typeof v==='string'&&v.length<=max&&bytes(v)<=max;
  const integer=v=>Number.isSafeInteger(v)&&v>=0;
  const reviews=['unreviewed','selected','needs_work','rejected'];
  function canonical(value){
    if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
    if(object(value))return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
    return JSON.stringify(value);
  }
  // JSON.parse alone silently collapses duplicate keys. Parse bounded JSON without
  // a reviver or evaluating content; escaped duplicate keys are duplicates too.
  function parse(raw,limit=LIMITS.total){
    if(typeof raw!=='string'||raw.length>limit||bytes(raw)>limit)fail('Recovery JSON exceeds its byte limit.');
    let at=0,keyCount=0;
    const space=()=>{while(/[\x20\t\r\n]/.test(raw[at]||'!'))at++;};
    function string(){
      const start=at++;
      while(at<raw.length){const c=raw[at++];if(c==='"')return JSON.parse(raw.slice(start,at));if(c==='\\')at++;}
      fail('Invalid JSON string.');
    }
    function value(depth){
      space();if(depth>LIMITS.depth)fail('Recovery JSON depth limit exceeded.');
      const c=raw[at];
      if(c==='"')return string();
      if(c==='{'||c==='['){
        at++;space();const array=c==='[',out=array?[]:{},seen=new Set(),end=array?']':'}';
        if(raw[at]===end){at++;return out;}
        while(at<raw.length){
          space();let key;
          if(!array){
            if(raw[at]!=='"')fail('Invalid JSON object key.');key=string();
            if(seen.has(key))fail('Duplicate JSON key.');seen.add(key);
            if(++keyCount>LIMITS.keys)fail('Recovery JSON keys limit exceeded.');
            space();if(raw[at++]!==':')fail('Invalid JSON object.');
          }
          const child=value(depth+1);
          if(array)out.push(child);else Object.defineProperty(out,key,{value:child,enumerable:true,writable:true,configurable:true});
          space();if(raw[at]===end){at++;return out;}
          if(raw[at++]!==',')fail('Invalid JSON separator.');
        }
        fail('Incomplete JSON object.');
      }
      for(const [token,result] of [['true',true],['false',false],['null',null]])if(raw.startsWith(token,at)){at+=token.length;return result;}
      const match=raw.slice(at).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
      if(!match)fail('Invalid JSON value.');at+=match[0].length;const number=Number(match[0]);
      if(!Number.isFinite(number))fail('JSON numbers must be finite.');return number;
    }
    const result=value(0);space();if(at!==raw.length)fail('Invalid trailing JSON.');return result;
  }
  const metadataKeys=['id','workspace_id','metadata_revision','title','notes','tags','review','favorite','trashed_at'];
  const formKeys=['title','tags','review','notes'];
  const commandKeys=['ids','action','workspace_id','expected_revisions','request_id','title','notes','tags','favorite','review','collection_id'];
  function form(v){return keys(v,formKeys)&&text(v.title,200)&&text(v.tags)&&text(v.notes)&&reviews.includes(v.review);}
  function ids(v){return Array.isArray(v)&&v.length<=LIMITS.ids&&v.every(id)&&new Set(v).size===v.length;}
  function metadata(v,w){
    return keys(v,metadataKeys,['id','metadata_revision','title','notes','tags','review','favorite'])&&id(v.id)&&integer(v.metadata_revision)&&
      (w===null?!Object.hasOwn(v,'workspace_id')||scope(v.workspace_id):v.workspace_id===w)&&text(v.title,200)&&text(v.notes)&&
      Array.isArray(v.tags)&&v.tags.length<=200&&v.tags.every(t=>text(t,256))&&reviews.includes(v.review)&&typeof v.favorite==='boolean'&&
      (v.trashed_at==null||typeof v.trashed_at==='number'&&Number.isFinite(v.trashed_at));
  }
  function operation(v,w,slot,target){
    if(!keys(v,slot==='detail'?['command','body','kind','snapshot']:['command','body']))return false;
    const c=v.command;
    if(!keys(c,commandKeys,['ids','action','expected_revisions','request_id'])||!ids(c.ids)||!c.ids.length||!id(c.request_id)||c.request_id.length<16||
       (w!==null&&c.workspace_id!==w)||!keys(c.expected_revisions,c.ids)||c.ids.some(k=>!integer(c.expected_revisions[k]))||
       !['edit','trash','restore','add_collection','remove_collection'].includes(c.action)||!text(v.body,128*1024))return false;
    for(const field of ['title','notes','collection_id'])if(Object.hasOwn(c,field)&&!text(c[field],field==='title'?200:LIMITS.string))return false;
    if(Object.hasOwn(c,'tags')&&(!Array.isArray(c.tags)||c.tags.length>200||c.tags.some(t=>!text(t,256))))return false;
    if(Object.hasOwn(c,'favorite')&&typeof c.favorite!=='boolean')return false;
    if(Object.hasOwn(c,'review')&&!reviews.includes(c.review))return false;
    if(!same(parse(v.body,128*1024),c))return false;
    return slot!=='detail'||same(c.ids,[target])&&['details','favorite','trash'].includes(v.kind)&&form(v.snapshot);
  }
  function validatePayload(slot,v){
    if(!object(v)||![1,2].includes(v.version))fail('Unsupported recovery payload version.');
    const w=v.version===2?v.workspace_id:null;
    if(v.version===2&&!scope(w))fail('Invalid Workspace identity.');
    if(slot==='library'){
      if(!keys(v,['version','workspace_id','operation','selection'],['version','operation','selection'])||!ids(v.selection)||!operation(v.operation,w,slot))fail('Invalid bounded library recovery.');
    }else if(slot==='detail'){
      if(!keys(v,['version','workspace_id','id','metadata','baseline','draft','operation','conflict'],['version','id','metadata','baseline','draft','operation','conflict'])||
         !id(v.id)||!metadata(v.metadata,w)||v.metadata.id!==v.id||!form(v.baseline)||!form(v.draft)||v.operation!==null&&!operation(v.operation,w,slot,v.id))fail('Invalid review recovery identity or field bound.');
      if(v.conflict!==null){
        const c=v.conflict;
        if(!keys(c,['workspace_id','current','confirmed_request_id'],['workspace_id','current'])||c.workspace_id!==w||!Array.isArray(c.current)||c.current.length>10||
           c.current.some(m=>!metadata(m,w)||m.id!==v.id)||new Set(c.current.map(m=>m.id)).size!==c.current.length||
           Object.hasOwn(c,'confirmed_request_id')&&!id(c.confirmed_request_id))fail('Invalid scoped conflict observation.');
      }
    }else fail('Unknown recovery slot.');
    const raw=canonical(v);if(raw.length>LIMITS.record||bytes(raw)>LIMITS.record)fail('Recovery record exceeds its byte limit.');
    return v;
  }
  function project(slot,input){
    // Projection applies to trusted in-tab data only. Import validation below
    // rejects extra fields instead of silently accepting a different document.
    const pick=(v,names)=>Object.fromEntries(names.filter(k=>Object.hasOwn(v,k)).map(k=>[k,v[k]]));
    const v=pick(input,slot==='detail'?['version','workspace_id','id','metadata','baseline','draft','operation','conflict']:['version','workspace_id','operation','selection']);
    if(slot==='detail'){
      v.metadata=pick(input.metadata,metadataKeys);v.baseline=pick(input.baseline,formKeys);v.draft=pick(input.draft,formKeys);
      if(v.conflict){v.conflict=pick(v.conflict,['workspace_id','current','confirmed_request_id']);v.conflict.current=v.conflict.current.map(m=>pick(m,metadataKeys));}
    }
    if(v.operation){v.operation=pick(v.operation,['command','body',...(slot==='detail'?['kind','snapshot']:[])]);}
    return validatePayload(slot,parse(canonical(v),LIMITS.record));
  }
  async function hash(value,crypto){
    if(!crypto?.subtle)fail('WebCrypto is unavailable; recovery cannot be verified.');
    const result=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(value)));
    return Array.from(new Uint8Array(result),b=>b.toString(16).padStart(2,'0')).join('');
  }
  function shape(r){
    if(!keys(r,['version','id','slot','workspace_id','created_at','updated_at','generation','payload','sha256'])||r.version!==1)fail('Unsupported shelf record version or fields.');
    if(!scope(r.id)||!integer(r.created_at)||!integer(r.updated_at)||r.updated_at<r.created_at||!integer(r.generation)||r.generation<1||!digest(r.sha256))fail('Invalid shelf identity or timestamps.');
    validatePayload(r.slot,r.payload);
    if(r.workspace_id!==(r.payload.version===2?r.payload.workspace_id:null))fail('Shelf Workspace identity does not match its payload.');
    const raw=canonical(r);if(raw.length>LIMITS.record||bytes(raw)>LIMITS.record)fail('Recovery record exceeds its byte limit.');
  }
  async function seal(slot,input,identity,crypto=globalThis.crypto){
    const payload=project(slot,input);
    const r={version:1,...identity,slot,workspace_id:payload.version===2?payload.workspace_id:null,payload};
    r.sha256=await hash(r,crypto);shape(r);return r;
  }
  async function verify(r,crypto){
    shape(r);const {sha256,...content}=r;
    if(await hash(content,crypto)!==sha256)fail('Recovery digest mismatch; evidence was not changed or restored.');
  }
  async function encode(records,crypto=globalThis.crypto){
    if(!Array.isArray(records)||records.length>LIMITS.records)fail('Recovery shelf capacity limit reached; export or explicitly discard a record.');
    const seen=new Set(),requests=new Set();
    for(const r of records){
      await verify(r,crypto);if(seen.has(r.id))fail('Duplicate recovery record identity.');seen.add(r.id);
      if(r.payload.operation){const key=String(r.workspace_id)+':'+r.payload.operation.command.request_id;if(requests.has(key))fail('Duplicate pending request identity.');requests.add(key);}
    }
    const raw=canonical({version:1,records});if(raw.length>LIMITS.total||bytes(raw)>LIMITS.total)fail('Recovery shelf aggregate byte limit reached.');return raw;
  }
  async function decode(raw,crypto=globalThis.crypto){
    const v=parse(raw);if(!keys(v,['version','records'])||v.version!==1)fail('Unsupported recovery bundle version or fields.');
    await encode(v.records,crypto);return v.records;
  }
  function create({storage,locks,crypto=globalThis.crypto,lockTimeoutMs=5000}){
    const target=()=>typeof storage==='function'?storage():storage;
    const locker=()=>typeof locks==='function'?locks():locks;
    async function read(){const raw=target().getItem(KEY);return raw===null?[]:decode(raw,crypto);}
    async function change(update){
      const lock=locker();if(!lock?.request)fail('Browser locks are unavailable; no shelf-dependent write was sent.');
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),lockTimeoutMs);
      try{return await lock.request(LOCK,{mode:'exclusive',signal:controller.signal},async()=>{
        clearTimeout(timer);
        const store=target(),before=store.getItem(KEY),records=before===null?[]:await decode(before,crypto);
        const next=await update(records),raw=await encode(next,crypto);
        // Also detect writes by older/uncooperative clients that do not take this lock.
        if(store.getItem(KEY)!==before)fail('Recovery storage changed during inspection; refresh before retrying.');
        try{store.setItem(KEY,raw);if(store.getItem(KEY)!==raw)fail('Recovery readback did not verify.');}
        catch(error){throw Error('Could not retain recovery storage: '+error.message);}
        return next;
      });}finally{clearTimeout(timer);}
    }
    return {
      list:read,
      async put(record,expectedDigest=null){
        await verify(record,crypto);
        await change(records=>{
          const at=records.findIndex(r=>r.id===record.id),prior=records[at];
          if((prior?.sha256||null)!==expectedDigest)fail('Recovery record changed in another tab; both viewpoints are retained.');
          if(prior){
            if(prior.slot!==record.slot||prior.workspace_id!==record.workspace_id||prior.created_at!==record.created_at||record.updated_at<prior.updated_at||record.generation!==prior.generation+1||
               prior.slot==='detail'&&prior.payload.id!==record.payload.id)fail('Recovery identity or generation changed.');
            if(prior.payload.operation&&!same(prior.payload.operation,record.payload.operation))fail('An immutable pending command cannot be changed or cleared by a shelf update.');
            records[at]=record;
          }else{if(record.generation!==1)fail('New recovery records must start at generation one.');records.push(record);}
          return records;
        });return record;
      },
      async remove(identifier,expectedDigest){return change(records=>{const r=records.find(r=>r.id===identifier);if(!r||r.sha256!==expectedDigest)fail('Recovery record changed; inspect before discard.');return records.filter(r=>r.id!==identifier);});},
      async importRecords(records){await encode(records,crypto);return change(existing=>{const known=new Set(existing.map(r=>r.id));if(records.some(r=>known.has(r.id)))fail('Duplicate imported record already exists.');return [...existing,...records];});},
      async export(){return encode(await read(),crypto);},
      raw(){const raw=target().getItem(KEY);if(raw!==null&&(raw.length>LIMITS.total||bytes(raw)>LIMITS.total))fail('Raw recovery exceeds the safe export limit.');return raw;}
    };
  }
  return {KEY,LOCK,LIMITS,parse,canonical,project,seal,encode,decode,create};
});
