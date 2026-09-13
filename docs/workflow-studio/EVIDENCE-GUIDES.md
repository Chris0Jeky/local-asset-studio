# Evidence-aware guided paths

Continuation of #118, 13 September 2026. This builds on the existing opt-in coach,
not another navigation shell, queue or execution controller. Initial source was
main `aebe10c58c7fa3ce8f89276740096eaf98c2cc20`, including merged #156/#157/#160/#161.
The separate source-continuation work (#164) owns reference handoff mutations;
this guide reads the workbench without replacing that mechanism.

## Use it

Open **Guided workflows**, choose a path, and start or resume it. The existing
seven paths remain: first image, character/reference editing, comparisons, scenes,
game assets, node workflows and headless agents. **Show the control** looks again
at the current tool, including controls that appeared after selecting a recipe.
It focuses the control without activating it. Reference steps support either the
role board or the ordinary first/last reference controls, as appropriate.

**Check this step** observes a prerequisite. It never presses Generate, uploads a
file, switches environments, installs resources, saves a workflow or accepts art.
The result has both a text label and a distinct presentation:

| Label | Meaning |
| --- | --- |
| Observed | This specific prerequisite has current supporting evidence. |
| Needs attention | A required selection/value/result is absent or a known blocker exists. |
| Not known | Not checked, changed during a check, unavailable or unsupported evidence. |
| Your decision | A human judgment or a step with no automatic evidence predicate. |

For output/review steps, explicitly choose the run being inspected. The list shows
up to 200 recent runs and labels that bound; the guide never guesses that the
latest job belongs to the current task. A retained selection can be checked again
on resume. A completed job without output records is not treated as a produced
asset. A partial/failed run with outputs can have useful output evidence without
being presented as successful inference.

Review checks join each output's asset ID to its unique matching Workspace job
record. `selected`, `needs_work` and `rejected` are all recorded decisions;
`unreviewed` is not. **Recording review is not creative acceptance.** The coach
never changes any of these values or interprets licensing decisions.

## Architecture and contracts

`studio_workflow/guides.py` publishes version 2 with stable per-path stage IDs,
read-only predicate names and feature-owned target IDs. Old numeric-step links
remain supported. New navigation/resume links carry both forms. The manifest
copies shared steps before assigning IDs and never mutates a shared definition.
Resume stores only path position and an explicitly chosen run identity, not prompt
text, drafts, successful evidence or approval.

`studio-guide-state.js` is a pure predicate/target/route module. `studio-guide.js`
collects fresh snapshots on explicit checks. Its only startup request is GET of
the guide manifest. Network observations use the existing GET health, backend,
job and Workspace routes. These existing backend routes may perform their normal
readiness probes; the coach has no direct ComfyUI connection. There are no new
server endpoints, executors, stores or automatic polling loops.

Readiness requires explicit online, worker, schema and dependency data and matching
observed backend/endpoint identities. A timeout, malformed or incomplete reply is
unknown, never ready. The result explicitly does not certify memory fit, custom
validation or output quality. Final runtime admission remains authoritative.

A selected local file is distinguished from a staged filename; masks need their
existing dedicated validation, not an inferred pass. The graph coach reads the
builder's frozen `authoringStatus()` projection of existing current connection
checks; edits or schema changes invalidate those checks as before. Saved-state
coaching reads the existing shared-document binding, including dirty, pending and
conflict states. It does not save or run automatically.

Epochs plus local snapshot equality discard delayed results after recipe, input,
run selection, schema or shared-document changes. Navigation/source text is data,
rendered using textContent. Targets are same-document visible IDs; route links are
restricted to the existing local tools. Checks have a ten-second abort deadline
and a 2 MiB post-read display bound; this is not a streaming network-byte limit.
Pause aborts owned reads, removes listeners/highlights and retains position only.

## Verification and release limits

- `python -m unittest discover -s tests -p test_studio_guide.py -v`: manifest
  version/stage/feature-anchor audit plus 22 Node evidence-rule contracts.
- `python tests/studio_guide_browser.py --out .runtime/guide-proof`: actual Studio
  pages/scripts/styles on the existing synthetic HTTP fixture, all seven paths,
  delayed target discovery, HTTP failures, changed inputs, explicit run selection,
  human review, graph-check invalidation, keyboard navigation, resume, 390px and
  200% zoom. The fixture never exposes a real Comfy runtime.
- `Guided journey browser` CI installs test-only pinned Playwright and uses native
  HTTP/localStorage. The source environment blocks localhost browser navigation;
  no local native-browser pass is claimed. Read the recorded hosted result.
- The full unittest suite and repository validator remain separate gates. A
  browser fixture is neither an owner-run creative journey nor inference evidence.

No owner settings, models, downloads, queues or HUMAN_TODO values are changed.
Intent-to-recipe recommendations, mask geometry, comparison/scene/export-specific
completion predicates and an owner-run journey remain #118 work. Manual stages
say so; there is no overall automatic "completed" badge or hidden action.

## Primary-source research

[W3C status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html),
inspected 13 September 2026, informs the polite status region and separate explicit
focus action. Status changes do not themselves move focus. Reduced-motion and
forced-colour treatment extend the existing coach styling rather than introducing
an animated/modal tour. These implementation choices are not a claim of full WCAG
conformance or a completed assistive-technology audit.
