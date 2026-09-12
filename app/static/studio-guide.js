/* Opt-in in-context coach. Navigation only: never clicks a control or mutates a job. */
(function () {
  'use strict';
  const params = new URLSearchParams(location.search), id = params.get('guide');
  if (!id || !/^[a-z-]{1,40}$/.test(id)) return;
  const make = (tag, text) => { const node = document.createElement(tag); node.textContent = text; return node; };
  fetch('/api/workflow-studio/guides').then(r => { if (!r.ok) throw Error('Guide unavailable'); return r.json(); }).then(data => {
    const guide = data.guides.find(g => g.id === id); if (!guide) return;
    let index = Number(params.get('step') || 0); if (!Number.isInteger(index) || index < 0 || index >= guide.steps.length) index = 0;
    const step = guide.steps[index], main = document.querySelector('main'); if (!main) return;
    const panel = make('section', ''); panel.className = 'studio-guide-panel'; panel.setAttribute('aria-label', 'Guided walkthrough');
    const heading = make('h2', step.title), progress = make('p', `${guide.title} · step ${index + 1} of ${guide.steps.length}`), detail = make('p', step.detail), actions = make('div', '');
    heading.tabIndex = -1; progress.className = 'studio-guide-progress'; actions.className = 'studio-guide-actions';
    const addButton = (label, fn) => { const b = make('button', label); b.type = 'button'; b.onclick = fn; actions.append(b); };
    function go(next) { const url = new URL(guide.steps[next].route, location.origin); url.searchParams.set('guide', id); url.searchParams.set('step', String(next)); location.assign(url.pathname + url.search + url.hash); }
    if (index) addButton('Back', () => go(index - 1));
    const targetURL = new URL(step.route, location.origin);
    if (location.pathname !== targetURL.pathname || (targetURL.hash && location.hash !== targetURL.hash)) addButton('Open this step’s tool', () => go(index));
    addButton(index < guide.steps.length - 1 ? 'Next step' : 'Return to guided paths', () => index < guide.steps.length - 1 ? go(index + 1) : location.assign('/workflow-studio.html#journeys'));
    addButton('Pause guide', () => { document.querySelectorAll('.studio-guide-target').forEach(n => n.classList.remove('studio-guide-target')); panel.remove(); const url = new URL(location.href); url.searchParams.delete('guide'); url.searchParams.delete('step'); history.replaceState(null, '', url.pathname + url.search + url.hash); });
    const note = make('small', 'You decide when to run. Guide progress records navigation, not completed work.');
    panel.append(progress, heading, detail, actions, note); main.prepend(panel);
    try { localStorage.setItem('studio.guide.' + id, JSON.stringify({step: index})); } catch (_) {}
    setTimeout(() => { const target = step.target ? document.querySelector(step.target) : null; if (target && target.getClientRects().length && !target.closest('[hidden]')) { target.classList.add('studio-guide-target'); addButton('Show the control', () => { target.scrollIntoView({block: 'center', behavior: 'auto'}); if (target.matches('button,input,select,textarea,a')) target.focus({preventScroll: true}); }); } else if (step.target) note.textContent += ' The highlighted control appears after choosing a matching recipe or asset.'; }, 1000);
  }).catch(() => { /* The host Studio remains usable if guidance cannot load. */ });
})();
