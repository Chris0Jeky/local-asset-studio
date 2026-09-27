import { describe, expect, it } from 'vitest';
import { parseDispatch, parseRecipes, parseShowcase, parseSnapshot } from '../src/contracts';
import { projectDiscovery, sourceLine } from '../src/discovery';
import { RECIPES, SHOWCASE, rawSnapshot } from './fixtures';

describe('projection contracts', () => {
  it('copies a valid snapshot into frozen data without legacy references', () => {
    const raw = rawSnapshot();
    const snapshot = parseSnapshot(raw)!;
    expect(snapshot.view.primaryAction.id).toBe('review-sources');
    expect(snapshot.view.authorizesSubmission).toBe(false);
    expect(Object.isFrozen(snapshot.view.primaryAction)).toBe(true);
    expect(snapshot.view.primaryAction).not.toBe((raw.view as { primaryAction: unknown }).primaryAction);
    expect(snapshot.recipe).toEqual({ id: 'krea-anime-atelier', name: 'Krea anime atelier' });
  });

  it('rejects a snapshot that claims submission authority or carries commands', () => {
    expect(parseSnapshot(rawSnapshot('ctx-1', { authorizesSubmission: true }))).toBeNull();
    expect(parseSnapshot(rawSnapshot('ctx-1', { commands: [{ id: 'generate' }] }))).toBeNull();
  });

  it('treats malformed or unknown intents as no snapshot rather than inventing an action', () => {
    expect(parseSnapshot(rawSnapshot('ctx-1', { primaryAction: { id: 'submit-job', title: 'Go', label: 'Go', workspaceId: 'create', contextStamp: 'ctx-1' } }))).toBeNull();
    expect(parseSnapshot(null)).toBeNull();
    expect(parseSnapshot({ view: 'nope' })).toBeNull();
  });

  it('keeps unknown source evidence unknown', () => {
    const snapshot = parseSnapshot(rawSnapshot('ctx-1', { sourceSummary: { state: 'mystery' } }))!;
    expect(snapshot.view.sourceSummary.state).toBe('unknown');
    expect(sourceLine(snapshot.view.sourceSummary)).toMatch(/not known/);
  });

  it('summarizes recipes without copying prompts or controls', () => {
    const recipes = parseRecipes(RECIPES);
    expect(recipes.map(recipe => recipe.availability)).toEqual(['installed', 'missing', 'unknown']);
    expect(JSON.stringify(recipes)).not.toContain('PRIVATE PROMPT TEXT');
    expect(() => parseRecipes({ recipes: 'x' })).toThrow();
  });

  it('accepts only same-origin example stills from the showcase', () => {
    const showcase = parseShowcase(SHOWCASE);
    expect([...showcase.keys()]).toEqual(['witch']);
    expect(parseShowcase({ examples: { a: { url: '/api/examples/../config/local.json' } } }).size).toBe(0);
  });

  it('normalizes dispatch results', () => {
    expect(parseDispatch({ ok: true, id: 'review-sources' })).toEqual({ ok: true, id: 'review-sources' });
    expect(parseDispatch({ ok: false, reason: 'stale-context' })).toEqual({ ok: false, reason: 'stale-context' });
    expect(parseDispatch(undefined)).toEqual({ ok: false, reason: 'unavailable-action' });
  });
});

describe('discovery projection', () => {
  const recipes = parseRecipes(RECIPES), showcase = parseShowcase(SHOWCASE);

  it('lists authored setups for the current recipe first, in authored order', () => {
    const view = projectDiscovery(recipes, showcase, { id: 'krea-anime-atelier', name: 'Krea' });
    expect(view.scope).toBe('current-recipe');
    expect(view.cards.map(card => card.id)).toEqual(['witch', 'meadow']);
    expect(view.cards[0]!.sample?.url).toBe('/api/examples/anime-fantasy-atelier/witch.jpg');
    expect(view.cards[1]!.availability).toBe('Missing 1 adapter');
    expect(view.cards[1]!.status).toBe('Not yet run here');
  });

  it('falls back to setups with a local example when the recipe has none', () => {
    const view = projectDiscovery(recipes, showcase, { id: 'unmatched', name: 'Unmatched' });
    expect(view.scope).toBe('showcase');
    expect(view.cards.map(card => card.id)).toEqual(['witch']);
    expect(view.caption).toMatch(/not art acceptance or licence clearance/);
  });

  it('says so when nothing is authored', () => {
    expect(projectDiscovery([], showcase, null).scope).toBe('none');
  });
});
