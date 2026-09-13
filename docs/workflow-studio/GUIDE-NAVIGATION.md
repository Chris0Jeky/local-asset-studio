# Preserve the workbench while advancing a guide

Follow-up correctness check for #118 / PR #169, 13 September 2026.

The original coach navigated every stage with `location.assign`, including stages
on the same Studio page. That reload loses live reference file selections and the
Workflow builder's in-memory document/schema. Create's browser recovery requires
an explicit Restore, so the next stage could show defaults rather than the edited
prompt. The initial native-browser gate checked stage URLs but did not assert that
the workbench survived. A passing navigation assertion did not prove this property.

Same-page Next/Back now remount only the coach, update the stable stage URL through
history, and use the existing Studio view-navigation event where appropriate.
Current prompts, reference inputs, graph drafts, installed schema and shared-save
state remain with their existing owners. The previous coach cancels its own reads
and removes listeners/highlights before remounting; there is no parallel controller.
Browser history changes remount the matching stage without replacing the editor.

Moving to a different tool page still requires navigation. The guide asks the user
to save or export first and notes that local files may need reattaching; it neither
saves silently nor claims cross-page lossless preservation. Pause removes the coach
and its listeners without executing work. Guide state remains navigation only.

The native browser regression now checks an explicit window sentinel, exact prompt
text through Next, Back and browser history, a selected local file through the next
reference stage, and a modified workflow plus its loaded node schema through the
next builder stage. These complement the earlier 54 native assertions rather than
substituting an assumed autosave. The authoritative current-head CI result and
artifact are recorded in the PR; no local native-browser pass is inferred in the
source environment where navigation is blocked.

No model, job, ticket, installed runtime, user setting or creative decision is
changed. See [the guide architecture](EVIDENCE-GUIDES.md) for the evidence predicates,
source boundaries and remaining manual stages.

## Runtime-block review correction

Automated review identified a separate readiness inconsistency: the original coach
snapshot omitted `recipe.runtime_block`, so a healthy endpoint could hide the same
configured blocker that disabled Generate. The snapshot now retains that field and
the evidence predicate returns a blocked result before considering healthy signals.
The exact configured reason is displayed as text; no configuration is changed.

The added Node test fails against the prior predicate (observed `met`, expected
`blocked`) and passes after the fix. Native browser coverage sets a synthetic
blocker on the real selected-recipe object and checks that both Generate and the
coach are blocked. This is a fixture, not an alteration of owner runtime policy.
