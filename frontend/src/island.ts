/* Mount/unmount with error containment. A failure unmounts only the island, removes the page flag so the legacy
   guidance returns, and never rethrows into the workbench. */
import { createApp, type App } from 'vue';
import TaskGuide from './TaskGuide.vue';
import type { IslandHost } from './contracts';

export type IslandState = 'mounted' | 'failed' | 'unmounted';
export interface IslandHandle { readonly state: () => IslandState; unmount(): void }

export const PAGE_FLAG = 'uiIsland';

export function mountIsland(target: HTMLElement, host: IslandHost): IslandHandle {
  const body = target.ownerDocument.body;
  let app: App | null = null, state: IslandState = 'unmounted';
  const release = (): void => {
    const current = app; app = null;
    try { current?.unmount(); } catch { /* already contained; the fallback below is authoritative */ }
    delete body.dataset[PAGE_FLAG];
  };
  const fail = (error: unknown): void => {
    if (state === 'failed') return;
    state = 'failed';
    release();
    const notice = target.ownerDocument.createElement('p');
    notice.className = 'ui-island__failed';
    notice.setAttribute('role', 'status');
    notice.textContent = 'The trial guide stopped. The standard guidance is shown instead; your work is unchanged.';
    target.replaceChildren(notice);
    target.dataset.state = 'failed';
    console.warn('[ui-island] contained failure:', error);
  };
  try {
    app = createApp(TaskGuide, { host });
    app.config.errorHandler = error => { queueMicrotask(() => fail(error)); };
    app.config.warnHandler = () => undefined;
    app.mount(target);
    if (state === 'unmounted') {
      state = 'mounted';
      target.dataset.state = 'mounted';
      body.dataset[PAGE_FLAG] = 'active';
    }
  } catch (error) {
    fail(error);
  }
  return Object.freeze({
    state: () => state,
    unmount(): void {
      if (state === 'unmounted') return;
      release();
      target.replaceChildren();
      target.dataset.state = 'unmounted';
      state = 'unmounted';
    }
  });
}
