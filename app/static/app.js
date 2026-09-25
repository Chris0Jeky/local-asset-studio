const $ = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const safeUrl = url => { try { const u = new URL(url); return ['http:','https:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };
const gib = n => (Number(n || 0) / 1024 ** 3).toFixed(2) + ' GiB';
const loraSlotKeys = ['lora','lora2','lora3','lora4','lora5','lora6'];
const loraNameKey = key => key + '_name';
const controlKeys = ['seed','steps','cfg','width','height','denoise','lora','lora2','lora3','lora4','lora5','lora6','lora_name','lora2_name','lora3_name','lora4_name','lora5_name','lora6_name','frames','fps','style_weight','pose_strength','depth_cut','sampler','scheduler'];
let catalog, selected, online = null, schemaAvailable = false, workerAlive = true, healthError = false, missingByPreset = {}, jobs = [], pinned = [], uploaded = null, lastUploaded = null, library, mode = 'all', submitting = false, view = 'create', jobsSignature = '', jobsDataSignature = '', activeJobId = null, readPoller = null;
let recipeTemplateHash = null, parentAssets = [], parentByInput = {}, serverSetups = [], knowledge = null, atelierRecipes = [], installedLoras = [];
let continuationState = null, continuationSource = null;
let estimateTimer = null, estimateAbort = null, estimateKey = '', estimateResultKey = '';
async function api(path, options={}) { const r = await fetch(path, options); const data = await r.json(); if (!r.ok) {const error=Error(data.error || 'Request failed');error.status=r.status;error.data=data;throw error;} return data; }
const post = (path, data) => api(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const getControl = key => document.querySelector('[data-key="' + key + '"]');
// Notification only: programmatic recipe changes do not emit DOM input/change.
function recipeChanged() { document.dispatchEvent?.(new Event('studio:recipe')); }
function i2vModeBlocker() {
  const mode = selected?.i2v_modes?.find(spec => spec.id === $('#i2vMode')?.value);
  const capacity = selected?.wan_decode_capacity;
  // Older catalogue responses retain their authored holds. No family/filename guessing.
  if (!capacity) return mode?.execution_block || null;
  const unknown = 'Wan decode readiness is unavailable. Reload the recipe before generating.';
  const limits = capacity.limits, keys = ['width','height','length','batch_size'];
  if (capacity.version !== 1 || !limits || !Array.isArray(capacity.latents) || !capacity.latents.length
      || !['max_side','max_pixels','max_frames','batch_size'].every(k => Number.isSafeInteger(limits[k]) && limits[k] > 0)) return unknown;
  for (const latent of capacity.latents) {
    if (!latent?.shape || !Array.isArray(latent.bindings)) return unknown;
    const shape = {...latent.shape};
    for (const binding of latent.bindings) {
      if (!binding || !['frames','width','height'].includes(binding.control) || !keys.includes(binding.input)) return unknown;
      let value = getControl(binding.control)?.value;
      // values() omits an empty control; prepare then uses the mode, or the graph literal.
      if (value === '' || value == null) value = mode?.controls?.[binding.control];
      if (value != null) shape[binding.input] = (typeof value === 'number' || typeof value === 'string') ? Number(value) : NaN;
    }
    if (!keys.every(k => Number.isSafeInteger(shape[k]) && shape[k] > 0)) return unknown;
    const {width, height, length: frames, batch_size: batch} = shape;
    if (Math.max(width,height) > limits.max_side || width*height > limits.max_pixels || frames > limits.max_frames || batch !== limits.batch_size)
      return `Held: ordinary Wan decode is unproven for ${width}x${height}, ${frames} frames, latent batch ${batch}. Use at most ${limits.max_side}px per side, ${limits.max_pixels} pixels, ${limits.max_frames} frames and latent batch ${limits.batch_size}. Quick diagnostic, Balanced or Short motion study provide smaller starting points. This is a capacity check, not a quality guarantee.`;
  }
  return null;
}
function applyI2VMode(id, notify=true) {
  const spec = selected?.i2v_modes?.find(mode => mode.id === id);
  if (!spec) return;
  Object.entries(spec.controls || {}).forEach(([key, value]) => {
    const input = key === 'positive' ? $('#positive') : key === 'negative' ? $('#negative') : getControl(key);
    if (input) input.value = value;
  });
  const modeInput = $('#i2vMode'); if (modeInput) modeInput.value = id;
  const note = $('#i2vModeNote'); if (note) note.textContent = [spec.execution_block, spec.description, spec.warning].filter(Boolean).join(' ');
  updateLoraHints(); updateReady(); scheduleTimeEstimate();
  if (notify) recipeChanged();
  if (notify) message(spec.name + ' loaded. Review the settings before generating.' + (spec.warning ? ' ' + spec.warning : ''));
}
function message(text, error=false) { $('#status').textContent = text; $('#status').classList.toggle('error', error); }
function durationLabel(value) {
  const seconds = Math.max(0, Number(value) || 0);
  if (seconds < 60) return Math.max(1, Math.round(seconds)) + ' s';
  const minutes = seconds / 60;
  if (minutes < 60) return (minutes < 10 ? minutes.toFixed(1) : Math.round(minutes)) + ' min';
  const hours = minutes / 60;
  return (hours < 10 ? hours.toFixed(1) : Math.round(hours * 10) / 10) + ' h';
}
function estimateReferenceCount() {
  const attached = typeof attachedReferencePayload === 'function' ? attachedReferencePayload().filter(r => r && r.file && !r.missing).length : 0;
  const fileInputs = ['#reference', '#lastReference'].reduce((count, id) => count + ($('#' + id.slice(1))?.files?.length ? 1 : 0), 0);
  return Math.max(attached, fileInputs, (uploaded ? 1 : 0) + (lastUploaded ? 1 : 0));
}
function renderTimeEstimate(data, key) {
  if (key !== estimateKey || !$('#timeEstimate')) return;
  const box = $('#timeEstimate'), value = $('#estimateValue'), range = $('#estimateRange'), basis = $('#estimateBasis');
  if (!data?.available) {
    value.textContent = 'Unavailable'; range.textContent = data?.reason || 'Choose a supported recipe to estimate it.'; basis.textContent = '';
    box.hidden = false; return;
  }
  const confidence = {high:'high confidence',medium:'medium confidence',low:'low confidence',none:'no history yet'}[data.confidence] || 'provisional';
  value.textContent = durationLabel(data.estimate_seconds);
  range.textContent = 'Typical range: ' + durationLabel(data.range_seconds?.[0]) + '–' + durationLabel(data.range_seconds?.[1]) + ' · ' + confidence;
  basis.textContent = (data.basis || []).join(' · ') + '. Queue wait is not included; the estimate learns from completed local ComfyUI runs.';
  box.hidden = false; estimateResultKey = key;
}
function scheduleTimeEstimate() {
  const box = $('#timeEstimate'); if (!box || !selected) return;
  const payload = {preset_id:selected.id, controls:values(), batch_count:Number($('#batch')?.value || 1), reference_count:estimateReferenceCount()};
  const key = JSON.stringify(payload);
  if (key === estimateKey && (estimateTimer || estimateAbort || estimateResultKey === key)) return;
  estimateKey = key; estimateResultKey = '';
  if (estimateTimer) { clearTimeout(estimateTimer); estimateTimer = null; }
  if (estimateAbort) { estimateAbort.abort(); estimateAbort = null; }
  box.hidden = false; $('#estimateValue').textContent = 'Calculating…'; $('#estimateRange').textContent = 'Matching this workflow against completed local runs…'; $('#estimateBasis').textContent = '';
  if (typeof setTimeout !== 'function') return;
  estimateTimer = setTimeout(async () => {
    estimateTimer = null; const controller = new AbortController(); estimateAbort = controller;
    try { renderTimeEstimate(await api('/api/estimate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal}), key); }
    catch (error) { if (error.name !== 'AbortError' && key === estimateKey) { $('#estimateValue').textContent = 'Unavailable'; $('#estimateRange').textContent = 'The local timing history could not be read.'; $('#estimateBasis').textContent = error.message; } }
    finally { if (estimateAbort === controller) estimateAbort = null; }
  }, 180);
}
const referenceHint = () => selected?.requires_rgba_mask ? 'Required: upload a real RGBA PNG; retain the image RGB, make the repair region transparent, and use width and height divisible by 8.' : (selected?.reference_hint || "PNG, JPG or WebP · up to 20 MiB. The recipe's example is used until replaced.");
function clearReference() { uploaded = lastUploaded = null; parentAssets=[]; parentByInput={}; if(typeof resetReferenceSlots==='function')resetReferenceSlots(); $('#reference').value = ''; $('#lastReference').value = ''; $('#referenceHint').textContent = referenceHint(); }
// Lineage is attributed per attachment point. A slot-less input and a board's distinct lastReference
// source record their claim in parentByInput; a role slot records it on its reference record (parent_asset, supplied by
// /api/assets/reference). A parent survives while any attachment point still claims it, and a parent
// with no attribution anywhere - a job-exported recipe, a production branch - is never dropped by an
// edit: only the point that changed may release what that point claimed.
function parentClaimed(id) { const attached=typeof attachedReferencePayload==='function'?attachedReferencePayload():[]; return Object.values(parentByInput).includes(id)||attached.some(r=>r.file&&!r.missing&&r.parent_asset===id); }
function releaseParentAsset(id) { if(id&&!parentClaimed(id))parentAssets=parentAssets.filter(p=>p!==id); }
function releaseInputParent(input) { if(!(input in parentByInput))return; const id=parentByInput[input]; delete parentByInput[input]; releaseParentAsset(id); }
function claimInputParent(input, id) { releaseInputParent(input); if(!id)return; if(!selected?.reference_slots?.length||input==='lastReference')parentByInput[input]=id; if(!parentAssets.includes(id))parentAssets=[...parentAssets,id]; }
// Pulling a saved source into one attachment point replaces whatever that point held before.
function replaceParentAsset(input, previous, id) { releaseParentAsset(previous); claimInputParent(input, id); }
// A handoff declares the whole lineage: this run descends from one source, on one input.
function setHandoffParent(input, id) { parentAssets=[]; parentByInput={}; claimInputParent(input, id); }
function renderPresets() {
  if (!catalog) return;
  const query = $('#presetSearch').value.toLowerCase(), category = $('#categorySelect').value;
  const list = catalog.presets.filter(p => (mode === 'all' || (p.modality || 'image') === mode) && (category === 'All' || p.category === category) && [p.name,p.family,p.description,p.category].join(' ').toLowerCase().includes(query));
  $('#filteredCount').textContent = list.length;
  $('#presetList').innerHTML = list.map(p => '<button class="preset ' + (selected?.id === p.id ? 'chosen' : '') + '" data-id="' + esc(p.id) + '"><b>' + esc(p.name) + '</b><span>' + esc(p.description) + '</span><div class="recipe-meta"><span>' + esc(p.family || p.category) + '</span><em class="badge ' + (p.verified ? 'tested' : '') + '">' + (p.verified ? 'Run recorded · review separate' : 'Experimental · review separate') + '</em></div></button>').join('') || '<p class="muted">No recipes match. Try another collection or search.</p>';
}
function updateReady() {
  const missing = missingByPreset[selected?.id] || [];
  const modeBlock = i2vModeBlocker();
  const mode = selected?.i2v_modes?.find(spec => spec.id === $('#i2vMode')?.value), note = $('#i2vModeNote');
  if (note && mode) note.textContent = [modeBlock, mode.description, mode.warning].filter(Boolean).join(' ');
  $('#generate').disabled = submitting || (typeof backendSwitching !== 'undefined' && backendSwitching) || !online || !workerAlive || !schemaAvailable || !selected || !!selected.runtime_block || !!modeBlock || missing.length > 0 || (typeof referencesReady==='function'&&!referencesReady()) || continuationBlockers().length > 0;
  $('#health').textContent = online === null ? healthError ? 'Readiness unavailable' : 'Checking ComfyUI…' : !workerAlive ? 'Studio worker unavailable' : !online ? 'ComfyUI offline' : !schemaAvailable ? 'Checking node readiness' : missing.length ? 'Recipe needs models' : 'ComfyUI connected';
  $('#health').className = 'pill ' + (online && workerAlive && schemaAvailable && !missing.length ? 'ready' : online === null && !healthError ? '' : 'offline');
  scheduleTimeEstimate();
}
const activeLoraSlots = () => loraSlotKeys.filter(k => selected && (selected[loraNameKey(k)] || selected.bindings_extra?.[loraNameKey(k)]));
const loraEntry = name => (name && knowledge?.loras?.[name]) || null;
function renderLoraSlots() {
  const slots = activeLoraSlots(), box = $('#loraSlots');
  box.hidden = !slots.length;
  if (!slots.length) { box.innerHTML = ''; return; }
  const missing = selected.missing_loras || [];
  box.innerHTML = '<div class="section-title"><h3>Adapter stack</h3><small>Strength 0 turns a slot off and removes it from the submitted graph</small></div>'
    + (missing.length ? '<p class="lora-missing">Authored adapters not installed: ' + esc(missing.join(', ')) + '</p>' : '')
    + slots.map((key,index) => {
      const nameKey = loraNameKey(key), authored = selected.defaults?.[nameKey] || '';
      const options = selected.choices?.[nameKey]?.length ? selected.choices[nameKey] : installedLoras;
      const list = !options.length ? (authored ? [authored] : []) : authored && !options.includes(authored) ? [authored, ...options] : options;
      return '<div class="lora-slot"><label class="lora-file"><span>Slot ' + (index + 1) + '</span><select data-key="' + nameKey + '">' + (list.length ? '' : '<option value="">No installed adapter found</option>') + list.map(v => '<option' + (v === authored ? ' selected' : '') + '>' + esc(v) + '</option>').join('') + '</select></label>'
        + '<label class="lora-strength"><span>Strength</span><input data-key="' + key + '" type="number" min="0" max="2" step="0.05"></label>'
        + '<small class="lora-hint" data-hint="' + esc(key) + '"></small></div>';
    }).join('');
}
function updateLoraHints() {
  activeLoraSlots().forEach(key => {
    const hint = document.querySelector('[data-hint="' + key + '"]'); if (!hint) return;
    const entry = loraEntry(getControl(loraNameKey(key))?.value);
    hint.textContent = !entry ? '' : entry.trigger ? 'Trigger: ' + entry.trigger + (entry.trigger_position && entry.trigger_position !== 'none' ? ' · place it at the ' + entry.trigger_position + ' of the prompt' : '') : (entry.label || 'No trigger word');
  });
}
function familyRecipes() { return atelierRecipes.filter(r => r.preset_id === selected?.id); }
function renderRecipeChoices() {
  const list = familyRecipes();
  $('#recipeWrap').hidden = !list.length;
  $('#recipeSelect').innerHTML = '<option value="">Recipe defaults</option>' + list.map((r,i) => '<option value="' + i + '">' + esc(r.name) + (r.available === false ? ' · missing adapters' : '') + '</option>').join('');
  $('#recipeNotes').innerHTML = '';
}
function describeRecipe(recipe) {
  return '<p><b>' + esc(recipe.name) + '</b> · ' + (recipe.status === 'executed' ? 'Generated locally; inspect separately' : 'Settings recorded, not executed here') + '</p>'
    + (recipe.notes ? '<p>' + esc(recipe.notes) + '</p>' : '')
    + (recipe.missing?.length ? '<p class="lora-missing">Not installed: ' + esc(recipe.missing.join(', ')) + '</p>' : '')
    + (recipe.evidence?.prompt_id ? '<small>ComfyUI prompt ' + esc(recipe.evidence.prompt_id) + (recipe.evidence.seconds ? ' · ' + esc(recipe.evidence.seconds) + ' s' : '') + '</small>' : '')
    + (recipe.sources || []).map(u => ' <small><a href="' + esc(safeUrl(u)) + '" target="_blank" rel="noreferrer">Source ↗</a></small>').join('');
}
function applyRecipe(recipe) {
  if (!recipe) return;
  if (recipe.preset_id !== selected?.id) {
    if (!catalog.presets.some(p => p.id === recipe.preset_id)) throw Error('This recipe needs a preset that is not in the library');
    selectPreset(recipe.preset_id);
  }
  const modeSpec=selected.i2v_modes?.find(mode=>mode.id===recipe.controls?.mode);
  if(modeSpec)applyI2VMode(modeSpec.id,false);
  const overrides={...(modeSpec?.controls||{}),...(recipe.controls||{})};
  const controls=continuationState?StudioContinuation.settings(selected,overrides,values()):overrides;
  Object.entries(controls).forEach(([k,v]) => { if(k==='mode')return;const el = k === 'positive' ? $('#positive') : k === 'negative' ? $('#negative') : getControl(k); if (el) el.value = v; });
  $('#batch').value = recipe.batch_count || 1; updateLoraHints(); updateReady();
  const index = familyRecipes().findIndex(r => r.id === recipe.id); if (index >= 0) $('#recipeSelect').value = String(index);
  $('#recipeNotes').innerHTML = describeRecipe(recipe) + (continuationState ? '<p>Only the setup changed. Your source and wording are retained; the recorded execution used the original example, not this image.</p>' : '');
  message(recipe.name + ' loaded. Review the settings before generating.' + (recipe.missing?.length ? ' Some adapters are not installed.' : ''));
  scheduleTimeEstimate(); recipeChanged();
}
async function loadAtelier() {
  // /api/options also warms the server's node schema, so the catalog's own
  // per-preset choices fill in on the next poll; until then this is the list.
  try { installedLoras = (await api('/api/options')).loras || []; } catch (e) { installedLoras = []; }
  try { knowledge = await api('/api/knowledge'); } catch (e) { knowledge = null; }
  try { atelierRecipes = (await api('/api/recipes')).recipes || []; } catch (e) { atelierRecipes = []; }
}
const NEGATIVE_COLLAPSE_KEY = 'studio-negative-collapsed';
function negativeCollapsed() { try { return sessionStorage.getItem(NEGATIVE_COLLAPSE_KEY) === '1'; } catch (e) { return false; } }
function rememberNegativeCollapse(open) { try { sessionStorage.setItem(NEGATIVE_COLLAPSE_KEY, open ? '0' : '1'); } catch (e) {} }
$('#negativeWrap')?.addEventListener('toggle', () => rememberNegativeCollapse($('#negativeWrap').open));
// A long recipe description is a research report above step 01: the card shows its first sentence and what the recipe
// asks you to type; the measurements and the licence paragraph stay one disclosure away (#422 slice A).
function insertWildcard(name) {
  const field = $('#positive'); if (!field || field.hidden) return;
  const token = '__' + name + '__';
  const start = field.selectionStart ?? field.value.length, end = field.selectionEnd ?? start;
  const before = field.value.slice(0, start), after = field.value.slice(end);
  const padLeft = before && !/\s$/.test(before) ? ' ' : '';
  const padRight = after && !/^\s/.test(after) ? ' ' : '';
  field.value = before + padLeft + token + padRight + after;
  const cursor = (before + padLeft + token).length;
  field.focus(); field.setSelectionRange(cursor, cursor);
  field.dispatchEvent(new Event('input', {bubbles: true}));
  if (typeof updateReady === 'function') updateReady();
}
function renderWildcardChips() {
  const host = $('#wildcardChips'); if (!host) return;
  const list = catalog?.wildcards || [];
  if (!selected?.positive || !list.length) { host.hidden = true; host.innerHTML = ''; return; }
  host.hidden = false;
  host.innerHTML = '<p class="muted">Insert a wildcard. Server expands __name__ from presets/wildcards at Generate, one line per batch member.</p>'
    + list.map(item => '<button type="button" data-wildcard="' + esc(item.name) + '" title="' + esc(item.count) + ' options">' + esc(item.name) + '</button>').join('');
}
function renderNsfwIntel() {
  const box = $('#nsfwIntel'), body = $('#nsfwIntelBody');
  if (!box || !body) return;
  const lab = knowledge?.nsfw_lab;
  const family = selected?.family || '';
  const entry = lab?.families?.[family];
  if (!selected?.positive || !lab || !entry) { box.hidden = true; body.innerHTML = ''; return; }
  box.hidden = false;
  const wild = (lab.wildcards || []).map(w => '<li><code>__' + esc(w.name) + '__</code> — ' + esc(w.use) + '</li>').join('');
  body.innerHTML = '<p class="muted">' + esc(lab.caveat || '') + '</p>'
    + '<p><b>Undress</b> ' + esc(entry.undress || '') + '</p>'
    + '<p><b>Finish</b> ' + esc(entry.attractive || '') + '</p>'
    + '<p><b>Watch</b> ' + esc(entry.avoid || '') + '</p>'
    + (wild ? '<ul>' + wild + '</ul>' : '')
    + (lab.gallery ? '<p><a href="' + esc(lab.gallery) + '">Open the lab collection</a></p>' : '');
}
function recipeCard(preset) {
  const description = String(preset.description || ''), note = String(preset.commercial_note || '');
  const cut = description.length > 260 ? description.search(/\.\s(?=[A-Z])/) : -1;
  if (cut < 40) return '<p>' + esc(description) + '</p><small>' + esc(note) + '</small>';
  const fills = typeof StudioContinuation !== 'undefined' ? StudioContinuation.fills(preset, preset.continuation_prompt) : [];
  const typing = fills.length ? '<p class="recipe-typing">You fill in: ' + esc(fills.map(f => f.label.toLowerCase()).join(' · ')) + '.</p>' : '';
  return '<p>' + esc(description.slice(0, cut + 1)) + '</p>' + typing + '<details class="create-context-help recipe-more"><summary>More about this recipe</summary><p>' + esc(description.slice(cut + 1).trim()) + '</p><small>' + esc(note) + '</small></details>';
}
function renderSelected() {
  if (!selected) return;
  $('#selectedPreset').innerHTML = '<span class="badge">' + esc(selected.family || selected.category) + '</span> <span class="badge ' + (selected.verified ? 'tested' : '') + '">' + (selected.verified ? 'Run recorded · review separate' : 'Experimental · review separate') + '</span><h2>' + esc(selected.name) + '</h2>' + recipeCard(selected);
  $('#positiveWrap').hidden = !selected.positive;
  $('#positive').value = selected.defaults?.positive || ''; $('#negative').value = selected.defaults?.negative || ''; $('#negativeWrap').hidden = !selected.negative;
  renderWildcardChips();
  renderNsfwIntel();
  // What to avoid is part of the brief, not an advanced setting: open it whenever the recipe binds it,
  // and keep it collapsible. A manual collapse is remembered for this tab only (#278 friction 3).
  if (selected.negative) $('#negativeWrap').open = !negativeCollapsed();
  $('#pipeline').innerHTML = (selected.stages || ['Load model','Conditioning','Sample','Decode','Save output']).map(s => '<span>' + esc(s) + '</span>').join('');
  const variants = selected.variants || [{name:'3-seed audition',batch_count:3}];
  $('#variants').innerHTML = variants.map((v,i) => '<button data-variant="' + i + '"><b>' + esc(v.name) + '</b>' + (selected.reference && typeof StudioContinuation !== 'undefined' ? '<small>' + esc(StudioContinuation.variantHelp(selected,v)) + '</small>' : '') + '</button>').join('');
  const i2vModeControl = selected.i2v_modes?.length ? '<label>I2V mode<select id="i2vMode" data-key="mode">' + selected.i2v_modes.map(spec => '<option value="' + esc(spec.id) + '">' + esc(spec.name || spec.id) + '</option>').join('') + '</select><small id="i2vModeNote"></small></label>' : '';
  const specs = [['seed','Seed','number','min="0" max="9007199254740991" step="1"'],['steps','Steps','number','min="1" max="150"'],['cfg','Guidance (CFG)','number','min="0" max="30" step="0.1"'],['width','Width','number','min="64" max="' + ((selected.dimension_limits || [])[1] || 1536) + '" step="' + (selected.dimension_multiple || 8) + '"'],['height','Height','number','min="64" max="' + ((selected.dimension_limits || [])[1] || 1536) + '" step="' + (selected.dimension_multiple || 8) + '"'],['denoise','Denoise','number','min="0" max="1" step="0.01"'],['style_weight','Style weight','number','min="0" max="2" step="0.05"'],['pose_strength','Pose strength','number','min="0" max="2" step="0.05"'],['depth_cut','Cut the depth map below (% of its height; 100 = keep all)','number','min="0" max="100" step="1"'],['lora','LoRA strength','number','min="0" max="2" step="0.05"'],['lora2','LoRA 2 strength','number','min="0" max="2" step="0.05"'],['lora3','LoRA 3 strength','number','min="0" max="2" step="0.05"'],['lora4','LoRA 4 strength','number','min="0" max="2" step="0.05"'],['lora5','LoRA 5 strength','number','min="0" max="2" step="0.05"'],['lora6','LoRA 6 strength','number','min="0" max="2" step="0.05"'],['frames','Frames','number','min="5" max="365" step="' + (selected.frame_grid || 1) + '"'],['fps','Frames per second','number','min="1" max="60" step="1"'],['sampler','Sampler','select',''],['scheduler','Schedule','select','']];
  const inStack = new Set(activeLoraSlots().flatMap(k => [k, loraNameKey(k)]));
  $('#controls').innerHTML = i2vModeControl + specs.filter(([k]) => (selected[k] || selected.bindings_extra?.[k]) && !inStack.has(k)).map(([key,label,type,attrs]) => {
    if(['width','height'].includes(key)&&selected.dimension_limits)attrs='min="'+selected.dimension_limits[0]+'" max="'+selected.dimension_limits[1]+'" step="'+(selected.dimension_multiple||8)+'"';
    if (type === 'select') return '<label>' + label + '<select data-key="' + key + '">' + (selected.choices?.[key] || []).map(v => '<option>' + esc(v) + '</option>').join('') + '</select></label>';
    if (key === 'lora' && typeof selected.defaults?.lora === 'string') { type='text'; attrs=''; label='LoRA filename'; }
    return '<label>' + label + '<input data-key="' + key + '" type="' + type + '" ' + attrs + '>' + (key === 'frames' ? '<small>' + (selected.family==='MiniMax H3'?'24fps · 124 ≈ 5.2s · use 17k+5 frames':'24fps · 81 ≈ 3.4s · use 4k+1 frames') + '</small>' : '') + '</label>';
  }).join('');
  renderLoraSlots();
  controlKeys.forEach(k => { const input=getControl(k); if (input) input.value=selected.defaults?.[k] ?? ''; });
  if (selected.i2v_modes?.length) applyI2VMode(selected.i2v_default_mode || selected.i2v_modes[0].id, false);
  updateLoraHints(); renderRecipeChoices();
  $('#referenceWrap').hidden = !selected.reference; $('#lastReferenceWrap').hidden = !selected.last_reference; $('#referenceHint').textContent = referenceHint(); $('#referenceLabel').textContent = selected.reference_label || 'Reference / first frame'; $('#lastReferenceLabel').textContent = selected.last_reference_label || 'Last frame'; $('#lastReferenceHint').textContent = selected.last_reference_hint || 'Use the same image at both ends for a loop experiment.';
  if(typeof renderReferenceSlots==='function')renderReferenceSlots();
  $('#workflow').href = '/api/workflows/' + encodeURIComponent(selected.id);
  $('#visualWorkflow').hidden = !selected.visual; $('#visualWorkflow').href = $('#workflow').href + '?visual';
  $('#sourceLink').hidden = !selected.source; $('#sourceLink').href = safeUrl(selected.source);
  $('#generate').textContent = selected.modality === 'video' ? 'Generate video →' : selected.modality === '3d' ? 'Generate mesh →' : 'Generate image →';
  updateReady(); inspectSelected();
  if(selected.runtime_block) message(selected.runtime_block,true);
}
function dependencyMarkup(r) {
  const present=r.present===true, note=r.note || (present?'File present':r.present===false?'Missing · place in the indicated folder':'Availability unknown · inspect this requirement');
  const installation=!present&&r.installable!==true ? '<br><small>'+esc(r.install_note || 'Automatic installation is unavailable; inspect the source and exact destination.')+'</small>' : '';
  const copy=typeof r.path==='string'&&r.path ? '<button data-copy="'+esc(r.path)+'" title="Copy full file path">Copy path</button>' : '';
  const installable=r.present===false&&r.asset_id&&r.installable===true;
  return '<div class="dependency '+(present?'':'missing')+'"><span class="dot">'+(present?'●':'○')+'</span><div class="file-text"><code>'+esc(r.file)+'</code><small>'+esc(note)+'</small>'+installation+'</div>'+copy+(installable?'<button data-install="'+esc(r.asset_id)+'">Install</button>':'')+'</div>';
}
// A recipe ID alone cannot reject A→B→A or repeated-check responses.
let inspectionEpoch=0, inspectionController=null;
async function inspectSelected() {
  const epoch=++inspectionEpoch, preset=selected, id=preset?.id;
  inspectionController?.abort();inspectionController=null;
  if(!id)return;
  const controller=typeof AbortController==='function'?new AbortController():null;
  inspectionController=controller;
  const current=()=>epoch===inspectionEpoch&&selected===preset;
  $('#dependencyCount').textContent='Checking…';
  $('#dependencies').textContent='Checking required files for '+(preset.name||id)+'…';
  $('#dependencies').setAttribute?.('aria-busy','true');
  $('#nodeList').innerHTML='';$('#graphPreview').textContent='';
  let timer=null;
  const deadline=new Promise((_,reject)=>{
    if(typeof setTimeout==='function')timer=setTimeout(()=>{controller?.abort();reject(Error('Required-file check timed out. No installation or generation was started.'));},15000);
  });
  try {
    const data=await Promise.race([api('/api/inspect/'+encodeURIComponent(id),{signal:controller?.signal}),deadline]);
    if(!current())return;
    if(!Array.isArray(data?.requirements)||!Array.isArray(data.nodes)||!data.graph||typeof data.graph!=='object')throw Error('The required-file response is incomplete.');
    // Build all markup before publishing any successful count.
    const requirements=data.requirements.map(dependencyMarkup).join('')||'<p class="muted">No separate weight files in this workflow.</p>';
    const nodes=data.nodes.map(n=>'<code>'+esc(n.type)+'</code>').join('');
    const graph=JSON.stringify(data.graph,null,2);
    $('#dependencyCount').textContent=data.requirements.filter(r=>r.present===true).length+' / '+data.requirements.length+' present';
    $('#dependencies').innerHTML=requirements;$('#nodeList').innerHTML=nodes;$('#graphPreview').textContent=graph;
  } catch(e) {
    if(!current())return;
    $('#dependencyCount').textContent='Unavailable';
    $('#dependencies').innerHTML='<p class="error" role="status">Could not check required files for '+esc(preset.name||id)+': '+esc(e.message)+'</p><button type="button" data-inspect-retry="'+esc(id)+'">Recheck required files</button>';
  } finally {
    if(timer!==null)clearTimeout(timer);
    if(current()){$('#dependencies').setAttribute?.('aria-busy','false');inspectionController=null;}
  }
}

function selectPreset(id, reset=true, transition=false) {
  const next=catalog.presets.find(p=>p.id===id);if(!next)throw Error('This preset is unavailable.');
  if(continuationState&&!transition&&(id!==selected?.id||reset))throw Error('You are continuing an image. Use “Leave this continuation” before loading a different recipe, or reopen Continue with this asset to choose another route.');
  if(transition){continuationState=null;continuationSource=null;}
  recipeTemplateHash=null;
  selected=next; recipeChanged();
  if(reset) clearReference(); $('#batch').value=1; renderPresets(); renderSelected(); recipeChanged(); // Refresh targets against the rendered recipe, after early invalidation.
  message(selected.runtime_block || 'Recipe loaded. Change a setting or choose a variation, then generate when ready.',!!selected.runtime_block);
}
async function refreshHealth() {
  try {
    const h=await api('/api/health'); online=h.online; workerAlive=h.worker_alive!==false; schemaAvailable=!!h.schema_available; healthError=false; missingByPreset=h.missing_models || {};
    if(typeof renderRecovery==='function')renderRecovery(h.recovery);
    const failure=$('#workerFailure'),lost=h.worker_failure;if(failure){failure.hidden=!lost;failure.title=lost?String(lost.id):'';failure.textContent=lost?'Failure record not saved for job '+String(lost.id).slice(0,8)+' ('+lost.action+'). Nothing was resubmitted. Once no other program is holding files in the runs folder, open this job and note its prompt ID, or use Resume observation, before restarting the Studio.':'';}
    if(h.devices?.[0]) $('#hardware').textContent=h.devices[0].name.replace(/^cuda:\d+ /,'').replace(' : native','') + ' · ' + (h.devices[0].vram_total/1024**3).toFixed(0) + ' GB VRAM';
    if(h.comfy_url) $('#comfyLink').href=safeUrl(h.comfy_url);
    updateReady();
    if(!online) message('ComfyUI is offline. Start it with the Asset Studio launcher.',true);
    else if(!schemaAvailable) message('The node schema is unavailable; readiness cannot yet be verified.',true);
    else if(missingByPreset[selected?.id]?.length) message('This recipe needs: ' + missingByPreset[selected.id].join(', '),true);
  } catch(e) { online=null; schemaAvailable=false; healthError=true; updateReady(); }
}
function health(){return readPoller?readPoller.refresh('health'):refreshHealth();}
function values() {
  const c={}; if(selected.positive)c.positive=$('#positive').value; if(selected.negative)c.negative=$('#negative').value;
  controlKeys.forEach(k=>{const input=getControl(k); if(input&&input.value!=='')c[k]=input.value;});
  if(selected.i2v_modes?.length && $('#i2vMode')?.value)c.mode=$('#i2vMode').value;
  if(selected.reference&&uploaded)c.reference=uploaded; if(selected.last_reference&&lastUploaded)c.last_reference=lastUploaded; return c;
}
async function uploadInput(id) {
  const file=$('#'+id).files[0]; if(!file)return null;
  if(file.size>20*1024*1024)throw Error('Reference image exceeds 20 MiB');
  return (await api('/api/upload',{method:'POST',headers:{'Content-Type':file.type,'X-Filename':file.name},body:file})).file;
}
function mediaCard(job,index,output) {
  const id=esc(job.id), url='/api/image/'+id+'/'+index, type=output.media_type || 'image';
  const media=type==='video'?'<video controls preload="metadata" src="'+url+'"></video>':type==='audio'?'<audio controls src="'+url+'"></audio>':type==='3d'?'<model-viewer loading="lazy" camera-controls touch-action="pan-y" environment-image="neutral" shadow-intensity="0.7" src="'+url+'" alt="'+esc(job.preset_name)+' mesh"><span slot="poster">Load interactive 3D preview</span></model-viewer>':'<img loading="lazy" src="'+url+'" alt="'+esc(job.preset_name)+' output">';
  return '<article class="imageCard">'+media+'<div class="card-actions">'+(type==='image'?'<button class="pin" data-job="'+id+'" data-index="'+index+'">Compare</button><button class="reference-output" data-job="'+id+'" data-index="'+index+'">Use as reference</button><button class="reference-output" data-preset="anime-detail-fix" data-job="'+id+'" data-index="'+index+'" title="Repaint detected hands and faces; review settings before generating">Fix hands &amp; face</button><button class="reference-output" data-preset="krea-refine" data-job="'+id+'" data-index="'+index+'" title="Open Krea image refinement; review settings before generating">Refine image</button><button class="reference-output" data-preset="wan22-i2v" data-job="'+id+'" data-index="'+index+'">Animate</button><button class="reference-output" data-preset="trellis-auto-cutout" data-job="'+id+'" data-index="'+index+'">Make 3D</button>':'')+'<a download="'+esc(output.filename || 'asset')+'" href="'+url+'">Download</a><button class="recipe" data-job="'+id+'">Recipe</button></div><p>'+esc(job.controls.positive || job.preset_name)+'<br><small>Seed '+esc(output.seed ?? job.controls.seed ?? 'default')+' · '+esc(job.preset_name)+'</small></p></article>';
}
function renderCompare() { $('#compare').hidden=!pinned.length; $('#compareImages').innerHTML=pinned.map(p=>'<img src="/api/image/'+esc(p.job)+'/'+esc(p.index)+'" alt="Pinned comparison">').join(''); }
const mixedBatchCommands = new Map(), mixedBatchBusy = new Set();
function renderMixedBatch(job) {
  const batch=job.mixed_batch;if(!batch)return '';
  if(!batch.revision)return '<p role="status">'+esc(batch.message)+'</p>';
  const known=(batch.known||[]).map(s=>'Output '+(s.index+1)+': '+s.status).join(' · ');
  const detail='<p>'+esc(known)+'</p><p>Output '+esc(batch.unknown_index+1)+' has an unknown submission outcome. '+esc(batch.never_submitted_count)+' later outputs were not submitted.</p><p><small>'+esc(batch.message)+'</small></p>';
  if(job.status==='abandoned')return detail;
  return '<details class="mixedBatchControls" data-job="'+esc(job.id)+'" data-revision="'+esc(batch.revision)+'"><summary>Recover mixed batch</summary>'+detail+
    '<button data-mixed-action="observe" data-job="'+esc(job.id)+'" '+(batch.can_observe?'':'disabled')+'>Check known batch receipts</button><p><small>Only unresolved known IDs are queried, once per check. No generation, retry, cancellation or later stage.</small></p>'+
    '<label>Reason for local disposition<input data-mixed-reason maxlength="1000" required></label><label><input type="checkbox" data-mixed-ack> I understand that all unresolved remote outcomes remain unknown and this does not cancel remote work.</label>'+
    '<button data-mixed-action="dispose" data-job="'+esc(job.id)+'" '+(batch.can_dispose?'':'disabled')+'>Abandon remaining batch locally</button><small>Preserves outputs, exact submission evidence and spent reservations. A repair is a separate explicit action.</small></details>';
}
async function mixedBatchAction(button) {
  const identifier=button.dataset.job;if(button.disabled||mixedBatchBusy.has(identifier))return;
  const box=button.closest('.mixedBatchControls'),action=button.dataset.mixedAction;
  if(!box||!['observe','dispose'].includes(action))throw Error('Refresh the batch evidence before choosing an action.');
  const reason=box.querySelector('[data-mixed-reason]')?.value.trim(),ack=box.querySelector('[data-mixed-ack]')?.checked===true;
  if(action==='dispose'&&!reason)throw Error('Give a reason for the local disposition.');
  if(action==='dispose'&&!ack)throw Error('Acknowledge the unresolved remote outcomes before recording this disposition.');
  let request=mixedBatchCommands.get(identifier);
  if(request&&(request.action!==action||(action==='dispose'&&request.payload.reason!==reason)))throw Error('The previous command response is unconfirmed. Retry that exact action and reason or inspect the current job first.');
  if(!request){request={action,payload:{request_id:crypto.randomUUID(),expected_revision:box.dataset.revision,...(action==='dispose'?{reason,acknowledge_unknown:true}:{})}};mixedBatchCommands.set(identifier,request);}
  button.disabled=true;mixedBatchBusy.add(identifier);let confirmed=false;
  try {
    await post('/api/jobs/'+encodeURIComponent(identifier)+(action==='observe'?'/observe-known':'/dispose-mixed'),request.payload);
    confirmed=true;mixedBatchCommands.delete(identifier);await refresh();
  } catch(error) {
    if(!confirmed){
      if(error.status>=400&&error.status<500)mixedBatchCommands.delete(identifier);
      else throw Error('Response not confirmed for request '+request.payload.request_id+'. Inspect the job or retry this exact action; its request identity is retained.');
    }
    throw error;
  } finally {button.disabled=false;mixedBatchBusy.delete(identifier);}
}
function renderJobs(signature=JSON.stringify(jobs)) {
  if(signature===jobsSignature)return; jobsSignature=signature;
  const mixedDrafts=new Map([...document.querySelectorAll('.mixedBatchControls')].map(box=>[box.dataset.job,{revision:box.dataset.revision,open:box.open,reason:box.querySelector('[data-mixed-reason]')?.value,ack:box.querySelector('[data-mixed-ack]')?.checked}]));
  const cards=[],problems=[],problemsOpen=$('#jobProblems')?.open;
  jobs.forEach(job=>{
    if(job.status!=='completed'){
      const stopped=job.tracking_disposition?.status==='stopped', promptIds=(job.prompt_ids||[]).join(', ');
      const failure=window.StudioUX?.failureDetails?.(job);
      const failureContext=[failure?.node_type,failure?.exception_type].filter(Boolean).join(' · ');
      const failurePanel=failure?'<div class="jobFailure"><b>'+esc(failure.title||'Why it failed')+'</b><p>'+esc(failure.summary)+'</p><p><b>Next:</b> '+esc(failure.action)+'</p><small>Engine detail'+(failureContext?' · '+esc(failureContext):'')+': '+esc(failure.detail)+'</small></div>':'';
      const stoppedNote=stopped?'<p><b>Tracking stopped</b>: '+esc(job.tracking_disposition.reason)+'<br><small>Recorded '+esc(new Date(job.tracking_disposition.recorded_at*1000).toLocaleString())+'</small></p>':'';
      const resume=stopped&&job.can_resume_tracking?'<button class="resume" data-job="'+esc(job.id)+'">Resume observation of retained prompt</button>':!stopped&&!job.has_pending_submission&&['uncertain','partial'].includes(job.status)&&job.prompt_ids?.length?'<button class="resume" data-job="'+esc(job.id)+'">Resume observation</button>':'';
      const stop=job.can_stop_tracking?'<label>Reason for stopping tracking<input class="stopTrackingReason" data-stop-tracking-reason="'+esc(job.id)+'" maxlength="1000" required></label><button class="stopTracking" data-job="'+esc(job.id)+'">Stop tracking</button>':'';
      const abandonNote=job.abandonment?'<p><b>Abandoned locally</b>: '+esc(job.abandonment.reason)+'<br><small>'+esc(job.abandonment.basis==='never_submitted'?'No submission was recorded.':'Remote outcome remains unknown; no cancellation was sent.')+'</small></p>':'';
      const abandon=job.can_abandon?'<div class="abandonJobControls"><label>Reason for abandoning this local job<input data-abandon-reason maxlength="1000" required></label>'+(job.abandon_requires_acknowledgement?'<label><input type="checkbox" data-abandon-ack> I understand the remote outcome is unknown and this does not cancel remote work.</label>':'')+'<p><small>Keep the recipe, evidence and spent reservations. This job will not be retried. Backend switching still checks every live queue.</small></p><button class="abandonJob" data-job="'+esc(job.id)+'">Abandon local job</button></div>':'';
      const problem=['failed','partial','uncertain','abandoned'].includes(job.status);
      const putAway=!problem?'':job.put_away?(job.put_away_basis==='owner'?'<p class="putAwayNote"><small>Put away '+esc(new Date(job.put_away_at*1000).toLocaleString())+'. Status, prompt IDs, outputs and reservations are unchanged.</small></p>':'<p class="putAwayNote"><small>Off your desk because tracking was stopped. Resume observation brings it back.</small></p>')+(job.can_bring_back?'<button class="putAway" data-job="'+esc(job.id)+'" data-put-away="false">Bring back</button>':''):job.can_put_away?'<button class="putAway" data-job="'+esc(job.id)+'" data-put-away="true" title="Hide from Problems and your desk. Nothing is retried, cancelled or deleted.">Put away</button>':job.status==='uncertain'?'<p class="putAwayNote"><small>'+esc(job.can_stop_tracking?'Stop tracking before putting this away; its resume path stays open until then.':'Resolve or abandon this uncertain job before putting it away.')+'</small></p>':'';
      const html='<article class="jobStatus '+esc(job.status)+'"><b>'+esc(job.preset_name)+' · '+esc(job.status)+'</b><p>'+esc(job.message)+'</p>'+failurePanel+(promptIds?'<p><small>Known prompt IDs: '+esc(promptIds)+'</small></p>':'')+stoppedNote+abandonNote+resume+stop+abandon+renderMixedBatch(job)+'<button class="recipe" data-job="'+esc(job.id)+'">Recipe</button>'+putAway+'</article>';
      if(problem)problems.push({job,html});else cards.push(html);
    }
    job.outputs?.forEach((o,i)=>{if(cards.length>=10)return;const a=typeof assetState!=='undefined'&&assetState.assets.find(a=>a.id===o.asset_id);if(!a?.trashed_at)cards.push(mediaCard(job,i,o));});
  });
  const problemMarkup=renderProblems(problems,problemsOpen);
  const host=document.getElementById?.('jobProblemsHost')||null;
  $('#gallery').className=cards.length||(problems.length&&!host)?'gallery':'galleryEmpty';
  $('#gallery').innerHTML=(cards.length?cards.join(''):(problems.length&&!host)?'':'The next good idea starts here.<small>Generate your first output, or <a href="/#assets">open Asset library to import existing work</a>. Then choose Continue with this on an output to reuse it.</small>')+(host?'':problemMarkup);
  if(host)host.innerHTML=problemMarkup;
  for(const box of document.querySelectorAll('.mixedBatchControls')){const draft=mixedDrafts.get(box.dataset.job);if(draft){box.open=draft.open;if(draft.revision===box.dataset.revision){box.querySelector('[data-mixed-reason]').value=draft.reason||'';box.querySelector('[data-mixed-ack]').checked=!!draft.ack;}}}
  renderCompare();
}
// #940: newest open problems first; put-away ones stay one toggle away and are never deleted.
const PROBLEMS_SHOWN=5;let problemsShowAll=false,problemsShowPutAway=false;
function renderProblems(problems,open){
  if(!problems.length)return'';
  const newest=(a,b)=>(Number(b.job.created_at)||0)-(Number(a.job.created_at)||0);
  const active=problems.filter(p=>!p.job.put_away).sort(newest),away=problems.filter(p=>p.job.put_away).sort(newest);
  const shown=problemsShowAll?active:active.slice(0,PROBLEMS_SHOWN),rest=active.length-shown.length;
  const more=rest>0?'<p class="problemsMore"><small>'+rest+' older problem(s) not shown.</small> <button type="button" data-problems-toggle="all">Show all '+active.length+'</button></p>':problemsShowAll&&active.length>PROBLEMS_SHOWN?'<p class="problemsMore"><button type="button" data-problems-toggle="all">Show newest '+PROBLEMS_SHOWN+' only</button></p>':'';
  const awayToggle=away.length?'<p class="problemsMore"><button type="button" data-problems-toggle="away" aria-expanded="'+problemsShowPutAway+'">'+(problemsShowPutAway?'Hide put away':'Show put away ('+away.length+')')+'</button></p>'+(problemsShowPutAway?'<div class="problemsPutAway">'+away.map(p=>p.html).join('')+'</div>':''):'';
  return '<details id="jobProblems" class="job-problems" '+(open?'open':'')+'><summary>Problems · '+active.length+' run(s)'+(away.length?' · '+away.length+' put away':'')+'</summary>'+(active.length?'':'<p><small>No open problems.</small></p>')+shown.map(p=>p.html).join('')+more+awayToggle+'</details>';
}
async function refreshJobs(){try{const next=await api('/api/jobs'),signature=JSON.stringify(next),historyChanged=signature!==jobsDataSignature;jobs=next;jobsDataSignature=signature;renderJobs(signature);if(historyChanged){estimateKey='';estimateResultKey='';scheduleTimeEstimate();}const job=jobs.find(j=>j.id===activeJobId);if(job){message(job.preset_name+': '+job.message,['failed','uncertain'].includes(job.status));if(['completed','failed','partial','uncertain'].includes(job.status))activeJobId=null;}}catch(e){message(e.message,true);}}
function refresh(){return readPoller?readPoller.refresh('jobs'):refreshJobs();}
function showView(next){view=next;['create','assets','production','models','learn'].forEach(name=>{$('#'+name+'View').hidden=name!==next;document.querySelector('[data-view="'+name+'"]').classList.toggle('active',name===next);});$('.hero').hidden=next!=='create';if(next==='models'||next==='learn')refreshLibrary();if(next==='assets')refreshAssets();if(next==='production')refreshProduction();location.hash=next;}
function renderInventory(){if(!library)return;const q=$('#modelSearch').value.toLowerCase();$('#inventory').innerHTML=library.inventory.filter(m=>m.file.toLowerCase().includes(q)).map(m=>'<div class="inventory-row"><code>'+esc(m.file)+'</code><span>'+gib(m.bytes)+'</span></div>').join('')||'<p class="muted">No matching installed weights.</p>';}
async function refreshLibrary(){
  try{
    library=await api('/api/library');const s=library.storage;
    $('#storage').innerHTML='<div><b>'+gib(s.free_bytes)+'</b><small> free on the model drive</small></div><div class="bar"><span style="width:'+Math.min(100,s.free_bytes/s.total_bytes*100)+'%"></span></div><small>Downloads keep '+gib(s.reserve_bytes)+' free for cache, outputs and system memory. Model folder: '+esc(library.model_root)+'</small>';
    const busy=library.assets.some(a=>['queued','downloading','verifying'].includes(a.download?.status)&&Date.now()/1000-a.download.updated_at<180);
    $('#modelCards').innerHTML=library.assets.map(a=>{
      const d=a.download||{},active=['queued','downloading','verifying'].includes(d.status)&&Date.now()/1000-d.updated_at<180;
      const pinOnly=a.installable!==true;
      const state=a.verified?'SHA-256 verified':pinOnly?(a.present?'Present · pin only':'Pin only · not installed'):a.present?'Present · verify file':active?d.status:'Not installed';
      return '<article class="model-card"><span class="badge '+(a.verified?'tested':'')+'">'+esc(state)+'</span><h3>'+esc(a.name)+'</h3><p>'+esc(a.family)+' · '+gib(a.bytes)+'</p><code>'+esc(a.file)+'</code>'+(a.trigger?'<p>Trigger: <b>'+esc(a.trigger)+'</b></p>':'')+'<p>'+esc(a.license)+'</p>'+(active?'<progress max="'+a.bytes+'" value="'+(d.bytes_done||0)+'"></progress><p>'+gib(d.bytes_done)+' / '+gib(a.bytes)+'</p>':'')+(d.status==='failed'?'<p class="error">'+esc(d.message)+'</p>':'')+'<div class="model-actions"><a href="'+esc(safeUrl(a.source))+'" target="_blank" rel="noreferrer">Source ↗</a><button data-install="'+esc(a.id)+'" '+(a.verified||pinOnly||busy?'disabled':'')+' title="'+esc(pinOnly?(a.install_note||'Automatic installation eligibility is unknown; refresh the library.'):'')+'">'+(a.verified?'Installed':pinOnly?'Copy in by hand':a.present?'Verify existing file':'Install / use download')+'</button></div></article>';
    }).join('');
    $('#folders').innerHTML=library.folders.map(f=>'<article class="folder"><b>'+esc(f.label)+'</b><code>'+esc(f.path)+'</code><button data-folder="'+esc(f.id)+'">Open folder</button><button data-copy="'+esc(f.path)+'">Copy path</button></article>').join('');
    $('#collections').innerHTML=(library.collections || []).map(c=>'<article class="collection"><b><a href="'+esc(safeUrl(c.url))+'" target="_blank" rel="noreferrer">'+esc(c.name)+' ↗</a></b><p>'+esc(c.description)+'</p><small>'+esc(c.status || '')+'</small></article>').join('');
    renderInventory();
  }catch(e){$('#downloadStatus').textContent=e.message;}
}
async function install(id){try{const data=await post('/api/models/install',{id});$('#downloadStatus').textContent=data.message;message('Model installation started. Progress is in Models & folders.');await refreshLibrary();}catch(e){$('#downloadStatus').textContent=e.message;message(e.message,true);}}
function saved(){return serverSetups.map(s=>({...s.recipe,name:s.name,id:s.id}));}
async function loadSetups(){
  serverSetups=await api('/api/setups');
  const identity=await api('/api/identity'), migrationKey='asset-studio-setups-migrated:'+identity.workspace;
  if(!localStorage.getItem(migrationKey)){
    let old=[];try{old=JSON.parse(localStorage.getItem('asset-studio-saved')||'[]');}catch{}
    if(Array.isArray(old))for(const recipe of old){
      if(serverSetups.some(s=>s.name===recipe.name&&JSON.stringify(s.recipe)===JSON.stringify(recipe)))continue;
      const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(recipe)));
      const id='legacy-'+[...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('');
      await post('/api/setups',{id,name:recipe.name,recipe});
    }
    localStorage.setItem(migrationKey,'1');serverSetups=await api('/api/setups');
  }
  renderSaved();
}
function renderSaved(){$('#savedList').innerHTML=saved().map((s,i)=>'<span class="saved-chip"><button data-load="'+i+'">'+esc(s.name)+'</button><button data-delete-setup="'+esc(s.id)+'" aria-label="Delete '+esc(s.name)+' setup">×</button></span>').join('')||'<small>Save a variation once it is worth coming back to.</small>';}
function applySaved(s){
  if(!s||!catalog.presets.some(p=>p.id===s.preset))throw Error('This recipe uses an unavailable preset');
  if(s.continuation!=null&&(!StudioContinuation.normalize(s.continuation)||s.continuation.preset_id!==s.preset))throw Error('Invalid saved continuation.');
  selectPreset(s.preset);
  if(s.continuation!=null){continuationState=StudioContinuation.normalize(s.continuation);continuationSource=null;}
  parentAssets=Array.isArray(s.parent_assets)?s.parent_assets.filter(id=>typeof id==='string'):[];
  if(selected.reference_slots)restoreReferenceSlots(s.references);
  if (s.controls?.mode) applyI2VMode(s.controls.mode, false);
  Object.entries(s.controls||{}).forEach(([k,v])=>{if(k==='mode')return;const el=k==='positive'?$('#positive'):k==='negative'?$('#negative'):getControl(k);if(el)el.value=v;});
  if(selected.reference&&typeof s.controls?.reference==='string')uploaded=s.controls.reference;
  if(selected.last_reference&&typeof s.controls?.last_reference==='string')lastUploaded=s.controls.last_reference;
  // A saved setup round-trips each role record's parent_asset and each supported named-input mapping.
  // Board recipes still have a named lastReference continuation source, independent of their role slots.
  // Restore recorded mappings rather than re-deriving them; only a legacy slot-less record with no mapping
  // falls back to the unambiguous single-parent, single-input guess. A job-exported recipe has neither,
  // and an unattributed parent is never dropped by a later edit.
  const filled=[['reference',uploaded],['lastReference',lastUploaded]].filter(([,file])=>file);
  // An empty mapping is absence, not a recorded "nothing": a draft or setup written before #112 has
  // no attribution to restore, and reading {} as one would make the legacy fallback unreachable.
  const savedMapping=s.parent_by_input,mapped=savedMapping&&typeof savedMapping==='object'&&!Array.isArray(savedMapping)&&Object.keys(savedMapping).length?savedMapping:null;
  if(mapped)parentByInput=Object.fromEntries(filled.filter(([input])=>(!selected.reference_slots?.length||input==='lastReference')&&parentAssets.includes(mapped[input])).map(([input])=>[input,mapped[input]]));
  else if(!selected.reference_slots?.length&&parentAssets.length===1&&filled.length===1)parentByInput={[filled[0][0]]:parentAssets[0]};
  $('#batch').value=s.batch_count||s.batch||1;updateReady();message('Recipe loaded. Review the settings before generating.');recipeChanged();
}
function continuationPayload(){return continuationState?{continuation:{...continuationState}}:{};}
function continuationBlockerItems(){
  // Both the original run button and the workbench consume this shared list.
  // Source-free text recipes need wording too; image-only recipes have no binding.
  if(!continuationState)return selected?.positive&&!String($('#positive')?.value||'').trim()?[{code:'wording',message:'Add a prompt to generate.'}]:[];
  const controls=values();
  if(selected?.last_reference&&!controls.last_reference&&$('#lastReference').files?.length)controls.last_reference='pending-local-upload';
  return StudioContinuation.blockerItems(continuationState,selected,controls,parentAssets,attachedReferencePayload());
}
function continuationBlockers(){return continuationBlockerItems().map(item=>item.message);}
// Put the continuation source into the input its recipe reads it from: the pose picture of a style board, else the reference.
// A fresh handoff resets lineage to the source; putting the source back keeps whatever else is attached.
function attachContinuationSource(result,fresh=true){
  const claim=fresh?setHandoffParent:claimInputParent;
  if(StudioContinuation.sourceInput(selected?.continuation_capability)==='last_reference'){lastUploaded=result.file;uploaded=null;claim('lastReference',result.context.asset_id);$('#lastReference').value='';return;}
  uploaded=result.file;claim('reference',result.context.asset_id);
  if(selected.reference_slots?.length){Object.assign(referenceRecords[0],result,{missing:false});renderReferenceSlots();}
  $('#reference').value='';
}
function beginContinuation(result,presetId,intent='edit'){
  const target=catalog.presets.find(p=>p.id===presetId);
  if(!target)throw Error('The destination recipe is unavailable.');
  const prepared=StudioContinuation.initial(result.context,target,intent,result.file);
  if(result.sha256!==result.context.sha256||result.parent_asset!==result.context.asset_id)throw Error('The attached copy does not match the inspected source.');
  if(submitting)throw Error('Wait for the current submission before changing its source.');
  selectPreset(target.id,true,true);
  continuationState=prepared.claim;continuationSource=result.context;
  attachContinuationSource(result);
  $('#positive').value=prepared.positive;if(selected.negative)$('#negative').value=prepared.negative;
  // A restyle that keeps the picture draws it at its own aspect ratio; other routes keep the recipe canvas.
  const canvas=StudioContinuation.canvasFor(result.context,target);if(canvas)for(const key of ['width','height']){const input=getControl(key);if(input)input.value=canvas[key];}
  $('#batch').value=1;updateReady();
}
function leaveContinuation(){
  if(!continuationState)return;
  if(!window.confirm('Leave this source-bound task? The original stays in your library. Save or export this draft first to keep these edits. Create will reset to the recipe defaults.'))return;
  selectPreset(selected.id,true,true);message('Continuation ended. Choose a new recipe or reopen Continue with an asset.');
}
async function exportRecipe(id){const data=await api('/api/jobs/'+encodeURIComponent(id)+'/recipe'),a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download='asset-studio-recipe.json';a.click();URL.revokeObjectURL(a.href);}
document.querySelector('nav').onclick=e=>{if(e.target.dataset.view)showView(e.target.dataset.view);};
$('#presetSearch').oninput=renderPresets;$('#categorySelect').onchange=renderPresets;
$('#modalities').onclick=e=>{if(!e.target.dataset.mode)return;mode=e.target.dataset.mode;$('#categorySelect').value='All';document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));renderPresets();};
$('#presetList').onclick=e=>{const id=e.target.closest('[data-id]')?.dataset.id;if(id)try{selectPreset(id);}catch(err){message(err.message,true);}};
$('#wildcardChips')?.addEventListener('click', e => {
  const name = e.target.closest('[data-wildcard]')?.dataset.wildcard;
  if (name) insertWildcard(name);
});
$('#variants').onclick=e=>{const i=e.target.closest('[data-variant]')?.dataset.variant;if(i===undefined)return;const v=(selected.variants||[{name:'3-seed audition',batch_count:3}])[i];const controls=selected.reference?StudioContinuation.settings(selected,v.controls,values()):(v.controls||{});Object.entries(controls).forEach(([k,val])=>{const input=k==='positive'?$('#positive'):k==='negative'?$('#negative'):getControl(k);if(input)input.value=val;});$('#batch').value=v.batch_count||1;updateLoraHints();updateReady();scheduleTimeEstimate();message(v.name+' loaded. Press Generate to run.');recipeChanged();};
$('#controls').oninput=()=>updateReady();
$('#controls').onchange=e=>{if(e.target.id==='i2vMode')applyI2VMode(e.target.value);else updateReady();};
  $('#loraSlots').onchange=updateLoraHints;
  document.addEventListener('input',e=>{if(e.target===$('#positive'))updateReady();else if(e.target.closest('#createView'))scheduleTimeEstimate();});
  document.addEventListener('change',e=>{if(e.target===$('#positive'))updateReady();else if(e.target.closest('#createView'))scheduleTimeEstimate();});
  document.addEventListener('click',e=>{if(e.target.closest('#createView')){if(typeof setTimeout==='function')setTimeout(scheduleTimeEstimate,0);else scheduleTimeEstimate();}});
$('#recipeSelect').onchange=e=>{if(e.target.value===''){if(continuationState)applyRecipe({preset_id:selected.id,name:'Recipe defaults',controls:{}});return;}try{applyRecipe(familyRecipes()[Number(e.target.value)]);}catch(err){message(err.message,true);}};
$('#randomSeed').onclick=()=>{const input=getControl('seed');if(input)input.value=Math.floor(Math.random()*2147483647);scheduleTimeEstimate();recipeChanged();};
$('#reference').onchange=()=>{uploaded=null;releaseInputParent('reference');updateReady();};$('#lastReference').onchange=()=>{lastUploaded=null;releaseInputParent('lastReference');updateReady();};
$('#generate').onclick=async()=>{
  if(submitting||!selected)return;const blocked=continuationBlockers();if(blocked.length){message(blocked.join(' '),true);if(selected.positive&&!String($('#positive').value).trim())$('#positive').focus();return;}submitting=true;updateReady();
  // The whole Create surface stays interactive while uploads are in flight: snapshot the intent the operator pressed Generate for.
  const started=selected,startedHash=recipeTemplateHash,intent={preset_id:selected.id,...continuationPayload(),controls:values(),batch_count:$('#batch').value,expected_template_sha256:recipeTemplateHash,parent_assets:parentAssets,references:attachedReferencePayload()};
  try{
    const reference=await uploadInput('reference'),lastReference=await uploadInput('lastReference');
    if(selected!==started||recipeTemplateHash!==startedHash)throw Error('The recipe changed while the source was uploading; nothing was submitted. Press Generate again.');
    uploaded=reference||uploaded;lastUploaded=lastReference||lastUploaded; // Bind the uploads only to the recipe they were made for.
    if(selected.reference&&uploaded)intent.controls.reference=uploaded;if(selected.last_reference&&lastUploaded)intent.controls.last_reference=lastUploaded;
    const job=await post('/api/jobs',intent);activeJobId=job.id;message(job.message);await refresh();
  }catch(e){message(e.message,true);}finally{submitting=false;updateReady();}
};
// Ctrl+Enter (Cmd+Enter on a Mac) anywhere in Create does what one click on the Generate button does and nothing more:
// it clicks the real button only while that button is visible and enabled, so the handler's busy guard, readiness gate and
// intent snapshot still decide. A held key repeats keydown; a repeat never submits. A blocked button explains itself (#772).
function generateShortcutBlocker(button){
  if(submitting)return 'A run is already being submitted. Wait for it to finish.';
  if(!button.disabled)return 'Generate is not on screen. Open Create, then press Ctrl+Enter again.';
  return String($('#uxBlockers .ux-blocker p')?.textContent||'').trim()||'Generate is not available yet. Review the readiness checks.';
}
function generateShortcut(e){
  if(e.key!=='Enter'||!(e.ctrlKey||e.metaKey)||e.altKey||e.shiftKey||e.isComposing)return 'ignored';
  const button=$('#generate'),create=$('#createView'),target=e.target;
  if(!button||!create||create.hidden||!(target===document.body||create.contains(target))||target?.closest?.('dialog'))return 'ignored';
  e.preventDefault();
  if(e.repeat)return 'repeat';
  const visible=!button.closest('[hidden]')&&button.getClientRects().length>0;
  if(submitting||button.disabled||!visible){message(generateShortcutBlocker(button),true);return 'blocked';}
  button.click();return 'clicked';
}
document.addEventListener('keydown',generateShortcut);
if(typeof navigator!=='undefined'&&/Mac|iPhone|iPad/.test(navigator.platform||'')){const hint=$('#generateShortcut');if(hint){hint.textContent='⌘ Enter';hint.title='Press Cmd+Enter anywhere in Create to generate';}}
$('#gallery').onclick=async e=>{
  try{
    const mixed=e.target.closest('[data-mixed-action]');if(mixed){await mixedBatchAction(mixed);return;}
    const pin=e.target.closest('.pin');if(pin){const p={job:pin.dataset.job,index:pin.dataset.index};pinned=pinned.some(x=>x.job===p.job&&x.index===p.index)?pinned.filter(x=>x.job!==p.job||x.index!==p.index):[...pinned.slice(-1),p];renderCompare();}
    const recipe=e.target.closest('.recipe');if(recipe)await exportRecipe(recipe.dataset.job);
    const resume=e.target.closest('.resume');if(resume){await post('/api/jobs/'+encodeURIComponent(resume.dataset.job)+'/resume',{});await refresh();}
    const toggle=e.target.closest('[data-problems-toggle]');if(toggle){if(toggle.dataset.problemsToggle==='all')problemsShowAll=!problemsShowAll;else problemsShowPutAway=!problemsShowPutAway;jobsSignature='';renderJobs();return;}
    // Put away changes only the record's put_away_at; it never retries, resumes or cancels.
    const away=e.target.closest('.putAway');if(away){away.disabled=true;try{await post('/api/jobs/'+encodeURIComponent(away.dataset.job)+'/put-away',{put_away:away.dataset.putAway==='true'});await refresh();}finally{away.disabled=false;}return;}
    const stop=e.target.closest('.stopTracking');if(stop){const reason=stop.parentElement.querySelector('[data-stop-tracking-reason]')?.value.trim();if(!reason)throw Error('Give a reason before stopping tracking.');await post('/api/jobs/'+encodeURIComponent(stop.dataset.job)+'/stop-tracking',{reason});await refresh();}
    const abandon=e.target.closest('.abandonJob');if(abandon){
      const box=abandon.closest('.abandonJobControls'),reason=box.querySelector('[data-abandon-reason]')?.value.trim(),ack=box.querySelector('[data-abandon-ack]');
      if(!reason)throw Error('Give a reason before abandoning this local job.');
      if(ack&&!ack.checked)throw Error('Acknowledge the unknown remote outcome before abandoning this local job.');
      abandon.disabled=true;
      try{await post('/api/jobs/'+encodeURIComponent(abandon.dataset.job)+'/abandon',{reason,acknowledge_unknown:!!ack?.checked});await refresh();}finally{abandon.disabled=false;}
    }
    const ref=e.target.closest('.reference-output');if(ref){
      const source=jobs.find(j=>j.id===ref.dataset.job)?.outputs?.[Number(ref.dataset.index)];
      if(!source?.asset_id)throw Error('This output has no saved asset identity. Refresh the workspace before attaching it.');
      const result=await post('/api/assets/reference',{id:source.asset_id});
      const target=ref.dataset.preset||(selected?.reference?selected.id:catalog.presets.find(p=>p.id==='gentle-variation')?.id);
      const targetPreset=catalog.presets.find(p=>p.id===target),intent=targetPreset?.modality==='video'?'animate':targetPreset?.modality==='3d'?'mesh':'edit';
      beginContinuation(result,target,intent);
      $('#reference').value='';
      $('#referenceHint').textContent='Using the selected output as the reference. It has been copied into this recipe.';
      message('Reference attached. Adjust the prompt, then generate when ready.');
    }
  }catch(err){message(err.message,true);}
};
// A failed availability read can leave a source claim with no staged file. Preserve
// that uncertainty in the draft, but do not persist it as unattributed setup lineage.
function checkedSetupControls() {
  const controls=values();
  const inputs=[['reference','reference',selected?.reference_label||'Reference / first frame'],['lastReference','last_reference',selected?.last_reference_label||'Last frame']];
  const unstaged=inputs.filter(([input,key])=>selected?.[key]&&$('#'+input).files?.length&&!controls[key]);
  if(unstaged.length)throw Error('Setup not saved: '+unstaged.map(([, ,label])=>label).join(' and ')+
    ' is selected only in this browser and is not uploaded. Import the file into Asset library, then use Pull from library to attach it before saving. Your selection and setup name are unchanged.');
  const pending=inputs
    .filter(([input,key])=>parentByInput[input]&&parentAssets.includes(parentByInput[input])&&!controls[key]);
  if(pending.length)throw Error('Setup not saved: reattach '+pending.map(([, ,label])=>label).join(' and ')+
    ' using Pull from library. To use a new local file, import it into Asset library first. Its source link has no attached file. Your draft and setup name are unchanged.');
  return controls;
}
function setupMessage(text,error=false){message(text,error);$('#setupStatus').textContent=text;$('#setupStatus').classList.toggle('error',error);}
$('#save').onclick=async()=>{if(!selected)return;const name=$('#saveName').value.trim();if(!name){setupMessage('Give this setup a name first.');return;}try{await post('/api/setups',{name,recipe:{preset:selected.id,...continuationPayload(),controls:checkedSetupControls(),batch:$('#batch').value,parent_assets:parentAssets,parent_by_input:{...parentByInput},references:attachedReferencePayload()}});$('#saveName').value='';await loadSetups();setupMessage('Setup saved in your workspace, available in every browser.');}catch(e){setupMessage(e.message,true);}};
$('#savedList').onclick=async e=>{try{if(e.target.dataset.load!==undefined)applySaved(saved()[e.target.dataset.load]);if(e.target.dataset.deleteSetup){await post('/api/setups',{action:'delete',id:e.target.dataset.deleteSetup});await loadSetups();}}catch(err){message(err.message,true);}};
$('#importRecipe').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>1024*1024)throw Error('Recipe must be under 1 MiB');const recipe=JSON.parse(await file.text());const check=await post('/api/recipe-check',recipe);applySaved({preset:recipe.preset_id,continuation:recipe.continuation,controls:recipe.controls,batch_count:recipe.batch_count,parent_assets:recipe.parent_assets,references:recipe.references});recipeTemplateHash=check.template_sha256;message('Recipe loaded: embedded workflow matches this preset. Referenced inputs and model files remain local dependencies.');}catch(err){message('Could not import recipe: '+err.message,true);}finally{e.target.value='';}};
$('#refreshModels').onclick=async()=>{await api('/api/health?refresh');await health();await refreshLibrary();};$('#modelSearch').oninput=renderInventory;
function configureReadPolling(){
  if(!window.ReadPoller||readPoller)return;
  readPoller=new window.ReadPoller();window.StudioReadPoller=readPoller;
  window.addEventListener?.('pagehide',event=>{if(!event.persisted)readPoller.dispose();});
  window.addEventListener?.('pageshow',event=>{if(event.persisted)readPoller.wake(true);});
  const readAssets=refreshAssets,readProduction=refreshProduction,readLibrary=refreshLibrary;
  refreshAssets=(...args)=>readPoller.refresh('assets',...args);
  refreshProduction=(...args)=>readPoller.refresh('production',...args);
  refreshLibrary=(...args)=>readPoller.refresh('library',...args);
  readPoller.register('jobs',{interval:()=>jobs.some(j=>['running','waiting','queued'].includes(j.status))?4000:15000,task:refreshJobs});
  readPoller.register('health',{interval:15000,task:refreshHealth});
  readPoller.register('assets',{interval:15000,shouldPoll:()=>view==='assets',task:readAssets});
  readPoller.register('production',{interval:15000,shouldPoll:()=>view==='production',task:readProduction});
  readPoller.register('library',{interval:15000,shouldPoll:()=>view==='models'||view==='learn',task:readLibrary});
  window.dispatchEvent?.(new Event('studio-read-poller-ready'));
}
document.addEventListener('click',async e=>{
  const inspectRetry=e.target.closest('[data-inspect-retry]');
  if(inspectRetry){if(inspectRetry.dataset.inspectRetry===selected?.id)await inspectSelected();return;}

  const copy=e.target.closest('[data-copy]'),folder=e.target.closest('[data-folder]'),button=e.target.closest('[data-install]');
  try{if(copy){await navigator.clipboard.writeText(copy.dataset.copy);copy.textContent='Copied';}if(folder)await post('/api/folders/open',{id:folder.dataset.folder});if(button&&!button.disabled)await install(button.dataset.install);}catch(err){message(err.message,true);$('#downloadStatus').textContent=err.message;}
});
$('#importWorkflow').onchange=async e=>{
  try{const file=e.target.files[0];if(!file)return;if(file.size>1024*1024)throw Error('Workflow JSON must be under 1 MiB');const report=await post('/api/workflow-inspect',{workflow:JSON.parse(await file.text()),name:file.name});$('#importReport').innerHTML='<p><b>'+report.node_count+' nodes inspected</b> · '+esc(report.format)+'</p><p>Missing nodes: '+esc(report.missing_nodes.join(', ')||'none detected')+'</p><p>Model filenames: '+esc(report.models.join(', ')||'none found in saved values')+'</p><p>Missing files: '+esc(report.missing_models.join(', ')||'none detected')+'</p><small>'+esc(report.note)+'</small>';}catch(err){$('#importReport').textContent=err.message;}finally{e.target.value='';}
};
(async()=>{
  try{
    catalog=await api('/api/catalog');await loadAtelier();$('#recipeCount').textContent=catalog.presets.length+' editable recipes';
    $('#categorySelect').innerHTML=['All',...new Set(catalog.presets.map(p=>p.category||'Other'))].map(c=>'<option>'+esc(c)+'</option>').join('');
    selectPreset(catalog.presets.find(p=>p.id==='anima-portrait')?.id||catalog.presets[0].id);await loadSetups();await health();await refresh();await refreshAssets();await refreshLibrary();
    const initial=location.hash.slice(1);if(['create','assets','production','models','learn'].includes(initial))showView(initial);
    configureReadPolling();readPoller?.start();
  }catch(e){message(e.message,true);}
})();
