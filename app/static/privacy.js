/* Creation intent is independent of the Library/History view. No private draft text
   belongs in a persistent browser preference. Server records remain authoritative. */
(function () {
  'use strict';
  const stateKey = 'studio.privacy.session.v1';
  let sessionPrivate = false, override = null, view = 'regular', viewEpoch = 0, revision = 0;
  try {
    const saved = JSON.parse(sessionStorage.getItem(stateKey) || 'null');
    if (saved && typeof saved.sessionPrivate === 'boolean' && ['regular','private','all'].includes(saved.view)) {
      sessionPrivate = saved.sessionPrivate; view = saved.view;
      if (['regular','private'].includes(saved.override)) override = saved.override;
    }
  } catch (_) { /* A blocked preference store does not change safe defaults. */ }
  const creation = () => override || (sessionPrivate ? 'private' : 'regular');
  function valid(value, all = false) {
    if (!(all ? ['regular','private','all'] : ['regular','private']).includes(value)) throw Error('Choose a valid privacy scope.');
    return value;
  }
  function render() {
    const session = document.querySelector('#privateSession'), draft = document.querySelector('#creationPrivacy');
    if (session) session.checked = sessionPrivate;
    if (draft) draft.value = override || 'session';
    document.querySelectorAll('[data-privacy-scope]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.privacyScope === view));
      button.classList.toggle('active', button.dataset.privacyScope === view);
    });
    const status = document.querySelector('#privacyStatus');
    if (status) status.textContent = creation() === 'private'
      ? 'This creation is private. It stays out of Regular history and Library.'
      : 'This creation is regular.';
  }
  function change(reason, update) {
    const previousCreation = creation(), previousScope = view;
    update(); revision++;
    if (previousScope !== view) viewEpoch++;
    try { sessionStorage.setItem(stateKey, JSON.stringify({sessionPrivate, override, view})); } catch (_) {}
    render();
    document.dispatchEvent(new CustomEvent('studio:privacy-change', {detail:{
      creation:creation(), scope:view, previousCreation, previousScope, reason,
    }}));
  }
  function setSession(enabled) {
    if (typeof enabled !== 'boolean') throw Error('Private session must be on or off.');
    change('session', () => {
      sessionPrivate = enabled; override = null;
      if (view !== 'all') view = enabled ? 'private' : 'regular';
    });
  }
  function setCreation(value) {
    if (value !== null && value !== 'session') valid(value);
    change('draft', () => { override = value === 'session' ? null : value; });
  }
  function setScope(value) { valid(value, true); if (view !== value) change('scope', () => { view = value; }); }
  function capture() { return {scope:view, privacy:creation(), revision}; }
  function submitted(captured) {
    // A delayed acknowledgment cannot replace a choice made for the next creation.
    if (captured && captured.revision !== revision) return;
    if (override !== null) change('submitted', () => { override = null; });
  }
  function storageKey(base, classification = creation()) { return base + (valid(classification) === 'private' ? '.private' : ''); }
  function storage(classification = creation()) { return valid(classification) === 'private' ? sessionStorage : localStorage; }
  function allows(record, scope = view) {
    const classification = record?.privacy === undefined ? 'regular' : record.privacy;
    return ['regular','private'].includes(classification) && (scope === 'all' || scope === classification);
  }
  function headers(captured = capture(), supplied) {
    const result = new Headers(supplied || {});
    if (!result.has('X-Studio-Privacy')) result.set('X-Studio-Privacy', valid(captured.scope, true));
    else valid(result.get('X-Studio-Privacy'), true);
    if (!result.has('X-Studio-Creation-Privacy')) result.set('X-Studio-Creation-Privacy', valid(captured.privacy));
    else valid(result.get('X-Studio-Creation-Privacy'));
    return result;
  }
  function localURL(path) {
    try {
      const base = new URL(location.href), url = new URL(typeof path === 'string' ? path : path.url, base);
      return url.origin === base.origin && url.pathname.startsWith('/api/') ? url : null;
    } catch (_) { return null; }
  }
  async function scopedFetch(path, options) {
    const url = localURL(path);
    if (!url) return window.fetch(path, options);
    const context = capture(), epoch = viewEpoch, method = String(options?.method || path?.method || 'GET').toUpperCase();
    const supplied = new Headers(options?.headers || path?.headers || {}), query = url.searchParams.getAll('privacy');
    if (query.length > 1) throw Error('Supply exactly one privacy scope.');
    if (query.length) {
      const scope = valid(query[0], true);
      if (supplied.has('X-Studio-Privacy') && supplied.get('X-Studio-Privacy') !== scope) throw Error('Privacy query and header disagree.');
      context.scope = scope; // A media URL chooses a read scope, never a creation destination.
    }
    const sensitive = /^\/api\/(?:jobs(?:\/|$)|assets(?:\/|$)|workspace(?:\/|$)|collections(?:\/|$)|image\/|uploads?\/|exports\/)/.test(url.pathname);
    const read = sensitive && (method === 'GET' || method === 'HEAD' || ['/api/assets/selection','/api/assets/recovery/observe'].includes(url.pathname));
    const current = () => { if (read && epoch !== viewEpoch) throw Error('The privacy view changed. Refresh this view to continue.'); };
    const response = await window.fetch(path, {...options, headers:headers(context, supplied)});
    current();
    if (!read) return response; // Never discard a mutation acknowledgment or make it look safe to retry.
    return new Proxy(response, {get(target, key) {
      const value = Reflect.get(target, key, target);
      if (['json','text','blob','arrayBuffer','formData'].includes(key) && typeof value === 'function') return async (...args) => {
        current(); const result = await value.apply(target, args); current(); return result;
      };
      return typeof value === 'function' ? value.bind(target) : value;
    }});
  }
  function mediaUrl(path, record) {
    if (!path || record?.privacy !== 'private') return path;
    const url = localURL(path); if (!url) return path;
    url.searchParams.set('privacy','private');
    return url.pathname + url.search + url.hash;
  }
  window.StudioPrivacy = {creation, scope:()=>view, capture, submitted, setSession, setCreation, setScope,
    storageKey, storage, allows, headers, fetch:scopedFetch, mediaUrl};
  function wire() {
    document.querySelector('#privateSession')?.addEventListener('change', event => setSession(event.target.checked));
    document.querySelector('#creationPrivacy')?.addEventListener('change', event => setCreation(event.target.value));
    document.querySelectorAll('[data-privacy-scope]').forEach(button => button.addEventListener('click', () => setScope(button.dataset.privacyScope)));
    render();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire); else wire();
})();
