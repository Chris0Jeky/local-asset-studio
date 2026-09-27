/* Typed projection contracts for the guidance island (#907). Every value crossing from the legacy page or the API
   is validated here and copied into frozen plain data; the island never keeps a reference to a legacy object. */

export const INTENT_IDS = [
  'review-readiness', 'review-sources', 'inspect-operation',
  'resolve-draft-conflict', 'focus-generate', 'open-results'
] as const;
export type IntentId = typeof INTENT_IDS[number];

export type EvidenceState = 'unknown' | 'active' | 'attention' | 'outputs' | 'ready' | 'observed';
const EVIDENCE_STATES: readonly EvidenceState[] = ['unknown', 'active', 'attention', 'outputs', 'ready', 'observed'];

export interface GuidanceIntent {
  readonly id: IntentId;
  readonly title: string;
  readonly label: string;
  readonly description: string;
  readonly reason: string;
  readonly workspaceId: string;
  readonly contextStamp: string;
}

export interface SlotSummary { readonly id: string; readonly role: string }

export interface SourceSummary {
  readonly state: 'unknown' | 'attention' | 'satisfied' | 'not-required';
  readonly pendingFiles: number;
  readonly missing: readonly SlotSummary[];
  readonly pending: readonly SlotSummary[];
  readonly extra: number;
}

export interface PresentationView {
  readonly workspaceId: string;
  readonly contextStamp: string;
  readonly evidenceState: EvidenceState;
  readonly sourceSummary: SourceSummary;
  readonly primaryAction: GuidanceIntent;
  readonly secondaryActions: readonly GuidanceIntent[];
  /** Always false: presentation never authorizes a submission. A snapshot claiming otherwise is rejected. */
  readonly authorizesSubmission: false;
}

export interface RecipeIdentity { readonly id: string; readonly name: string }
export interface PresentationSnapshot { readonly view: PresentationView; readonly recipe: RecipeIdentity | null }

export type Availability = 'installed' | 'missing' | 'unknown';
export interface RecipeSummary {
  readonly id: string;
  readonly name: string;
  readonly presetId: string;
  readonly family: string;
  readonly tags: readonly string[];
  readonly executed: boolean;
  readonly availability: Availability;
  readonly missing: readonly string[];
}

export interface ShowcaseSample { readonly url: string; readonly caption: string }
export type Showcase = ReadonlyMap<string, ShowcaseSample>;

export type DispatchResult = { readonly ok: true; readonly id: IntentId } | { readonly ok: false; readonly reason: string };

type Plain = Record<string, unknown>;
const plain = (value: unknown): value is Plain => !!value && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown, max = 400): string | null =>
  typeof value === 'string' && value.trim() ? value.trim().slice(0, max) : null;
const TOKEN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const token = (value: unknown): string | null => typeof value === 'string' && TOKEN.test(value) ? value : null;
const count = (value: unknown): number => Number.isSafeInteger(value) && (value as number) >= 0 ? Math.min(value as number, 10000) : 0;
const isIntentId = (value: unknown): value is IntentId => (INTENT_IDS as readonly unknown[]).includes(value);

export function parseIntent(raw: unknown): GuidanceIntent | null {
  if (!plain(raw) || !isIntentId(raw.id)) return null;
  const workspaceId = token(raw.workspaceId), contextStamp = token(raw.contextStamp);
  const title = text(raw.title, 160), label = text(raw.label, 80);
  if (!workspaceId || !contextStamp || !title || !label) return null;
  return Object.freeze({
    id: raw.id, title, label, workspaceId, contextStamp,
    description: text(raw.description) ?? '', reason: text(raw.reason) ?? ''
  });
}

function slots(raw: unknown): readonly SlotSummary[] {
  if (!Array.isArray(raw)) return Object.freeze([]);
  const result: SlotSummary[] = [];
  for (const item of raw.slice(0, 32)) {
    if (!plain(item)) continue;
    const id = token(item.id) ?? token(item.slotId);
    if (id) result.push(Object.freeze({ id, role: text(item.role, 120) ?? id }));
  }
  return Object.freeze(result);
}

function parseSources(raw: unknown): SourceSummary {
  const value = plain(raw) ? raw : {};
  const state = value.state === 'attention' || value.state === 'satisfied' || value.state === 'not-required' ? value.state : 'unknown';
  return Object.freeze({
    state, pendingFiles: count(value.pendingFiles), missing: slots(value.missing), pending: slots(value.pending),
    extra: Array.isArray(value.extra) ? Math.min(value.extra.length, 64) : 0
  });
}

