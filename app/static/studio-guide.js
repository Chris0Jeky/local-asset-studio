/* Opt-in coach: explicit GET-only checks, never action dispatch or art approval. */
(function () {
  'use strict';
  const C = window.StudioGuideState, params = new URLSearchParams(location.search), id = params.get('guide');
  if (!C || !id || !/^[a-z-]{1,40}$/.test(id)) return;
  const AUTO_DELAY = 600, PRESET_ID = /^[A-Za-z0-9_-]{1,64}$/;
  const DOTS = {met:'●', blocked:'▲', unknown:'○', manual:'◆'};
  const FOOTER = 'The guide checks readiness; it never generates, approves art or clears licences.';
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
    let stopped = false, busy = false, epoch = 0, autoTimer = null, shown = false, lastState = 'unknown';
    const active = new Set(), get = path => read(path, active);
    const guide = data.guides?.find(g => g.id === id); if (!guide) throw Error('Unknown guided path.');
    let index = guide.steps.findIndex(s => s.id === params.get('stage'));
    if (index < 0) index = Number(params.get('step') || 0);
    if (!Number.isInteger(index) || index < 0 || index >= guide.steps.length) index = 0;
    const step = guide.steps[index], targetURL = C.route(step.route, location.origin);
    const recipeStep = ['recipe','reference_recipe'].includes(step.check) && Array.isArray(guide.recommended) && guide.recommended.some(x => typeof x === 'string' && PRESET_ID.test(x));
    const panel = make('section', null, {class:'studio-guide-panel', 'aria-label':'Guided walkthrough'});
    const heading = make('h2', step.title), progress = make('p', `${guide.title} · step ${index + 1} of ${guide.steps.length}`, {class:'studio-guide-progress'});
    const detail = make('p', step.detail), actions = make('div', null, {class:'studio-guide-actions'});
    const stepList = make('ol', null, {class:'studio-guide-steps', 'aria-label':'Steps in this guided path'});
    const evidence = make('p', '', {role:'status', id:'guideEvidence', 'aria-live':'polite'});
    const targetNote = make('small', '', {id:'guideTargetStatus'});
    const run = make('select', null, {id:'guideObservedRun', 'aria-label':'Specific run to inspect'});
    const runLabel = make('label', 'Specific run to inspect (no execution)'); runLabel.append(run);
    run.append(make('option', 'Loading available runs', {value:''}));
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
      stopped = true; epoch++; clearTimeout(autoTimer); autoTimer = null; active.forEach(c => c.abort());
      if (highlighted) highlighted.classList.remove('studio-guide-target');
      listeners.forEach(name => document.removeEventListener(name, stale));
      window.removeEventListener('hashchange', toolChanged); window.removeEventListener('popstate', restorePosition);
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
    function renderSteps() {
      stepList.replaceChildren(...guide.steps.map((item, i) => {
        const li = make('li', null, {}), button = make('button', null, {type:'button', 'aria-label':'Step ' + (i + 1) + ': ' + item.title});
        const mark = make('span', i === index ? (DOTS[lastState] || DOTS.unknown) : String(i + 1), {class:'studio-guide-dot'});
        if (i === index) { mark.dataset.state = lastState; li.setAttribute('aria-current', 'step'); }
        button.append(mark, make('span', item.title, {class:'studio-guide-steplabel'}));
        button.onclick = () => { if (i !== index) go(i); };
        li.append(button); return li;
      }));
    }
    function correctTool() { return location.pathname === targetURL.pathname && (!targetURL.hash || location.hash === targetURL.hash); }
    let highlighted = null;
    function find(show = false) {
      if (highlighted) highlighted.classList.remove('studio-guide-target'); highlighted = null;
      const reveal = show || !shown;
      const target = correctTool() ? (reveal ? C.visibleTarget(step, document) : C.peekTarget(step, document)) : null;
      targetNote.textContent = target ? 'Target control is available. Show the control opens collapsed panels and moves focus; it never activates the control.'
        : step.target ? 'Target is not visible here. Show the control can open collapsed panels; choose a matching recipe or asset if it stays unavailable.'
        : 'Reviewed in the tool itself; no single control is highlighted.';
      if (recipeButton) recipeButton.textContent = 'Choose ' + recommendedPreset().name;
      if (!target) return;
      // Reveal once per stage. Later observations respect the user's disclosure and focus choices.
      shown = true; highlighted = target; target.classList.add('studio-guide-target');
      if (!reveal) return;
      target.scrollIntoView({block:'center', behavior:'auto'});
      const idle = show || !document.activeElement || document.activeElement === document.body || panel.contains(document.activeElement);
      // An automatic reveal never focuses an action control: a Space or Enter meant for scrolling
      // must not press Generate, Save or Prepare. Only the explicit Show the control button may.
      if (idle && (show || !target.matches('button,a,[type=submit],input[type=file]'))) {
        if (!target.matches('button,input,select,textarea,a,[tabindex]')) target.setAttribute('tabindex','-1');
        target.focus({preventScroll:true});
      }
    }
    function recommendedPreset() {
      const ids = (guide.recommended || []).filter(x => typeof x === 'string' && PRESET_ID.test(x));
      const list = typeof catalog !== 'undefined' && Array.isArray(catalog?.presets) ? catalog.presets : [];
      for (const value of ids) { const found = list.find(p => p?.id === value); if (found) return {id:value, name:String(found.name || value)}; }
      return {id:ids[0], name:ids[0]};
    }
    // Selection reuses the recipe list's own handler; it never prepares or submits a run.
    function chooseRecipe() {
      const pick = recommendedPreset(); if (!pick.id) return;
      if (typeof selectPreset === 'function') {
        const current = typeof selected !== 'undefined' ? selected : null;
        if (current?.id === pick.id) { targetNote.textContent = pick.name + ' is already selected in Create. Nothing was generated.'; return; }
        const drafted = !!document.getElementById('positive')?.value.trim() || !!document.querySelector('#roleReferences input[type=file], #reference')?.files?.length;
        if (drafted && !confirm('Choosing ' + pick.name + ' resets the prompt, references and variation count in Create. Continue?')) { targetNote.textContent = 'Kept your current draft. Choose the recipe from the list when ready.'; return; }
        try { selectPreset(pick.id); targetNote.textContent = 'Selected ' + pick.name + ' through the Create recipe list. Nothing was generated.'; return; }
        catch (error) { targetNote.textContent = error.message + ' The guide changed nothing.'; return; }
      }
      const search = document.getElementById('presetSearch');
      if (!search) { targetNote.textContent = 'The recipe picker is not on this page. Open Create, then choose ' + pick.name + '.'; return; }
      search.value = pick.name; search.dispatchEvent(new Event('input', {bubbles:true}));
      targetNote.textContent = 'Filtered the recipe list to ' + pick.name + '. Click it to select it.';
      document.getElementById('presetList')?.focus?.();
    }
    function display(value, timed = false) {
      evidence.dataset.state = lastState = value.state;
      const label = {met:'Observed', blocked:'Needs attention', unknown:'Not known', manual:'Your decision'}[value.state] || 'Not known';
      evidence.textContent = label + ': ' + value.message + (timed ? ' Checked at ' + new Date().toLocaleTimeString() + '.' : '');
      renderSteps();
    }
    function snapshot() {
      const mainPage = !!document.getElementById('createView');
      const p = mainPage && typeof selected !== 'undefined' ? selected : null;
      const roles = mainPage && typeof referenceRecords !== 'undefined' ? referenceRecords : [];
      const reference = mainPage && typeof uploaded !== 'undefined' ? uploaded : null;
      const last = mainPage && typeof lastUploaded !== 'undefined' ? lastUploaded : null;
      const roleCount = p?.reference_slots?.length || 0;
      const files = ['reference','lastReference'].flatMap(id => [...(document.getElementById(id)?.files || [])].map(f => [id,f.name,f.size,f.lastModified]));
      const refs = roleCount ? C.referenceSlots(p, roles)
        : {attached:typeof reference === 'string' && !!reference && (!p?.last_reference || (typeof last === 'string' && !!last)), selected:files.length > 0};
      return {
        recipe:p ? {id:p.id, backend_id:p.backend_id || 'primary', runtime_block:p.runtime_block || null} : null,
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
    // Observation is automatic and debounced; it stays GET-only and discards late evidence.
    function schedule(delay = AUTO_DELAY) { clearTimeout(autoTimer); if (stopped) return; autoTimer = setTimeout(() => { autoTimer = null; runCheck(); }, delay); }
    function stale(event) {
      if (event?.target && panel.contains(event.target)) return;
      epoch++; display(C.unknown('The tool or input changed. Rechecking current evidence.')); find(); schedule();
    }
    async function runCheck() {
      if (stopped) return;
      if (step.check === 'manual') { display(C.evaluate('manual')); find(); return; }
      if (busy) { schedule(); return; }
      busy = true; clearTimeout(autoTimer); autoTimer = null; checkButton.disabled = true;
      const token = ++epoch, s = snapshot(), fingerprint = JSON.stringify(s);
      try {
        if (!correctTool()) { display(C.unknown('Open this step’s tool before its evidence can be read.')); return; }
        if (step.check === 'readiness' && s.recipe) { s.backend_report = await get('/api/backends'); s.health = await get('/api/health'); }
        if (['output','review'].includes(step.check)) {
          if (!s.job_id) {
            const jobs = await get('/api/jobs');
            if (!Array.isArray(jobs)) throw Error('Run list is unavailable.');
            if (!stopped && token === epoch && document.activeElement !== run && JSON.stringify(snapshot()) === fingerprint) {
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
    }
    // History traversal emits popstate before hashchange. The restored mount
    // already belongs to the destination; its paired hash event is not an edit.
    let observedTool = location.pathname + location.hash;
    function toolChanged() {
      const tool = location.pathname + location.hash;
      if (tool === observedTool) return;
      observedTool = tool; stale();
    }
    // Clicks cover button-driven state (Select visible, Clear selection, reference removal) that fires no input event.
    const listeners = ['input','change','click','studio:recipe','workflow:render','workflow:project'];
    listeners.forEach(name => document.addEventListener(name, stale)); window.addEventListener('hashchange', toolChanged); window.addEventListener('popstate', restorePosition);
    run.onchange = () => { epoch++; persist(); display(C.unknown('Run selection changed. Reading that run.')); schedule(); };
    const checkButton = add('Re-check', () => runCheck(), 'checkGuideStep');
    add('Show the control', () => find(true), 'showGuideControl');
    const recipeButton = recipeStep ? add('Choose recipe', chooseRecipe, 'chooseGuideRecipe') : null;
    if (index) add('Back', () => go(index - 1));
    if (!correctTool()) add('Open this step’s tool', () => go(index));
    add(index < guide.steps.length - 1 ? 'Next step' : 'Return to guided paths', () => index < guide.steps.length - 1 ? go(index + 1) : navigate(C.route('/workflow-studio.html#journeys', location.origin)));
    add('Pause guide', () => {
      cleanup(); const url = new URL(location.href); ['guide','step','stage'].forEach(k => url.searchParams.delete(k));
      history.replaceState(null, '', url.pathname + url.search + url.hash);
    });
    panel.append(progress,heading,detail,stepList,runLabel,evidence,actions,targetNote,make('small',FOOTER));
    main.prepend(panel);
    display(step.check === 'manual' ? C.evaluate('manual') : C.unknown('Reading current evidence.')); find(); persist(); runCheck();
  }
  read('/api/workflow-studio/guides').then(data => mount(data, params)).catch(error => {
    main.prepend(make('p', 'Guided walkthrough unavailable: ' + error.message + ' Open Guided workflows to choose a path; the Studio remains usable.', {role:'status'}));
  });
})();
