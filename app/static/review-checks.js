/* Quick review checks (#1203): one-tap yes/no answers stored as `check:<name>=yes|no` asset tags (app/workspace.py
   validates them). Only the owner presses a chip; absent means not checked, never no (K14/K15/K16). */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioReviewChecks=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const COMBINE=['pose','face','outfit','style','clean'],CREATE=['style','anatomy','composition','clean'];
  const CHARACTER=['face','outfit','silhouette','hands','style'],BACKGROUND=['composition','depth','palette','clean'];
  const HELP={pose:'Pose matches the pose picture',face:'Face is the character’s',outfit:'Clothes are right',style:'The look is right',clean:'No artifacts or broken details',anatomy:'Anatomy and hands look right',composition:'Framing and layout work',silhouette:'The character reads clearly in silhouette',hands:'Hands look right',depth:'Foreground and background feel separated',palette:'The colours work together'};
  const TAG=/^check:(pose|face|outfit|style|clean|anatomy|composition|silhouette|hands|depth|palette)=(yes|no)$/;
  // Combine judges the transfer; authored review_set selects a subject, and unknown routes keep Create's checks.
  function forPreset(preset){return preset?.continuation_capability?.operation==='combine'?COMBINE:preset?.review_set==='character'?CHARACTER:preset?.review_set==='background'?BACKGROUND:CREATE;}
  function forAsset(asset,presets){return asset?.media_type!=='image'?[]:forPreset((presets||[]).find(p=>p.id===asset.preset_id));}
  function answers(tags){
    const seen={},clash=new Set();
    for(const tag of Array.isArray(tags)?tags:[]){const m=TAG.exec(tag);if(!m)continue;const value=m[2]==='yes';if(m[1] in seen&&seen[m[1]]!==value)clash.add(m[1]);seen[m[1]]=value;}
    for(const name of clash)delete seen[name];
    return seen;
  }
  function answer(tags,name){const all=answers(tags);return name in all?all[name]:null;}
  function cycle(tags,name){
    if(!HELP[name])throw Error('Unknown check: '+name);
    const now=answer(tags,name),rest=(Array.isArray(tags)?tags:[]).filter(t=>!t.startsWith('check:'+name+'='));
    return now===null?[...rest,'check:'+name+'=yes']:now?[...rest,'check:'+name+'=no']:rest;
  }
  function tally(assets,names){
    const out=Object.fromEntries(names.map(n=>[n,{yes:0,checked:0}]));
    for(const asset of assets||[]){if(!asset||asset.trashed_at)continue;const all=answers(asset.tags);for(const n of names)if(n in all){out[n].checked++;if(all[n])out[n].yes++;}}
    return out;
  }
  function summary(assets,names){const t=tally(assets,names);return names.filter(n=>t[n].checked).map(n=>n+' '+t[n].yes+'/'+t[n].checked).join(' · ');}
  function chipsHTML({tags,names,attr,asset,disabled,escape}){
    return (names||[]).map((name,i)=>{
      const now=answer(tags,name),state=now===null?'not checked':now?'yes':'no';
      return '<button type="button" class="review-check'+(now===null?'':now?' is-yes':' is-no')+'" '+attr+'="'+name+'"'+(asset!=null?' data-asset="'+escape(asset)+'"':'')+' aria-label="'+name+': '+state+'. Key '+(i+1)+' changes it." title="'+escape(HELP[name])+'"'+(disabled?' disabled':'')+'>'+(now===null?'':now?'✓ ':'✗ ')+name+'</button>';
    }).join('');
  }
  function keyIndex(e){return e.repeat||e.ctrlKey||e.metaKey||e.altKey||!/^[1-5]$/.test(e.key||'')?-1:Number(e.key)-1;}
  return{COMBINE,CREATE,CHARACTER,BACKGROUND,HELP,forPreset,forAsset,answers,answer,cycle,tally,summary,chipsHTML,keyIndex};
});
