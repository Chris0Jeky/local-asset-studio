# Workshop Ambience Eligibility Policy Design

**Date:** 18 September 2026  
**Status:** Approved continuation of the Immersive Studio direction  
**Stack position:** #574 → #581 → #582 → this slice

## Purpose

Separate the user’s requested ambience from the decoration the browser may safely render at this moment. The workshop already offers `None`, `Night Shift`, and `Quiet Morning`; this slice makes the effective rendering decision explicit, observable, reversible, and independent from generation readiness.

The result is a local-only policy and a small presentation adapter. It does not add a media provider, remote downloader, loop, sound, service worker, shader, or framework build step.

## Design constraints

1. **Presentation has no execution authority.** Ambience cannot enable or disable Generate, select a recipe, stage a source, retry work, or infer backend health.
2. **Local ambience is independent from connectivity.** Internet-off with a healthy local backend and internet-on with a down backend must produce the same local-poster decision.
3. **Requested and effective state are distinct.** The persisted preference remains `none`, `night-shift`, or `quiet-morning`; effective mode is derived from live observations and is never persisted as another user choice.
4. **No duplicate owners.** `workshop.js` continues to own presentation controls. `workshop-ambience.js` only observes bounded presentation/readiness signals and applies the policy result to decorative attributes and status text.
5. **No optional decoration may block work.** Missing policy code, unavailable art, forced colours, or a hidden page must leave the prompt and generation controls intact.
6. **Still-first.** This slice renders only the existing local static poster or theme tokens. Motion eligibility is reported but no loop is introduced.
7. **No polling.** The adapter uses existing change signals plus a narrowly scoped `MutationObserver`; it never polls, submits, clicks, fetches, or rewrites domain state, and disconnects on `destroy()`.

## Inputs

The pure policy accepts a bounded observation object:

```js
{
  requested: 'none' | 'night-shift' | 'quiet-morning',
  assetState: 'available' | 'missing' | 'unknown',
  visibility: 'visible' | 'hidden',
  forcedColors: boolean,
  reducedMotion: boolean,
  saveData: boolean,
  userPaused: boolean,
  executionState:
    | 'idle' | 'blocked' | 'ready' | 'submitting' | 'running'
    | 'uncertain' | 'completed' | 'failed' | 'unknown',
  internetState: 'online' | 'offline' | 'unknown',
  backendState: 'ready' | 'down' | 'unknown'
}
```

Unknown or malformed values are normalised conservatively. The module does not accept URLs, HTML, CSS, filesystem paths, image bytes, credentials, prompt text, or arbitrary provider configuration.

## Output contract

`project(observation)` returns an immutable display decision:

```js
{
  requested: 'none' | 'night-shift' | 'quiet-morning',
  renderMode: 'none' | 'suspended' | 'tokens' | 'poster',
  assetId: null | 'night-shift' | 'quiet-morning',
  heroVisible: boolean,
  motionEligible: false,
  reason: string,
  status: string,
  authorizesExecution: false,
  commands: []
}
```

`motionEligible` is always false in this static-only slice. The field makes the still-first boundary explicit and prevents future UI from treating a poster as permission to play media.

## Precedence

1. `requested === 'none'` → `none`; no ambience gap is reserved.
2. hidden document → `suspended`; optional art is not painted while hidden.
3. forced-colour mode → `tokens`; preserve structure and remove illustration.
4. missing or unknown local asset → `tokens`; retain theme geometry and a quiet status.
5. available local asset → `poster`.

Reduced motion, data saving, user pause, active/uncertain execution, internet state, and backend state never remove a valid static poster. They keep motion ineligible and may refine the explanation. This avoids turning accessibility, economy, connectivity, or runtime pressure into an “offline punishment” visual.

## Modules and browser integration

### `workshop-ambience-policy.js`

The pure UMD/CommonJS module owns normalisation, projection and low-level environment listeners. `createController(window, options)` observes only:

- `document.visibilityState` / `visibilitychange`;
- `(forced-colors: active)`;
- `(prefers-reduced-motion: reduce)`;
- `navigator.connection.saveData` when exposed;
- explicit updates for requested ambience, execution state, asset state and user pause.

It sets allow-listed values on:

- `body.dataset.workshopAmbienceRender`;
- `#createView.dataset.workshopAmbienceRender`;
- `#workshopAmbienceHero.dataset.ambienceRender`.

It updates one status node with policy text. It does not fetch, decode, preload, poll, mutate storage, or register a service worker. `destroy()` removes every listener.

### `workshop-ambience.js`

The separate presentation adapter mounts only after the existing workshop has created its hero and controls. It:

- reads the allow-listed requested ambience from existing workshop data attributes;
- classifies the current visible execution evidence without changing it;
- forwards internet/backend observations only as explanatory context;
- creates `#workshopAmbienceStatus` when needed;
- exposes `create.__workshopAmbience` for inspection and bounded asset-state qualification;
- watches only ambience attributes, Generate disabled state, gallery/status/problem text and the connection label;
- never clicks Generate, changes a recipe, writes a prompt, stages a file, mutates storage, or invokes a backend.

`studio-shell.js` loads the presentation context, then the pure ambience policy, then `workshop.js`, then the ambience adapter. If the policy script fails to load, the shell still mounts `workshop.js`; the existing static appearance remains the fallback.

## CSS behaviour

`workshop-ambience.css` owns only effective-state overrides and the quiet status line:

- `poster`: existing Night Shift or Quiet Morning CSS illustration is visible.
- `tokens`: the hero keeps the gradient and layout but removes the illustration pseudo-element.
- `suspended`: the illustration is suppressed; the page is hidden, so no visible transition occurs.
- `none`: the existing preference logic hides the hero.
- forced colours continue to remove decorative art independently.

No essential text or control is baked into the image.

## Testing

### Pure contracts

- local-poster result is identical for offline/healthy-backend and online/down-backend cases;
- hidden, forced-colour, unavailable-asset, reduced-motion, save-data, user-pause, and active/unknown execution cases;
- malformed inputs fail closed;
- immutable result, empty commands, and false authority;
- controller listener cleanup and bounded data attributes.

### Integration contracts

- policy script loads before `workshop.js`, and the presentation adapter mounts afterwards;
- shell policy-load failure still mounts the ordinary workshop;
- presentation switching preserves prompt and file-input identity;
- visibility and media-query changes do not submit jobs;
- a missing poster falls back to tokens without hiding controls;
- desktop, mobile and 200% zoom retain no horizontal page overflow;
- browser run records no HTTP, HTTPS, WebSocket, service-worker or media requests.

A dedicated Chromium journey exercises available poster, missing-asset fallback, offline independence, forced-colour fallback/restoration and `None`, while retaining the original editable DOM nodes and zero submissions.

## Rollback

Remove the policy/adapter script loads, `workshop-ambience.js`, `workshop-ambience.css`, the status node and policy-specific tests. The existing v2 appearance preference remains valid and the earlier static workshop behaviour returns without a data migration or domain-state rollback.

## Deferred work

A local loop, request-epoch media loader, performance measurement during real inference, parallax, sound, and any remote source require separate approval and qualification. This slice does not imply those are accepted.
