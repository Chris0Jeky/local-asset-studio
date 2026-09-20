// Local recovery evidence only. AssetWorkspace and its typed receipts remain authoritative.
(function(root,factory){const value=factory();if(typeof module==='object'&&module.exports)module.exports=value;else root.StudioCollectionRecovery=value;})(globalThis,()=>{
  'use strict';
  const FORMAT='studio.collection-recovery/v1',PREFIX=FORMAT+'/',MAX_ENTRIES=16,MAX_SCOPES=8,MAX_BYTES=128*1024,MAX_COMMAND=16*1024;
  const scope=value=>typeof value==='string'&&/^[0-9a-f]{32}$/.test(value);
  const token=value=>typeof value==='string'&&/^[A-Za-z0-9_-]{16,128}$/.test(value);
  const entity=value=>typeof value==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(value);
  const integer=value=>Number.isSafeInteger(value)&&value>=0;
  function need(ok,message='Invalid local collection recovery evidence'){if(!ok)throw Error(message);}
  function fields(value,keys){need(value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join('|')===[...keys].sort().join('|'));}
  function text(value,max){need(typeof value==='string'&&value.length<=max,'Collection text exceeds its limit');need(!/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value),'Collection text contains an unpaired surrogate');}
  function values(value){fields(value,['name','description']);text(value.name,100);text(value.description,1000);}
  function canonical(value){return JSON.stringify(value,function(key,item){if(item&&typeof item==='object'&&!Array.isArray(item)){need(!Object.keys(item).some(k=>['__proto__','prototype','constructor'].includes(k)));return Object.fromEntries(Object.keys(item).sort().map(k=>[k,item[k]]));}return item;});}
  function bytes(value){return new TextEncoder().encode(value).length;}
  function parsed(raw,limit){need(typeof raw==='string'&&raw.length<=limit&&bytes(raw)<=limit,'Collection recovery exceeds its byte limit');const value=JSON.parse(raw);need(canonical(value)===raw,'Local collection evidence is not exact canonical JSON');return value;}
  function validateDraft(draft){
    fields(draft,['id','revision','baseline','values','updated_at']);
    need(draft.id===null?draft.revision===null:entity(draft.id)&&integer(draft.revision)&&draft.revision>=1);
    values(draft.baseline);values(draft.values);need(integer(draft.updated_at));
  }
  function validateCommand(command){
    need(command&&['create','rename','delete'].includes(command.action));
    fields(command,['format','workspace_id','request_id','action',...(command.action==='create'?[]:['id','expected_revision']),...(command.action==='delete'?[]:['name','description'])]);
    need(command.format==='studio.collection-command/v1'&&scope(command.workspace_id)&&token(command.request_id));
    if(command.action!=='create')need(entity(command.id)&&integer(command.expected_revision)&&command.expected_revision>=1&&command.expected_revision<Number.MAX_SAFE_INTEGER);
    if(command.action!=='delete'){values({name:command.name,description:command.description});need(command.name.trim().length>0&&command.name===command.name.trim()&&command.description===command.description.trim());}
    need(bytes(canonical(command))<=MAX_COMMAND,'Collection command exceeds its byte limit');
  }
  function pending(command,when,clickedValues={name:command.name??'',description:command.description??''}){
    validateCommand(command);need(integer(when));values(clickedValues);
    if(command.action!=='delete')need(clickedValues.name.trim()===command.name&&clickedValues.description.trim()===command.description,'Clicked values disagree with the normalized command');
    return {body:canonical(command),request_id:command.request_id,action:command.action,target_id:command.id??null,
      expected_revision:command.expected_revision??null,first_dispatch_at:when,clicked_values:{...clickedValues}};
  }
  function validatePending(value,workspace,draft){
    fields(value,['body','request_id','action','target_id','expected_revision','first_dispatch_at','clicked_values']);
    const command=parsed(value.body,MAX_COMMAND);validateCommand(command);
    need(canonical(value)===canonical(pending(command,value.first_dispatch_at,value.clicked_values)),'Pending command identity does not match its exact body');
    need(command.workspace_id===workspace&&value.target_id===draft.id&&value.expected_revision===draft.revision,'Pending command belongs to another Workspace or source revision');
    return command;
  }
  class Journal{
    constructor(storage,workspace){need(scope(workspace),'A valid Workspace identity is required for recovery');this.storage=storage;this.workspace=workspace;this.key=PREFIX+workspace;}
    _read(){
      const raw=this.storage.getItem(this.key);
      if(raw===null)return {raw,value:{format:FORMAT,workspace_id:this.workspace,entries:[]}};
      const value=parsed(raw,MAX_BYTES);fields(value,['format','workspace_id','entries']);
      need(value.format===FORMAT&&value.workspace_id===this.workspace&&Array.isArray(value.entries));
      need(value.entries.length<=MAX_ENTRIES,'Collection recovery entry limit exceeded');const seen=new Set();
      for(const entry of value.entries){fields(entry,['draft','pending']);validateDraft(entry.draft);need(!seen.has(entry.draft.id),'Duplicate recovered collection target');seen.add(entry.draft.id);if(entry.pending!==null)validatePending(entry.pending,this.workspace,entry.draft);}
      return {raw,value};
    }
    list(){return this._read().value.entries;}
    get(id){return this.list().find(entry=>entry.draft.id===id)??null;}
    _change(change,cleanup=false){
      const {raw,value}=this._read();change(value.entries);need(value.entries.length<=MAX_ENTRIES,'Local collection recovery is full; no pending command was evicted');
      const next=value.entries.length?canonical(value):null;let total=next===null?0:bytes(next),count=next===null?0:1;
      for(let i=0;i<this.storage.length;i++){const key=this.storage.key(i);if(key?.startsWith(PREFIX)&&key!==this.key){const other=this.storage.getItem(key);need(typeof other==='string','Local recovery changed during inspection');total+=bytes(other);count++;}}
      need((cleanup&&raw!==null&&(next===null||bytes(next)<=bytes(raw)))||(count<=MAX_SCOPES&&total<=MAX_BYTES),'Local collection recovery byte or Workspace limit is full; nothing was evicted');
      need(this.storage.getItem(this.key)===raw,'Local collection recovery changed before writing');
      if(next===null)this.storage.removeItem(this.key);else this.storage.setItem(this.key,next);
      need(this.storage.getItem(this.key)===next,'Local collection recovery write could not be verified');
    }
    keep(draft,pendingValue=null){
      validateDraft(draft);if(pendingValue!==null)validatePending(pendingValue,this.workspace,draft);
      this._change(entries=>{const at=entries.findIndex(entry=>entry.draft.id===draft.id),before=entries[at];
        need(!before?.pending||canonical(before.pending)===canonical(pendingValue),'An unconfirmed pending command cannot be changed or dropped');
        const entry={draft,pending:pendingValue};if(at<0)entries.push(entry);else entries[at]=entry;});
      return this.get(draft.id);
    }
    resolve(id,pendingValue,nextDraft){
      if(nextDraft!==null)validateDraft(nextDraft);
      this._change(entries=>{const at=entries.findIndex(entry=>entry.draft.id===id),before=entries[at];
        need(before?.pending&&canonical(before.pending)===canonical(pendingValue),'The retained pending command changed; inspect before resolving');
        need(nextDraft===null||nextDraft.id===id||!entries.some(entry=>entry.draft.id===nextDraft.id),'Another existing draft owns the confirmed collection target');
        entries.splice(at,1);if(nextDraft!==null)entries.push({draft:nextDraft,pending:null});});
    }
    discard(id){this._change(entries=>{const at=entries.findIndex(entry=>entry.draft.id===id);if(at>=0)entries.splice(at,1);},true);}
    reset(){this.storage.removeItem(this.key);need(this.storage.getItem(this.key)===null,'Local recovery discard could not be verified');}
  }
  async function digest(raw,crypto){need(crypto?.subtle,'Secure receipt verification is unavailable');return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw)))].map(n=>n.toString(16).padStart(2,'0')).join('');}
  async function verifyReceipt(reply,pendingValue,crypto=globalThis.crypto){
    const command=parsed(pendingValue.body,MAX_COMMAND);validateCommand(command);
    need(reply?.format==='studio.collection-result/v1'&&reply.workspace_id===command.workspace_id&&reply.request_id===command.request_id&&reply.status==='committed'&&reply.generation_submitted===false,'The reply did not confirm this collection command');
    const receipt=parsed(reply.receipt_json,MAX_COMMAND);fields(receipt,['format','workspace_id','request_id','action','status','request_sha256','result','affected_asset_count']);
    fields(receipt.result,['id','name','description','revision','deleted']);values({name:receipt.result.name,description:receipt.result.description});
    need(canonical(reply.receipt)===reply.receipt_json,'Receipt fields differ from retained bytes');
    need(await digest(reply.receipt_json,crypto)===reply.receipt_sha256&&await digest(pendingValue.body,crypto)===receipt.request_sha256,'Collection receipt or command hash does not match');
    const result=receipt.result;
    need(receipt.format==='studio.collection-receipt/v1'&&receipt.workspace_id===command.workspace_id&&receipt.request_id===command.request_id&&receipt.action===command.action&&receipt.status==='committed');
    need(integer(receipt.affected_asset_count)&&(command.action==='delete'||receipt.affected_asset_count===0));
    need(command.action==='create'?scope(result.id):result.id===command.id);
    need(integer(result.revision)&&result.revision===(command.action==='create'?1:command.expected_revision+1));
    need(result.deleted===(command.action==='delete'));
    if(command.action!=='delete')need(result.name===command.name&&result.description===command.description,'Receipt does not contain the clicked snapshot');
    return receipt;
  }
  return Object.freeze({Journal,pending,canonical,verifyReceipt,PREFIX,MAX_ENTRIES,MAX_SCOPES,MAX_BYTES});
});
