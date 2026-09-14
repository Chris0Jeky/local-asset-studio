/* Pure observation rules. A met prerequisite is never creative acceptance. */
(function(root){
  'use strict';
  const object = x => !!x && typeof x === 'object' && !Array.isArray(x);
  const result = (state, message) => ({state, message});
  const unknown = message => result('unknown', message || 'Not checked yet. The guide is reading current evidence.');
  function evaluate(check, s = {}) {
    const met = text => result('met', text), blocked = text => result('blocked', text);
    if (check === 'manual') return result('manual', 'This step needs your judgment. Next records navigation only.');
    if (['recipe', 'reference_recipe', 'prompt', 'references', 'readiness'].includes(check) && !s.recipe)
      return blocked('Choose a recipe in Create first.');
    if (check === 'recipe') return met('Recipe selected: ' + s.recipe.id + '. Selection is not a readiness check.');
    if (check === 'reference_recipe') return s.references?.supported ? met('A reference-capable recipe is selected. Inspect its source and editing mechanism.') : blocked('Choose a recipe with reference inputs; a text-only recipe cannot preserve a supplied source.');
    if (check === 'prompt') return s.prompt_present ? met('Wording is present. Its suitability and intended invariants still need your review.') : blocked('Describe the result or instruction in the prompt field.');
    if (check === 'references') {
      const r = s.references;
      if (!r?.supported) return blocked('This recipe has no supported reference input. Choose a reference recipe first.');
      if (r.pending) return unknown('Reference upload or validation is still pending.');
      if (r.selected && !r.attached) return unknown('A local source is selected but not yet staged. Use normal recipe preparation; the guide does not upload it.');
      if (!r.attached || r.missing) return blocked('Attach every required reference. Missing sources are not replaced by recipe examples.');
      if (r.mask) return unknown('A source is attached, but this guide does not validate RGBA mask coverage. Inspect the mask through the recipe tools.');
      return met('Required sources are attached in the workbench. Bytes, roles and compatibility are rechecked by the normal preparation path.');
    }
    if (check === 'readiness') {
      if (s.recipe.runtime_block) return blocked('This recipe is blocked by runtime configuration: ' + (typeof s.recipe.runtime_block === 'string' ? s.recipe.runtime_block : 'inspect its requirement notice in Create.'));
      if (s.switching) return blocked('An environment switch is in progress. Wait for it to finish; the guide will not switch it.');
      const h = s.health;
      if (!object(h)) return unknown('Readiness is unavailable. A failed check is not evidence that the backend is ready.');
      if (h.online === false) return blocked('ComfyUI reports offline. Inspect Models & setup; no restart was requested here.');
      if (h.worker_alive === false) return blocked('The Studio worker is unavailable. Do not start a run until it is restored.');
      if (h.online !== true || h.schema_available !== true || h.worker_alive !== true || !object(h.missing_models)) return unknown('Backend, worker or node-schema readiness is not fully known.');
      const b = s.backend_report;
      if (!s.backend || !object(b) || !Array.isArray(b.profiles) || b.busy !== false) return unknown('The active environment is not fully known. Inspect Models & setup.');
      const profile = b.profiles.filter(p => object(p) && p.id === b.active);
      if (b.active !== s.backend || profile.length !== 1 || typeof profile[0].url !== 'string' || profile[0].url !== h.comfy_url) return unknown('Readiness and environment identities differ. Recheck after the environment settles.');
      if (s.backend !== s.recipe.backend_id) return blocked('This recipe needs ' + s.recipe.backend_id + '; the active environment is ' + s.backend + '. Switching is your decision.');
      const missing = h.missing_models[s.recipe.id] ?? [];
      if (!Array.isArray(missing)) return unknown('Dependency readiness was malformed. Inspect the recipe requirements.');
      if (missing.length) return blocked('Missing dependencies: ' + missing.map(String).join(', '));
      return met('Current backend, worker and reported dependencies are ready. This does not certify memory fit, custom-node behavior or generation quality.');
    }
    if (check === 'schema') return s.authoring?.schema_loaded ? met('Installed node definitions are loaded. Native-only behavior may still need an adapter.') : blocked('Load the installed node catalog in Workflow builder.');
    if (check === 'graph_check') {
      if (!s.authoring?.document_present) return blocked('Import or create a workflow first.');
      if (!s.authoring.schema_matches) return blocked('Load the correct environment and explicitly reconcile the draft schema.');
      if (s.authoring.checked_valid === null) return blocked('Use Check connections after the latest draft change.');
      return s.authoring.checked_valid === true ? met('The current draft passed static connection checks. Runtime validation and resources are separate.') : blocked('The current connection check has errors. Follow the node/input diagnostics.');
    }
    if (check === 'saved') {
      if (!s.project?.id) return blocked('Use Save to Workspace or open a saved workflow.');
      if (s.project.blocked || s.project.conflict) return unknown('Resolve the pending save or conflict before preparing a new run.');
      return s.project.dirty ? blocked('Local edits are unsaved. Save deliberately or keep them as a separate copy.') : met('Attached to Workspace revision ' + s.project.revision + '. Saving did not run it.');
    }
    if (check === 'selection') return Number.isSafeInteger(s.selection) && s.selection > 0 ? met(s.selection + ' assets selected. Selection does not establish that they are accepted.') : blocked('Select the source assets in the Asset library.');
    if (check === 'output' || check === 'review') {
      const j = s.job;
      if (!s.job_id) return unknown('Choose the specific run to inspect. The guide never assumes the latest run belongs to this task.');
      if (!object(j) || j.id !== s.job_id || !Array.isArray(j.outputs) || !j.outputs.every(object)) return unknown('The selected run evidence is unavailable or malformed. Keep its original identity.');
      if (['uncertain','submitting','running','waiting','queued'].includes(j.status)) return unknown('Selected run is ' + j.status + '. Observe the original job; do not create a replacement to retry.');
      if (!['completed','partial','failed','cancelled'].includes(j.status)) return unknown('The selected run has an unrecognized state.');
      if (!j.outputs.length) return blocked('No output is recorded for this run (' + j.status + '). Engine completion alone is not output evidence.');
      if (check === 'output') return met(j.outputs.length + ' output records found for the selected run (' + j.status + '). Inspect the files; this is not art acceptance.');
      if (!Array.isArray(s.assets)) return unknown('Asset review records are unavailable.');
      const decisions = [];
      for (const output of j.outputs) {
        const matches = s.assets.filter(a => object(a) && typeof output.asset_id === 'string' && a.id === output.asset_id && a.job_id === j.id);
        if (matches.length !== 1 || !['unreviewed','selected','needs_work','rejected'].includes(matches[0].review)) return unknown('An output has no unique matching Workspace review record.');
        decisions.push(matches[0].review);
      }
      if (decisions.includes('unreviewed')) return blocked(decisions.filter(x => x !== 'unreviewed').length + ' of ' + decisions.length + ' output reviews recorded. Review the remaining outputs yourself.');
      return met('Review decisions recorded: ' + decisions.join(', ') + '. Recording a rejection also completes review; the guide never approves artwork.');
    }
    return unknown('This step has no evidence adapter yet. Continue manually without a completion claim.');
  }
  const targetSelectors = step => [step.target, ...(step.alternatives || [])]
    .filter(selector => typeof selector === 'string' && /^#[A-Za-z][A-Za-z0-9_-]{0,95}$/.test(selector));
  function targetVisible(node, doc) {
    return !!(node && node.getClientRects().length && !node.closest('[hidden]') &&
      !['hidden','collapse'].includes(doc.defaultView?.getComputedStyle(node).visibility));
  }
  function visibleTarget(step, doc) {
    for (const selector of targetSelectors(step)) {
      const node = doc.getElementById(selector.slice(1));
      if (targetVisible(node, doc)) return node;
    }
    return null;
  }
  function revealTarget(step, doc) {
    for (const selector of targetSelectors(step)) {
      const node = doc.getElementById(selector.slice(1));
      if (!node) continue;
      let disclosure = node.closest?.('details:not([open])') || null;
      while (disclosure) {
        disclosure.open = true;
        disclosure = disclosure.parentElement?.closest?.('details:not([open])') || null;
      }
      if (targetVisible(node, doc)) return node;
    }
    return null;
  }
  function route(value, origin) {
    const u = new URL(value, origin);
    if (u.username || u.password || u.origin !== origin || !['/', '/workflow-studio.html', '/av.html', '/voice.html'].includes(u.pathname) || u.search) throw Error('Unsupported guide route');
    return u;
  }
  const api = {evaluate, unknown, visibleTarget, revealTarget, route};
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.StudioGuideState = Object.freeze(api);
})(globalThis);
