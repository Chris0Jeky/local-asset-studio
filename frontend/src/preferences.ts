/* Presentation-only preference. Storage failure is a usable tab-only mode, never a fatal error. */
import type { IslandHost } from './contracts';

export const STORAGE_KEY = 'studio.ui-island.v1';

export interface IslandPreferences { readonly collapsed: boolean }

export function readPreferences(host: IslandHost): { value: IslandPreferences; persistent: boolean } {
  try {
    const storage = host.storage();
    if (!storage) return { value: { collapsed: false }, persistent: false };
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw || raw.length > 256) return { value: { collapsed: false }, persistent: true };
    const parsed: unknown = JSON.parse(raw);
    const collapsed = !!parsed && typeof parsed === 'object' && (parsed as { collapsed?: unknown }).collapsed === true;
    return { value: { collapsed }, persistent: true };
  } catch {
    return { value: { collapsed: false }, persistent: false };
  }
}

export function writePreferences(host: IslandHost, value: IslandPreferences): boolean {
  try {
    const storage = host.storage();
    if (!storage) return false;
    storage.setItem(STORAGE_KEY, JSON.stringify({ collapsed: value.collapsed === true }));
    return true;
  } catch {
    return false;
  }
}
