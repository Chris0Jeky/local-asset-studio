import {slots, routes, collectionPage, assetPage, previews, findAsset} from './fixtures.mjs';
import {storageKey, freshDraft, readDraft, assign, candidates, routeState, requestFor, signature, prepare, returnResult, summary} from './model.mjs';

const $ = s => document.querySelector(s);
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let draft, storageProblem = '', preserveSaved = false, notice = '';
const searches = {}, libraryModes = {};
try { draft = readDraft(localStorage.getItem(storageKey)); }
catch (error) { draft = freshDraft(); preserveSaved = true; storageProblem = 'Saved draft unavailable. Edits stay in this tab; download a copy or reset the demo.'; }
function persist() {
  if (!preserveSaved) {
    try { localStorage.setItem(storageKey, JSON.stringify(draft)); storageProblem = ''; }
    catch { storageProblem = 'Browser storage unavailable. Edits stay in this tab; download a copy before leaving.'; }
  }
  $('#saveState').textContent = storageProblem || 'Draft saved in this browser';
  $('#saveState').classList.toggle('warning', !!storageProblem);
}
function announce(message) { $('#announcement').textContent = message; }
function go(path, message = '') { notice = message; if (location.hash === `#${path}`) render(); else location.hash = path; }
function current() {
  const parts = location.hash.slice(1).split('/').filter(Boolean);
  if (!parts.length) return {view: 'slot', slotId: 'background'};
  if (['gaps','routes'].includes(parts[0]) && parts.length === 1) return {view: parts[0]};
  if (parts[0] !== 'slot' || !slots.some(s => s.id === parts[1]) || parts.length > 4 ||
      parts[2] && !['library','prepare'].includes(parts[2]) || parts[2] === 'prepare' && !slots.find(s => s.id === parts[1]).routes.includes(parts[3]) ||
      parts[2] !== 'prepare' && parts.length > 3) return {view: 'missing'};
  return {view: parts[2] || 'slot', slotId: parts[1], routeId: parts[3]};
}
const kindLabel = kind => ({image:'Image', video:'Video', audio:'Audio', '3d':'3D'})[kind];
function drawing(type, label = '') {
  const content = {
    marsh: '<path d="M0 70 Q50 56 100 72 T200 69V120H0Z" class="land"/><path d="M65 120 95 73h25l45 47M95 73v-7m25 7v-7M82 92h55"/><path d="M30 100V60m-8 16 8 10 9-20M172 104V64m-10 14 10 9 9-15"/><path d="M103 40h12v18h-12zM109 40v-9" class="light"/>',
    moon: '<circle cx="145" cy="30" r="15" class="light"/><path d="M0 75Q45 59 100 78T200 76V120H0Z" class="land"/><path d="m48 120 58-47h19l29 47M106 73v-7m19 7v-7M75 98h65M25 98V63m-7 17 7 9 8-16"/>',
    sprite: '<circle cx="94" cy="28" r="11"/><path d="m85 42-15 44h46l-15-44zM83 86l-5 25m27-25 6 25M78 50 61 69m48-19 19 16m0-8v12M121 70h15v20h-15z"/><path d="M121 70h15v20h-15z" class="light"/>',
    key: '<circle cx="74" cy="44" r="19"/><circle cx="74" cy="44" r="7"/><path d="m88 58 46 46 8-8-12-12 9-9-10-10-9 9-22-22" class="light"/>',
    video: '<rect x="44" y="23" width="112" height="76" rx="6"/><path d="m90 43 30 18-30 18z" class="light"/><path d="M34 32v58m132-58v58"/>',
    audio: '<path d="M24 60h15m8-18v36m12-51v66m12-56v46m12-34v22m12-50v78m12-61v44m12-53v62m12-44v26m12-17v8m8-4h20"/>',
    '3d': '<path d="m100 15 45 26v51l-45 26-45-26V41zM55 41l45 26 45-26m-45 26v51M100 15v52"/><path d="m83 40 17-10 17 10v34l-17 10-17-10z" class="light"/>'
  }[type] || '';
  return `<svg viewBox="0 0 200 125" ${label ? `role="img" aria-label="${escape(label)}"` : 'aria-hidden="true"'}>${content}</svg>`;
}
function preview(item, slot) {
  const meta = previews[item.id] || {drawing:slot.drawing, detail:'Synthetic return record · no generated media bytes'};
  return `<div class="asset-preview ${escape(meta.drawing)}">${drawing(meta.drawing, `${item.title}, schematic placeholder`)}<span>Schematic</span></div>`;
}
function briefHeader() {
  const sum = summary(draft);
  return `<section class="brief-header"><div><h1>${escape(draft.title || 'Untitled scene')}</h1><p>A small game scene, built one asset at a time.</p></div><a class="progress-link" href="#/gaps"><strong>${sum.assigned} of 6</strong> slots have candidates<span>${sum.missing.length} missing · all candidates need review</span></a></section>
    <details class="brief-editor"><summary>Edit the shared brief <span>Changes are kept as you type</span></summary><label>Scene name<input data-field="title" maxlength="120" value="${escape(draft.title)}"></label><label>Creative direction<textarea data-field="brief" maxlength="2000" rows="3">${escape(draft.brief)}</textarea></label></details>`;
}
function slotList(selected) {
  return `<nav class="slots" aria-label="Scene slots"><h2>Asset set</h2>${slots.map(slot => {
    const item = findAsset(draft.slots[slot.id].assetId);
    return `<a href="#/slot/${slot.id}" class="slot-row ${slot.id === selected ? 'active' : ''}" ${slot.id === selected ? 'aria-current="page"' : ''}>
      <span class="slot-icon">${drawing(slot.drawing)}</span><span><strong>${slot.name}</strong><small>${kindLabel(slot.kind)} · ${item ? 'Candidate selected' : 'No candidate'}</small></span><span class="slot-mark" aria-label="${item ? 'Has candidate' : 'Missing candidate'}">${item ? '●' : '○'}</span></a>`;
  }).join('')}<p>Selected is not accepted.<br>Each asset keeps its own review and rights checks.</p></nav>`;
}
function routeList(slot) {
  return `<section class="routes"><h3>Routes for this slot</h3>${slot.routes.map(id => {
    const route = routes[id], state = routeState(draft, slot.id, id);
    return `<a class="route-row" href="#/slot/${slot.id}/prepare/${id}"><span><strong>${route.name}</strong><small>${route.owner}</small></span><span class="tag ${state.state}">${{preview:'Preview handoff', blocked:'Needs setup', unsupported:'Unsupported'}[state.state]}</span></a>`;
  }).join('')}</section>`;
}
function slotDetail(slot) {
  const state = draft.slots[slot.id], item = findAsset(state.assetId);
  return `<section class="detail" aria-labelledby="slotTitle"><div class="detail-heading"><h2 id="slotTitle">${slot.name}</h2><span class="tag">${kindLabel(slot.kind)}</span></div>
    <label>What this slot needs<textarea data-slot-field="intent" maxlength="600" rows="3">${escape(state.intent)}</textarea></label>
    <label>Usable when<textarea data-slot-field="criteria" maxlength="1000" rows="2">${escape(state.criteria)}</textarea></label>
    <section class="chosen"><h3>Current candidate</h3>${item ? `<div class="chosen-asset">${preview(item, slot)}<div><strong>${escape(item.title)}</strong><p>${escape(previews[item.id]?.detail || 'Fixture return only · not a generated asset')}</p><span class="tag">Unreviewed</span><span class="tag">Rights unknown</span></div></div>` : `<div class="empty"><p>No ${kindLabel(slot.kind).toLowerCase()} selected yet.</p><span>Reuse something from the collection, or explore a supported preparation route.</span></div>`}
    <div class="actions"><a class="button primary" href="#/slot/${slot.id}/library">${item ? 'Replace candidate' : 'Choose existing asset'}</a>${item ? '<button data-action="remove">Clear slot</button>' : ''}${state.previousAssetId ? '<button data-action="undo">Restore previous</button>' : ''}</div></section>
    ${routeList(slot)}<p class="slot-gap">Still to check: ${slot.gap}</p></section>`;
}
function libraryCards(slot) {
  const mode = libraryModes[slot.id] || 'normal';
  if (mode === 'error') return '<div class="empty error" role="alert"><h3>Collection observation failed</h3><p>No assets have been changed. Retry the sample read to continue with this slot and its current choice.</p><button data-action="retry">Retry sample read</button></div>';
  const items = mode === 'empty' ? [] : candidates(slot.id, searches[slot.id] || '');
  return items.length ? `<div class="library-grid">${items.map(item => `<article class="library-item">${preview(item, slot)}<h3>${escape(item.title)}</h3><p>${escape(previews[item.id].detail)}</p><p class="muted">Unreviewed · rights unknown</p><button data-choose="${item.id}" ${draft.slots[slot.id].assetId === item.id ? 'disabled' : ''}>${draft.slots[slot.id].assetId === item.id ? 'Current candidate' : 'Use this asset'}</button></article>`).join('')}</div>` : `<div class="empty"><h3>No matching ${kindLabel(slot.kind).toLowerCase()} assets</h3><p>${mode === 'empty' ? 'This sample collection is empty. Your current slot is retained.' : 'Try another name, or clear the search. Your current slot is retained.'}</p><button data-action="clear-search">Show sample assets</button><a href="#/slot/${slot.id}">Return to slot</a></div>`;
}
function library(slot) {
  return `<section class="detail"><a class="back" href="#/slot/${slot.id}">Back to ${slot.name}</a><h2>Choose an existing ${kindLabel(slot.kind).toLowerCase()}</h2><p>Lantern Marsh collection · Regular · one observed page</p><p class="muted">Choosing a record changes this brief only. No Library membership, review or media is changed.</p>
    <label>Find an asset<input id="assetSearch" type="search" value="${escape(searches[slot.id] || '')}" placeholder="Search sample names" maxlength="200"></label><div id="libraryResults">${libraryCards(slot)}</div>
    <details class="scenario-controls"><summary>Preview empty and failed reads</summary><label>Sample Library response<select id="libraryMode"><option value="normal">Sample assets</option><option value="empty" ${(libraryModes[slot.id] === 'empty') ? 'selected' : ''}>Empty collection</option><option value="error" ${(libraryModes[slot.id] === 'error') ? 'selected' : ''}>Read failed</option></select></label><p>Fixture controls; they never contact the Studio.</p></details></section>`;
}
function handoff(slot, routeId) {
  const route = routes[routeId], state = routeState(draft, slot.id, routeId), captured = draft.slots[slot.id].prepared;
  let prepared = false, request = null;
  if (state.state === 'preview') { request = requestFor(draft, slot.id, routeId); prepared = captured?.routeId === routeId && captured.signature === signature(draft, slot.id, routeId); }
  return `<section class="detail"><a class="back" href="#/slot/${slot.id}">Back to ${slot.name}</a><h2>${route.name}</h2><p class="route-owner">${route.owner}</p><p>${route.description}</p>
    <div class="handoff-context"><strong>Returning to ${escape(draft.title || 'Untitled scene')} / ${slot.name}</strong><p>${escape(draft.slots[slot.id].intent)}</p><small>Current candidate: ${escape(findAsset(draft.slots[slot.id].assetId)?.title || 'none')}. It stays selected until you explicitly use a result.</small></div>
    <h3>Prerequisites</h3><ul class="checks">${route.prerequisites.map(p => `<li>${escape(p)}</li>`).join('')}</ul>
    ${state.state === 'preview' ? `<div class="preview-step"><h3>${prepared ? 'Synthetic preparation returned' : 'Review the preparation handoff'}</h3><p>${prepared ? 'No job or native export ran. The result below is a fictional candidate record, ready to exercise the return journey.' : 'This previews the existing request shape. Live preparation would revalidate sources, look revisions and readiness.'}</p><div class="actions"><button data-action="prepare" class="${prepared ? '' : 'primary'}">${prepared ? 'Preview again' : 'Preview preparation'}</button>${prepared ? '<button data-action="return" class="primary">Use synthetic result in slot</button>' : ''}</div>${captured && !prepared ? '<p class="warning">The brief or its sources changed. Preview preparation again before returning.</p>' : ''}</div>
    <details><summary>Inspect the contract</summary><p>Target: <code>${route.endpoint}</code> (never called here)</p><pre>${escape(JSON.stringify(request, null, 2))}</pre><p>Fictional IDs and revision. These are not live execution instructions.</p></details>` : `<div class="empty"><h3>${state.state === 'unsupported' ? 'Unsupported for this brief' : 'Preparation is blocked'}</h3><p>${state.reason}</p><a class="button" href="#/slot/${slot.id}/library">Choose an existing ${kindLabel(slot.kind).toLowerCase()}</a></div>`}
    <p class="slot-gap">Still to check: ${slot.gap}</p></section>`;
}
function gaps() {
  const sum = summary(draft);
  return `<section class="report"><h2>What remains for this scene</h2><p>${sum.assigned} slots have candidate references. ${sum.missing.length ? `${sum.missing.length} still need an asset.` : 'Every slot has a candidate.'} None is marked owner accepted.</p>
    <div class="gap-list">${slots.map(s => `<a href="#/slot/${s.id}"><span><strong>${s.name}</strong><small>${escape(findAsset(draft.slots[s.id].assetId)?.title || 'Choose a candidate')}</small></span><span>${draft.slots[s.id].assetId ? s.gap : 'Missing candidate · ' + s.gap}</span></a>`).join('')}</div>
    <p class="callout">A filled brief is a plan for review. Technical validity, artistic acceptance and rights clearance are separate decisions.</p></section>`;
}
function routeMap() {
  return `<section class="report"><h2>Available routes, honest limits</h2><p>This is a map of existing owners, with synthetic readiness. No runtime was probed.</p><div class="route-map">${slots.map(s => `<section><h3>${s.name}</h3>${routeList(s)}<p>${s.gap}</p></section>`).join('')}</div>
    <details><summary>Collection discovery contract</summary><p>Fixture response for the existing bounded collection reader introduced in #1680. It supplies the stable collection ID for the asset page; the prototype does not create another inventory.</p><pre>${escape(JSON.stringify(collectionPage, null, 2))}</pre><p>Asset page: ${assetPage.format}. Privacy: Regular. All previews are schematic; media bytes are unverified.</p></details></section>`;
}
function render() {
  const route = current(), slot = slots.find(s => s.id === route.slotId);
  const nav = route.view === 'routes' ? 'routes' : route.view === 'gaps' ? 'gaps' : 'brief';
  document.querySelectorAll('[data-nav]').forEach(a => { if (a.dataset.nav === nav) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
  $('#gapCount').textContent = summary(draft).missing.length;
  document.title = `${draft.title || 'Untitled scene'} · Asset brief preview`;
  $('#main').innerHTML = briefHeader() + (notice ? `<p class="notice" role="status">${escape(notice)}</p>` : '') +
    (slot ? `<div class="workspace">${slotList(slot.id)}${route.view === 'library' ? library(slot) : route.view === 'prepare' ? handoff(slot, route.routeId) : slotDetail(slot)}</div>` :
      route.view === 'gaps' ? gaps() : route.view === 'routes' ? routeMap() : '<section class="report"><h2>This preview route is unavailable</h2><p>Your brief is still saved.</p><a href="#/slot/background">Return to the scene brief</a></section>');
  $('#saveState').textContent = storageProblem || 'Local draft · synthetic data';
  $('#saveState').classList.toggle('warning', !!storageProblem);
}
$('#main').addEventListener('input', event => {
  const target = event.target, route = current();
  if (target.dataset.field) {
    draft[target.dataset.field] = target.value;
    if (target.dataset.field === 'title') { $('h1').textContent = target.value || 'Untitled scene'; document.title = `${target.value || 'Untitled scene'} · Asset brief preview`; }
  }
  else if (target.dataset.slotField && route.slotId) draft.slots[route.slotId][target.dataset.slotField] = target.value;
  else if (target.id === 'assetSearch') { searches[route.slotId] = target.value; $('#libraryResults').innerHTML = libraryCards(slots.find(s => s.id === route.slotId)); return; }
  else return;
  persist();
});
$('#main').addEventListener('change', event => {
  if (event.target.id !== 'libraryMode') return;
  const route = current(); libraryModes[route.slotId] = event.target.value;
  $('#libraryResults').innerHTML = libraryCards(slots.find(s => s.id === route.slotId));
});
$('#main').addEventListener('click', event => {
  const button = event.target.closest('button'), route = current();
  if (!button || !route.slotId) return;
  const state = draft.slots[route.slotId], action = button.dataset.action;
  try {
    if (button.dataset.choose) { assign(draft, route.slotId, button.dataset.choose); persist(); go(`/slot/${route.slotId}`, 'Candidate selected. Review and rights status are unchanged.'); return; }
    if (action === 'remove') { state.previousAssetId = state.assetId; state.assetId = null; state.prepared = null; }
    if (action === 'undo' && state.previousAssetId) assign(draft, route.slotId, state.previousAssetId);
    if (action === 'prepare') { prepare(draft, route.slotId, route.routeId); notice = 'Synthetic preparation only. Zero jobs submitted.'; }
    if (action === 'return') { returnResult(draft, route.slotId, route.routeId); persist(); go(`/slot/${route.slotId}`, 'Synthetic candidate returned to this slot. Remaining review gaps are retained.'); return; }
    if (['retry','clear-search'].includes(action)) { searches[route.slotId] = ''; libraryModes[route.slotId] = 'normal'; }
    persist(); render(); $('#main').focus({preventScroll:true}); announce(notice || 'Draft updated.');
  } catch (error) { notice = error.message; render(); announce(notice); }
});
$('#download').addEventListener('click', () => {
  const link = document.createElement('a'), url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], {type:'application/json'}));
  link.href = url; link.download = 'lantern-marsh-prototype-draft.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  announce('Draft copy downloaded. It contains prototype references, not asset files.');
});
$('#reset').addEventListener('click', () => $('#resetDialog').showModal());
$('#cancelReset').addEventListener('click', () => $('#resetDialog').close());
$('#confirmReset').addEventListener('click', () => {
  draft = freshDraft(); preserveSaved = false; storageProblem = ''; notice = 'Fictional starting brief restored.';
  Object.keys(searches).forEach(k => delete searches[k]); Object.keys(libraryModes).forEach(k => delete libraryModes[k]);
  persist(); $('#resetDialog').close(); go('/slot/background', notice);
});
// Focus navigation must not replace the hash that owns the active slot and handoff.
$('.skip').addEventListener('click', event => { event.preventDefault(); $('#main').focus(); $('#main').scrollIntoView(); });
window.addEventListener('hashchange', () => { render(); $('#main').focus({preventScroll:true}); announce('View changed. Your brief is retained.'); });
window.addEventListener('storage', event => {
  if (event.key !== storageKey) return;
  preserveSaved = true; storageProblem = 'Another tab changed this demo. This tab will not overwrite it. Download your edits, then reload to read the saved draft.'; persist();
});
render();
