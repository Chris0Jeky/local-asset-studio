/* The only binding to the legacy page: the workshop's read-only snapshot/notification and intent dispatcher, the
   bundle explorer's open adapter, one same-origin GET and the existing showcase module. */
import { parseDispatch, parseSnapshot } from './contracts';
import type { GuidanceIntent, IslandHost } from './contracts';

interface WorkshopApi {
  presentationSnapshot?: () => unknown;
  dispatchIntent?: (intent: GuidanceIntent) => unknown;
}
type CreateView = HTMLElement & { __workshop?: WorkshopApi };
type StudioWindow = Window & { StudioBundleExplorer?: { open(id?: string): unknown } };

const SHOWCASE_MODULE = '/static/bundle-showcase.js';

export function createBrowserHost(win: StudioWindow): IslandHost {
  const create = () => win.document.getElementById('createView') as CreateView | null;
  return Object.freeze({
    readSnapshot: () => {
      try { return parseSnapshot(create()?.__workshop?.presentationSnapshot?.()); } catch { return null; }
    },
    subscribe(listener) {
      const target = create();
      if (!target) return () => undefined;
      const handler = (event: Event) => listener(parseSnapshot((event as CustomEvent<unknown>).detail));
      target.addEventListener('studio:presentation', handler);
      return () => target.removeEventListener('studio:presentation', handler);
    },
    dispatchIntent(intent) {
      const dispatch = create()?.__workshop?.dispatchIntent;
      if (typeof dispatch !== 'function') return { ok: false, reason: 'unavailable-action' };
      try { return parseDispatch(dispatch(intent)); } catch { return { ok: false, reason: 'handler-failed' }; }
    },
    openDiscovery(recipeId) {
      const explorer = win.StudioBundleExplorer;
      if (!explorer || typeof explorer.open !== 'function') return false;
      try { void Promise.resolve(recipeId ? explorer.open(recipeId) : explorer.open()).catch(() => undefined); return true; }
      catch { return false; }
    },
    async loadRecipes(signal) {
      const response = await win.fetch('/api/recipes', { signal, credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    },
    async loadShowcase() {
      const module: { default?: unknown } = await import(/* @vite-ignore */ SHOWCASE_MODULE);
      return module.default;
    },
    storage() {
      try { return win.localStorage; } catch { return null; }
    },
    reducedMotion(listener) {
      const query = typeof win.matchMedia === 'function' ? win.matchMedia('(prefers-reduced-motion: reduce)') : null;
      if (!query) return { reduced: false, stop: () => undefined };
      const handler = (event: MediaQueryListEvent) => listener(event.matches);
      query.addEventListener('change', handler);
      return { reduced: query.matches, stop: () => query.removeEventListener('change', handler) };
    }
  } satisfies IslandHost);
}
