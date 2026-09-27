<script setup lang="ts">
/* Task guidance + recipe discovery island. Reads immutable snapshots; dispatches only existing reveal/navigation
   intents. It owns no draft, submits no job, uploads nothing and adds no timer or poll. */
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue';
import { parseRecipes, parseShowcase } from './contracts';
import type { GuidanceIntent, IslandHost, PresentationSnapshot, RecipeSummary, Showcase } from './contracts';
import { projectDiscovery, sourceLine } from './discovery';
import { readPreferences, writePreferences } from './preferences';

const props = defineProps<{ host: IslandHost }>();
const host = props.host;

const snapshot = shallowRef<PresentationSnapshot | null>(host.readSnapshot());
const recipes = shallowRef<readonly RecipeSummary[]>([]);
const recipeState = ref<'loading' | 'ready' | 'unavailable'>('loading');
const showcase = shallowRef<Showcase>(new Map());
const failedImages = ref(new Set<string>());
const initial = readPreferences(host);
const collapsed = ref(initial.value.collapsed);
const persistent = ref(initial.persistent);
const status = ref('');
const reducedMotion = ref(false);
const motion = host.reducedMotion(reduced => { reducedMotion.value = reduced; });
reducedMotion.value = motion.reduced;
const cardList = ref<HTMLElement | null>(null);

const view = computed(() => snapshot.value?.view ?? null);
const discovery = computed(() => projectDiscovery(recipes.value, showcase.value, snapshot.value?.recipe ?? null));
const sources = computed(() => view.value ? sourceLine(view.value.sourceSummary) : '');
const EVIDENCE: Record<string, string> = {
  unknown: 'not known yet', active: 'an operation is active', attention: 'needs attention',
  outputs: 'outputs recorded', ready: 'reported ready', observed: 'observed'
};
const REASONS: Record<string, string> = {
  'stale-context': 'The workbench changed since this advice was shown. The latest advice is now displayed; press again if it still applies.',
  'cross-workspace': 'This advice belongs to another workspace and was not used.',
  'unavailable-action': 'The workbench cannot open that destination right now.',
  'unsupported-action': 'That action is not supported by the workbench.',
  'handler-failed': 'The workbench could not open that destination. Nothing was changed.'
};

let unsubscribe: (() => void) | null = null;
const abort = new AbortController();

function runIntent(intent: GuidanceIntent): void {
  const result = host.dispatchIntent(intent);
  if (result.ok) { status.value = ''; return; }
  snapshot.value = host.readSnapshot();
  status.value = REASONS[result.reason] ?? REASONS['unavailable-action']!;
}

function inspect(recipeId?: string): void {
  status.value = host.openDiscovery(recipeId) ? '' : 'The bundle explorer is still loading. Try again in a moment; nothing was changed.';
}

function toggle(): void {
  collapsed.value = !collapsed.value;
  persistent.value = writePreferences(host, { collapsed: collapsed.value });
}

/** Roving keyboard movement between recipe cards; Tab still leaves the list normally. */
function onCardKey(event: KeyboardEvent): void {
  const buttons = [...(cardList.value?.querySelectorAll<HTMLButtonElement>('button[data-recipe-card]') ?? [])];
  const index = buttons.indexOf(event.target as HTMLButtonElement);
  if (index < 0 || !buttons.length) return;
  const next = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? Math.min(index + 1, buttons.length - 1)
    : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? Math.max(index - 1, 0)
      : event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : -1;
  if (next < 0) return;
  event.preventDefault();
  buttons[next]!.focus();
}

function imageFailed(id: string): void {
  failedImages.value = new Set([...failedImages.value, id]);
}

onMounted(() => {
  unsubscribe = host.subscribe(next => { snapshot.value = next; });
  host.loadRecipes(abort.signal).then(raw => {
    if (abort.signal.aborted) return;
    recipes.value = parseRecipes(raw); recipeState.value = 'ready';
  }).catch(() => { if (!abort.signal.aborted) recipeState.value = 'unavailable'; });
  host.loadShowcase().then(raw => { if (!abort.signal.aborted) showcase.value = parseShowcase(raw); }).catch(() => undefined);
});

