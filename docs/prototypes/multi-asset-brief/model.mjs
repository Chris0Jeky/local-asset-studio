import {slots, routes, assets, findAsset, resultAsset, workspaceId} from './fixtures.mjs';
export const storageKey = 'studio.prototype.multi-asset-brief.v1';
export function freshDraft() {
  return {version: 1, workspace_id: workspaceId, collection_id: 'lantern-marsh', title: 'Lantern Marsh',
    brief: 'A small exploration game about finding the way home. Blue-hour reeds, weathered brass and one warm light. Keep the scene quiet, readable and a little mysterious.',
    slots: Object.fromEntries(slots.map(s => [s.id, {intent: s.intent, criteria: s.criteria,
      assetId: s.initial || null, previousAssetId: null, prepared: null}]))};
}
const bounded = (value, max) => typeof value === 'string' && value.length <= max;
export function readDraft(raw) {
  if (raw === null) return freshDraft();
  const value = JSON.parse(raw);
  if (value?.version !== 1 || value.workspace_id !== workspaceId || value.collection_id !== 'lantern-marsh' ||
      !bounded(value.title, 120) || !bounded(value.brief, 2000) || !value.slots) throw Error('Saved draft is not compatible.');
  const clean = freshDraft(); clean.title = value.title; clean.brief = value.brief;
  for (const slot of slots) {
    const s = value.slots[slot.id];
    if (!s || !bounded(s.intent, 600) || !bounded(s.criteria, 1000)) throw Error('A saved slot is unreadable.');
    for (const key of ['assetId', 'previousAssetId']) {
      if (s[key] !== null && (typeof s[key] !== 'string' || findAsset(s[key])?.media_type !== slot.kind)) throw Error('Saved asset reference is unavailable.');
    }
    // A prepared handoff is re-observed after reload; it is never authority to execute or return.
    clean.slots[slot.id] = {intent: s.intent, criteria: s.criteria, assetId: s.assetId, previousAssetId: s.previousAssetId, prepared: null};
  }
  return clean;
}
export function assign(draft, slotId, assetId) {
  const slot = slots.find(s => s.id === slotId), item = findAsset(assetId);
  if (!slot || !item || item.media_type !== slot.kind) throw Error('Choose an asset of the required media kind.');
  const state = draft.slots[slotId];
  if (state.assetId !== assetId) { state.previousAssetId = state.assetId; state.assetId = assetId; }
  state.prepared = null;
}
export function candidates(slotId, search = '') {
  const slot = slots.find(s => s.id === slotId);
  return assets.filter(a => a.media_type === slot?.kind && `${a.title} ${a.filename}`.toLowerCase().includes(search.toLowerCase()));
}
export function routeState(draft, slotId, routeId) {
  const slot = slots.find(s => s.id === slotId), route = routes[routeId];
  if (!slot?.routes.includes(routeId)) return {state: 'unsupported', reason: 'This route does not belong to this slot.'};
  if (route.state !== 'preview') return {state: route.state, reason: route.description};
  if (!draft.title.trim() || !draft.brief.trim() || !draft.slots[slotId].intent.trim()) return {state: 'blocked', reason: 'Add a scene title, a brief and slot wording first.'};
  if (routeId === 'scene' && !draft.slots.background.assetId) return {state: 'blocked', reason: 'Select a PNG background in the Background slot first.'};
  return {state: 'preview', reason: 'Synthetic preparation is available. Live readiness is not checked.'};
}
export function requestFor(draft, slotId, routeId) {
  if (routeState(draft, slotId, routeId).state !== 'preview') throw Error('Preparation is blocked or unsupported.');
  const route = routes[routeId], slot = draft.slots[slotId];
  if (routeId === 'scene') return {action: 'create', name: `${draft.title} · atmosphere`,
    asset_ids: [draft.slots.background.assetId, draft.slots.sound.assetId].filter(Boolean),
    fps: [24, 1], size: [640, 360], frames_per_shot: 96, actor: 'user'};
  return {id: route.lookId, scene: `${draft.brief}\n\n${slot.intent}`, expected_revision: 1};
}
export function signature(draft, slotId, routeId) {
  return JSON.stringify([requestFor(draft, slotId, routeId), draft.slots[slotId].criteria, draft.slots[slotId].assetId]);
}
export function prepare(draft, slotId, routeId) {
  const captured = signature(draft, slotId, routeId);
  draft.slots[slotId].prepared = {routeId, signature: captured};
}
export function returnResult(draft, slotId, routeId) {
  const prepared = draft.slots[slotId].prepared;
  if (!prepared || prepared.routeId !== routeId || prepared.signature !== signature(draft, slotId, routeId)) throw Error('The brief or sources changed. Preview preparation again.');
  const result = resultAsset(slotId);
  if (!result) throw Error('No synthetic return exists for this route.');
  assign(draft, slotId, result.id);
}
export function summary(draft) {
  return {assigned: slots.filter(s => draft.slots[s.id].assetId).length,
    missing: slots.filter(s => !draft.slots[s.id].assetId), review: slots.filter(s => draft.slots[s.id].assetId)};
}
