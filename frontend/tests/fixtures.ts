import type { DispatchResult, GuidanceIntent, IslandHost, PresentationSnapshot } from '../src/contracts';
import { parseSnapshot } from '../src/contracts';

export function intent(id: GuidanceIntent['id'], stamp = 'ctx-00000001', title = 'Review the source roles'): Record<string, unknown> {
  return { id, title, label: 'Review sources', description: 'Attach or stage every required source role.', reason: 'Exact slot identities are kept separate.', workspaceId: 'create', contextStamp: stamp };
}

export function rawSnapshot(stamp = 'ctx-00000001', extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    view: {
      version: 1, workspaceId: 'create', contextStamp: stamp, taskId: 'generate', evidenceState: 'attention',
      sourceSummary: { state: 'attention', pendingFiles: 0, required: [], provided: [], missing: [{ id: 'character', role: 'Character picture', required: true }], pending: [], extra: [] },
      primaryAction: intent('review-sources', stamp),
      secondaryActions: [intent('review-readiness', stamp, 'Resolve the next blocker')],
      authorizesSubmission: false, commands: [], ...extra
    },
    recipe: { id: 'krea-anime-atelier', name: 'Krea anime atelier' }
  };
}

export const RECIPES = {
  version: 1, available: true, source: 'test',
  recipes: [
    { id: 'witch', name: 'Painterly witch', preset_id: 'krea-anime-atelier', family: 'Krea 2 Turbo', tags: ['anime'], status: 'executed', available: true, missing: [], controls: { positive: 'PRIVATE PROMPT TEXT' } },
    { id: 'meadow', name: 'Golden meadow', preset_id: 'krea-anime-atelier', family: 'Krea 2 Turbo', tags: [], status: 'unverified', available: false, missing: ['a.safetensors'] },
    { id: 'other', name: 'Other preset look', preset_id: 'wai', family: 'WAI', tags: [], status: 'executed', available: null, missing: [] }
  ]
};

export const SHOWCASE = { version: 1, examples: {
  witch: { url: '/api/examples/anime-fantasy-atelier/witch.jpg', caption: 'Meadow witch.' },
  other: { url: 'https://example.invalid/remote.jpg', caption: 'Remote must be dropped.' }
} };

export interface FakeHost extends IslandHost {
  listeners: Set<(snapshot: PresentationSnapshot | null) => void>;
  dispatched: GuidanceIntent[];
  opened: (string | undefined)[];
  signals: AbortSignal[];
  motionListeners: Set<(reduced: boolean) => void>;
  emit(raw: unknown): void;
}

export function fakeHost(options: {
  snapshot?: unknown; recipes?: () => Promise<unknown>; showcase?: () => Promise<unknown>;
  storage?: () => Pick<Storage, 'getItem' | 'setItem'> | null; reduced?: boolean;
  dispatch?: (intent: GuidanceIntent) => DispatchResult; readSnapshot?: () => PresentationSnapshot | null;
} = {}): FakeHost {
  let current = parseSnapshot(options.snapshot === undefined ? rawSnapshot() : options.snapshot);
  const values = new Map<string, string>();
  const host: FakeHost = {
    listeners: new Set(), dispatched: [], opened: [], signals: [], motionListeners: new Set(),
    emit(raw) { current = parseSnapshot(raw); for (const listener of host.listeners) listener(current); },
    readSnapshot: options.readSnapshot ?? (() => current),
    subscribe(listener) { host.listeners.add(listener); return () => { host.listeners.delete(listener); }; },
    dispatchIntent(value) { host.dispatched.push(value); return options.dispatch ? options.dispatch(value) : { ok: true, id: value.id }; },
    openDiscovery(id) { host.opened.push(id); return true; },
    loadRecipes(signal) { host.signals.push(signal); return options.recipes ? options.recipes() : Promise.resolve(RECIPES); },
    loadShowcase() { return options.showcase ? options.showcase() : Promise.resolve(SHOWCASE); },
    storage: options.storage ?? (() => ({ getItem: key => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value); } })),
    reducedMotion(listener) {
      host.motionListeners.add(listener);
      return { reduced: options.reduced === true, stop: () => { host.motionListeners.delete(listener); } };
    }
  };
  return host;
}

export async function settle(): Promise<void> {
  for (let index = 0; index < 5; index++) await new Promise(resolve => setTimeout(resolve, 0));
}
