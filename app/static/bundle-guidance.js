/* Scoped explanations over the existing catalog and KB. The server owns policy. */
import '/static/bundle-guidance-client.js';
const C=globalThis.BundleGuidanceClient;
const kinds={creator_documentation:'Upstream documentation',local_observation:'Historical local observation',controlled_experiment:'Controlled experiment',authored_hypothesis:'Authored starting point'};
function el(tag,text,attrs={}){const node=document.createElement(tag);if(text!==null)node.textContent=text;for(const [key,value]of Object.entries(attrs))node.setAttribute(key,value);return node;}
function describe(band){return band?.values?band.values.join(' / '):band?.range?band.range.join('–'):'not recorded';}
function sourceLink(url){try{const value=new URL(url);if(value.protocol!=='https:'||value.username||value.password)return null;return el('a','Read source ↗',{href:value.href,target:'_blank',rel:'noreferrer noopener'});}catch{return null;}}

export function mount(host,capture){
  const style=document.querySelector('link[data-bundle-guidance]')||el('link',null,{rel:'stylesheet',href:'/static/bundle-guidance.css','data-bundle-guidance':''});if(!style.isConnected)document.head.append(style);
  host.className='bundle-guidance';host.setAttribute('aria-label','Guidance for this exact draft');
  const heading=el('h4','Why these settings?'),intro=el('p','Advice for the resources and values in this draft. No setting is changed automatically.');
  const status=el('p','Inspecting the recipe…',{role:'status','aria-live':'polite'}),body=el('div',null,{class:'bundle-guidance-results'}),refresh=el('button','Recheck guidance',{type:'button'});
  host.replaceChildren(heading,intro,status,body,refresh);
  const latest=new C.Latest();let timer=null,controller=null,last='',lastReport=null;
  const live=()=>host.isConnected&&!latest.closed;
  function show(report){
    lastReport=report;body.replaceChildren();const applicable=report.claims.filter(c=>c.applicability==='applies');
    const outside=applicable.reduce((n,c)=>n+c.checks.filter(x=>x.assessment==='outside').length,0);
    status.textContent=report.conflicts.length?`${report.conflicts.length} conflicting setting(s). No recommendation was chosen for you.`:outside?`${outside} value(s) outside recorded recommendations. Review the source conditions.`:applicable.length?`${applicable.length} scoped record(s). Matching advice is not a quality or runtime guarantee.`:'No applicable scoped guidance. Existing family notes remain available below.';
    for(const conflict of report.conflicts)body.append(el('p','Sources disagree for '+conflict.target+': '+conflict.claims.join(', ')+'. Review both; do not average them.',{class:'bundle-guidance-warning'}));
    for(const claim of report.claims){
      const details=el('details',null);details.open=claim.applicability==='applies'&&claim.checks.some(x=>x.assessment==='outside');
      const state=claim.applicability==='applies'?'Applies to catalog pins':claim.applicability==='unknown'?'Scope unknown':'Not applicable';
      details.append(el('summary',claim.title+' · '+state));
      details.append(el('p',(kinds[claim.source.kind]||'Unclassified source')+' · '+(claim.source.retrieved_at?'retrieved '+claim.source.retrieved_at:'retrieval date unrecorded')+(claim.review_due?' · review due':''),{class:'bundle-guidance-meta'}));
      if(claim.source.revision)details.append(el('p','Source revision: '+claim.source.revision,{class:'bundle-guidance-meta'}));
      else details.append(el('p','Source revision not pinned; retained retrieval date is not an immutable snapshot.',{class:'bundle-guidance-meta'}));
      details.append(el('p',claim.rationale));for(const reason of claim.reasons)details.append(el('p',reason,{class:'bundle-guidance-warning'}));
      for(const check of claim.checks){
        const row=el('div',null,{class:'bundle-guidance-setting'}),label=check.control?(globalThis.StudioBundles?.controlLabel(check.control)||check.control):check.key;
        row.append(el('b',label+' · current '+String(check.current)),el('small','Input '+check.key));
        if(check.recommended)row.append(el('span','Recommended: '+describe(check.recommended)));
        if(check.tested)row.append(el('span','Observed/tested: '+describe(check.tested)+' · not a recommendation'));
        if(claim.applicability==='applies'&&check.assessment==='outside')row.append(el('strong','Outside this source’s recommendation',{class:'bundle-guidance-warning'}));
        if(check.control){const jump=el('button','Find control',{type:'button'});jump.onclick=()=>{const field=host.closest('#bundleBody')?.querySelector('[data-bundle-control="'+CSS.escape(check.control)+'"]');if(field){field.scrollIntoView({block:'center'});field.focus();}else status.textContent='This control is visible in the existing Create workbench after applying the reviewed bundle.';};row.append(jump);}
        details.append(row);
      }
      const link=sourceLink(claim.source.url);if(link)details.append(link);details.append(el('p',claim.source.locator,{class:'bundle-guidance-meta'}));body.append(details);
    }
    if(report.uncovered_resources.length){const missing=el('details',null);missing.append(el('summary',report.uncovered_resources.length+' resource(s) without applicable scoped advice'));for(const file of report.uncovered_resources)missing.append(el('p',file));body.append(missing);}
    for(const diagnostic of report.diagnostics)body.append(el('p','Guidance data needs review: '+diagnostic,{class:'bundle-guidance-warning'}));
    body.append(el('p',report.notice,{class:'bundle-guidance-meta'}));
    const download=el('button','Download explanation',{type:'button'});download.onclick=()=>{if(!lastReport)return;const blob=new Blob([JSON.stringify(lastReport,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a',null,{href:url,download:'bundle-guidance.json'});a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};body.append(download);
  }
  async function load(value,ticket){
    if(!live())return;controller=new AbortController();const own=controller,deadline=setTimeout(()=>own.abort(),10000);host.setAttribute('aria-busy','true');
    try{
      const response=await fetch(C.PATH,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value),signal:own.signal});
      const raw=await response.text();if(raw.length>2097152)throw Error('Guidance response exceeds the display limit.');const data=JSON.parse(raw);
      if(!response.ok)throw Error(data.error||'Guidance is unavailable.');C.validate(data,value.preset_id);
      if(!live()||!latest.accepts(ticket,C.payload(capture())))return;show(data);
    }catch(error){
      if(!live()||ticket.epoch!==latest.epoch)return;body.replaceChildren();lastReport=null;status.textContent=error.name==='AbortError'?'Guidance check timed out. Use Recheck guidance; your settings are unchanged.':error.message;
    }finally{clearTimeout(deadline);if(live()&&ticket.epoch===latest.epoch)host.removeAttribute('aria-busy');}
  }
  function update(force=false){
    if(!live())return;let value;
    try{value=C.payload(capture());}catch(error){latest.invalidate();last='';clearTimeout(timer);controller?.abort();host.removeAttribute('aria-busy');body.replaceChildren();lastReport=null;status.textContent=error.message;return;}
    const key=JSON.stringify(value);if(!force&&key===last)return;last=key;clearTimeout(timer);controller?.abort();body.replaceChildren();lastReport=null;status.textContent='Checking the current draft…';
    const ticket=latest.begin(value);timer=setTimeout(()=>load(value,ticket),200);
  }
  function destroy(){latest.close();clearTimeout(timer);controller?.abort();}
  refresh.onclick=()=>update(true);update();return{update,destroy};
}
