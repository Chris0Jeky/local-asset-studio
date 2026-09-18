"""Temporary branch-local patcher for PR #634. Removed by the workflow that runs it."""
from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}")
    write(path, text.replace(old, new, 1))


workshop = "app/static/workshop.js"
replace_once(
    workshop,
    "    dirty:() => typeof draftDirty !== 'undefined' && !!draftDirty,\n",
    "",
)
replace_once(
    workshop,
    "        [Context.ACTIONS.INSPECT_OPERATION]:() => reveal(q('#jobProblems') || q('#jobProblemsHost') || results),\n"
    "        [Context.ACTIONS.RESOLVE_DRAFT_CONFLICT]:() => reveal(draftOptions || draftBar),\n",
    "",
)
replace_once(
    workshop,
    "        draft:{dirty:!!bridge.dirty?.(), conflict:false, pendingFiles:pending, references:refs}\n",
    "        draft:{conflict:false, pendingFiles:pending, references:refs}\n",
)

write(
    "docs/workshop/PRESENTATION-CONTEXT.md",
    '''# Read-only presentation context

`app/static/presentation-context.js` is the pure, immutable observation and intent boundary used by the production Create workshop. `studio-shell.js` loads it before `workshop.js`; the offline workshop prototype and exporter keep the same order.

The boundary does not own editable state or execution. Existing recipe, reference, draft, readiness, job and result owners publish bounded primitive observations. The boundary normalizes those observations, projects one primary intent plus optional secondary observations, and rejects stale or cross-workspace dispatch.

## What it never does

It does not:

- read the network or poll the page;
- persist prompts, paths, file objects, model settings or credentials;
- select a recipe or rewrite a prompt;
- stage, remove or relabel a source;
- submit, retry, cancel or approve a job;
- accept arbitrary selectors, URLs, callback payloads or model-generated commands.

Every projection returns `authorizesSubmission: false` and an empty `commands` array.

## Production capture

The workshop captures one snapshot during its existing scheduled `sync()` pass. It adds no second observer or timer. The snapshot contains:

- workspace and task identity;
- selected recipe and backend identity when known;
- exact source-slot IDs, human-readable roles and required flags from `reference-model.js`;
- source records expressed only as bounded IDs, slot IDs, roles and `selected` / `checked` / `staged` stages;
- pending-file count from the shared reference projection;
- current Generate readiness, the first existing blocker and current result count;
- `conflict: false` until an existing draft owner explicitly publishes a conflict observation.

Prompt text, file paths and image bytes never enter the context stamp or frozen projection. A monotonically increasing local revision makes an older intent stale after relevant UI evidence changes.

## Source projection

`reference-model.js` is the single owner of reference readiness semantics. The presentation bridge consumes its slots, references, pending count and `hasSources` result. It does not re-derive `reference_slots`, `last_reference`, board cardinality or staging.

The projected source summary keeps these cases distinct:

- required role with no selected source;
- selected source still checking or staging;
- staged source;
- source that does not match an available slot;
- optional source role with no source.

## Intent precedence

The pure module supports a wider vocabulary for consumers that can publish the corresponding evidence:

1. active or uncertain operation inspection;
2. draft-conflict review;
3. missing, pending or extra source review;
4. unknown or blocked readiness review;
5. existing output review;
6. known-ready Generate focus.

Unknown evidence remains unknown. The projection does not convert absence of evidence into backend failure or readiness.

## Production-reachable actions

The current production workshop captures only `blocked`, `ready` or `completed` execution and does not claim a draft conflict. Its closed action adapter therefore registers only four actions that the current capture can emit:

- `review-readiness` reveals the existing readiness disclosure;
- `review-sources` focuses the exact outstanding existing file input or source board;
- `focus-generate` focuses and scrolls the existing Generate button without activating it;
- `open-results` opens and focuses the existing Recent runs disclosure.

The pure boundary still defines `inspect-operation` and `resolve-draft-conflict` for tests and future consumers. Production does not register those handlers until the existing job or draft owner exposes matching observations. Keeping an action in the pure vocabulary is not a claim that the current Create capture can emit it.

## Safe local dispatch

```js
const adapter = Context.createActionAdapter({
  workspaceId: 'create',
  getContextStamp: () => currentView.contextStamp,
  actions: {
    [Context.ACTIONS.REVIEW_READINESS]: () => reveal(existingReadinessDetails),
    [Context.ACTIONS.REVIEW_SOURCES]: () => focusOutstandingExistingSource(),
    [Context.ACTIONS.FOCUS_GENERATE]: () => existingGenerateButton.focus(),
    [Context.ACTIONS.OPEN_RESULTS]: () => openExistingRecentRuns()
  }
});

const result = adapter.dispatch(currentView.primaryAction);
```

The adapter rejects unsupported action IDs, another workspace, stale context and missing handlers before invoking anything. Handlers receive no arbitrary payload. There is no submission action.

## Context stamps and late observations

`makeContextStamp(value)` produces a deterministic local FNV-1a identity over bounded primitive identity data. It is not encryption, provenance or authorization.

`createObservationGate()` supplies monotonically increasing tokens so a delayed A result is rejected after an A → B → A sequence. Matching text alone does not make an old observation current.

## Qualification boundary

Node contracts prove normalization, immutability, precedence, guarded dispatch and freshness. Browser and native-application tests prove script ordering, original-node identity, source focus, stale-intent rejection and zero implicit submissions against repository fixtures. They do not prove live backend readiness, GPU execution, model compatibility, artistic acceptance or every assistive-technology configuration. Real-machine acceptance remains under #539.
''',
)

