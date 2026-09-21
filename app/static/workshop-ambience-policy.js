/* Local static ambience eligibility. Presentation only; no execution authority. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.StudioWorkshopAmbiencePolicy = Object.freeze(api);
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const REQUESTS = Object.freeze(['none', 'night-shift', 'quiet-morning']);
  const ASSET_STATES = Object.freeze(['available', 'missing', 'unknown']);
  const RENDER_MODES = Object.freeze(['none', 'suspended', 'tokens', 'poster']);
  const EXECUTION_STATES = Object.freeze([
    'idle', 'blocked', 'ready', 'submitting', 'running', 'uncertain',
    'completed', 'failed', 'unknown'
  ]);
  const INTERNET_STATES = Object.freeze(['online', 'offline', 'unknown']);
  const BACKEND_STATES = Object.freeze(['ready', 'down', 'unknown']);
  const ACTIVE_EXECUTION = new Set(['submitting', 'running', 'uncertain', 'unknown']);
  const UPDATE_KEYS = Object.freeze([
    'requested', 'assetState', 'executionState', 'internetState',
    'backendState', 'userPaused'
  ]);

  const oneOf = (value, allowed, fallback) => allowed.includes(value) ? value : fallback;
  const bool = value => value === true;

  function deepFreeze(value) {
    if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
    for (const item of Object.values(value)) deepFreeze(item);
    return Object.freeze(value);
  }

  function normalize(input = {}) {
    const source = input && typeof input === 'object' && !Array.isArray(input) ? input : {};
    return deepFreeze({
      requested:oneOf(source.requested, REQUESTS, 'none'),
      assetState:oneOf(source.assetState, ASSET_STATES, 'unknown'),
      visibility:source.visibility === 'hidden' ? 'hidden' : 'visible',
      forcedColors:bool(source.forcedColors),
      reducedMotion:bool(source.reducedMotion),
      saveData:bool(source.saveData),
      userPaused:bool(source.userPaused),
      executionState:oneOf(source.executionState, EXECUTION_STATES, 'unknown'),
      internetState:oneOf(source.internetState, INTERNET_STATES, 'unknown'),
      backendState:oneOf(source.backendState, BACKEND_STATES, 'unknown')
    });
  }

  function posterStatus(observation) {
    const reasons = [], details = [];
    if (observation.reducedMotion) {
      reasons.push('Reduced-motion preference keeps ambience still.');
      details.push('motion disabled');
    }
    if (observation.saveData) {
      reasons.push('Data-saving preference suppresses optional media work.');
      details.push('no optional transfer');
    }
    if (observation.userPaused) {
      reasons.push('The user paused optional ambience motion.');
      details.push('optional motion paused');
    }
    if (ACTIVE_EXECUTION.has(observation.executionState)) {
      reasons.push('Runtime work is active or uncertain, so ambience remains still.');
      details.push('runtime-safe still mode');
    }
    if (!reasons.length) return ['An approved local poster is available.', 'Local static poster · no network.'];
    return [reasons.join(' '), 'Local static poster · ' + details.join(' · ') + '.'];
  }

  function project(input = {}) {
    const observation = normalize(input);
    let renderMode, assetId = null, heroVisible, reason, status;

    if (observation.requested === 'none') {
      renderMode = 'none'; heroVisible = false;
      reason = 'No ambience is requested.';
      status = 'No ambience selected.';
    } else if (observation.visibility === 'hidden') {
      renderMode = 'suspended'; heroVisible = true;
      reason = 'The document is hidden, so optional art is suspended.';
      status = 'Ambience suspended while this page is hidden.';
    } else if (observation.forcedColors) {
      renderMode = 'tokens'; heroVisible = true;
      reason = 'Forced-colour mode suppresses decorative illustration.';
      status = 'Theme colours only · forced-colour mode.';
    } else if (observation.assetState !== 'available') {
      renderMode = 'tokens'; heroVisible = true;
      reason = observation.assetState === 'missing'
        ? 'The local ambience poster is missing.'
        : 'The local ambience poster has not been confirmed.';
      status = 'Theme colours only · local poster unavailable.';
    } else {
      renderMode = 'poster'; heroVisible = true; assetId = observation.requested;
      [reason, status] = posterStatus(observation);
    }

    return deepFreeze({
      requested:observation.requested,
      renderMode,
      assetId,
      heroVisible,
      motionEligible:false,
      reason,
      status,
      authorizesExecution:false,
      commands:[]
    });
  }

  function listen(target, name, callback) {
    if (!target || typeof target.addEventListener !== 'function') return () => {};
    target.addEventListener(name, callback);
    return () => target.removeEventListener?.(name, callback);
  }

  function mediaQuery(w, query) {
    try { return typeof w?.matchMedia === 'function' ? w.matchMedia(query) : null; }
    catch (_) { return null; }
  }

  function createController(w, options = {}) {
    const d = w?.document || null;
    const body = options.body || d?.body || null;
    const create = options.create || null;
    const hero = options.hero || null;
    const status = options.status || null;
    const forced = mediaQuery(w, '(forced-colors: active)');
    const reduced = mediaQuery(w, '(prefers-reduced-motion: reduce)');
    const connection = w?.navigator?.connection || null;
    const initial = options.initial && typeof options.initial === 'object' && !Array.isArray(options.initial)
      ? options.initial : {};
    const state = {};
    for (const key of UPDATE_KEYS) if (Object.hasOwn(initial, key)) state[key] = initial[key];
    let decision = project(state), destroyed = false;

    function observation() {
      return {
        ...state,
        visibility:d?.visibilityState === 'hidden' ? 'hidden' : 'visible',
        forcedColors:forced?.matches === true,
        reducedMotion:reduced?.matches === true,
        saveData:connection?.saveData === true
      };
    }

    function render() {
      if (destroyed) return decision;
      decision = project(observation());
      if (body?.dataset) body.dataset.workshopAmbienceRender = decision.renderMode;
      if (create?.dataset) create.dataset.workshopAmbienceRender = decision.renderMode;
      if (hero?.dataset) hero.dataset.ambienceRender = decision.renderMode;
      if (status && status.textContent !== decision.status) status.textContent = decision.status;
      return decision;
    }

    const refresh = () => { render(); };
    const cleanup = [
      listen(d, 'visibilitychange', refresh),
      listen(forced, 'change', refresh),
      listen(reduced, 'change', refresh),
      listen(connection, 'change', refresh)
    ];

    render();
    return Object.freeze({
      update(patch = {}) {
        if (destroyed || !patch || typeof patch !== 'object' || Array.isArray(patch)) return decision;
        for (const key of UPDATE_KEYS) if (Object.hasOwn(patch, key)) state[key] = patch[key];
        return render();
      },
      snapshot() { return decision; },
      destroy() {
        if (destroyed) return;
        destroyed = true;
        for (const remove of cleanup.splice(0)) remove();
      }
    });
  }

  return Object.freeze({
    REQUESTS, ASSET_STATES, RENDER_MODES, EXECUTION_STATES,
    normalize, project, createController
  });
});
