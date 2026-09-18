/* Create presentation only. Existing controls, drafts and executor retain ownership. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (!root?.document) return;
  root.StudioWorkshop = api;
  const start = () => api.mount(root, {
    recipe: () => typeof selected === 'undefined' ? null : selected,
    hasSources: () => (typeof uploaded !== 'undefined' && !!uploaded)
      || (typeof lastUploaded !== 'undefined' && !!lastUploaded)
      || (typeof parentAssets !== 'undefined' && parentAssets.length > 0)
      || (typeof referenceRecords !== 'undefined' && referenceRecords.some(r => r.file))
  });
  if (root.document.readyState === 'loading') root.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';
  const STORAGE_KEY = 'studio.workshop.presentation.v1';
  const LAYOUTS = Object.freeze({focus:'Focus'});
  const SKINS = Object.freeze({atelier:'Atelier'});
  function preferences(value) {
    const plain = value && typeof value === 'object' && !Array.isArray(value);
    const own = key => plain && Object.hasOwn(value, key) ? value[key] : null;
    return {layout:Object.hasOwn(LAYOUTS, own('layout')) ? own('layout') : 'focus',
      skin:Object.hasOwn(SKINS, own('skin')) ? own('skin') : 'atelier'};
  }
  function readPreferences(storage) {
    try { const raw = storage?.getItem(STORAGE_KEY); return preferences(raw && raw.length < 2048 ? JSON.parse(raw) : null); }
    catch (_) { return preferences(null); }
  }
  function writePreferences(storage, value) {
    try { if (!storage) return false; storage.setItem(STORAGE_KEY, JSON.stringify(preferences(value))); return true; }
    catch (_) { return false; }
  }
  function mount(w, bridge = {}) {
    const d = w.document, q = selector => d.querySelector(selector), create = q('#createView');
    if (!create || create.__workshop) return create?.__workshop || null;
    const editor = q('#createView .editor'), setup = q('#createView .setup');
    const parameters = q('.ux-parameters'), runBox = q('.ux-run-box'), actions = q('#generate')?.closest('.actions');
    // Progressive enhancement must leave the older UI intact if its contract isn't present.
    if (!editor || !setup || !parameters || !runBox || !actions || !q('#positive') || !q('#presetList')) return null;
    let storage;
    try { storage = w.localStorage; } catch (_) { storage = null; }
    let initialiseDisclosure = true;
    try { initialiseDisclosure = !storage?.getItem(STORAGE_KEY); } catch (_) { /* This tab can still use the workshop. */ }
    let state = readPreferences(storage), opener = null, pageScroll = null, scheduled = false, recoveryPending = false;
    const el = (tag, className, text) => {
      const node = d.createElement(tag); if (className) node.className = className;
      if (text !== undefined) node.textContent = text; return node;
    };
    const text = (node, value) => { if (node.textContent !== value) node.textContent = value; };
    const button = (id, label, callback) => {
      const node = el('button', '', label); node.id = id; node.type = 'button';
      node.addEventListener('click', callback); return node;
    };
    const disclosure = (id, label, nodes) => {
      const node = el('details', 'wk-disclosure'); node.id = id;
      node.append(el('summary', '', label)); nodes.filter(Boolean).forEach(n => node.append(n)); return node;
    };
    if (!q('#workshopStyles')) {
      const css = el('link'); css.id = 'workshopStyles'; css.rel = 'stylesheet'; css.href = '/static/workshop.css'; d.head.append(css);
    }
    create.classList.add('workshop');
    const toolbar = el('div', 'wk-toolbar');
    const recipeChip = el('div', 'wk-recipe');
    const recipeMark = el('span', 'wk-recipe-mark', '✦'); recipeMark.setAttribute('aria-hidden','true');
    const recipeInfo = el('div'); recipeInfo.append(el('small', '', 'ACTIVE RECIPE'));
    const recipeName = el('strong', '', 'Choose a starting point'); recipeName.id = 'workshopRecipeName'; recipeInfo.append(recipeName);
    const change = button('workshopRecipeChange', 'Change recipe', () => openRecipes());
    change.setAttribute('aria-haspopup', 'dialog'); change.setAttribute('aria-controls', 'workshopRecipeDialog');
    recipeChip.append(recipeMark, recipeInfo, change);
    const presentation = el('div', 'wk-presentation');
    function choice(id, label, options, key) {
      const wrap = el('label', '', label), select = el('select'); select.id = id;
      for (const [value, name] of Object.entries(options)) { const option = el('option', '', name); option.value = value; select.append(option); }
      select.value = state[key]; wrap.append(select); presentation.append(wrap);
      select.addEventListener('change', () => { state = preferences({...state, [key]:select.value}); applyPresentation();
        text(preferenceNotice, writePreferences(storage, state) ? '' : 'Appearance applies in this tab; browser storage is unavailable.'); });
    }
    choice('workshopLayout', 'Layout', LAYOUTS, 'layout'); choice('workshopSkin', 'Skin', SKINS, 'skin');
    const preferenceNotice = el('p', 'wk-preference-notice'); preferenceNotice.setAttribute('role','status');
    const quickTune = button('workshopTune', 'Fine-tune the recipe', () => reveal(parameters));
    quickTune.className = 'wk-quick-tune'; parameters.id = 'workshopParameters';
    quickTune.setAttribute('aria-controls', parameters.id);
    toolbar.append(recipeChip, presentation, quickTune, preferenceNotice); editor.before(toolbar);

    // One native modal around the current picker. Its search, shortlist and handlers are unchanged.
    const recipeDialog = el('dialog', 'wk-recipe-dialog'); recipeDialog.id = 'workshopRecipeDialog';
    recipeDialog.setAttribute('aria-labelledby','workshopRecipeTitle');
    const dialogHeading = el('div', 'wk-dialog-heading');
    const titleBlock = el('div'); titleBlock.append(el('span', 'eyebrow', 'A STARTING POINT, NOT A COMMITMENT'));
    const title = el('h2', '', 'Find your recipe'); title.id = 'workshopRecipeTitle';
    titleBlock.append(title, el('p', 'muted', 'Search the library. Your current draft stays put until you choose.'));
    const close = button('workshopRecipeClose', 'Close', () => recipeDialog.close());
    dialogHeading.append(titleBlock, close);
    const pickerStatus = el('p', 'wk-picker-status'); pickerStatus.setAttribute('role','status');
    recipeDialog.append(dialogHeading, pickerStatus, setup); create.append(recipeDialog);
    const drawer = setup.querySelector('.ux-recipe-drawer'); if (drawer) drawer.open = true;
    function openRecipes() {
      if (create.hidden || recipeDialog.open) return;
      // Do not stack our picker above a source, proposal, or other owned modal.
      if (d.querySelector('dialog[open]')) return;
      opener = d.activeElement; pageScroll = {left:w.scrollX, top:w.scrollY};
      if (drawer) drawer.open = true;
      pickerStatus.textContent = '';
      recipeDialog.showModal(); change.setAttribute('aria-expanded','true'); q('#presetSearch')?.focus({preventScroll:true});
    }
    recipeDialog.addEventListener('close', () => {
      change.setAttribute('aria-expanded','false');
      if (!create.hidden) {
        const target = opener?.isConnected && opener.getClientRects().length ? opener : change;
        target.focus({preventScroll:true}); if (pageScroll) w.scrollTo(pageScroll);
      }
      opener = null; pageScroll = null;
    });
    recipeDialog.addEventListener('keydown', e => {
      if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey && !e.target.closest('input,textarea,select,[contenteditable]')) {
        e.preventDefault(); q('#presetSearch')?.focus();
      }
    });
    function hasEdits() {
      const recipe = bridge.recipe?.();
      if (!recipe) return false;
      if (q('#positive').value !== String(recipe.defaults?.positive || '')
          || (q('#negative')?.value || '') !== String(recipe.defaults?.negative || '') || bridge.hasSources?.()) return true;
      for (const input of [...editor.querySelectorAll('input,select,textarea'), ...actions.querySelectorAll('input,select')]) {
        if (input.type === 'file') { if (input.files?.length) return true; continue; }
        if (input.closest('#uxDraftBar') || input.id === 'positive' || input.id === 'negative') continue;
        if (input.type === 'checkbox' || input.type === 'radio') { if (input.checked !== input.defaultChecked) return true; continue; }
        const key = input.dataset.key;
        // Legacy renderSelected assigns .value, not a value attribute. Compare bound
        // controls to catalogue graph defaults, not the empty HTML defaultValue.
        const initial = key && Object.hasOwn(recipe.defaults || {}, key) ? String(recipe.defaults[key] ?? '')
          : input.tagName === 'SELECT' ? [...input.options].find(o => o.defaultSelected)?.value ?? input.options[0]?.value : input.defaultValue;
        if (initial !== undefined && input.value !== initial) return true;
      }
      return false;
    }
    const pickerChoices = new WeakMap();
    setup.addEventListener('click', e => {
      const item = e.target.closest('#presetList button[data-id]');
      if (!item) return;
      if (item.dataset.id === bridge.recipe?.()?.id) {
        e.preventDefault(); e.stopImmediatePropagation(); recipeDialog.close(); return;
      }
      if (hasEdits() && !w.confirm('Use this recipe instead? It replaces the current wording, settings and source bindings. Cancel keeps your current work unchanged.')) {
        e.preventDefault(); e.stopImmediatePropagation(); return;
      }
      pickerChoices.set(e, item.dataset.id);
    }, true);
    // Bubble after the legacy list handler. A capture-phase microtask runs too early
    // in native click dispatch; keep the choice even if renderPresets detached its button.
    setup.addEventListener('click', e => {
      const id = pickerChoices.get(e);
      if (id && bridge.recipe?.()?.id === id) { recipeDialog.close(); sync(); }
      else if (id) text(pickerStatus, q('#status')?.textContent || 'This recipe could not be selected. Your current work is unchanged.');
    });
    // Existing readiness and shortlist actions focus controls inside the moved picker.
    d.addEventListener('click', e => { if (e.target.closest('[data-ux-resolve="recipes"]')) openRecipes(); }, true);
    for (const name of ['studio:shortlist-source','studio:shortlist-sources']) d.addEventListener(name, openRecipes, true);

    // Keep the actual full recipe, generated graph and provenance available, not above the prompt.
    const inspection = disclosure('workshopInspect', 'Recipe details & under the hood', []);
    for (const selector of ['#selectedPreset','#pipeline','#recipeNotesHelp','#recipeNotes','.dependencies','#nodeList','#graphPreview','.advanced']) {
      const node = q(selector); if (!node || inspection.contains(node)) continue;
      const owner = selector === '#nodeList' || selector === '#graphPreview' ? node.closest('details') || node : node;
      if (!inspection.contains(owner)) inspection.append(owner);
    }
    inspection.querySelectorAll('details').forEach(n => { n.open = false; });
    const parameterExtras = el('div', 'wk-parameter-extras');
    for (const selector of ['#variants','#recipeWrap','#randomSeed']) { const node = q(selector); if (node) parameterExtras.append(node); }
    parameters.querySelector('summary').after(parameterExtras);
    parameters.open = false;
    const paramSummary = parameters.querySelector('summary');
    paramSummary.replaceChildren(el('span', '', 'Fine-tune the recipe'));
    const paramHint = el('small', 'wk-parameter-summary'); paramSummary.append(paramHint);
    // Remove only the now-empty legacy caption, not controls injected by another feature.
    const caption = [...editor.children].find(n => n.classList.contains('section-title'));
    if (caption && !caption.querySelector('button,input,select,textarea')) caption.hidden = true;
    const promptHint = el('small', 'wk-prompt-hint', 'Describe the result you want. Tune the recipe when you need to.');
    q('#positiveWrap').append(promptHint);
    q('#positive').rows = 5;
    const draftBar = q('#uxDraftBar'), draftButtons = draftBar?.querySelector(':scope > div');
    let draftOptions;
    if (draftButtons) { draftOptions = disclosure('workshopDraftOptions', 'Draft options', [draftButtons]); draftBar.append(draftOptions); }

    const review = disclosure('workshopChecks', 'Readiness & run details', [runBox]);
    const reviewSummary = review.querySelector('summary');
    editor.append(parameters, inspection, review);
    const dock = el('div', 'wk-run-dock'); dock.setAttribute('aria-label','Generation controls');
    const dockInfo = el('div', 'wk-dock-info'), readiness = el('strong'), eta = el('span');
    readiness.id = 'workshopReadiness'; eta.id = 'workshopEta';
    const reviewButton = button('workshopReview', 'Review checks', () => reveal(review));
    dockInfo.append(readiness, eta, reviewButton);
    const status = q('#status'); dock.append(dockInfo, actions); if (status) dock.append(status); create.append(dock);
    const estimate = q('#timeEstimate'); if (estimate) runBox.append(estimate);
    const compare = q('#planComparison'); if (compare) runBox.append(compare);
    const saved = q('#createView .saved');
    const savedDetails = disclosure('workshopSaved', 'Saved setups', [saved]); editor.append(savedDetails);
    const gallery = q('#createView .gallery-panel');
    const results = disclosure('workshopResults', 'Recent runs', [gallery]); results.classList.add('wk-results'); create.append(results);
    q('#generate').addEventListener('click', () => { if (!q('#generate').disabled) results.open = true; }, true);
    function reveal(target) {
      if (!target || create.hidden) return;
      if (setup.contains(target)) openRecipes();
      for (let node = target; node && node !== create; node = node.parentElement) if (node.tagName === 'DETAILS') node.open = true;
      const focus = target.tagName === 'DETAILS' ? target.querySelector('summary') : target;
      focus?.focus({preventScroll:true}); target.scrollIntoView({block:'center', behavior:'instant'});
    }
    // Only one secondary workbench disclosure at a time. Negative prompt and required sources are independent.
    for (const panel of [parameters, inspection, review, savedDetails]) panel.addEventListener('toggle', () => {
      if (panel === parameters) quickTune.setAttribute('aria-expanded', String(parameters.open));
      if (panel.open) for (const other of [parameters, inspection, review, savedDetails]) if (other !== panel) other.open = false;
    });
    function groupControls() {
      const controls = q('#controls'); if (!controls) return;
      const labels = [...controls.children].filter(n => n.tagName === 'LABEL'); if (!labels.length) return;
      const groups = new Map();
      for (const label of labels) {
        const key = label.querySelector('[data-key]')?.dataset.key || '';
        const name = ['width','height','frames','fps'].includes(key) ? 'Canvas & duration'
          : key === 'seed' ? 'Seed'
          : ['steps','cfg','sampler','scheduler','denoise'].includes(key) ? 'Sampling' : 'Model & guidance';
        if (!groups.has(name)) { const group = el('fieldset', 'wk-control-group'); group.append(el('legend', '', name)); groups.set(name, group); }
        groups.get(name).append(label);
      }
      for (const name of ['Canvas & duration','Sampling','Seed','Model & guidance']) if (groups.has(name)) controls.append(groups.get(name));
    }
    function applyPresentation() {
      create.dataset.workshopLayout = state.layout; d.body.dataset.workshopSkin = state.skin;
      results.open = state.layout === 'studio';
    }
    function sync() {
      const active = !create.hidden;
      d.body.classList.toggle('workshop-active', active);
      if (!active && recipeDialog.open) recipeDialog.close();
      const recipe = bridge.recipe?.();
      text(recipeName, recipe?.name || q('#uxRecipeLabel')?.textContent || 'Choose a starting point');
      // One-time presentation migration, after the first real recipe has rendered.
      // Existing negative-wrap toggle handling remains the session preference owner.
      if (initialiseDisclosure && recipe) {
        initialiseDisclosure = false; if (q('#negativeWrap')) q('#negativeWrap').open = false;
        writePreferences(storage, state);
      }
      groupControls();
      const value = key => q('[data-key="'+key+'"]')?.value;
      const dims = [value('width'),value('height')].filter(Boolean).join(' × ');
      const steps = value('steps') ? value('steps')+' steps' : '';
      const seed = value('seed') ? 'Seed '+value('seed') : '';
      const adapters = [...d.querySelectorAll('#loraSlots .lora-slot')].filter(slot => Number(slot.querySelector('input[data-key]')?.value) > 0).length;
      const summary = [dims, steps, adapters ? adapters+' active adapter'+(adapters === 1 ? '' : 's') : 'No active adapters'].filter(Boolean).join(' · ');
      text(paramHint, [summary, seed].filter(Boolean).join(' · '));
      text(quickTune, summary+'   ·   Tune settings ↗');
      const blocked = q('#generate').disabled, first = q('#uxBlockers .ux-blocker p')?.textContent;
      text(readiness, blocked ? first || 'Review readiness before generating.' : 'No blockers reported');
      const time = q('#estimateValue')?.textContent;
      text(eta, estimate && !estimate.hidden && time ? 'Expected: '+time : 'Runtime estimate not available');
      text(reviewSummary, blocked ? 'Readiness & run details · needs attention' : 'Readiness & run details');
      const pending = ['uxRestoreDraft','uxKeepDraft'].some(id => q('#'+id) && !q('#'+id).hidden);
      if (draftOptions && pending && !recoveryPending) draftOptions.open = true;
      recoveryPending = pending;
      const outputs = q('#gallery')?.querySelectorAll('.imageCard').length || 0;
      text(results.querySelector('summary'), 'Recent runs'+(outputs ? ' · '+outputs+' output'+(outputs === 1 ? '' : 's') : ''));
    }
    const schedule = () => {
      if (scheduled) return; scheduled = true;
      w.queueMicrotask(() => { scheduled = false; sync(); });
    };
    d.addEventListener('studio:recipe', schedule);
    create.addEventListener('input', schedule); create.addEventListener('change', schedule);
    const observer = new w.MutationObserver(schedule);
    for (const id of ['selectedPreset','controls','loraSlots','gallery','uxBlockers','estimateValue','uxDraftStatus']) {
      const node = q('#'+id); if (node) observer.observe(node, {childList:true,subtree:true,characterData:true});
    }
    observer.observe(create, {attributes:true, attributeFilter:['hidden']});
    observer.observe(q('#generate'), {attributes:true, attributeFilter:['disabled']});
    if (estimate) observer.observe(estimate, {attributes:true, attributeFilter:['hidden']});
    const resize = typeof w.ResizeObserver === 'function' ? new w.ResizeObserver(() => {
      if (create.hidden) return;
      d.body.style.setProperty('--workshop-dock-space', Math.ceil(dock.getBoundingClientRect().height + 24)+'px');
    }) : null;
    resize?.observe(dock);
    create.__workshop = {reveal, sync, openRecipes};
    applyPresentation(); sync(); return create.__workshop;
  }
  return {STORAGE_KEY, LAYOUTS, SKINS, preferences, readPreferences, writePreferences, mount};
});
