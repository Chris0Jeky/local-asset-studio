/* Pure recipe-discovery projection. Deterministic, authored order, no ranking by private prompt text. */
import type { Availability, RecipeIdentity, RecipeSummary, Showcase, ShowcaseSample } from './contracts';

export interface DiscoveryCard {
  readonly id: string;
  readonly name: string;
  readonly family: string;
  readonly tags: readonly string[];
  readonly status: string;
  readonly availability: string;
  readonly sample: ShowcaseSample | null;
}

export interface DiscoveryView {
  readonly scope: 'current-recipe' | 'showcase' | 'none';
  readonly heading: string;
  readonly caption: string;
  readonly cards: readonly DiscoveryCard[];
  readonly total: number;
  readonly matching: number;
}

const AVAILABILITY: Record<Availability, string> = {
  installed: 'Adapters installed',
  missing: 'Missing adapters',
  unknown: 'Adapter inventory unknown'
};

function card(recipe: RecipeSummary, showcase: Showcase): DiscoveryCard {
  const availability = recipe.availability === 'missing' && recipe.missing.length
    ? 'Missing ' + recipe.missing.length + ' adapter' + (recipe.missing.length === 1 ? '' : 's')
    : AVAILABILITY[recipe.availability];
  return Object.freeze({
    id: recipe.id, name: recipe.name, family: recipe.family, tags: recipe.tags, availability,
    status: recipe.executed ? 'Run recorded here' : 'Not yet run here',
    sample: showcase.get(recipe.id) ?? null
  });
}

export function projectDiscovery(
  recipes: readonly RecipeSummary[], showcase: Showcase, current: RecipeIdentity | null, limit = 4
): DiscoveryView {
  const total = recipes.length;
  const matching = current ? recipes.filter(recipe => recipe.presetId === current.id) : [];
  if (matching.length) {
    return Object.freeze({
      scope: 'current-recipe', total, matching: matching.length,
      heading: 'Authored setups for ' + current!.name,
      caption: matching.length + ' authored setup' + (matching.length === 1 ? '' : 's') + ' use this recipe. Inspecting one opens the bundle explorer; nothing changes until you apply it there.',
      cards: Object.freeze(matching.slice(0, limit).map(recipe => card(recipe, showcase)))
    });
  }
  const featured = recipes.filter(recipe => showcase.has(recipe.id));
  const pool = featured.length ? featured : recipes;
  if (!pool.length) {
    return Object.freeze({
      scope: 'none', total, matching: 0, heading: 'Recipe ideas',
      caption: 'No authored setups are recorded in presets/recipes.json.', cards: Object.freeze([])
    });
  }
  return Object.freeze({
    scope: 'showcase', total, matching: 0,
    heading: current ? 'Recipe ideas' : 'Start from an authored setup',
    caption: (current ? 'No authored setups use ' + current.name + ' yet. ' : '')
      + 'These have a local example run. Examples are not art acceptance or licence clearance.',
    cards: Object.freeze(pool.slice(0, limit).map(recipe => card(recipe, showcase)))
  });
}

/** Plain-language source line; unknown stays unknown rather than becoming "none missing". */
export function sourceLine(summary: { state: string; missing: readonly { role: string }[]; pending: readonly unknown[]; pendingFiles: number; extra: number }): string {
  if (summary.state === 'unknown') return 'Source requirements are not known until a recipe is observed.';
  if (summary.state === 'not-required') return 'This recipe needs no source pictures.';
  if (summary.state === 'satisfied') return 'Every required source is staged.';
  const parts: string[] = [];
  if (summary.missing.length) parts.push('Needs: ' + summary.missing.map(slot => slot.role).join(', '));
  if (summary.pending.length) parts.push(summary.pending.length + ' not staged yet');
  if (summary.pendingFiles) parts.push(summary.pendingFiles + ' local file check' + (summary.pendingFiles === 1 ? '' : 's') + ' pending');
  if (summary.extra) parts.push(summary.extra + ' without a matching slot');
  return parts.join(' · ') || 'Sources need attention.';
}
