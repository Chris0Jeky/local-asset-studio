/* Connect the local ambience policy to the existing workshop presentation. */
(function (root, factory) {
  const AmbiencePolicy = typeof module === 'object' && module.exports
    ? require('./workshop-ambience-policy.js') : root?.StudioWorkshopAmbiencePolicy;
  const api = factory(AmbiencePolicy);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else if (root) root.StudioWorkshopAmbience = Object.freeze(api);
  if (!root?.document || !AmbiencePolicy) return;
  const start = () => api.mount(root);
  if (root.document.readyState === 'loading') root.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})(typeof window !== 'undefined' ? window : null, function (AmbiencePolicy) {
  'use strict';

  const ASSET_STATES = new Set(['available', 'missing', 'unknown']);
  const REQUESTS = new Set(['none', 'night-shift', 'quiet-morning']);

  function mount(w, options = {}) {
    const d = w?.document;
    const q = selector => d?.querySelector(selector);
    const create = options.create || q('#createView');
    const hero = options.hero || q('#workshopAmbienceHero');
    if (!d || !create || !hero || typeof AmbiencePolicy?.createController !== 'function') return null;
    if (create.__workshopAmbience) return create.__workshopAmbience;

    if (!q('#workshopAmbiencePolicyStyles')) {
      const css = d.createElement('link');
      css.id = 'workshopAmbiencePolicyStyles';
      css.rel = 'stylesheet';
      css.href = '/static/workshop-ambience.css';
      d.head.append(css);
    }

    let status = options.status || q('#workshopAmbienceStatus');
    if (!status) {
      status = d.createElement('p');
      status.id = 'workshopAmbienceStatus';
      status.className = 'wk-ambience-status';
      status.setAttribute('role', 'status');
      status.setAttribute('aria-live', 'polite');
      (hero.querySelector('.wk-hero-copy') || hero).append(status);
    }

    const styles = options.styles || q('#workshopImmersiveStyles');
    const explicitAssetState = ASSET_STATES.has(options.assetState);
    function stylesheetState(node) {
      if (!node) return 'unknown';
      try { return node.sheet ? 'available' : 'unknown'; }
      catch (_) { return 'unknown'; }
    }
    let assetState = explicitAssetState ? options.assetState : stylesheetState(styles);
    let scheduled = false;

    function requested() {
      const value = create.dataset?.workshopAmbience || d.body?.dataset?.workshopAmbience;
      return REQUESTS.has(value) ? value : 'none';
    }

    function executionState() {
      const message = [q('#status')?.textContent, q('#jobProblemsHost')?.textContent]
        .filter(Boolean).join(' ').toLowerCase();
      if (/uncertain|outcome could not|could not confirm|unknown outcome/.test(message)) return 'uncertain';
      if (/submitting|queued|running|generating|in progress/.test(message)) return 'running';
      if (q('#generate')?.disabled) return 'blocked';
      if (q('#gallery .imageCard')) return 'completed';
      return 'ready';
    }

    function internetState() {
      if (w.navigator?.onLine === true) return 'online';
      if (w.navigator?.onLine === false) return 'offline';
      return 'unknown';
    }

    function backendState() {
      const text = q('#health')?.textContent?.toLowerCase() || '';
      if (/ready|connected|online/.test(text)) return 'ready';
      if (/down|offline|failed|unavailable|disconnected/.test(text)) return 'down';
      return 'unknown';
    }

    const controller = AmbiencePolicy.createController(w, {
      body:d.body,
      create,
      hero,
      status,
      initial:{
        requested:requested(),
        assetState,
        executionState:executionState(),
        internetState:internetState(),
        backendState:backendState(),
        userPaused:false
      }
    });

    function refresh() {
      const ambienceDecision = controller.update({
        requested:requested(),
        assetState,
        executionState:executionState(),
        internetState:internetState(),
        backendState:backendState()
      });
      hero.hidden = !ambienceDecision.heroVisible;
      return ambienceDecision;
    }

    const schedule = () => {
      if (scheduled) return;
      scheduled = true;
      w.queueMicrotask(() => { scheduled = false; refresh(); });
    };

    const styleCleanup = [];
    if (!explicitAssetState && styles?.addEventListener) {
      const available = () => { assetState = 'available'; refresh(); };
      const missing = () => { assetState = 'missing'; refresh(); };
      styles.addEventListener('load', available);
      styles.addEventListener('error', missing);
      styleCleanup.push(() => styles.removeEventListener('load', available));
      styleCleanup.push(() => styles.removeEventListener('error', missing));
    }

    const observer = new w.MutationObserver(schedule);
    observer.observe(d.body, {attributes:true, attributeFilter:['data-workshop-ambience']});
    observer.observe(create, {attributes:true, attributeFilter:['hidden','data-workshop-ambience']});
    const generate = q('#generate');
    if (generate) observer.observe(generate, {attributes:true, attributeFilter:['disabled']});
    for (const node of [q('#gallery'), q('#status'), q('#jobProblemsHost'), q('#health')]) {
      if (node) observer.observe(node, {childList:true, subtree:true,characterData:true});
    }

    const api = Object.freeze({
      refresh,
      snapshot:() => controller.snapshot(),
      setAssetState(value) {
        assetState = ASSET_STATES.has(value) ? value : 'unknown';
        return refresh();
      },
      destroy() {
        observer.disconnect();
        for (const remove of styleCleanup.splice(0)) remove();
        controller.destroy();
        if (create.__workshopAmbience === api) delete create.__workshopAmbience;
      }
    });
    create.__workshopAmbience = api;
    refresh();
    return api;
  }

  return Object.freeze({mount});
});
