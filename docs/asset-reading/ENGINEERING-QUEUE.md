# Difficult engineering work: 20 September 2026

This is a prioritization/ownership snapshot, not another backlog or an assertion
that all acceptance has been delivered. Inspection started at main
`f41855f1851ffce156c883962d0c4cca38ad3765`; the uploaded source was
`f8fcc40f7388c23d13309c20c2776017a20004b2`. The only intervening main change was the
docs-only #704 merge. The complete local source tree was reconciled to main before
implementation. Recheck live heads/comments before taking another slice.

## Highest-complexity themes

| Theme / existing issue owners | Why it is difficult | Current disposition / useful next boundary |
| --- | --- | --- |
| Shared authored execution, #122 / #123 / #65 | Immutable graph/model/input identities, approval/budgets, one executor, persisted intent, and ambiguous remote outcomes must agree without claiming exactly-once inference. | Continue through existing shared commands, never a raw prompt proxy or another queue. Separate deterministic fault evidence from owner-run execution promotion. |
| Stage admission and resource cleanup, #178 / #306 | Reservations, process ownership, cleanup, delayed evidence and retained holds interact across restart and uncertainty. | #656 / #674 / #679 already form an implementation line. Do not duplicate it; reconcile parent drift before extending. Ordinary observation and persistence fixes are separately covered by #701 / #705 (#608 / #703). |
| Narration mutation and long-form lifecycle, #671 / #635–#641 | Current-predecessor CAS, receipt replay, cross-process locks, child-project uncertainty, sample-exact assembly and derived exports have different owners. | #671 was already claimed on `codex/671-narration-registry-cas` over #676. The #653 → #669 → #676 and #688 → #700 → #707 lines are active. #673 still needs a genuinely pinned producer and workstation evidence, not only profile metadata. |
| Bounded library reads and persistent selection, #177 | Stable pagination under mutation cannot equate off-page with missing; Workspace replacement, query drift, metadata bloat and long-lived selections must remain distinct. | **Core landed in #719.** #222/#233/#273 already cover membership-count work, selection disclosure and DOM continuity. Keep existing consumers unchanged, run the serialized full-suite gate, then add one stacked read-only transport/client slice. |
| Recovery lifecycle, #388 / #392–#395 | Exact immutable pending commands must survive local drafts, tab closure, partial targets, historical receipts, Workspace replacement and late responses. | #684 covers collection recovery; #698 / #706 cover the opt-in asset shelf/import boundary. Broader lifecycle/accessibility, file-staging and setup-history acceptance remain separate; do not create another recovery store. |
| Protected repair geometry and publication, #244 / #245 / #248 / #251 | Source normalization, resampling, effective write support, protected hidden RGB/alpha, scope review and stale-source publication must all describe the same pixels. | Normalization/scaled-pixel/scope foundations are already delivered by #264/#268/#274/#279/#284; #702 covers another capture-race boundary. Native mask-consumer registration and a privately reviewed neural repair cannot be inferred from CPU fixtures. |
| Revisioned commands and durable receipts, #314 | Extract common consistency values without erasing domain validation, copying lifecycle machines or pretending file effects are SQLite-atomic. | The shared toolkit is present on main; use its proven domain boundaries rather than restart the extraction. Preserve two-domain real-SQLite fault/response compatibility before extending it. |
| Immutable provider evidence, #438 / #694 | A mutable conditional-GET cache is not historical evidence retention. Changed bodies, 304s, deduplication, quota, corruption and concurrent publication need exact digest semantics. | #579 / #687 / #693 cover the transport line; #694 records the separate historical-payload gap. The adult-illustration programme remains subject to its existing owner review; no model downloads or promotion are implied. |

## Sequential delivery rule for this pass

One owned line: #177 core first, transport/client as a child only after core tests.
No edits to other active branches, no new umbrella issues, no automatic merges,
no runtime/model installations and no changes to HUMAN_TODO decisions. Draft PRs
are used as requested. The following grid/media integration should consume these
read contracts and preserve #233/#273's identities and selection/focus behavior.

## Evidence still requiring the actual workstation

The native host-memory failures in #77/#89, model output quality, original narration
identity/long-listening acceptance, and Krita/Comfy consumer alignment are not
software-only completion claims. Keep successful synthetic tests, successful
runtime execution, subjective review and owner acceptance as different facts.