readme_path = "docs/workshop/README.md"
readme = read(readme_path)
start = readme.index("## Contextual guidance\n")
end = readme.index("\n## Try the standalone prototype", start)
readme_section = '''## Contextual guidance

Immersive Studio renders one primary semantic action from the read-only presentation context:

- **Review readiness** reveals the existing readiness disclosure when Generate is blocked or readiness is unknown;
- **Review sources** focuses the exact outstanding existing file input or source board when source roles need attention;
- **Focus Generate** focuses the existing Generate control when it is ready, without activating it;
- **Open recent runs** opens the existing result disclosure when outputs are present.

The production action adapter maps only those four actions because the current capture publishes `blocked`, `ready` or `completed` execution and no draft-conflict claim. The pure context module retains operation-inspection and conflict-review vocabulary for consumers that can publish those states, but the current workshop does not register unreachable handlers.

Guidance never clicks Generate, changes a recipe, rewrites a prompt, stages a reference, retries an operation or asserts backend health. Its explanation identifies the observation it used, and a demoted readiness action retains the specific blocker description.
'''
write(readme_path, readme[:start] + readme_section + readme[end:])

design_path = "docs/workshop/DESIGN.md"
design = read(design_path)
start = design.index("## Context guidance contract\n")
end = design.index("\n## Visual and media policy", start)
design_section = '''## Context guidance contract

The production contextual rail has four reachable actions:

1. **Review readiness** reveals the existing readiness disclosure and its first reported blocker.
2. **Review sources** focuses the exact outstanding existing source input or reveals the current source board.
3. **Focus Generate** moves focus to the existing Generate button without invoking it.
4. **Open recent runs** opens and focuses the existing result disclosure.

The current production capture reports only `blocked`, `ready` or `completed` execution and hard-codes no draft conflict. It therefore does not register `inspect-operation` or `resolve-draft-conflict` handlers. Those IDs remain part of the pure presentation-context vocabulary for a future consumer only after an existing job or draft owner publishes matching evidence.

The rail cannot infer an installed model, fabricate VRAM/timing, change a recipe, mutate a source, submit a job or retry an uncertain operation. Its “Why this?” text states which current UI observation it used. Source, readiness and result actions reveal or focus existing owners; they do not create a second workflow path.
'''
write(design_path, design[:start] + design_section + design[end:])

spec_path = "docs/superpowers/specs/2026-09-18-workshop-context-guidance-design.md"
spec = read(spec_path)
start = spec.index("## Closed local action map\n")
end = spec.index("\n## Progressive compatibility", start)
spec_section = '''## Closed local action map

Production currently maps only semantic IDs its current capture can emit:

- `review-readiness` → reveal the existing readiness disclosure;
- `review-sources` → reveal and focus the exact outstanding reference board or file input;
- `focus-generate` → focus and scroll the existing Generate button;
- `open-results` → open and focus the existing Recent runs disclosure.

The pure context boundary also defines `inspect-operation` and `resolve-draft-conflict`. They remain valid projection vocabulary and test cases, but the current Create capture emits only `blocked`, `ready` or `completed` execution and explicitly publishes no conflict. Production does not register handlers for unreachable intents. A future integration must first obtain those observations from the existing job or draft owner rather than infer them in presentation code.

The adapter checks workspace and current context stamp before invoking a handler. A stale intent returns `stale-context`. There is no submit action.
'''
write(spec_path, spec[:start] + spec_section + spec[end:])

plan_notes = {
    "docs/superpowers/plans/2026-09-18-presentation-context.md": '''
## Completion note

The pure boundary was implemented and qualified in #581. The production integration that consumes it landed in the stacked guidance work, and #626 removed the duplicate reference-readiness derivation discovered during independent review. All publication and review gates above are complete for this delivered plan.
''',
    "docs/superpowers/plans/2026-09-18-workshop-context-guidance.md": '''
## Completion note

The integration was implemented and qualified in #582. Independent follow-up #626 moved reference readiness into one shared projection and corrected source focus, replacement confirmation and secondary blocker detail. The final accuracy follow-up removes unreachable production handlers and reconciles the delivered documentation. All implementation and publication gates above are complete.
''',
}
for path, note in plan_notes.items():
    text = read(path).replace("- [ ]", "- [x]")
    if "## Completion note" not in text:
        text = text.rstrip() + "\n" + note
    write(path, text)