onBeforeUnmount(() => {
  abort.abort();
  unsubscribe?.(); unsubscribe = null;
  motion.stop();
});
</script>

<template>
  <div class="ui-island__frame" :data-motion="reducedMotion ? 'reduced' : 'full'">
    <header class="ui-island__header">
      <span class="eyebrow">TASK GUIDE · TRIAL ISLAND</span>
      <h2 id="uiIslandTitle">Next step</h2>
    </header>

    <p v-if="!view" class="ui-island__waiting" role="status">Waiting for the workbench to report its state. Nothing is assumed ready.</p>
    <div v-else class="ui-island__guidance" :data-evidence="view.evidenceState">
      <h3 id="uiIslandPrimaryTitle">{{ view.primaryAction.title }}</h3>
      <p>{{ view.primaryAction.description }}</p>
      <button id="uiIslandPrimary" type="button" class="ui-island__primary" :data-intent="view.primaryAction.id"
        @click="runIntent(view.primaryAction)">{{ view.primaryAction.label }}</button>
      <ul v-if="view.secondaryActions.length" class="ui-island__secondary" aria-label="Also worth checking">
        <li v-for="item in view.secondaryActions" :key="item.id">
          <button type="button" class="ui-island__link" :data-intent="item.id" @click="runIntent(item)">{{ item.title }}</button>
          <span>{{ item.description }}</span>
        </li>
      </ul>
      <p class="ui-island__sources" data-testid="sources">{{ sources }}</p>
      <details class="ui-island__why">
        <summary>Why this?</summary>
        <p>{{ view.primaryAction.reason }}</p>
        <p>Evidence: {{ EVIDENCE[view.evidenceState] }}. This guide never submits, retries or uploads anything.</p>
      </details>
    </div>

    <section class="ui-island__discovery" aria-labelledby="uiIslandDiscoveryTitle">
      <div class="ui-island__discovery-head">
        <h3 id="uiIslandDiscoveryTitle">{{ discovery.heading }}</h3>
        <button id="uiIslandToggle" type="button" class="ui-island__link" aria-controls="uiIslandDiscoveryBody"
          :aria-expanded="!collapsed" @click="toggle">{{ collapsed ? 'Show ideas' : 'Hide ideas' }}</button>
      </div>
      <div v-show="!collapsed" id="uiIslandDiscoveryBody" class="ui-island__discovery-body">
        <p v-if="recipeState === 'loading'" role="status">Loading authored setups…</p>
        <p v-else-if="recipeState === 'unavailable'" class="ui-island__unavailable" role="status">
          Authored setups could not be read. The workbench and the bundle explorer are unaffected.
        </p>
        <template v-else>
          <p class="ui-island__caption">{{ discovery.caption }}</p>
          <ul v-if="discovery.cards.length" ref="cardList" class="ui-island__cards" @keydown="onCardKey">
            <li v-for="card in discovery.cards" :key="card.id" class="ui-island__card" :data-recipe="card.id">
              <img v-if="card.sample && !failedImages.has(card.id)" :src="card.sample.url" alt="" loading="lazy"
                decoding="async" width="96" height="128" @error="imageFailed(card.id)">
              <span v-else class="ui-island__no-preview" aria-hidden="true">No local preview</span>
              <div class="ui-island__card-body">
                <h4>{{ card.name }}</h4>
                <p class="ui-island__meta">{{ card.family }} · {{ card.status }} · {{ card.availability }}</p>
                <p v-if="card.sample" class="ui-island__sample">{{ card.sample.caption }}</p>
                <button type="button" data-recipe-card :aria-label="'Inspect ' + card.name + ' in the bundle explorer'"
                  @click="inspect(card.id)">Inspect</button>
              </div>
            </li>
          </ul>
          <button v-if="discovery.total" id="uiIslandBrowse" type="button" class="ui-island__link"
            @click="inspect()">Browse all {{ discovery.total }} authored setups</button>
        </template>
      </div>
      <p v-if="!persistent" class="ui-island__note">Browser storage is unavailable, so this layout choice lasts for this tab only.</p>
    </section>
    <p class="ui-island__status" role="status" aria-live="polite">{{ status }}</p>
  </div>
</template>
