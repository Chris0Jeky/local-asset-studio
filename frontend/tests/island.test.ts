import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mountIsland, type IslandHandle } from '../src/island';
import { STORAGE_KEY } from '../src/preferences';
import { fakeHost, rawSnapshot, settle } from './fixtures';

let root: HTMLElement;
let handle: IslandHandle | null = null;
const q = <T extends Element = HTMLElement>(selector: string) => root.querySelector<T & Element>(selector) as unknown as T;

beforeEach(() => {
  document.body.innerHTML = '<main id="createView"></main>';
  root = document.createElement('section');
  document.getElementById('createView')!.append(root);
});
afterEach(() => { handle?.unmount(); handle = null; vi.restoreAllMocks(); });

describe('mount and unmount', () => {
  it('renders guidance, owns one listener, and releases everything on unmount', async () => {
    const host = fakeHost();
    handle = mountIsland(root, host);
    await settle();
    expect(handle.state()).toBe('mounted');
    expect(document.body.dataset.uiIsland).toBe('active');
    expect(q('#uiIslandPrimaryTitle').textContent).toBe('Review the source roles');
    expect(q('[data-testid=sources]').textContent).toContain('Character picture');
    expect(root.querySelectorAll('[data-recipe-card]')).toHaveLength(2);
    expect(host.listeners.size).toBe(1);
    expect(host.motionListeners.size).toBe(1);
    handle.unmount();
    expect(handle.state()).toBe('unmounted');
    expect(host.listeners.size).toBe(0);
    expect(host.motionListeners.size).toBe(0);
    expect(host.signals[0]!.aborted).toBe(true);
    expect(root.childElementCount).toBe(0);
    expect(document.body.dataset.uiIsland).toBeUndefined();
  });

  it('remounts repeatedly without duplicate listeners or duplicate dispatches', async () => {
    const host = fakeHost();
    for (let index = 0; index < 3; index++) { handle?.unmount(); handle = mountIsland(root, host); }
    await settle();
    expect(host.listeners.size).toBe(1);
    expect(root.querySelectorAll('#uiIslandPrimary')).toHaveLength(1);
    q<HTMLButtonElement>('#uiIslandPrimary').click();
    expect(host.dispatched).toHaveLength(1);
  });

  it('follows owner notifications and never dispatches on its own', async () => {
    const host = fakeHost();
    handle = mountIsland(root, host);
    await settle();
    host.emit(rawSnapshot('ctx-00000002', { primaryAction: { id: 'focus-generate', title: 'Ready when you are', label: 'Focus Generate', workspaceId: 'create', contextStamp: 'ctx-00000002' }, secondaryActions: [] }));
    await settle();
    expect(q('#uiIslandPrimaryTitle').textContent).toBe('Ready when you are');
    expect(host.dispatched).toHaveLength(0);
    expect(host.opened).toHaveLength(0);
  });

  it('shows an honest waiting state when the workbench has not reported', async () => {
    handle = mountIsland(root, fakeHost({ snapshot: null }));
    await settle();
    expect(q('.ui-island__waiting').textContent).toMatch(/Nothing is assumed ready/);
    expect(root.querySelector('#uiIslandPrimary')).toBeNull();
  });
});

describe('commands stay with existing owners', () => {
  it('dispatches the displayed intent unchanged and reports a stale context without retrying', async () => {
    const host = fakeHost({ dispatch: () => ({ ok: false, reason: 'stale-context' }) });
    handle = mountIsland(root, host);
    await settle();
    q<HTMLButtonElement>('#uiIslandPrimary').click();
    await settle();
    expect(host.dispatched).toHaveLength(1);
    expect(host.dispatched[0]).toMatchObject({ id: 'review-sources', workspaceId: 'create', contextStamp: 'ctx-00000001' });
    expect(q('.ui-island__status').textContent).toMatch(/workbench changed/);
  });

  it('opens discovery for inspection only', async () => {
    const host = fakeHost();
    handle = mountIsland(root, host);
    await settle();
    q<HTMLButtonElement>('[data-recipe-card]').click();
    q<HTMLButtonElement>('#uiIslandBrowse').click();
    expect(host.opened).toEqual(['witch', undefined]);
    expect(host.dispatched).toHaveLength(0);
  });
});

