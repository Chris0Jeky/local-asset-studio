/* The one reference readiness model. Pure: it reads recipe, records and file inputs; it never writes DOM or submits. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.StudioReferenceModel = Object.freeze(api);
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // referencesReady() used to live in references.js and workshop.js re-derived a second, drifting copy of the
  // same semantics (#610 items 1 and 3). Both now read this projection, so `required`, board cardinality and
  // last_reference are decided once. `ready` is the Generate gate and is bit-identical to the old function for
  // every shape a catalog can produce; a malformed non-array reference_slots degrades to ready instead of
  // throwing, where the old expression read a string's length. prepare() re-validates server side either way.
  const object = value => !!value && typeof value === 'object' && !Array.isArray(value);
  const token = (value, fallback) => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(value.trim()) ? value.trim() : fallback;
  const label = (value, fallback) => typeof value === 'string' && value.trim() ? value.trim().slice(0, 120) : fallback;
  const counted = value => { const n = Number(value); return Number.isSafeInteger(n) && n >= 0 ? n : 0; };
  const BLOCKER = Object.freeze({code:'references', message:'Attach every required reference before starting.', target:'references'});

  function deepFreeze(value) {
    if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
    for (const item of Object.values(value)) deepFreeze(item);
    return Object.freeze(value);
  }

  function project(input = {}) {
    const source = object(input) ? input : {};
    const recipe = object(source.recipe) ? source.recipe : null;
    const records = Array.isArray(source.records) ? source.records : [];
    const uploads = counted(source.pending);
    const picked = object(source.picked) ? source.picked : {};
    const pickedSlots = Array.isArray(picked.slots) ? picked.slots : [];
    const authored = recipe && Array.isArray(recipe.reference_slots) ? recipe.reference_slots : null;
    const board = authored && recipe.reference_board ? recipe.reference_board : null;
    const uploaded = source.uploaded || null, lastUploaded = source.lastUploaded || null;
    const slots = [];
    if (authored) for (const [index, slot] of authored.entries()) {
      const record = records[index], missing = !!record?.missing, staged = !!record?.file && !missing;
      slots.push({id:token(slot?.id || slot?.key, 'reference-'+(index+1)),
        role:label(record?.role || slot?.role, 'Reference '+(index+1)), kind:board ? 'board' : 'slot', index,
        // A board recipe is gated on reference_board.min across the board, not slot by slot (#582 / fe9b888).
        required:!board && slot?.required !== false, staged, pending:!staged && (!!pickedSlots[index] || missing), missing});
    }
    // A slot-less reference is not a referencesReady() prerequisite: the recipe's example stands until replaced.
    // studio-workbench.js also reports sourceMissing for one with a continuation_operation; that stays its own
    // advisory, and readiness keeps primacy there, so the rail shows its specific message rather than this slot.
    else if (recipe?.reference) slots.push({id:'reference', role:label(recipe.reference_label, 'Reference'), kind:'input', index:null,
      required:false, staged:!!uploaded, pending:!uploaded && !!picked.reference, missing:false});
    // #610 item 1: last_reference is a real slot alongside an authored board, not only in the slot-less shape.
    // It is required exactly where studio-workbench.js reports sourceMissing, so nothing new is invented here.
    if (recipe?.last_reference) slots.push({id:'last-reference', role:label(recipe.last_reference_label, 'Last frame'), kind:'input', index:null,
      required:!source.continuation && (!!recipe.reference_board || !!recipe.continuation_operation),
      staged:!!lastUploaded, pending:!lastUploaded && !!picked.lastReference, missing:false});
    const references = slots.filter(slot => slot.staged || slot.pending).map(slot => ({
      id:'source-'+slot.id, slotId:slot.id, role:slot.role, stage:slot.staged ? 'staged' : 'selected'}));
    const filled = records.filter(r => r.file && !r.missing).length;
    const ready = !authored?.length ? true
      : uploads || records.length !== authored.length ? false
        : board ? filled >= (board.min ?? 1) && !records.some(r => r.missing) : filled === records.length;
    return deepFreeze({
      mode:authored?.length ? (board ? 'board' : 'slots') : slots.length ? 'inputs' : 'none',
      slots, references, board:board ? {min:board.min ?? 1, filled, total:authored.length} : null,
      pendingFiles:Math.max(references.filter(r => r.stage !== 'staged').length, uploads),
      // Restores the pre-#582 disjunction: a carried source, a claimed library asset and a missing saved
      // record all still count as work the recipe picker must confirm before it clears them (#610 item 3).
      hasSources:references.length > 0 || counted(source.claimedAssets) > 0 || !!uploaded || !!lastUploaded,
      ready, blockers:ready ? [] : [{...BLOCKER}]
    });
  }

  // The only reader of live Studio state. Script-scope `let`s in app.js and references.js are not window
  // properties, so they are reached by bare name; every access is a read.
  function live(scope) {
    const d = scope?.document || (typeof document !== 'undefined' ? document : null);
    const recipe = typeof selected === 'undefined' ? null : selected;
    const chosen = selector => !!d?.querySelector(selector)?.files?.length;
    return project({
      recipe,
      records:typeof referenceRecords !== 'undefined' && Array.isArray(referenceRecords) ? referenceRecords : [],
      pending:typeof referencePending !== 'undefined' ? referencePending : 0,
      uploaded:typeof uploaded !== 'undefined' ? uploaded : null,
      lastUploaded:typeof lastUploaded !== 'undefined' ? lastUploaded : null,
      claimedAssets:typeof parentAssets !== 'undefined' && Array.isArray(parentAssets) ? parentAssets.length : 0,
      continuation:typeof continuationState !== 'undefined' && !!continuationState,
      picked:{slots:(Array.isArray(recipe?.reference_slots) ? recipe.reference_slots : []).map((_, index) => chosen('[data-ref-file="'+index+'"]')),
        reference:chosen('#reference'), lastReference:chosen('#lastReference')}
    });
  }

  return Object.freeze({project, live});
});
