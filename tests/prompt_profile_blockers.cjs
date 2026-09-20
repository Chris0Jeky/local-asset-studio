/* Exact-profile blocker wording: node tests/prompt_profile_blockers.cjs */
'use strict';
const assert = require('node:assert/strict');
const U = require('../app/static/studio-core.js');

function blocker(code, raw) {
  const [item] = U.promptBlockers({
    state: 'blocked',
    profile: {name: 'Exact anime profile', min_refs: 0, max_refs: 0},
    intent: {references: [], avoid: []},
    fields: {},
    errors: [{code, message: raw}],
    diagnostics: [],
  });
  return item;
}

for (const [code, raw, message, action] of [
  [
    'MODEL_SCORE_TOKEN_CONFLICT',
    'positive: score_* tokens need a reviewed rewrite or a different profile; text is retained unchanged',
    /score_\*|score token/i,
    /remove|rewrite|switch/i,
  ],
  [
    'MODEL_TAG_ORDER_CONFLICT',
    'Quality terms must form a final tail in this profile; review the existing order, no tags were moved',
    /quality.*(end|final)|final.*quality/i,
    /move|reorder|remove/i,
  ],
]) {
  const item = blocker(code, raw);
  assert.equal(item.code, code);
  assert.equal(item.blocking, true);
  assert.notEqual(item.message, raw, code + ' must not fall through to raw compiler prose');
  assert.match(item.message, message, code + ' must explain the user-visible conflict');
  assert.match(item.action, action, code + ' must name a direct repair');
  assert.doesNotMatch(item.action, /compiler detail/i, code + ' must not use the generic fallback action');
}

console.log('PASS: exact-profile blocker wording');
