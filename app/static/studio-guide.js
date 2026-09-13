/* Opt-in coach: explicit GET-only checks, never action dispatch or art approval. */
(function () {
  'use strict';
  const C = window.StudioGuideState, params = new URLSearchParams(location.search), id = params.get('guide');
  if (!C || !id || !/^[a-z-]{1,40}$/.test(id)) return;
  const make = (tag, text, attrs = {}) => { const n = document.createElement(tag); if (text !== null) n.textContent = text; for (const [k,v] of Object.entries(attrs)) n.setAttribute(k,v); return n; };
  const main = document.querySelector('main'); if (!main) return;
  async function read(path, active = new Set()) {
    const controller = new AbortController(); active.add(controller);
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const r = await fetch(path, {method: 'GET', signal: controller.signal});
      const text = await r.text(); if (text.length > 2 * 1024 * 1024) throw Error('Guide evidence exceeds the 2 MiB display limit. Inspect it in its own tool.');
      if (!r.ok) throw Error('Evidence request failed (HTTP ' + r.status + ').');
      return JSON.parse(text);
    } finally { clearTimeout(timeout); active.delete(controller); }
  }
  function mount(data, params) {
    let stopped = false, busy = false, epoch = 0;
    const active = new Set(), get = path => read(path, active);
    const guide = data.guides?.find(g => g.id === id); if (!guide) throw Error('Unknown guided path.');
    let index = guide.steps.findIndex(s => s.id === params.get('stage'));
    if (index < 0) index = Number(params.get('step') || 0);
    if (!Number.isInteger(index) || index < 0 || index >= guide.steps.length) index = 0;
    const step = guide.steps[index], targetURL = C.route(step.route, location.origin);
    const panel = make('section', null, {class:'studio-guide-panel', 'aria-label':'Guided walkthrough'});
    const heading = make('h2', step.title), progress = make('p', `${guide.title} · step ${index + 1} of ${guide.steps.length}`, {class:'studio-guide-progress'});
    const detail = make('p', step.detail), actions = make('div', null, {class:'studio-guide-actions'});
    const evidence = make('p', '', {role:'status', id:'guideEvidence', 'aria-live':'polite'});
    const targetNote = make('small', '', {id:'guideTargetStatus'});
    const run = make('select', null, {id:'guideObservedRun', 'aria-label':'Specific run to inspect'});
    const runLabel = make('label', 'Specific run to inspect (no execution)'); runLabel.append(run);
    run.append(make('option', 'Check this step to load available runs', {value:''}));
    runLabel.hidden = !['output','review'].includes(step.check);
    let stored = {};
    try { stored = JSON.parse(localStorage.getItem('studio.guide.' + id)) || {}; } catch (_) {}
    if (typeof stored.job_id === 'string' && /^[A-Za-z0-9_-]{1,96}$/.test(stored.job_id)) {
      run.append(make('option', 'Retained run ' + stored.job_id, {value:stored.job_id})); run.value = stored.job_id;
    }
    function persist() {
      try { localStorage.setItem('studio.guide.' + id, JSON.stringify({version:2, step:index, stage:step.id, job_id:run.value})); }
      catch (_) { targetNote.textContent += ' Browser resume storage is unavailable.'; }
    }
    const add = (label, fn, key) => { const b = make('button', label, {type:'button'}); if (key) b.id = key; b.onclick = fn; actions.append(b); return b; };
    function cleanup() {
      stopped = true; epoch++; active.forEach(c => c.abort());
      if (highlighted) highlighted.classList.remove('studio-guide-target');
      listeners.forEach(name => document.removeEventListener(name, stale));
      window.removeEventListener('hashchange', stale); window.removeEventListener('popstate', restorePosition);
      panel.remove();
    }
    function showTool(url) {
      if (url.pathname === '/' && url.hash) document.dispatchEvent(new CustomEvent('studio:navigate', {detail:url.hash.slice(1)}));
      else if (url.hash) document.getElementById(url.hash.slice(1))?.scrollIntoView({block:'start'});
    }
    function navigate(url) {
      persist();
      if (url.pathname !== location.pathname) {
        if (confirm('Open another Studio page? Save or export unsaved work first; local files may need reattaching. The guide does not save it for you.')) location.assign(url.pathname + url.search + url.hash);
        return;
      }
      cleanup(); history.pushState(null, '', url.pathname + url.search + url.hash);
      showTool(url);
      if (url.searchParams.get('guide') === id) mount(data, url.searchParams);
    }
    function restorePosition() {
      const url = new URL(location.href); cleanup(); showTool(url);
      if (url.searchParams.get('guide') === id) mount(data, url.searchParams);
    }
    function go(next) {
      const url = C.route(guide.steps[next].route, location.origin);
      url.searchParams.set('guide', id); url.searchParams.set('step', String(next)); url.searchParams.set('stage', guide.steps[next].id);
      navigate(url);
    }
    function correctTool() { return location.pathname === targetURL.pathname && (!targetURL.hash || location.hash === targetURL.hash); }
    let highlighted = null;
    function find(show = false) {
      if (highlighted) highlighted.classList.remove('studio-guide-target'); highlighted = null;
      const target = correctTool() ? C.visibleTarget(step, document) : null;
      targetNote.textContent = target ? 'Target control is available. Show the control moves focus; it does not activate it.'
        : step.target ? 'Target is not visible here. Open this step’s tool, choose a matching recipe or asset, then use Show the control again.'
        : 'This step is reviewed in the tool itself; no single control is highlighted.';
      if (target && show) {
        highlighted = target; target.classList.add('studio-guide-target'); target.scrollIntoView({block:'center', behavior:'auto'});
        if (!target.matches('button,input,select,textarea,a,[tabindex]')) target.setAttribute('tabindex','-1');
        target.focus({preventScroll:true});
      }
    }
    function display(value, timed = false) {
      evidence.dataset.state = value.state;
      const label = {met:'Observed', blocked:'Needs attention', unknown:'Not known', manual:'Your decision'}[value.state] || 'Not known';
      evidence.textContent = label + ': ' + value.message + (timed ? ' Checked at ' + new Date().toLocaleTimeString() + '.' : '');
    }
    function snapshot() {
      const mainPage = !!document.getElementById('createView');
      const p = mainPage && typeof selected !== 'undefined' ? selected : null;
      const roles = mainPage && typeof referenceRecords !== 'undefined' ? referenceRecords : [];
      const reference = mainPage && typeof uploaded !== 'undefined' ? uploaded : null;
      const last = mainPage && typeof lastUploaded !== 'undefined' ? lastUploaded : null;
      const roleCount = p?.reference_slots?.length || 0;
      const files = ['reference','lastReference'].flatMap(id => [...(document.getElementById(id)?.files || [])].map(f => [id,f.name,f.size,f.lastModified]));
      const refs = roleCount ? {attached:roles.length === roleCount && roles.every(r => typeof r.file === 'string' && r.file), missing:roles.some(r => r.missing)}
        : {attached:typeof reference === 'string' && !!reference && (!p?.last_reference || (typeof last === 'string' && !!last)), selected:files.length > 0};
      return {
        recipe:p ? {id:p.id, backend_id:p.backend_id || 'primary'} : null,
        prompt_present:!!document.getElementById('positive')?.value.trim(),
        references:{...refs, supported:!!(roleCount || p?.reference), mask:!!p?.requires_rgba_mask,
          pending:mainPage && typeof referencePending !== 'undefined' ? referencePending > 0 : false},
        switching:mainPage && typeof backendSwitching !== 'undefined' ? backendSwitching : false,
        backend:mainPage && typeof backendActive !== 'undefined' ? backendActive : null,
        authoring:window.WorkflowStudio?.authoringStatus?.() || null,
        project:window.WorkflowProject?.snapshot?.() || null,
        selection:mainPage && typeof assetSelection !== 'undefined' ? assetSelection.size : 0,
        // A local fingerprint only: no prompt or draft is sent or persisted by the coach.
        fields:mainPage ? [...document.querySelectorAll('#createView input,#createView select,#createView textarea')].map(n => [n.id,n.dataset.key,n.value]) : [],
        role_identity:roles.map(r => [r.file,r.sha256,r.role,!!r.missing]), reference_identity:[reference,last,files], job_id:run.value,
        tool:location.pathname + location.hash
      };
    }
    function stale(event) {
      if (event?.target && panel.contains(event.target)) return;
      epoch++; display(C.unknown('The tool or input changed. Check this step again; previous observations are not completion evidence.')); find();
    }
    const listeners = ['input','change','workflow:render','workflow:project'];
    listeners.forEach(name => document.addEventListener(name, stale)); window.addEventListener('hashchange', stale); window.addEventListener('popstate', restorePosition);
    run.onchange = () => { epoch++; persist(); display(C.unknown('Run selection changed. Check this specific run.')); };
    const checkButton = add('Check this step', async () => {
      if (busy || stopped) return; busy = true; checkButton.disabled = true;
      const token = ++epoch, s = snapshot(), fingerprint = JSON.stringify(s);
      try {
        if (!correctTool()) { display(C.unknown('Open this step’s tool before checking its evidence.')); return; }
        display(C.unknown('Checking the selected step; no job is being submitted.'));
        if (step.check === 'readiness' && s.recipe) { s.backend_report = await get('/api/backends'); s.health = await get('/api/health'); }
        if (['output','review'].includes(step.check)) {
          if (!s.job_id) {
            const jobs = await get('/api/jobs');
            if (!Array.isArray(jobs)) throw Error('Run list is unavailable.');
            if (!stopped && token === epoch && JSON.stringify(snapshot()) === fingerprint) {
              run.replaceChildren(make('option',jobs.length > 200 ? 'Choose a run (200 most recent shown)' : 'Choose a specific run',{value:''}));
              for (const j of jobs.slice(0,200)) if (typeof j?.id === 'string' && /^[A-Za-z0-9_-]{1,96}$/.test(j.id))
                run.append(make('option', `${j.preset_name || j.preset_id || 'Run'} · ${j.status} · ${j.id}`, {value:j.id}));
            }
          } else {
            s.job = await get('/api/jobs/' + encodeURIComponent(s.job_id));
            if (step.check === 'review') s.assets = (await get('/api/workspace')).assets;
          }
        }
        if (stopped) return;
        if (token !== epoch || JSON.stringify(snapshot()) !== fingerprint) { display(C.unknown('State changed during the check. Late evidence was discarded; check again.')); return; }
        display(C.evaluate(step.check, s), true); find(); persist();
      } catch (error) { if (!stopped && token === epoch) display(C.unknown(error.message + ' No successful check is inferred.')); }
      finally { busy = false; if (!stopped) checkButton.disabled = false; }
    }, 'checkGuideStep');
    add('Show the control', () => find(true), 'showGuideControl');
    if (index) add('Back', () => go(index - 1));
    add('Open this step’s tool', () => go(index));
    add(index < guide.steps.length - 1 ? 'Next step' : 'Return to guided paths', () => index < guide.steps.length - 1 ? go(index + 1) : navigate(C.route('/workflow-studio.html#journeys', location.origin)));
    add('Pause guide', () => {
      cleanup(); const url = new URL(location.href); ['guide','step','stage'].forEach(k => url.searchParams.delete(k));
      history.replaceState(null, '', url.pathname + url.search + url.hash);
    });
    panel.append(progress,heading,detail,runLabel,evidence,actions,targetNote,
      make('small','Guide position is navigation only. Observed prerequisites, engine results, human review and licensing are separate.'));
    main.prepend(panel); display(step.check === 'manual' ? C.evaluate('manual') : C.unknown()); find(); persist();
  }
  read('/api/workflow-studio/guides').then(data => mount(data, params)).catch(error => {
    main.prepend(make('p', 'Guided walkthrough unavailable: ' + error.message + ' Open Guided workflows to choose a path; the Studio remains usable.', {role:'status'}));
  });
})();
