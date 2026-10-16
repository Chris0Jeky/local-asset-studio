/** Pure integration reference. It performs no playback, requests or commands. */
export function motionDecision(input = {}) {
  const s = input && typeof input === 'object' ? input : {};
  const result = (mode, reason) => ({mode, reason, crossfadeMs: mode === 'local-loop' ? 240 : 0});
  if (s.hidden === true) return result('paused', 'hidden');
  if (s.inViewport === false) return result('paused', 'outside-viewport');
  if (s.hidden !== false || s.inViewport !== true) return result('static', 'visibility-unobserved');
  if (s.reducedMotion === true || s.forcedColors === true) return result('static', 'accessibility-preference');
  if (s.reducedMotion !== false || s.forcedColors !== false) return result('static', 'accessibility-unobserved');
  if (!['subtle', 'cinematic'].includes(s.choice)) return result('static', 'no-motion-opt-in');
  if (s.jobState !== 'idle') return result('static', 'runtime-active-or-unknown');
  if (s.saveData === true) return result('static', 'economy');
  if (s.userPaused === true) return result('paused', 'user-pause');
  if (s.saveData !== false || s.userPaused !== false) return result('static', 'preference-unobserved');
  if (s.approvedLocalLoop !== true || s.mediaReady !== true) return result('static', 'no-approved-ready-local-media');
  return result('local-loop', 'explicit-idle-local-motion');
}
