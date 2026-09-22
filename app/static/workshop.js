/* Create presentation only. Existing controls, drafts and executor retain ownership. */
(function (root, factory) {
  const Context = typeof module === 'object' && module.exports
    ? require('./presentation-context.js') : root?.StudioPresentationContext;
  const api = factory(Context);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (!root?.document || !Context) return;
  root.StudioWorkshop = api;
  const currentRecipe = () => typeof selected === 'undefined' ? null : selected;
  // Presentation consumes the readiness model; it never re-derives one. reference-model.js owns `required`,
  // board cardinality, last_reference and staging (#610 items 1 and 3); references.js owns the Generate gate.
  const projection = () => typeof StudioReferenceModel === 'undefined' ? null : StudioReferenceModel.live(root);
  const start = () => api.mount(root, {
    recipe:currentRecipe,
    backend:() => typeof backendActive !== 'undefined' && backendActive ? String(backendActive) : 'current',
    referenceSlots:() => (projection()?.slots || []).map(slot => ({id:slot.id, role:slot.role, required:slot.required, index:slot.index, staged:slot.staged})),
    references:() => (projection()?.references || []).map(reference => ({...reference})),
    pendingFiles:() => projection()?.pendingFiles || 0,
    hasSources:() => !!projection()?.hasSources
  });
  if (root.document.readyState === 'loading') root.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})(typeof window !== 'undefined' ? window : null, function (Context) {
  'use strict';
  const LEGACY_STORAGE_KEY = 'studio.workshop.presentation.v1';
  const STORAGE_KEY = 'studio.workshop.presentation.v2';
  const LAYOUTS = Object.freeze({focus:'Focus',studio:'Studio',immersive:'Immersive Studio'});
  const SKINS = Object.freeze({atelier:'Atelier',arcade:'Arcade',sakura:'Sakura','retro-anime':'Retro Anime'});
  const AMBIENCES = Object.freeze({none:'None','night-shift':'Night Shift','quiet-morning':'Quiet Morning'});

  function preferences(value) {
    const plain = value && typeof value === 'object' && !Array.isArray(value);
    const own = key => plain && Object.hasOwn(value, key) ? value[key] : null;
    return {
      layout:Object.hasOwn(LAYOUTS, own('layout')) ? own('layout') : 'focus',
      skin:Object.hasOwn(SKINS, own('skin')) ? own('skin') : 'atelier',
      ambience:Object.hasOwn(AMBIENCES, own('ambience')) ? own('ambience') : 'none'
    };
  }
  function parseStored(storage, key) {
    try {
      const raw = storage?.getItem(key);
      if (!raw || raw.length >= 2048) return null;
      const value = JSON.parse(raw);
      return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
    } catch (_) { return null; }
  }
  function readPreferences(storage) {
    try {
      const current = parseStored(storage, STORAGE_KEY);
      if (current) return preferences(current);
      const legacy = parseStored(storage, LEGACY_STORAGE_KEY);
      return preferences(legacy);
    } catch (_) { return preferences(null); }
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
    let initialiseDisclosure = true, persistInitialPresentation = true;
    try {
      const hasCurrentPresentation = !!storage?.getItem(STORAGE_KEY);
      const hasLegacyPresentation = !!storage?.getItem(LEGACY_STORAGE_KEY);
      initialiseDisclosure = !hasCurrentPresentation && !hasLegacyPresentation;
      persistInitialPresentation = !hasCurrentPresentation;
    } catch (_) { /* This tab can still use the workshop. */ }
    // A details toggle is deferred; flush the visible choice before navigation
    // through the existing session-preference owner, not a second settings store.
    w.addEventListener('pagehide', () => {
      const negative = q('#negativeWrap');
      if (negative) w.rememberNegativeCollapse?.(negative.open);
    });
    let state = readPreferences(storage), opener = null, pageScroll = null, scheduled = false, recoveryPending = false;
    let contextRevision = 0, currentView = null, actionAdapter = null;
    const el = (tag, className, text) => {
      const node = d.createElement(tag); if (className) node.className = className;
      if (text !== undefined) node.textContent = text; return node;
    };
    const text = (node, value) => { if (node && node.textContent !== value) node.textContent = value; };
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
    if (!q('#workshopImmersiveStyles')) {
      const css = el('link'); css.id = 'workshopImmersiveStyles'; css.rel = 'stylesheet'; css.href = '/static/workshop-immersive.css'; d.head.append(css);
    }
    create.classList.add('workshop');

    const hero = el('section', 'wk-immersive-hero'); hero.id = 'workshopAmbienceHero';
    const heroCopy = el('div', 'wk-hero-copy');
    heroCopy.append(el('span', 'eyebrow', 'LOCAL / PRIVATE / YOURS'));
    const heroTitle = el('h2', '', 'Turn your ideas into something real.');
    const heroText = el('p', '', 'A calm visual environment around the same working draft.');
    heroCopy.append(heroTitle, heroText);
    const heroArt = el('div', 'wk-hero-art'); heroArt.setAttribute('aria-hidden','true');
    hero.append(heroCopy, heroArt);

    const modebar = el('nav', 'wk-modebar'); modebar.setAttribute('aria-label','Create workspace routes');
    const currentMode = el('button', 'active', 'Generate'); currentMode.type = 'button'; currentMode.setAttribute('aria-current','page');
    currentMode.addEventListener('click', () => q('#positive')?.focus({preventScroll:true}));
    const route = (label, href) => { const link = el('a', '', label); link.href = href; return link; };
    modebar.append(currentMode, route('Guided workflows','/workflow-studio.html'), route('Prompt Lab','/prompt-lab.html'), route('Asset library','/#assets'), route('Runs & review','/#production'));

    const toolbar = el('div', 'wk-toolbar');
    const preferenceNotice = el('p', 'wk-preference-notice'); preferenceNotice.setAttribute('role','status');
    const selectControls = el('div', 'wk-select-controls');
    function persistPresentation() {
      text(preferenceNotice, writePreferences(storage, state) ? '' : 'Appearance applies in this tab; browser storage is unavailable.');
    }
    function updatePreference(key, value) {
      state = preferences({...state, [key]:value});
      applyPresentation(); persistPresentation(); sync();
    }
    function choice(id, label, options, key) {
      const wrap = el('label', 'wk-select-control', label), select = el('select'); select.id = id;
      for (const [value, name] of Object.entries(options)) { const option = el('option', '', name); option.value = value; select.append(option); }
      select.value = state[key]; wrap.append(select); selectControls.append(wrap);
      select.addEventListener('change', () => updatePreference(key, select.value));
      return select;
    }
    const layoutSelect = choice('workshopLayout', 'Layout', LAYOUTS, 'layout');
    const ambienceSelect = choice('workshopAmbience', 'Ambience', AMBIENCES, 'ambience');
    const skinControl = el('div', 'wk-skin-control');
    const skinLabel = el('span', 'wk-control-label', 'Skin');
    const nativeSkinLabel = el('label', 'wk-native-skin-select', 'Skin');
    const skinSelect = el('select'); skinSelect.id = 'workshopSkin'; skinSelect.setAttribute('aria-label','Skin');
    for (const [value, name] of Object.entries(SKINS)) { const option = el('option', '', name); option.value = value; skinSelect.append(option); }
    skinSelect.value = state.skin; nativeSkinLabel.append(skinSelect);
    const skinPicker = el('div', 'wk-skin-picker'); skinPicker.setAttribute('role','group'); skinPicker.setAttribute('aria-label','Visual skin');
    const skinButtons = new Map();
    for (const [value, name] of Object.entries(SKINS)) {
      const skinButton = button('workshopSkinChoice-'+value, name, () => updatePreference('skin', value));
      skinButton.className = 'wk-skin-choice'; skinButton.dataset.workshopSkinChoice = value;
      const swatch = el('span', 'wk-skin-swatch'); swatch.setAttribute('aria-hidden','true');
      skinButton.prepend(swatch); skinPicker.append(skinButton); skinButtons.set(value, skinButton);
    }
    skinSelect.addEventListener('change', () => updatePreference('skin', skinSelect.value));
    skinControl.append(skinLabel, nativeSkinLabel, skinPicker);
    toolbar.append(selectControls, skinControl, preferenceNotice);

    const setupRail = el('aside', 'wk-setup-rail'); setupRail.id = 'workshopSetupRail';
    const setupHeading = el('div', 'wk-rail-heading');
    setupHeading.append(el('span', 'eyebrow', 'RECIPE & READINESS'), el('h2', '', 'Run setup'));
    const recipeChip = el('div', 'wk-recipe');
    const recipeMark = el('span', 'wk-recipe-mark', '✦'); recipeMark.setAttribute('aria-hidden','true');
    const recipeInfo = el('div'); recipeInfo.append(el('small', '', 'ACTIVE RECIPE'));
    const recipeName = el('strong', '', 'Choose a starting point'); recipeName.id = 'workshopRecipeName'; recipeInfo.append(recipeName);
    const change = button('workshopRecipeChange', 'Change recipe', () => openRecipes());
    change.setAttribute('aria-expanded', 'false');
    change.setAttribute('aria-haspopup', 'dialog'); change.setAttribute('aria-controls', 'workshopRecipeDialog');
    recipeChip.append(recipeMark, recipeInfo, change);
    const quickTune = button('workshopTune', 'Fine-tune the recipe', () => reveal(parameters));
    quickTune.className = 'wk-quick-tune'; parameters.id = 'workshopParameters'; quickTune.setAttribute('aria-controls', parameters.id);
    const setupStatus = el('div', 'wk-setup-status');
    const setupReadiness = el('strong', '', 'Checking readiness…'); setupReadiness.id = 'workshopSetupReadiness';
    const setupEta = el('span', '', 'Runtime estimate not available'); setupEta.id = 'workshopSetupEta';
    setupStatus.append(setupReadiness, setupEta);
    setupRail.append(setupHeading, recipeChip, quickTune, setupStatus);
    editor.before(hero, modebar, toolbar, setupRail);

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
    function syncPicker() {
      const open = recipeDialog.open;
      change.setAttribute('aria-expanded', String(open));
      // Native dialog already excludes closed content. Make that state explicit for
      // accessibility inspection and retain it if a future style changes display.
      if (drawer) { drawer.inert = !open; drawer.setAttribute('aria-hidden', String(!open)); }
    }
    syncPicker();
    function openRecipes() {
      if (create.hidden || recipeDialog.open) return;
      // Do not stack our picker above a source, proposal, or other owned modal.
      if (d.querySelector('dialog[open]')) return;
      opener = d.activeElement; pageScroll = {left:w.scrollX, top:w.scrollY};
      if (drawer) drawer.open = true;
      pickerStatus.textContent = '';
      if (drawer) { drawer.inert = false; drawer.removeAttribute('aria-hidden'); }
      recipeDialog.showModal(); syncPicker(); q('#presetSearch')?.focus({preventScroll:true});
    }
    recipeDialog.addEventListener('close', () => {
      // close is deferred: an older event must not make a newly reopened picker inert.
      if (recipeDialog.open) return;
      syncPicker();
      if (!create.hidden) {
        const target = opener?.isConnected && opener.getClientRects().length ? opener : change;
        target.focus({preventScroll:true}); if (pageScroll) w.scrollTo(pageScroll);
      }
      opener = null; pageScroll = null;
    });
    function finishRecipeSelection(target) {
      if (!recipeDialog.open) return;
      // Only a successful handoff calls this. Cancel/refusal keeps the picker.
      // Its deferred close event must restore the destination, not the launcher.
      opener = target; recipeDialog.close();
    }
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
    for (const selector of ['#variants','#recipeWrap']) { const node = q(selector); if (node) parameterExtras.append(node); }
    const variantLabel = q('#recipeWrap');
    if (variantLabel?.firstChild?.nodeType === 3) variantLabel.firstChild.textContent = 'Recipe variants';
    parameters.querySelector('summary').after(parameterExtras);
    parameters.open = false;
    const paramSummary = parameters.querySelector('summary');
    paramSummary.replaceChildren(el('span', '', 'Fine-tune the recipe'));
    const paramHint = el('small', 'wk-parameter-summary'); paramSummary.append(paramHint);
    const promptHint = el('small', 'wk-prompt-hint', 'Describe the result you want. Tune the recipe when you need to.');
    q('#positiveWrap').append(promptHint);
    q('#positive').rows = 5;
    const draftBar = q('#uxDraftBar'), draftButtons = draftBar?.querySelector(':scope > div');
    let draftOptions;
    if (draftButtons) { draftOptions = disclosure('workshopDraftOptions', 'Draft options', [draftButtons]); draftBar.append(draftOptions); }

    const review = disclosure('workshopChecks', 'Readiness & run details', [runBox]);
    const reviewSummary = review.querySelector('summary');
    editor.append(parameters, inspection, review);
    const setupReview = button('workshopSetupReview', 'Review readiness', () => reveal(review));
    setupReview.className = 'wk-setup-review'; setupRail.append(setupReview);
    const dock = el('div', 'wk-run-dock'); dock.setAttribute('aria-label','Generation controls');
    const dockInfo = el('div', 'wk-dock-info'), readiness = el('strong'), eta = el('span');
    readiness.id = 'workshopReadiness'; eta.id = 'workshopEta';
    const reviewButton = button('workshopReview', 'Review checks', () => reveal(review));
    dockInfo.append(readiness, eta, reviewButton);
    const status = q('#status'); dock.append(dockInfo, actions); if (status) dock.append(status); create.append(dock);
    const estimate = q('#timeEstimate'); if (estimate) runBox.append(estimate);
    const runTools = el('div', 'wk-run-tools'); runTools.setAttribute('aria-label', 'Plan and vary this run');
    const compare = q('#planComparison'), newSeed = q('#randomSeed');
    for (const tool of [newSeed, compare]) if (tool) runTools.append(tool);
    actions.after(runTools);
    // Remove only the now-empty legacy caption, not controls injected by another feature.
    const caption = [...editor.children].find(n => n.classList.contains('section-title'));
    if (caption && !caption.querySelector('button,input,select,textarea')) caption.hidden = true;
    const saved = q('#createView .saved');
    const savedDetails = disclosure('workshopSaved', 'Saved setups', [saved]); editor.append(savedDetails);
    const gallery = q('#createView .gallery-panel');
    const problemsHost = el('div'); problemsHost.id = 'jobProblemsHost';
    const results = disclosure('workshopResults', 'Recent runs', [gallery]); results.classList.add('wk-results');
    create.append(problemsHost, results);
    problemsHost.onclick = q('#gallery')?.onclick;
    q('#generate').addEventListener('click', () => { if (!q('#generate').disabled) results.open = true; }, true);

    const guidance = el('aside', 'wk-guidance'); guidance.id = 'workshopGuidance';
    guidance.append(el('span', 'eyebrow', 'ONE NEXT ACTION'));
    const guidanceTitle = el('h2', '', 'Review readiness'); guidanceTitle.id = 'workshopGuidanceTitle';
    const guidanceDescription = el('p', '', 'Use the current readiness evidence before running.'); guidanceDescription.id = 'workshopGuidanceDescription';
    const guidanceAction = button('workshopGuidanceAction', 'Review readiness', () => {
      if (currentView) dispatchIntent(currentView.primaryAction);
    });
    const guidanceWhy = el('details', 'wk-guidance-why'); guidanceWhy.id = 'workshopGuidanceWhy';
    guidanceWhy.append(el('summary', '', 'Why this?'));
    const guidanceReason = el('p', '', 'Based on existing UI observations. No job is submitted.');
    guidanceWhy.append(guidanceReason);
    const guidanceSecondary = el('p', 'wk-guidance-secondary', 'Presentation never changes execution authority.');
    guidance.append(guidanceTitle, guidanceDescription, guidanceAction, guidanceWhy, guidanceSecondary);
    editor.after(guidance);

    function reveal(target) {
      if (!target || create.hidden) return;
      if (setup.contains(target)) openRecipes();
      for (let node = target; node && node !== create; node = node.parentElement) if (node.tagName === 'DETAILS') node.open = true;
      const focus = target.tagName === 'DETAILS' ? target.querySelector('summary') : target;
      focus?.focus({preventScroll:true}); target.scrollIntoView({block:'center', behavior:'instant'});
    }
    function focusExisting(target) {
      if (!target || create.hidden || target.closest('[hidden]')) return false;
      for (let node = target; node && node !== create; node = node.parentElement) if (node.tagName === 'DETAILS') node.open = true;
      target.focus?.({preventScroll:true}); target.scrollIntoView?.({block:'center', behavior:'instant'}); return true;
    }
    function revealSources() {
      // The projection knows which slot is outstanding. Focusing the first file input on the page instead put the
      // cursor on an already-filled board picture when the missing source was the kept image (#610 review).
      const slots = Array.isArray(bridge.referenceSlots?.()) ? bridge.referenceSlots() : [];
      const outstanding = slots.find(slot => slot.required && !slot.staged);
      const named = !outstanding ? null : Number.isInteger(outstanding.index) ? q('[data-ref-file="'+outstanding.index+'"]')
        : q(outstanding.id === 'last-reference' ? '#lastReferenceWrap input[type=file]' : '#referenceWrap input[type=file]');
      const candidates = [
        named, q('#roleReferences input[type=file]'), q('#referenceWrap input[type=file]'), q('#lastReferenceWrap input[type=file]')
      ];
      for (const target of candidates) if (target && !target.closest('[hidden]') && target.getClientRects().length && focusExisting(target)) return;
      const board = q('#roleReferences:not([hidden])') || q('#referenceWrap:not([hidden])') || q('#lastReferenceWrap:not([hidden])');
      if (board) reveal(board);
    }
    function openResults() {
      results.open = true; results.querySelector('summary')?.focus({preventScroll:true}); results.scrollIntoView({block:'center', behavior:'instant'});
    }
    actionAdapter = Context.createActionAdapter({
      workspaceId:'create',
      getContextStamp:() => currentView?.contextStamp || null,
      actions:{
        [Context.ACTIONS.REVIEW_READINESS]:() => reveal(review),
        [Context.ACTIONS.REVIEW_SOURCES]:revealSources,
        [Context.ACTIONS.FOCUS_GENERATE]:() => focusExisting(q('#generate')),
        [Context.ACTIONS.OPEN_RESULTS]:openResults
      }
    });
    function dispatchIntent(intent) { return actionAdapter.dispatch(intent); }
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
        if (label.querySelector('#i2vMode')) continue;
        const key = label.querySelector('[data-key]')?.dataset.key || '';
        const name = ['width','height','frames','fps'].includes(key) ? 'Canvas & duration'
          : key === 'seed' ? 'Seed'
          : ['steps','cfg','sampler','scheduler','denoise'].includes(key) ? 'Sampling' : 'Model & guidance';
        if (!groups.has(name)) { const group = el('fieldset', 'wk-control-group'); group.append(el('legend', '', name)); groups.set(name, group); }
        groups.get(name).append(label);
      }
      for (const name of ['Seed','Canvas & duration','Sampling','Model & guidance']) if (groups.has(name)) controls.append(groups.get(name));
    }
    function applyPresentation() {
      create.dataset.workshopLayout = state.layout;
      create.dataset.workshopAmbience = state.ambience;
      d.body.dataset.workshopSkin = state.skin;
      d.body.dataset.workshopAmbience = state.ambience;
      hero.dataset.ambience = state.ambience;
      hero.hidden = state.ambience === 'none';
      layoutSelect.value = state.layout; ambienceSelect.value = state.ambience; skinSelect.value = state.skin;
      for (const [value, skinButton] of skinButtons) {
        const active = value === state.skin; skinButton.setAttribute('aria-pressed', String(active)); skinButton.classList.toggle('active', active);
      }
      results.open = state.layout === 'studio' || state.layout === 'immersive';
      text(heroTitle, state.ambience === 'quiet-morning' ? 'Make room for the next idea.' : 'Turn your ideas into something real.');
      text(heroText, state.ambience === 'quiet-morning'
        ? 'The same private workspace, with a quieter morning atmosphere.'
        : 'A calm visual environment around the same working draft.');
    }
    function capturePresentationContext(blocked, first, outputs) {
      const recipe = bridge.recipe?.();
      const slots = Array.isArray(bridge.referenceSlots?.()) ? bridge.referenceSlots() : [];
      const refs = Array.isArray(bridge.references?.()) ? bridge.references() : [];
      const pending = Number.isSafeInteger(bridge.pendingFiles?.()) ? bridge.pendingFiles() : 0;
      const backendId = String(bridge.backend?.() || recipe?.backend_id || 'current');
      const revisionIdentity = {
        revision:contextRevision,
        recipeId:recipe?.id || null,
        backendId,
        blocked:!!blocked,
        outputs:Number(outputs) || 0,
        pendingFiles:pending,
        slots:slots.map(slot => [slot.id, slot.required !== false]),
        references:refs.map(reference => [reference.id, reference.slotId, reference.stage])
      };
      const contextStamp = Context.makeContextStamp(revisionIdentity);
      const capability = recipe ? {state:'known', value:{
        recipeId:String(recipe.id || 'selected-recipe'), backendId,
        referenceSlots:slots.map((slot, index) => ({
          id:String(slot.id || 'reference-'+(index+1)), role:String(slot.role || 'Reference '+(index+1)), required:slot.required !== false
        }))
      }} : {state:'unknown', reason:'Choose a recipe before readiness can be interpreted.'};
      const executionState = blocked ? 'blocked' : outputs ? 'completed' : 'ready';
      const execution = {state:'known', observedAt:Date.now(), contextStamp, value:{
        state:executionState, operationId:null,
        blockers:blocked ? [{code:'current-blocker', message:first || 'Review readiness before generating.', target:'readiness'}] : [],
        outputs:Number(outputs) || 0
      }};
      return Context.captureContext({
        workspaceId:'create', contextStamp, taskId:'generate', capability, execution,
        draft:{conflict:false, pendingFiles:pending, references:refs}
      });
    }
    function renderGuidance(blocked, first, outputs) {
      const context = capturePresentationContext(blocked, first, outputs);
      currentView = Context.project(context, {task:'generate', assistance:'studio', ...state});
      const primary = currentView.primaryAction;
      text(guidanceTitle, primary.title);
      text(guidanceDescription, primary.description);
      text(guidanceAction, primary.label);
      guidanceAction.dataset.intent = primary.id;
      text(guidanceReason, primary.reason);
      // A demoted readiness intent still carries the specific blocker in .description; dropping it left the
      // rail with a generic "Resolve the next blocker" while the real message sat only in the dock (#610 item 4).
      const secondary = currentView.secondaryActions.map(action => action.title + ' · ' + action.description).join(' — ');
      text(guidanceSecondary, secondary || 'Presentation never changes execution authority.');
    }
    function sync() {
      const active = !create.hidden;
      d.body.classList.toggle('workshop-active', active);
      if (!active && recipeDialog.open) recipeDialog.close();
      const recipe = bridge.recipe?.();
      syncPicker();
      const name = recipe ? String(recipe.name || recipe.id) : '';
      text(recipeName, name || 'Choose a starting point');
      text(change, name ? 'Change: '+name : 'Choose recipe');
      change.setAttribute('aria-label', name ? 'Change recipe: '+name : 'Choose recipe');
      // One-time presentation migration, after the first real recipe has rendered.
      // Existing negative-wrap toggle handling remains the session preference owner.
      if (recipe && (initialiseDisclosure || persistInitialPresentation)) {
        if (initialiseDisclosure && q('#negativeWrap')) q('#negativeWrap').open = false;
        if (persistInitialPresentation) writePreferences(storage, state);
        initialiseDisclosure = false; persistInitialPresentation = false;
      }
      groupControls();
      const value = key => q('[data-key="'+key+'"]')?.value;
      const dims = [value('width'),value('height')].filter(Boolean).join(' × ');
      const steps = value('steps') ? value('steps')+' steps' : '';
      const seed = value('seed') ? 'Seed '+value('seed') : '';
      if (newSeed) { newSeed.hidden = !q('[data-key=seed]'); newSeed.title = seed ? seed+' · choose a new seed without generating' : 'This recipe has no seed control'; }
      const adapters = [...d.querySelectorAll('#loraSlots .lora-slot')].filter(slot => Number(slot.querySelector('input[data-key]')?.value) > 0).length;
      const summary = [dims, steps, adapters ? adapters+' active adapter'+(adapters === 1 ? '' : 's') : 'No active adapters'].filter(Boolean).join(' · ');
      text(paramHint, [summary, seed].filter(Boolean).join(' · '));
      text(quickTune, summary+'   ·   Tune settings ↗');
      const blocked = q('#generate').disabled, first = q('#uxBlockers .ux-blocker p')?.textContent;
      const readinessText = blocked ? first || 'Review readiness before generating.' : 'No blockers reported';
      text(readiness, readinessText); text(setupReadiness, readinessText);
      const time = q('#estimateValue')?.textContent;
      const etaText = estimate && !estimate.hidden && time ? 'Expected: '+time : 'Runtime estimate not available';
      text(eta, etaText); text(setupEta, etaText);
      text(reviewSummary, blocked ? 'Readiness & run details · needs attention' : 'Readiness & run details');
      const pending = ['uxRestoreDraft','uxKeepDraft'].some(id => q('#'+id) && !q('#'+id).hidden);
      if (draftOptions && pending && !recoveryPending) draftOptions.open = true;
      recoveryPending = pending;
      const outputs = q('#gallery')?.querySelectorAll('.imageCard').length || 0;
      text(results.querySelector('summary'), 'Recent runs'+(outputs ? ' · '+outputs+' output'+(outputs === 1 ? '' : 's') : ''));
      renderGuidance(blocked, first, outputs);
    }
    const schedule = () => {
      contextRevision++;
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
    create.__workshop = {
      reveal, sync, openRecipes, finishRecipeSelection, preferences:()=>({...state}),
      presentationView:() => currentView,
      dispatchIntent
    };
    applyPresentation(); sync();
    // A recipe-goal deep link is an explicit request to open discovery.
    if (new w.URLSearchParams(w.location.search).has('recipe_goal')) openRecipes();
    return create.__workshop;
  }
  return {LEGACY_STORAGE_KEY, STORAGE_KEY, LAYOUTS, SKINS, AMBIENCES, preferences, readPreferences, writePreferences, mount};
});