describe('keyboard flow', () => {
  it('moves between recipe cards with arrows, Home and End', async () => {
    handle = mountIsland(root, fakeHost());
    await settle();
    const cards = [...root.querySelectorAll<HTMLButtonElement>('[data-recipe-card]')];
    cards[0]!.focus();
    cards[0]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    expect(document.activeElement).toBe(cards[1]);
    cards[1]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    expect(document.activeElement).toBe(cards[1]);
    cards[1]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
    expect(document.activeElement).toBe(cards[0]);
    cards[0]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
    expect(document.activeElement).toBe(cards[1]);
  });

  it('uses native buttons with accessible names and a disclosure state', async () => {
    handle = mountIsland(root, fakeHost());
    await settle();
    for (const button of root.querySelectorAll('button')) expect(button.getAttribute('type')).toBe('button');
    expect(q('[data-recipe-card]').getAttribute('aria-label')).toBe('Inspect Painterly witch in the bundle explorer');
    const toggle = q<HTMLButtonElement>('#uiIslandToggle');
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    toggle.click();
    await settle();
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
  });
});

describe('storage denial', () => {
  it('keeps working in tab-only mode when storage throws', async () => {
    const host = fakeHost({ storage: () => ({ getItem: () => { throw new DOMException('denied', 'SecurityError'); }, setItem: () => { throw new DOMException('denied', 'SecurityError'); } }) });
    handle = mountIsland(root, host);
    await settle();
    expect(handle.state()).toBe('mounted');
    expect(q('.ui-island__note').textContent).toMatch(/this tab only/);
    q<HTMLButtonElement>('#uiIslandToggle').click();
    await settle();
    expect(q('#uiIslandToggle').getAttribute('aria-expanded')).toBe('false');
  });

  it('keeps working when storage itself is unavailable', async () => {
    handle = mountIsland(root, fakeHost({ storage: () => null }));
    await settle();
    expect(q('.ui-island__note').textContent).toMatch(/this tab only/);
  });

  it('persists only the presentation choice when storage works', async () => {
    const saved = new Map<string, string>();
    handle = mountIsland(root, fakeHost({ storage: () => ({ getItem: key => saved.get(key) ?? null, setItem: (key, value) => { saved.set(key, value); } }) }));
    await settle();
    q<HTMLButtonElement>('#uiIslandToggle').click();
    expect([...saved.entries()]).toEqual([[STORAGE_KEY, '{"collapsed":true}']]);
    expect(root.querySelector('.ui-island__note')).toBeNull();
  });
});

describe('network denial', () => {
  it('reports unreadable recipes and keeps guidance usable', async () => {
    const host = fakeHost({ recipes: () => Promise.reject(new TypeError('Failed to fetch')), showcase: () => Promise.reject(new TypeError('Failed to fetch')) });
    handle = mountIsland(root, host);
    await settle();
    expect(q('.ui-island__unavailable').textContent).toMatch(/could not be read/);
    expect(q('#uiIslandPrimary')).not.toBeNull();
    expect(handle.state()).toBe('mounted');
  });

  it('shows cards without previews when the example index is unavailable', async () => {
    handle = mountIsland(root, fakeHost({ showcase: () => Promise.reject(new Error('offline')) }));
    await settle();
    expect(root.querySelectorAll('img')).toHaveLength(0);
    expect(root.querySelectorAll('.ui-island__no-preview')).toHaveLength(2);
  });
});

describe('error containment', () => {
  it('contains a setup failure, restores the legacy guidance flag and does not throw', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const host = fakeHost({ readSnapshot: () => { throw new Error('boom'); } });
    expect(() => { handle = mountIsland(root, host); }).not.toThrow();
    await settle();
    expect(handle!.state()).toBe('failed');
    expect(document.body.dataset.uiIsland).toBeUndefined();
    expect(root.textContent).toMatch(/standard guidance is shown/);
    expect(host.listeners.size).toBe(0);
    expect(warn).toHaveBeenCalledOnce();
  });

  it('contains a render failure after mount', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const host = fakeHost();
    handle = mountIsland(root, host);
    await settle();
    // A listener delivering a value that breaks rendering must not escape into the page.
    const poisoned = { view: new Proxy({}, { get() { throw new Error('poisoned'); } }), recipe: null };
    for (const listener of host.listeners) listener(poisoned as never);
    await settle();
    expect(handle.state()).toBe('failed');
    expect(document.body.dataset.uiIsland).toBeUndefined();
    expect(host.listeners.size).toBe(0);
  });
});

describe('reduced motion', () => {
  it('follows the OS preference at mount and on change', async () => {
    const host = fakeHost({ reduced: true });
    handle = mountIsland(root, host);
    await settle();
    expect(q('.ui-island__frame').dataset.motion).toBe('reduced');
    for (const listener of host.motionListeners) listener(false);
    await settle();
    expect(q('.ui-island__frame').dataset.motion).toBe('full');
  });
});
