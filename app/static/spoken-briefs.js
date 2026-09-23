/* Native local player and explicit evidence saves. No inference or background writes. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), prefix = '/api/spoken-briefs';
  const findings = {pronunciation:'Pronunciation', omissions_repetitions:'Omissions / repetitions', delivery:'Delivery', fatigue:'Listening fatigue'};
  const url = (route, query={}) => prefix + route + (Object.keys(query).length ? '?' + new URLSearchParams(query) : '');
  const unavailable = () => Error('Spoken Brief API unavailable. Check that Studio is running, then reload this page.');
  async function request(route, query={}, body) {
    let response;
    try { response = await fetch(url(route, query), {method:body === undefined ? 'GET' : 'POST', cache:'no-store',
      credentials:'same-origin', redirect:'error', headers:body === undefined ? {} : {'Content-Type':'application/json'},
      body:body === undefined ? undefined : JSON.stringify(body)}); } catch (_) { throw unavailable(); }
    if (!/^application\/json(?:\s*;|$)/i.test(response.headers.get('Content-Type') || '') || !response.body) throw unavailable();
    const reader = response.body.getReader(), parts=[]; let bytes=0;
    try {
      while (true) {
        const {value, done} = await reader.read(); if (done) break;
        bytes += value.length;
        if (bytes > 8 * 1024 * 1024) { await reader.cancel(); throw Error('Response exceeds the inspection budget'); }
        parts.push(value);
      }
    } finally { reader.releaseLock(); }
    const raw = new Uint8Array(bytes); let offset=0;
    for (const part of parts) { raw.set(part,offset); offset += part.length; }
    let value;
    try { value = JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw)); } catch (_) { throw unavailable(); }
    if (!response.ok) throw Error(value?.error || `Request refused (${response.status})`);
    return value;
  }
  const session = new SpokenReview.ReviewSession(request), drafts = new Map();
  let playerBinding=null, pendingSeek=null, loop=null, chosenReview=null, discoveryTicket=0, discardDraft=false, reviewBaseline=null;
  const status = text => { $('status').textContent=text; };
  const option = (value,text) => { const e=document.createElement('option'); e.value=value; e.textContent=text; return e; };
  const seconds = sample => (sample/48000).toFixed(3) + ' s';
  const draftKey = () => session.current && session.current.key + ':' + session.current.snapshot.archive_sha256;
  function playerReady() {
    const player=$('player');
    return !!session.current && playerBinding?.epoch === session.epoch && player.currentSrc === playerBinding.src
      && player.readyState >= 1 && !pendingSeek && !player.seeking && !player.error && Number.isFinite(player.currentTime);
  }
  function buttons() {
    const blocked=session.blocked(); $('savePosition').disabled=blocked || !playerReady(); $('saveReview').disabled=blocked;
    $('loadReport').disabled=!session.current || !$('reportList').value;
    $('loadReview').disabled=!session.current || !$('reviewList').value;
  }
  for (const [key,label] of Object.entries(findings)) {
    const wrapper=document.createElement('label'); wrapper.textContent=label;
    const select=document.createElement('select'); select.id='finding-'+key;
    for (const [value,text] of [['not-reviewed','Not reviewed'],['acceptable','Acceptable'],['needs-work','Needs work']]) select.append(option(value,text));
    wrapper.append(select); $('findings').append(wrapper);
  }
  const reviewFields = () => ({target:$('reviewTarget').value, decision:$('decision').value, reviewer:$('reviewer').value,
    reason:$('reason').value, findings:Object.fromEntries(Object.keys(findings).map(k=>[k,$('finding-'+k).value]))});
  function retainDraft() {
    const key=draftKey(); if (!key || discardDraft) return true;
    const draft=reviewFields();
    if (JSON.stringify(draft) === reviewBaseline) { drafts.delete(key); return true; }
    if (!drafts.has(key) && drafts.size >= 64) { status('The in-tab draft limit is reached. Discard this draft explicitly before switching.'); return false; }
    drafts.set(key, draft);
    return true; // In-tab drafts are bounded; never evict silently.
  }
  function resetPlayer() { $('player').pause(); $('player').removeAttribute('src'); $('player').load(); playerBinding=null; pendingSeek=null; }
  function applyRate() {
    const rate=Number($('rate').value);
    if (Number.isFinite(rate) && rate>=.5 && rate<=3) {
      // load() restores defaultPlaybackRate; keep both properties in sync.
      $('player').defaultPlaybackRate=rate; $('player').playbackRate=rate;
    }
  }
  function selectAudio(target, seekSample=null) {
    if (!session.current) return;
    const {key,snapshot}=session.current;
    const src=new URL(url('/audio',{key,archive_sha256:snapshot.archive_sha256,target}),document.baseURI).href;
    $('audioTarget').value=target; applyRate();
    pendingSeek=null; playerBinding={epoch:session.epoch,target,src}; $('player').pause();
    if ($('player').src !== src) { $('player').src=src; pendingSeek=null; }
    if (seekSample !== null) {
      pendingSeek={src,seconds:seekSample/48000,epoch:session.epoch};
      if ($('player').readyState >= 1 && $('player').currentSrc === src) applySeek();
      else $('player').load();
    }
    buttons();
  }
  function applySeek() {
    if (!pendingSeek || pendingSeek.epoch !== session.epoch || $('player').currentSrc !== pendingSeek.src) return;
    $('player').currentTime=pendingSeek.seconds; pendingSeek=null;
    $('player').playbackRate=Number($('rate').value);
  }
  $('player').addEventListener('loadedmetadata',()=>{applySeek(); buttons();});
  for (const event of ['emptied','seeking','seeked','error']) $('player').addEventListener(event,buttons);
  $('player').addEventListener('error',()=>{ if (playerBinding) status('Audio could not be read. Inspect this archive again; no generation or retry was sent.'); });
  $('player').addEventListener('timeupdate',()=>{
    if (loop && playerBinding?.target === 'master' && $('player').currentTime >= loop[1]/48000) $('player').currentTime=loop[0]/48000;
  });
  $('audioTarget').onchange=()=>selectAudio($('audioTarget').value);
  $('rate').onchange=applyRate;
  function loopText() { $('loopStatus').textContent=loop ? `Local loop: ${loop[0]}–${loop[1]} samples. Save position to retain it.` : 'No listening loop selected.'; }
  $('clearLoop').onclick=()=>{loop=null; loopText();};
  function savedText() {
    const p=session.current.snapshot.playback;
    $('savedPosition').textContent=`Saved: ${p.sample} samples (${seconds(p.sample)}) · ${p.status || 'unheard'} · ${p.rate}×`;
  }
  function records(select, ids, label) { select.replaceChildren(option('',label),...ids.map(id=>option(id,id))); }
  function renderSegments() {
    if (!session.current) return;
    const a=session.current.snapshot.archive, report=session.reportValue;
    const map=new Map((report?.targets || []).map(t=>[t.id,t])); const body=$('segments').querySelector('tbody'); body.replaceChildren();
    for (const s of a.segments) {
      const machine=map.get(s.id), state=machine?.transcript_status || 'Not loaded';
      if ($('exceptionsOnly').checked && report && state === 'match') continue;
      const row=document.createElement('tr');
      const labels=[`${s.id}\n${s.start_sample} samples`,s.text,state,
        chosenReview?.target === s.id ? `${chosenReview.decision} · ${chosenReview.reviewer}` : 'Unreviewed · no record selected'];
      for (const text of labels) { const cell=document.createElement('td'); cell.textContent=text; row.append(cell); } body.append(row);
    }
  }
  function renderInspection() {
    const {key,snapshot}=session.current, a=snapshot.archive;
    $('archiveTitle').textContent=a.source.name; $('duration').textContent=`${a.segments.length} segments · ${seconds(a.master.samples)}`;
    $('identity').textContent=JSON.stringify(a,null,2); $('recordWarnings').textContent=[...snapshot.record_refusals,
      ...(snapshot.record_lists_truncated ? ['Record list limit reached; use the CLI for additional records.'] : [])].join('\n');
    const targets=[option('master','Full archival master'), ...a.segments.map(s=>option(s.id,`${s.id} · ${s.text.slice(0,80)}`))];
    $('audioTarget').replaceChildren(...targets); $('reviewTarget').replaceChildren(...targets.map(x=>x.cloneNode(true)));
    $('rate').value=snapshot.playback.rate; loop=snapshot.playback.loop; loopText(); savedText();
    selectAudio('master');
    $('downloadAudio').href=url('/audio',{key,archive_sha256:snapshot.archive_sha256,target:'master',download:'1'});
    $('downloadChapters').href=url('/chapters',{key,archive_sha256:snapshot.archive_sha256});
    $('chapters').replaceChildren();
    for (const [i,chapter] of a.chapters.entries()) {
      const row=document.createElement('div'); row.className='chapter';
      const seek=document.createElement('button'); seek.dataset.chapter=i; seek.textContent=`${chapter.title} · ${seconds(chapter.start_sample)}`;
      seek.onclick=()=>selectAudio('master',chapter.start_sample);
      const repeat=document.createElement('button'); repeat.textContent='Loop chapter'; repeat.setAttribute('aria-label','Loop '+chapter.title);
      repeat.onclick=()=>{loop=[chapter.start_sample,chapter.end_sample]; loopText(); selectAudio('master',chapter.start_sample);};
      row.append(seek,repeat); $('chapters').append(row);
    }
    records($('reportList'),snapshot.reports,'Choose an exact machine report'); records($('reviewList'),snapshot.reviews,'Choose an exact owner record');
    $('machineSummary').textContent='No machine report selected.'; $('reportDetail').textContent='No report selected.';
    $('humanSummary').textContent='Unreviewed · no owner record selected.'; $('reviewDetail').textContent='No record selected.';
    $('linkReport').checked=false; $('linkReport').disabled=true; chosenReview=null;
    const draft=drafts.get(draftKey()); $('reviewForm').reset(); discardDraft=false;
    reviewBaseline=JSON.stringify(reviewFields());
    if (draft) {
      $('reviewTarget').value=draft.target; $('decision').value=draft.decision; $('reviewer').value=draft.reviewer; $('reason').value=draft.reason;
      for (const k of Object.keys(findings)) $('finding-'+k).value=draft.findings[k];
    }
    renderSegments(); $('archivePanel').hidden=false; buttons();
  }
  $('discover').onclick=async()=>{
    const ticket=++discoveryTicket; $('discover').disabled=true; status('Discovering archive directories. No inference.');
    try {
      const result=await request('/archives'); if (ticket!==discoveryTicket) return;
      $('archiveList').replaceChildren(...result.archives.map(x=>option(x.key,x.key)));
      if(result.archives.length) $('archiveList').selectedIndex=0;
      $('inspect').disabled=!result.archives.length;
      $('listStatus').textContent=`${result.archives.length} possible archives. ${result.truncated ? 'Discovery limit reached; narrow archive_root.' : 'Not yet audio-verified.'}`;
      $('refusals').textContent=result.refusals.length ? JSON.stringify(result.refusals,null,2) : 'None observed.';
      status('Discovery complete. Select an archive and inspect it.');
    } catch(e) { status(e.message); } finally { if(ticket===discoveryTicket) $('discover').disabled=false; }
  };
  $('inspect').onclick=async()=>{
    if (!$('archiveList').value) return;
    if (!retainDraft()) return; resetPlayer(); $('archivePanel').hidden=true; status('Verifying the retained archive and its actual PCM samples…');
    try {
      const result=await session.open($('archiveList').value);
      if (result) { renderInspection(); status('Archive verified. Playing and reviewing remain separate actions.'); }
    } catch(e) { status(e.message); } finally { buttons(); }
  };
  $('resume').onclick=()=>selectAudio('master',session.current.snapshot.playback.sample);
  $('savePosition').onclick=async()=>{
    if (!playerReady()) { status('Load the selected audio and let seeking finish before saving its position. No save was sent.'); buttons(); return; }
    const rate=Number($('rate').value);
    if (!String($('rate').value).trim() || !Number.isFinite(rate) || rate<.5 || rate>3) {
      status('Choose a playback speed from 0.5 to 3 before saving. No save was sent.'); $('rate').focus(); return;
    }
    const a=session.current.snapshot.archive, segment=a.segments.find(x=>x.id===playerBinding.target);
    const sample=Math.min(a.master.samples,Math.max(0,Math.round($('player').currentTime*48000)+(segment?.start_sample||0)));
    const pending=session.bookmark({sample,rate,loop}); buttons();
    try { const out=await pending; if(out.current) savedText(); status(`Bookmark saved for ${out.key}.${out.current ? '' : ' Inspect that archive again before saving.'}`); }
    catch(e) { status(e.message); } finally { buttons(); }
  };
  $('reportList').onchange=()=>{
    session.clearReport(); $('linkReport').checked=false; $('linkReport').disabled=true;
    $('machineSummary').textContent='No machine report selected.'; $('reportDetail').textContent='No report selected.';
    renderSegments(); buttons();
  };
  $('reviewList').onchange=()=>{
    session.clearReview(); chosenReview=null; $('humanSummary').textContent='Unreviewed · no owner record selected.';
    $('reviewDetail').textContent='No record selected.'; renderSegments(); buttons();
  };
  $('exceptionsOnly').onchange=renderSegments;
  $('loadReport').onclick=async()=>{
    $('linkReport').checked=false; $('linkReport').disabled=true;
    $('machineSummary').textContent='Inspecting the selected machine report…'; $('reportDetail').textContent='No report selected.';
    const pending=session.report($('reportList').value); renderSegments();
    try {
      const report=await pending; if(!report) return;
      const counts={}; for(const t of report.targets) counts[t.transcript_status]=(counts[t.transcript_status]||0)+1;
      $('machineSummary').textContent=Object.entries(counts).map(([key,n])=>`${n} ${key}`).join(' · ')+' · Not listening acceptance.';
      $('reportDetail').textContent=JSON.stringify(report,null,2); $('linkReport').disabled=false; renderSegments();
    } catch(e) { $('machineSummary').textContent=e.message; renderSegments(); }
  };
  $('loadReview').onclick=async()=>{
    chosenReview=null; $('humanSummary').textContent='Inspecting selected owner record…';
    $('reviewDetail').textContent='No record selected.'; renderSegments();
    try {
      const review=await session.savedReview($('reviewList').value); if(!review) return;
      chosenReview=review; $('humanSummary').textContent=`${review.target}: ${review.decision} · ${review.reviewer}`;
      $('reviewDetail').textContent=JSON.stringify(review,null,2); renderSegments();
    } catch(e) { $('humanSummary').textContent=e.message; }
  };
  $('reviewForm').addEventListener('input',()=>{discardDraft=false;});
  $('discardDraft').onclick=()=>{ if(draftKey()) drafts.delete(draftKey()); $('reviewForm').reset(); discardDraft=true; status('Unsaved review draft discarded in this tab. Saved records remain; an in-flight save is not cancelled.'); };
  $('reviewForm').onsubmit=async event=>{
    event.preventDefault(); if(!session.current) return;
    const a=session.current.snapshot.archive, target=$('reviewTarget').value;
    const audio=target==='master' ? a.master.sha256 : a.segments.find(s=>s.id===target)?.audio_sha256;
    const value={target,audio_sha256:audio,decision:$('decision').value,reviewer:$('reviewer').value,reason:$('reason').value,
      findings:Object.fromEntries(Object.keys(findings).map(k=>[k,$('finding-'+k).value])),
      report_sha256:$('linkReport').checked ? session.reportValue?.report_sha256 : null};
    const pending=session.review(value); buttons();
    try {
      const out=await pending;
      if(out.current) {
        const selected=$('reviewList').value;
        records($('reviewList'),session.current.snapshot.reviews,'Choose an exact owner record');
        $('reviewList').value=selected; buttons();
      }
      status(`Listening review saved for ${out.key}: ${out.result.id}. No replacement was started.`);
    } catch(e) { status(e.message); } finally { buttons(); }
  };
  request('/capabilities').then(value=>{
    $('discover').disabled=!value.enabled;
    $('configuration').textContent=value.enabled ? 'Archive access enabled. Discovery and all saves are explicit.'
      : 'Archive access is disabled. Set spoken_briefs.archive_root to an absolute local directory in config/local.json, then restart Studio.';
    status('No archive has been opened. No generation is available on this page.');
  }).catch(e=>{ $('discover').disabled=true; $('configuration').textContent=e.message; status('Archive access unavailable. Other Studio tools are unchanged.'); });
})();