/** Accepts the workshop's `studio:presentation` detail. Anything malformed or claiming authority is null (unknown). */
export function parseSnapshot(raw: unknown): PresentationSnapshot | null {
  if (!plain(raw) || !plain(raw.view)) return null;
  const view = raw.view;
  if (view.authorizesSubmission !== false || (Array.isArray(view.commands) && view.commands.length)) return null;
  const primaryAction = parseIntent(view.primaryAction);
  const workspaceId = token(view.workspaceId), contextStamp = token(view.contextStamp);
  if (!primaryAction || !workspaceId || !contextStamp) return null;
  const secondaryActions = Object.freeze((Array.isArray(view.secondaryActions) ? view.secondaryActions : [])
    .slice(0, 2).map(parseIntent).filter((item): item is GuidanceIntent => !!item));
  const evidenceState = EVIDENCE_STATES.find(state => state === view.evidenceState) ?? 'unknown';
  let recipe: RecipeIdentity | null = null;
  if (plain(raw.recipe)) {
    const id = token(raw.recipe.id);
    if (id) recipe = Object.freeze({ id, name: text(raw.recipe.name, 160) ?? id });
  }
  return Object.freeze({
    view: Object.freeze({
      workspaceId, contextStamp, evidenceState, sourceSummary: parseSources(view.sourceSummary),
      primaryAction, secondaryActions, authorizesSubmission: false as const
    }),
    recipe
  });
}

/** `/api/recipes` payload -> authored summaries. Controls, prompts and notes are deliberately not copied. */
export function parseRecipes(raw: unknown): readonly RecipeSummary[] {
  if (!plain(raw) || !Array.isArray(raw.recipes)) throw new TypeError('The recipe list is malformed.');
  const seen = new Set<string>(), result: RecipeSummary[] = [];
  for (const item of raw.recipes.slice(0, 500)) {
    if (!plain(item)) continue;
    const id = token(item.id), presetId = token(item.preset_id);
    if (!id || !presetId || seen.has(id)) continue;
    seen.add(id);
    const missing = Object.freeze((Array.isArray(item.missing) ? item.missing : [])
      .map(name => text(name, 200)).filter((name): name is string => !!name).slice(0, 16));
    result.push(Object.freeze({
      id, presetId,
      name: text(item.name, 160) ?? id,
      family: text(item.family, 80) ?? 'Unlabelled family',
      tags: Object.freeze((Array.isArray(item.tags) ? item.tags : []).map(tag => token(tag)).filter((tag): tag is string => !!tag).slice(0, 6)),
      executed: item.status === 'executed',
      availability: item.available === true ? 'installed' : item.available === false ? 'missing' : 'unknown',
      missing
    }));
  }
  return Object.freeze(result);
}

const EXAMPLE_URL = /^\/api\/examples\/[A-Za-z0-9][A-Za-z0-9._\/-]*\.(?:png|jpe?g|webp|gif)$/i;

/** bundle-showcase.js default export -> same-origin example stills only. Remote or odd URLs are dropped. */
export function parseShowcase(raw: unknown): Showcase {
  const result = new Map<string, ShowcaseSample>();
  if (!plain(raw) || !plain(raw.examples)) return result;
  for (const [id, item] of Object.entries(raw.examples)) {
    if (!token(id) || !plain(item) || typeof item.url !== 'string' || !EXAMPLE_URL.test(item.url) || item.url.includes('..')) continue;
    result.set(id, Object.freeze({ url: item.url, caption: text(item.caption, 240) ?? 'Local example run.' }));
  }
  return result;
}

export function parseDispatch(raw: unknown): DispatchResult {
  if (plain(raw) && raw.ok === true && isIntentId(raw.id)) return { ok: true, id: raw.id };
  return { ok: false, reason: plain(raw) ? token(raw.reason) ?? 'unavailable-action' : 'unavailable-action' };
}

/** The only surface the island may touch. Reads are snapshots; commands are navigation/reveal intents. */
export interface IslandHost {
  readSnapshot(): PresentationSnapshot | null;
  subscribe(listener: (snapshot: PresentationSnapshot | null) => void): () => void;
  dispatchIntent(intent: GuidanceIntent): DispatchResult;
  /** Opens the existing bundle explorer (optionally inspecting one recipe). Never applies a recipe. */
  openDiscovery(recipeId?: string): boolean;
  loadRecipes(signal: AbortSignal): Promise<unknown>;
  loadShowcase(): Promise<unknown>;
  storage(): Pick<Storage, 'getItem' | 'setItem'> | null;
  reducedMotion(listener: (reduced: boolean) => void): { readonly reduced: boolean; stop(): void };
}
