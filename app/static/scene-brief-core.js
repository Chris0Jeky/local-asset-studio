/* Brief draft/recovery policy. Server cards and asset records are authoritative. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioBriefCore=api;})(globalThis,function(){
  'use strict';
  const FORMAT='studio.scene-brief/v1',SLOTS={background:['Background','image'],sprite:['Sprite sheet','image'],icon:['Icon','image'],video:['Video / scene','video'],audio:['Audio / ambience','audio'],mesh:['3D asset','3d']};
  const copy=value=>JSON.parse(JSON.stringify(value));
  const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
  const keys=(v,wanted)=>object(v)&&Object.keys(v).sort().join(',')===[...wanted].sort().join(',');
  const integer=v=>Number.isSafeInteger(v)&&v>=0;
  const id=v=>typeof v==='string'&&/^[A-Za-z0-9_-]{3,128}$/.test(v);
  const workspace=v=>typeof v==='string'&&/^[a-f0-9]{32}$/.test(v);
  const ref=v=>v===null||(keys(v,['asset_id','sha256','metadata_revision'])&&typeof v.asset_id==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(v.asset_id)&&/^[a-f0-9]{64}$/.test(v.sha256)&&integer(v.metadata_revision));
  function validBody(v){return keys(v,['format','workspace_id','collection_id','direction','slots'])&&v.format===FORMAT&&workspace(v.workspace_id)&&(v.collection_id===null||typeof v.collection_id==='string'&&/^[A-Za-z0-9_-]{1,128}$/.test(v.collection_id))&&typeof v.direction==='string'&&v.direction.length<=4000&&keys(v.slots,Object.keys(SLOTS))&&Object.values(v.slots).every(s=>keys(s,['intent','criteria','selected','previous'])&&['intent','criteria'].every(k=>typeof s[k]==='string'&&s[k].length<=2000)&&ref(s.selected)&&ref(s.previous));}
  function newCard(scope,identifier){return {id:identifier,kind:'brief',name:'Untitled scene',revision:null,body:{format:FORMAT,workspace_id:scope,collection_id:null,direction:'',slots:Object.fromEntries(Object.keys(SLOTS).map(k=>[k,{intent:'',criteria:'',selected:null,previous:null}]))}};}
  const content=card=>JSON.stringify([card.name,card.body]);
  function recovery(raw,scope,identifier){
    if(raw===null)return null;
    const v=JSON.parse(raw);
    if(!keys(v,['format','base_revision','card'])||v.format!=='studio.brief-draft/v1'||!(v.base_revision===null||integer(v.base_revision))||!object(v.card)||v.card.kind!=='brief'||!id(v.card.id)||v.card.id!==identifier||typeof v.card.name!=='string'||v.card.name.length>120||!validBody(v.card.body)||v.card.body.workspace_id!==scope)throw Error('Unrecognized recovery data. The original is preserved.');
    return v;
  }
  const envelope=(card,base)=>({format:'studio.brief-draft/v1',base_revision:base,card:copy(card)});
  const storageKey=(scope,identifier)=>'studio.brief-draft.v1:'+scope+':'+identifier;
  function route(hash){const [view,query='']=String(hash).replace(/^#/,'').split('?');const p=new URLSearchParams(query);return {view,id:id(p.get('id'))?p.get('id'):null,slot:Object.hasOwn(SLOTS,p.get('slot'))?p.get('slot'):'background',picker:p.get('picker')==='1',q:(p.get('q')||'').slice(0,200),cursor:(p.get('cursor')||'').slice(0,12288),returned:/^\d+$/.test(p.get('return_rev')||'')?Number(p.get('return_rev')):null};}
  function hash(value){const p=new URLSearchParams();if(value.id)p.set('id',value.id);if(value.slot)p.set('slot',value.slot);if(value.picker)p.set('picker','1');if(value.q)p.set('q',value.q);if(value.cursor)p.set('cursor',value.cursor);if(integer(value.returned))p.set('return_rev',value.returned);return '#briefs'+(p.size?'?'+p:'');}
  function context(v){return keys(v,['workspace_id','id','revision','slot'])&&workspace(v.workspace_id)&&id(v.id)&&integer(v.revision)&&Object.hasOwn(SLOTS,v.slot);}
  function choose(card,slot,asset){if(!Object.hasOwn(SLOTS,slot)||asset.media_type!==SLOTS[slot][1]||asset.privacy&&asset.privacy!=='regular'||asset.trashed_at||asset.archived_at)throw Error('Choose an active candidate of the slot’s type.');const selected={asset_id:asset.id,sha256:asset.sha256,metadata_revision:asset.metadata_revision};if(!ref(selected))throw Error('This candidate has no valid snapshot.');const next=copy(card),target=next.body.slots[slot];if(JSON.stringify(target.selected)!==JSON.stringify(selected)){target.previous=target.selected;target.selected=selected;}return next;}
  return {FORMAT,SLOTS,copy,validBody,newCard,content,recovery,envelope,storageKey,route,hash,context,choose};
});
