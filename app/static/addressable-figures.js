/* Addressable figure editor: local crop commands over immutable Workspace images. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object' && module.exports)module.exports=api;
  else{
    root.StudioAddressableFigures=api;
    const boot=()=>api.install(root.document);
    if(root.document?.readyState==='loading')root.document.addEventListener('DOMContentLoaded',boot,{once:true});
    else boot();
  }
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const BASIS=10000,MAX_FIGURES=32,MIN_POINTER_DRAG=4,PENDING_KEY='studio.addressable-figures.pending.v1';
  const fields=['x','y','width','height'];
  function copyRect(rect){return Object.fromEntries(fields.map(key=>[key,rect[key]]));}
  function integer(value,label){
    if(typeof value==='string' && value.trim()!=='')value=Number(value);
    if(!Number.isSafeInteger(value))throw Error(label+' must be an integer basis-point value.');
    return value;
  }
  function normalizeRect(rect,index=0){
    if(!rect || typeof rect!=='object' || Array.isArray(rect))throw Error('Rectangle '+(index+1)+' is invalid.');
    const value=Object.fromEntries(fields.map(key=>[key,integer(rect[key],'Rectangle '+(index+1)+' '+key)]));
    if(value.x<0 || value.y<0 || value.width<=0 || value.height<=0 || value.x+value.width>BASIS || value.y+value.height>BASIS)
      throw Error('Rectangle '+(index+1)+' must stay inside the source image.');
    return value;
  }
  function overlaps(a,b){return a.x<b.x+b.width && b.x<a.x+a.width && a.y<b.y+b.height && b.y<a.y+a.height;}
  function validateRectangles(rectangles,requireNonOverlapping=true){
    if(!Array.isArray(rectangles) || !rectangles.length)throw Error('Add at least one rectangle.');
    if(rectangles.length>MAX_FIGURES)throw Error('A split can create at most '+MAX_FIGURES+' child assets.');
    const values=rectangles.map(normalizeRect);
    if(requireNonOverlapping)for(let i=0;i<values.length;i++)for(let j=i+1;j<values.length;j++)if(overlaps(values[i],values[j]))
      throw Error('Rectangles '+(i+1)+' and '+(j+1)+' overlap. Turn off non-overlap only when the artwork intentionally crosses panels.');
    return values;
  }
  function clamp(value,min,max){return Math.min(max,Math.max(min,value));}
  function fromPixels(start,end,bounds){
    if(!bounds || !(bounds.width>0) || !(bounds.height>0))throw Error('The source image dimensions are unavailable.');
    const left=clamp(Math.min(start.x,end.x)-bounds.left,0,bounds.width),right=clamp(Math.max(start.x,end.x)-bounds.left,0,bounds.width);
    const top=clamp(Math.min(start.y,end.y)-bounds.top,0,bounds.height),bottom=clamp(Math.max(start.y,end.y)-bounds.top,0,bounds.height);
    let x=Math.round(left/bounds.width*BASIS),y=Math.round(top/bounds.height*BASIS);
    let edgeX=Math.round(right/bounds.width*BASIS),edgeY=Math.round(bottom/bounds.height*BASIS);
    x=clamp(x,0,BASIS-1);y=clamp(y,0,BASIS-1);edgeX=clamp(edgeX,x+1,BASIS);edgeY=clamp(edgeY,y+1,BASIS);
    return normalizeRect({x,y,width:edgeX-x,height:edgeY-y});
  }
  function createHistory(initial=[]){
    let current=initial.map(copyRect),past=[];
    const api={
      value:()=>current.map(copyRect),
      canUndo:()=>past.length>0,
      commit(next){const clean=Array.isArray(next)?next.map(copyRect):[];if(JSON.stringify(clean)===JSON.stringify(current))return false;past.push(current);current=clean;return true;},
      undo(){if(!past.length)return false;current=past.pop();return true;},
      clear(){return api.commit([]);},
      remove(index){if(index<0 || index>=current.length)return false;const next=api.value();next.splice(index,1);return api.commit(next);},
      move(index,delta){const target=index+delta;if(index<0 || index>=current.length || target<0 || target>=current.length)return false;const next=api.value(),[item]=next.splice(index,1);next.splice(target,0,item);return api.commit(next);},
      replace(index,rect){if(index<0 || index>=current.length)return false;const next=api.value();next[index]=copyRect(rect);return api.commit(next);}
    };
    return api;
  }
  function requestMatchesAsset(request,asset){return !!request && !!asset && request.workspace_id===asset.workspace_id && request.asset_id===asset.id && request.parent_sha256===asset.sha256;}
  function createRequest({workspaceId,asset,rectangles,requestId,requireNonOverlapping=true}){
    if(!/^[0-9a-f]{32}$/.test(workspaceId||''))throw Error('Reload the Workspace before splitting figures.');
    if(!asset || typeof asset.id!=='string' || !/^[0-9a-f]{64}$/.test(asset.sha256||''))throw Error('The parent asset identity is unavailable.');
    if(typeof requestId!=='string' || !requestId.length || requestId.length>200)throw Error('The split request identity is invalid.');
    return {workspace_id:workspaceId,request_id:requestId,asset_id:asset.id,parent_sha256:asset.sha256,
      rectangles:validateRectangles(rectangles,requireNonOverlapping),require_non_overlapping:!!requireNonOverlapping};
  }
  function restoreRequest(value){
    try{
      if(!value || typeof value!=='object' || Array.isArray(value) || !/^[0-9a-f]{32}$/.test(value.request_id||''))throw Error('invalid retained request');
      const canonical=createRequest({workspaceId:value.workspace_id,asset:{id:value.asset_id,sha256:value.parent_sha256},rectangles:value.rectangles,requestId:value.request_id,requireNonOverlapping:value.require_non_overlapping});
      if(JSON.stringify(canonical)!==JSON.stringify(value))throw Error('retained request bytes are not canonical');
      return canonical;
    }catch(error){throw Error('The retained figure split request is invalid.');}
  }
  function validateReceipt(receipt,request){
    const created=receipt?.created,figures=receipt?.figures;
    if(receipt?.status!=='created' || receipt.action!=='split_figures' || receipt.workspace_id!==request.workspace_id ||
       receipt.parent_asset_id!==request.asset_id || receipt.request_id!==request.request_id ||
       receipt.generation_submitted!==false || !Array.isArray(created) || created.length!==request.rectangles.length || created.some(id=>typeof id!=='string' || !/^[0-9a-f]{32}$/.test(id)) ||
       !Array.isArray(figures) || figures.length!==created.length || figures.some((figure,index)=>figure?.index!==index+1 || figure.asset_id!==created[index]))
      throw Error('The server returned an invalid figure-split receipt. Keep the exact request for recovery.');
    return receipt;
  }
  function failureKind(error){return error && Number.isInteger(error.status) && error.status>=400 && error.status<500?'refused':'unconfirmed';}
  function randomId(cryptoObject){
    if(!cryptoObject?.getRandomValues)throw Error('Secure request identities are unavailable in this browser.');
    const bytes=new Uint8Array(16);cryptoObject.getRandomValues(bytes);return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
  }
  function install(doc){
    if(!doc || doc.documentElement?.dataset.addressableFiguresInstalled)return false;
    const handoffs=doc.querySelector('#assetHandoffs'),dialog=doc.querySelector('#assetDialog');
    if(!handoffs || !dialog)return false;
    doc.documentElement.dataset.addressableFiguresInstalled='true';
    if(!doc.querySelector('link[data-addressable-figures-style]')){
      const link=doc.createElement('link');link.rel='stylesheet';link.href='/static/addressable-figures.css';link.dataset.addressableFiguresStyle='';doc.head.append(link);
    }
    const panel=doc.createElement('section');panel.id='figureSplitEditor';panel.className='figure-split-editor';panel.hidden=true;
    panel.innerHTML='<div class="figure-split-head"><div><span class="eyebrow">LOCAL CROP · NO GENERATION</span><h3>Split this image into child assets</h3></div><button type="button" data-figure-close aria-label="Close figure splitter">Close</button></div><p>Draw boxes over figures, or enter exact basis points. The numbered list is the child order. The parent image and its metadata stay unchanged.</p><div class="figure-split-layout"><div><div id="figureSplitStage" class="figure-split-stage" tabindex="0" aria-label="Source image. Drag to add a crop rectangle; keyboard users can use the exact rectangle form."><img id="figureSplitImage" draggable="false" alt=""><div id="figureSplitOverlay" aria-hidden="true"></div></div><small id="figureSplitSource"></small></div><div class="figure-split-controls"><form id="figureSplitAdd"><fieldset><legend>Add exact rectangle · basis points 0–10000</legend><label>X<input name="x" type="number" min="0" max="9999" step="1" value="0" required></label><label>Y<input name="y" type="number" min="0" max="9999" step="1" value="0" required></label><label>Width<input name="width" type="number" min="1" max="10000" step="1" value="5000" required></label><label>Height<input name="height" type="number" min="1" max="10000" step="1" value="10000" required></label><button type="submit">Add rectangle</button></fieldset></form><ol id="figureSplitList" aria-label="Figure rectangles in child order"></ol><div class="figure-split-options"><label><input id="figureSplitNoOverlap" type="checkbox" checked> Require non-overlapping rectangles</label><button type="button" data-figure-undo>Undo last change</button><button type="button" data-figure-clear>Clear rectangles</button></div><p id="figureSplitStatus" role="status" aria-live="polite"></p><div id="figureSplitRecovery" class="asset-save-recovery" hidden></div><button id="figureSplitCreate" type="button" class="primary">Create child assets</button><div id="figureSplitChildren"></div></div></div>';
    dialog.append(panel);
    const stage=panel.querySelector('#figureSplitStage'),image=panel.querySelector('#figureSplitImage'),overlay=panel.querySelector('#figureSplitOverlay'),list=panel.querySelector('#figureSplitList');
    const status=panel.querySelector('#figureSplitStatus'),recovery=panel.querySelector('#figureSplitRecovery'),children=panel.querySelector('#figureSplitChildren');
    let session=null,drag=null,busy=false;
    const globals={
      asset(){try{return typeof activeAsset==='object'?activeAsset:null;}catch(error){return null;}},
      async request(path,options){
        if(typeof globalThis.api==='function')return globalThis.api(path,options);
        const response=await fetch(path,options),data=await response.json();if(!response.ok){const error=Error(data.error||response.statusText);error.status=response.status;error.data=data;throw error;}return data;
      },
      async refresh(expectedIds=[]){
        if(typeof globalThis.refreshAssets!=='function')return {ok:false,error:'Workspace refresh is unavailable.'};
        const outcome=await globalThis.refreshAssets(true);
        if(outcome?.ok===false)return {ok:false,error:outcome.error||'Workspace refresh failed.'};
        try{
          const records=typeof assetState==='object'&&Array.isArray(assetState.assets)?assetState.assets:[];
          return expectedIds.every(id=>records.some(asset=>asset?.id===id))?{ok:true}:{ok:false,error:'The refreshed Workspace does not contain the new child assets yet.'};
        }catch(error){return {ok:false,error:'The refreshed Workspace could not be verified.'};}
      },
      open(id){if(typeof globalThis.openAsset==='function')return globalThis.openAsset(id);return false;},
      message(text,error=false){if(typeof globalThis.assetMessage==='function')globalThis.assetMessage(text,error);}
    };
    function storage(){try{return sessionStorage;}catch(error){return null;}}
    function readPending(){
      const store=storage();if(!store)return null;
      try{const raw=store.getItem(PENDING_KEY);if(raw==null)return null;const value=JSON.parse(raw);if(value?.version!==1)throw Error('unsupported retained record');return restoreRequest(value.request);}catch(error){return {invalid:true};}
    }
    function writePending(request){
      const store=storage(),record=JSON.stringify({version:1,request});
      if(!store)throw Error('This browser cannot retain the exact split request. No request was sent.');
      try{store.setItem(PENDING_KEY,record);if(store.getItem(PENDING_KEY)!==record)throw Error('retained bytes did not match');}
      catch(error){throw Error('The exact split request could not be retained in this tab. No request was sent.');}
    }
    function clearPending(request){const store=storage();if(!store)return;try{const saved=JSON.parse(store.getItem(PENDING_KEY));if(!request || saved?.request?.request_id===request.request_id)store.removeItem(PENDING_KEY);}catch(error){} }
    function current(){const asset=globals.asset();return asset?.media_type==='image' && !asset.trashed_at?asset:null;}
    function setStatus(text,error=false){status.textContent=text;status.classList.toggle('error',error);}
    function values(){return session?.history.value()||[];}
    function setLocked(locked){
      for(const control of panel.querySelectorAll('input,button')){
        if(control.matches('[data-figure-close], [data-figure-check], [data-figure-retry]'))continue;
        if(locked){if(!control.disabled)control.dataset.figureLocked='true';control.disabled=true;}
        else if(control.dataset.figureLocked){delete control.dataset.figureLocked;control.disabled=false;}
      }
      panel.querySelector('[data-figure-close]').disabled=false;
    }
    function reviewMessage(error=''){
      if(error)return error;
      const count=values().length;return count?count+' rectangle'+(count===1?'':'s')+' ready in list order. Review every box, then create local child assets. The parent stays unchanged and no generation is submitted.':'Draw a box on the image or add exact coordinates. Nothing has been created.';
    }
    function renderOverlay(draft=null){
      overlay.replaceChildren();
      values().forEach((rect,index)=>{
        const box=doc.createElement('span');box.className='figure-split-box';box.style.left=rect.x/BASIS*100+'%';box.style.top=rect.y/BASIS*100+'%';box.style.width=rect.width/BASIS*100+'%';box.style.height=rect.height/BASIS*100+'%';box.textContent=index+1;overlay.append(box);
      });
      if(draft){const box=doc.createElement('span');box.className='figure-split-box is-draft';box.style.left=draft.x/BASIS*100+'%';box.style.top=draft.y/BASIS*100+'%';box.style.width=draft.width/BASIS*100+'%';box.style.height=draft.height/BASIS*100+'%';overlay.append(box);}
    }
    function rowInput(rect,index,key){return '<label><span>'+key+'</span><input data-figure-field="'+key+'" data-figure-index="'+index+'" type="number" min="'+(key==='width'||key==='height'?1:0)+'" max="10000" step="1" value="'+rect[key]+'"></label>';}
    function render(keepStatus=false){
      if(!session)return;
      const rectangles=values();list.innerHTML=rectangles.map((rect,index)=>'<li data-figure-row="'+index+'"><b>Figure '+(index+1)+'</b><div class="figure-split-row-fields">'+fields.map(key=>rowInput(rect,index,key)).join('')+'</div><div><button type="button" data-figure-move="-1" data-figure-index="'+index+'" '+(index===0?'disabled':'')+'>Move earlier</button><button type="button" data-figure-move="1" data-figure-index="'+index+'" '+(index===rectangles.length-1?'disabled':'')+'>Move later</button><button type="button" data-figure-remove data-figure-index="'+index+'">Remove</button></div></li>').join('');
      renderOverlay();if(!keepStatus)setStatus(reviewMessage());renderRecovery();
      panel.querySelector('[data-figure-undo]').disabled=!session.history.canUndo() || busy || !!session.pending;
      panel.querySelector('[data-figure-clear]').disabled=!rectangles.length || busy || !!session.pending;
      panel.querySelector('#figureSplitCreate').disabled=!rectangles.length || busy || !!session.pending;
    }
    function renderRecovery(){
      const pending=session?.pending;recovery.hidden=!pending;
      recovery.innerHTML=pending?'<p>This exact split is unconfirmed. Check the durable receipt or retry the identical request. Editing stays locked so a new request cannot accidentally duplicate children.</p><code>'+pending.request_id+'</code><div class="asset-detail-actions"><button type="button" data-figure-check>Check split status</button><button type="button" data-figure-retry>Retry exact split</button></div>':'';
      setLocked(!!pending);
    }
    function openEditor(){
      const asset=current();if(!asset){globals.message('Only active, non-trashed images can be split into figure children.',true);return;}
      if(!session || session.asset.id!==asset.id || session.asset.sha256!==asset.sha256 || session.asset.workspace_id!==asset.workspace_id){
        const pending=readPending();
        if(pending && !requestMatchesAsset(pending,asset)){const identity=pending.invalid?'an invalid retained record':'request '+pending.request_id+' for source '+pending.asset_id;globals.message('An unconfirmed figure split belongs to '+identity+'. Reopen that source and resolve it before starting another split in this tab. If it is unavailable, record the request ID before closing the tab.',true);return;}
        session={asset:{id:asset.id,sha256:asset.sha256,workspace_id:asset.workspace_id,url:asset.url,title:asset.title},history:createHistory(pending?.rectangles||[]),pending,receipt:null};
      }
      image.src=asset.url;image.alt='Split figures from '+asset.title;panel.querySelector('#figureSplitSource').textContent=asset.title+' · '+asset.sha256.slice(0,12)+'… · coordinates are retained as basis points';
      panel.hidden=false;children.innerHTML='';render();panel.scrollIntoView({block:'start',behavior:'smooth'});
    }
    function closeEditor(){panel.hidden=true;drag=null;renderOverlay();}
    function add(rect){
      if(!session || busy || session.pending)return;
      const next=values();if(next.length>=MAX_FIGURES){setStatus('A split can create at most '+MAX_FIGURES+' children.',true);return;}
      next.push(normalizeRect(rect,next.length));
      try{validateRectangles(next,panel.querySelector('#figureSplitNoOverlap').checked);session.history.commit(next);render();}
      catch(error){setStatus(error.message,true);}
    }
    async function sendPending(observe=false){
      if(!session?.pending || busy)return;
      const operation=session,request=operation.pending,current=()=>session===operation;
      busy=true;setLocked(true);setStatus(observe?'Checking the retained split receipt…':'Submitting the exact retained split…');
      try{
        const path=observe?'/api/assets/commands/'+encodeURIComponent(request.request_id)+'?workspace_id='+encodeURIComponent(request.workspace_id):'/api/assets/split-figures';
        const result=await globals.request(path,observe?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
        if(observe && result?.status==='unknown'){
          if(current())setStatus('The split is still unconfirmed. No new request was sent.',true);
          return;
        }
        validateReceipt(result,request);clearPending(request);operation.pending=null;operation.receipt=result;operation.history=createHistory([]);
        let refreshError=null;
        try{const refreshed=await globals.refresh(result.created);if(!refreshed?.ok)refreshError=Error(refreshed?.error||'Workspace refresh failed.');}catch(error){refreshError=error;}
        if(!current()){
          globals.message('Figure split confirmed for '+operation.asset.title+'. Reopen that source to inspect its '+result.created.length+' child asset'+(result.created.length===1?'':'s')+'.'+(refreshError?' The Workspace refresh failed: '+refreshError.message:''),!!refreshError);
          return;
        }
        if(refreshError){
          children.innerHTML='<p><b>'+result.created.length+' child asset'+(result.created.length===1?'':'s')+' created.</b> The parent is unchanged, but the Workspace could not refresh. Refresh the library before opening the children.</p>';
          setStatus('Split confirmed, but the Workspace refresh failed: '+refreshError.message+' Refresh the library before opening the children.',true);
          globals.message('Figure split confirmed, but the Workspace refresh failed. Refresh the library before opening the children.',true);
          return;
        }
        const buttons=result.created.map((id,index)=>'<button type="button" data-figure-child="'+id+'">Open child '+(index+1)+'</button>').join('');
        children.innerHTML='<p><b>'+result.created.length+' child asset'+(result.created.length===1?'':'s')+' created.</b> The parent is unchanged; generation and artistic review remain separate.</p><div class="asset-detail-actions">'+buttons+'</div>';
        setStatus('Split confirmed. The new children are ordinary Workspace images and can use Continue with this.');globals.message('Created '+result.created.length+' local figure child asset'+(result.created.length===1?'':'s')+'.');
      }catch(error){
        if(!observe && failureKind(error)==='refused'){
          clearPending(request);operation.pending=null;
          if(current())setStatus('Split was not applied. '+error.message+' Review the source and rectangles before creating a new request.',true);
          else globals.message('The retained split for '+operation.asset.title+' was refused. Reopen that source before trying again.',true);
        }else if(current())setStatus((observe?'Split status not confirmed. ':'Split not confirmed. ')+error.message+' No automatic retry or new request was sent.',true);
        else globals.message('The retained split for '+operation.asset.title+' remains unconfirmed. Reopen that source to check or retry the exact request.',true);
      }finally{
        busy=false;
        if(session)render(true);
      }
    }
    async function createChildren(){
      if(!session || busy || session.pending)return;
      let request;
      try{request=createRequest({workspaceId:session.asset.workspace_id,asset:session.asset,rectangles:values(),requestId:randomId(globalThis.crypto),requireNonOverlapping:panel.querySelector('#figureSplitNoOverlap').checked});}
      catch(error){setStatus(error.message,true);return;}
      if(!globalThis.confirm('Create '+request.rectangles.length+' child asset'+(request.rectangles.length===1?'':'s')+' from these exact rectangles? The parent stays unchanged and no model job runs.'))return;
      try{writePending(request);}catch(error){setStatus(error.message,true);return;}
      session.pending=request;renderRecovery();await sendPending(false);
    }
    function syncAction(){
      const asset=current(),existing=handoffs.querySelector('[data-figure-split-open]');
      if(asset && dialog.open){
        if(!existing){const button=doc.createElement('button');button.type='button';button.dataset.figureSplitOpen='';button.textContent='Split figures';button.title='Mark rectangular figures and create local child images without generation';handoffs.append(button);}
      }else existing?.remove();
      if(session && (!asset || session.asset.id!==asset.id || session.asset.sha256!==asset.sha256))panel.hidden=true;
    }
    new MutationObserver(syncAction).observe(handoffs,{childList:true});
    dialog.addEventListener('close',()=>{panel.hidden=true;drag=null;});
    doc.addEventListener('click',event=>{
      const target=event.target.closest?.('button');if(!target)return;
      if(target.matches('[data-figure-split-open]'))return openEditor();
      if(!panel.contains(target))return;
      if(target.matches('[data-figure-close]'))return closeEditor();
      if(target.matches('[data-figure-undo]')){session?.history.undo();render();return;}
      if(target.matches('[data-figure-clear]')){session?.history.clear();render();return;}
      if(target.matches('[data-figure-remove]')){session?.history.remove(Number(target.dataset.figureIndex));render();return;}
      if(target.matches('[data-figure-move]')){session?.history.move(Number(target.dataset.figureIndex),Number(target.dataset.figureMove));render();return;}
      if(target.matches('[data-figure-check]'))return void sendPending(true);
      if(target.matches('[data-figure-retry]'))return void sendPending(false);
      if(target.matches('#figureSplitCreate'))return void createChildren();
      if(target.matches('[data-figure-child]')){const id=target.dataset.figureChild;closeEditor();globals.open(id);}
    });
    panel.querySelector('#figureSplitAdd').addEventListener('submit',event=>{
      event.preventDefault();const data=new FormData(event.currentTarget);try{add(Object.fromEntries(fields.map(key=>[key,Number(data.get(key))])));}catch(error){setStatus(error.message,true);}
    });
    list.addEventListener('change',event=>{
      const input=event.target.closest('[data-figure-field]');if(!input || !session || session.pending)return;
      const index=Number(input.dataset.figureIndex),rect=values()[index];rect[input.dataset.figureField]=Number(input.value);
      try{normalizeRect(rect,index);const next=values();next[index]=rect;validateRectangles(next,panel.querySelector('#figureSplitNoOverlap').checked);session.history.commit(next);render();}
      catch(error){setStatus(error.message,true);render(true);}
    });
    panel.querySelector('#figureSplitNoOverlap').addEventListener('change',event=>{
      try{validateRectangles(values(),event.target.checked);setStatus(reviewMessage());}
      catch(error){setStatus(error.message,true);}
    });
    stage.addEventListener('pointerdown',event=>{
      if(!session || busy || session.pending || event.button!==0)return;const bounds=image.getBoundingClientRect();if(!bounds.width || !bounds.height)return setStatus('Wait for the source image to load before drawing.',true);
      drag={start:{x:event.clientX,y:event.clientY},bounds};stage.setPointerCapture?.(event.pointerId);event.preventDefault();
    });
    stage.addEventListener('pointermove',event=>{if(!drag)return;try{renderOverlay(fromPixels(drag.start,{x:event.clientX,y:event.clientY},drag.bounds));}catch(error){}});
    stage.addEventListener('pointerup',event=>{
      if(!drag)return;const pending=drag;drag=null;
      if(Math.abs(event.clientX-pending.start.x)<MIN_POINTER_DRAG || Math.abs(event.clientY-pending.start.y)<MIN_POINTER_DRAG){renderOverlay();setStatus('Drag at least '+MIN_POINTER_DRAG+' pixels in both directions to add a rectangle. Use exact coordinates for smaller crops.',true);event.preventDefault();return;}
      try{add(fromPixels(pending.start,{x:event.clientX,y:event.clientY},pending.bounds));}catch(error){setStatus(error.message,true);}event.preventDefault();
    });
    stage.addEventListener('pointercancel',()=>{drag=null;renderOverlay();});
    syncAction();return true;
  }
  return {BASIS,MAX_FIGURES,MIN_POINTER_DRAG,fromPixels,validateRectangles,createHistory,createRequest,restoreRequest,validateReceipt,failureKind,randomId,requestMatchesAsset,install};
});
