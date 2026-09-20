/* Bridge the existing tab journal to optional persistent snapshots. No network owner. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./asset-recovery-shelf.js'):root.StudioAssetRecoveryShelf);if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioAssetRecoveryShelfSession=api;})(globalThis,function(Core){
  'use strict';
  function create({journal,store,crypto=globalThis.crypto,now=Date.now,onStatus=()=>{}}){
    let enabled=false,tail=Promise.resolve(),scheduled=false;
    const pending=new Map(),writers=new Map(),errors=new Map();
    const serial=work=>{const result=tail.catch(()=>{}).then(work);tail=result.catch(()=>{});return result;};
    const status=(text,error=false)=>onStatus(text,error);
    const copy=v=>JSON.parse(JSON.stringify(v));
    const identifier=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join('');
    async function capture(slot,input){
      const payload=Core.project(slot,input);let prior=writers.get(slot);
      if(prior&&(prior.workspace_id!==(payload.workspace_id||null)||slot==='detail'&&prior.payload.id!==payload.id))prior=null;
      if(prior?.payload.operation&&Core.canonical(prior.payload.operation)!==Core.canonical(payload.operation))prior=null;
      if(!prior){
        // Exact snapshots can be reused after reload. Different local text is not
        // permission to adopt another tab's pending record or overwrite its view.
        prior=(await store.list()).find(r=>r.slot===slot&&Core.canonical(r.payload)===Core.canonical(payload));
        if(prior){writers.set(slot,prior);return prior;}
      }
      if(prior&&Core.canonical(prior.payload)===Core.canonical(payload)){
        const current=(await store.list()).find(r=>r.id===prior.id);
        if(current?.sha256!==prior.sha256)throw Error('Recovery changed in another tab; inspect both viewpoints before saving.');
        return prior;
      }
      const time=Math.max(0,Math.floor(now()),prior?.updated_at||0);
      const record=await Core.seal(slot,payload,{id:prior?.id||identifier(),created_at:prior?.created_at??time,updated_at:time,generation:(prior?.generation||0)+1},crypto);
      await store.put(record,prior?.sha256||null);writers.set(slot,record);return record;
    }
    async function checkpoint(slot,input){
      try{const result=await capture(slot,input);errors.delete(slot);const other=errors.values().next().value;status(other?'Device recovery failed: '+other.message:'Device recovery checkpoint verified. Clearing browser data still removes it.',!!other);return result;}
      catch(error){errors.set(slot,error);status('Device recovery failed: '+error.message,true);throw error;}
    }
    function schedule(){
      if(scheduled||!enabled||!pending.size)return;
      scheduled=true;status('Saving local recovery on this device…');
      void serial(async()=>{const batch=[...pending];pending.clear();for(const [slot,value] of batch)if(enabled){try{await checkpoint(slot,value);}catch(_){/* Keep processing the other bounded slot; its evidence is independent. */}}})
        .catch(()=>{}).finally(()=>{scheduled=false;schedule();});
    }
    function changed(slot,value){
      if(!enabled)return;
      if(value===null){pending.delete(slot);return;} // Never delete shelf evidence on session clear.
      pending.set(slot,copy(value));schedule();
    }
    function prepare(slot,value){
      pending.delete(slot);
      return serial(()=>checkpoint(slot,copy(value)));
    }
    async function flush(){
      do{await tail;await Promise.resolve();}while(scheduled||pending.size);
      if(errors.size)throw errors.values().next().value;
    }
    return {
      get enabled(){return enabled;},
      async enable(){enabled=true;journal.connect({changed,prepare});for(const slot of ['detail','library']){const value=journal.read(slot);if(value)changed(slot,value);}await flush();},
      async disable(){enabled=false;pending.clear();journal.connect(null);await tail;errors.clear();status('Device checkpoints disabled for this tab. Existing shelf records remain.');},
      flush,
      restore(record,workspaceId){
        if(record.workspace_id!==workspaceId||!workspaceId||record.payload.version!==2)throw Error('Another or unknown Workspace is inspection/export/discard only.');
        const value=copy(record.payload);
        // Canonical bundle key ordering must not alter the retained wire body or
        // the existing journal's command/body equality check.
        if(value.operation)value.operation.command=JSON.parse(value.operation.body);
        if(record.slot==='detail'){
          // The existing editor compares JSON-stringified forms. Rebuild only
          // these in-memory views in its field order; never rewrite wire bytes.
          const form=v=>({title:v.title,tags:v.tags,review:v.review,notes:v.notes});
          value.baseline=form(value.baseline);value.draft=form(value.draft);
          if(value.operation)value.operation.snapshot=form(value.operation.snapshot);
        }
        const local=journal.read(record.slot);
        if(local&&Core.canonical(Core.project(record.slot,local))!==Core.canonical(record.payload))throw Error('This tab has a different local viewpoint. Both are retained; inspect/export or explicitly discard one first.');
        writers.set(record.slot,copy(record));journal.write(record.slot,value);return value;
      },
      async discard(record){return serial(async()=>{
        await store.remove(record.id,record.sha256);
        for(const [slot,r] of writers)if(r.id===record.id){writers.delete(slot);pending.delete(slot);errors.delete(slot);}
      });},
      forget(recordId){for(const [slot,r] of writers)if(r.id===recordId)writers.delete(slot);}
    };
  }
  return {create};
});
