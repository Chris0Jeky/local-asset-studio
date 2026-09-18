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
    if (observation.reducedMotion)
      return ['Reduced-motion preference keeps ambience still.', 'Local static poster · motion disabled.'];
    if (observation.saveData)
      return ['Data-saving preference suppresses optional media work.', 'Local static poster · no optional transfer.'];
    if (observation.userPaused)
      return ['The user paused optional ambience motion.', 'Local static poster · optional motion paused.'];
    if (ACTIVE_EXECUTION.has(observation.executionState))
      return ['Runtime work is active or uncertain, so ambience remains still.', 'Local static poster · runtime-safe still mode.'];
    return ['An approved local poster is available.', 'Local static poster · no network.'];
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

  return Object.freeze({
    REQUESTS, ASSET_STATES, RENDER_MODES, EXECUTION_STATES,
    normalize, project
  });
});
