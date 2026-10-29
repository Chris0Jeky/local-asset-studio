/* A same-tab return address, never evidence that a generated asset was accepted. */
(function(){
  'use strict';
  const C=window.StudioBriefCore,main=document.querySelector('main');if(!C||!main)return;
  const banner=document.createElement('aside');banner.className='brief-return';banner.hidden=true;banner.setAttribute('aria-label','Return to scene brief');main.prepend(banner);let epoch=0;
  const allowed=()=>!window.StudioPrivacy||(StudioPrivacy.scope()==='regular'&&StudioPrivacy.creation()==='regular');
  async function refresh(){
    const token=++epoch;banner.hidden=true;if(!allowed()||C.route(location.hash).view==='briefs')return;
    let context;try{context=JSON.parse(sessionStorage.getItem('studio.brief-return.v1'));}catch(_){return;}if(!C.context(context))return;
    try{const response=await (window.StudioPrivacy?StudioPrivacy.fetch('/api/briefs/'+context.id):fetch('/api/briefs/'+context.id));if(!response.ok)return;const data=await response.json();if(token!==epoch||!allowed()||data.card.body.workspace_id!==context.workspace_id||data.card.trashed_at)return;
      const current=data.card.revision===context.revision;const p=document.createElement('p');p.textContent=current?'Prepared from '+data.card.name+' · '+C.SLOTS[context.slot][0]+'. Return to choose a real candidate.':'The saved brief changed after preparation. Reopen it before returning a candidate.';
      const link=document.createElement('a');link.textContent=current?'Return to this slot':'Reopen brief';link.href='/'+C.hash({id:context.id,slot:context.slot,picker:current,returned:current?context.revision:null});
      const dismiss=document.createElement('button');dismiss.textContent='Dismiss return link';dismiss.onclick=()=>{try{sessionStorage.removeItem('studio.brief-return.v1');}catch(_){}++epoch;banner.hidden=true;};
      banner.replaceChildren(p,link,dismiss);banner.hidden=false;
    }catch(_){/* Failed observation cannot manufacture a return authority. */}
  }
  document.addEventListener('studio:privacy-change',refresh);document.addEventListener('studio:brief-return-change',refresh);window.addEventListener('hashchange',refresh);refresh();
})();
