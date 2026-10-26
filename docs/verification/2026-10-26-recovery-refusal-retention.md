# Retained refusal qualification — 26 October 2026

Refs #393. This is a bounded follow-up to the existing recovery journal, shelf
and detail/Library handlers. It adds no metadata protocol, automatic request,
recovery store, generation, runtime installation or owner decision.

## Source and ownership

The core change began on local recovery integration `5c3bf45` and was rebased
onto the coordinator's frozen Library integration
`25bca8fbadd52e577e2357bc1a7f9e973feabeeb` before any Workspace hook was edited.
The final local branch includes predecessor `7530dfb6d770729d09f23ae6506dac1aba167af1`,
which adds the Library publication note and bounded AV CI setup without changing
the tested recovery production files. The coordinator owns authoritative GitHub
reconciliation, publication, hosted candidate CI and merge verification. Local
reconstructed commits are not claimed as authoritative remote main identities.

The initial native qualification, before the transactional shelf correction,
used production/test commit `4f617a5` with these
exact SHA-256 values; subsequent documentation changes do not change those files:

| File | SHA-256 |
| --- | --- |
| `app/static/asset-recovery.js` | `68db33c2788fb57f1ca72400832fd02f877270af6ba419a049cfa2f51db2c07e` |
| `app/static/asset-recovery-shelf.js` | `df2982650706fc2d1e6bfa7f04be80d0015efbae089aaff2d78d48344577d530` |
| `app/static/workspace.js` | `d823ae8c442c4748ea27e411631a91a22ac17e8e7509b6c3ec068b007258008c` |
| `tests/asset_recovery_refusal_browser.py` | `8d1e42a9c4919872f4f134954fbc0f5ba5da3d64b095a3937d73b9294eb7b40a` |

## Delivered behavior

`last_refusal` is optional and lives beside the exact pending `operation`. Its
strict schema binds Workspace and request identity, limits the literal message
to 1,000 Unicode code points/4,000 UTF-8 bytes, admits only integer HTTP 4xx
status, bounds the optional server code and observation date, and rejects future
versions or extra fields. The journal reads the latest retained payload before
annotating, verifies exact body and identity, then uses its existing verified
write and checkpoint notification. No command byte or editable draft is rebuilt
from the error.

The existing handlers carry the annotation explicitly when reconstructing the
same recovery record. Only a current POST refusal can add or replace it; a GET
failure, unknown receipt, stale request, Workspace A→B→A or explicit foreign
error-envelope identity cannot. The two panels render escaped literal text under
**Last recorded refusal**. A later exact retry with a lost reply or HTTP 5xx can
leave that historical explanation in place without describing the new outcome
as refused. The command remains unconfirmed until a matching receipt is read.

Current confirmation, verified conflict transition and explicit session discard
remove current annotation ownership. Historical shelf records retain their
existing explicit-discard semantics. If recording the explanation fails, the
original refusal remains visible with a truthful retention warning, while the
exact command and newer draft stay available.

## Causal and contract evidence

- Initial core/codec run: **32 expected failures** against the old carrier,
  demonstrating dropped shelf annotations, missing validation and absent update
  behavior. The expanded core set subsequently passed **34/34**.
- Initial Workspace run: **30 failures / 40 passes** before hooks. Failures
  covered both slots, transient explanation loss, cleanup, secondary storage
  errors and shelf restoration; existing stale/foreign controls stayed green.
- Independent review reproduced two presentation defects with **5 expected
  failures / 41 passes** on `4568df3`: both slots falsely labeled an earlier
  refusal as the last attempt after a later lost reply or HTTP 500, and an
  unverified missing-target conflict omitted the original reason when annotation
  persistence failed. Two narrow Workspace string corrections made all **46/46**
  editor refusal cases pass; exact commands/drafts remained unchanged.
- Final focused run: **152/152 passed**, covering annotation, refusal, session,
  shelf restore, shelf codec/session and checkpoint contracts.
- Existing reload contracts: **14/14**; editor contracts: **28/28**; frontend
  handoff script: passed.
- JavaScript/Python syntax, whitespace and repository validator: passed.

The conflict cleanup fixture initially omitted the required `trashed_at` field
from its supposedly verified metadata snapshot. The real validator correctly
kept that incomplete conflict pending. Adding the real `null` lifecycle field
made the intended valid-conflict control pass; no production guard or assertion
was relaxed. The native fixture's empty `jobs` mapping is test-server setup,
matching the family-read contract; it is not a product change.

Raw causal and qualification logs are preserved under local `/tmp` with the
`recovery-annotation-` prefix. The complete offline suite was started on the
earlier candidate, then deliberately interrupted before applying independent
review corrections, at the publication coordinator's direction. Its
`/tmp/refusal-annotation-full-suite.log` is interrupted evidence, not a completed
pass. Final source qualification above was rerun after the correction. The
complete suite remains a required exact-head hosted CI gate before merge; no
full-suite result is inferred from focused contracts or mixed source versions.

## Native browser evidence

Executed command:

```console
python tests/asset_recovery_refusal_browser.py --out .runtime/refusal-annotation-reviewed-native
```

Result: **32/32 passed**, **zero JavaScript exceptions**. The fixture uses shipped
UI, actual loopback HTTP handlers, real temporary SQLite, native browser stores,
WebCrypto and Web Locks. Local Playwright is 1.56.0 with bundled Chromium
1194/141; the hosted refusal workflow pins Playwright 1.57.0 and requires its own
exact-head Ubuntu and Windows qualification.

For each journal slot it commits a command while losing its response, holds a
403 on an exact retry, moves focus while the refusal is pending, and verifies
that the literal explanation appears without taking that newer focus. Detail
typing while the response is held remains independent of the submitted body.
A further explicit exact retry then loses its response. The annotation and all
pending bytes stay unchanged; the current attempt is unconfirmed and the panel
still accurately labels the earlier recorded refusal. These are three deliberate
metadata POST attempts per slot. Reopening and a real reload preserve the
explanation without querying receipts or resending metadata.

The same native journey flushes the optional device checkpoint, exports the
shelf, clears both browser stores, closes the old page and opens a fresh tab.
Inspection persists nothing and makes no receipt query. Explicit import and
restore recover the annotation and byte-identical command. One explicit GET
confirms the historical result, preserves the newer draft/complete selection,
removes current refusal presentation, and leaves historical shelf evidence for
explicit discard. The synthetic original file hash remains unchanged.

The 390px detail and Library screenshots were inspected: the long literal error
wraps, markup remains text, and recovery actions remain visible. This is a
bounded responsive/focus check, not full keyboard or screen-reader acceptance.
Native receipts and screenshots live under ignored
`.runtime/refusal-annotation-reviewed-native/`. The optional `--inert` path passed
**22/22**, with zero JavaScript exceptions, under
`.runtime/refusal-annotation-reviewed-inert/`; it has narrower substituted
storage/transport coverage and is not native persistence evidence. The earlier
candidate's 30/30 native and 20/20 inert runs remain historical evidence rather
than being relabeled as the corrected candidate's result.

## Transactional parent integration

The parent shelf subsequently replaced localStorage as its current write owner
after the cross-renderer lost update in #825. The refusal change was integrated
onto that reviewed correction and the Library fixture corrections without
changing its command or annotation semantics.

Two old fixture assumptions were reproduced and corrected:

- The annotation checkpoint component test instantiated the browser default
  without IndexedDB. It now uses the explicitly labelled single-process memory
  owner supplied by the parent. Before correction, 33 cases passed and the
  checkpoint case refused for unavailable IndexedDB; afterward all 34 passed.
  Production retains the fail-closed browser requirement.
- The native fresh-tab journey cleared localStorage and sessionStorage but left
  the new current owner intact, correctly failing its empty-shelf assertion at
  `detail-09`. It now uses the shared disposable-browser helper to clear the
  IndexedDB owner as well, before closing the page. The original failure is
  retained in `.runtime/refusal-new-owner-red/`.

On integrated local commit `e390e058d8c14e09814a3763e0e38e3d474a347e`, the
complete native journey again passed **32/32**, zero JavaScript exceptions,
with real Chromium, loopback HTTP, SQLite and IndexedDB. Both detail and Library
slots retain their exact pending bodies and historical explanations through
export, actual browser-storage clearing, a fresh tab, explicit import/restore
and one GET confirmation. The focused Python refusal wrappers also pass.

| Integrated file | SHA-256 |
| --- | --- |
| `app/static/asset-recovery-shelf.js` | `4e422f746d0a322432821646d6e8bf8016aa4b234e15d61617af2f6ac9e8fccd` |
| `app/static/workspace.js` | `d823ae8c442c4748ea27e411631a91a22ac17e8e7509b6c3ec068b007258008c` |
| `tests/asset_recovery_refusal_browser.py` | `bfa70aeba80aed56f3046988f4795a46e1e1e62709a9f5e7587f8f05bf687d72` |
| `tests/browser_shelf_owner.py` | `9edc97f321fbbee5286df4c47b9ba368c940bd06c61a213c374b09d04744d8a4` |

The new receipt and narrow-screen screenshots are under
`.runtime/refusal-transactional-final/`. This is separate from the earlier
localStorage/inert evidence above. Final published-head hosted qualification
remains a merge gate.

## Compatibility and remaining work

New readers accept prior records without the annotation. Older open tabs have a
strict shelf codec and may refuse the new optional field while preserving raw
bytes; reload them onto the current application before continuing checkpoints.
Unsupported annotation schemas are not silently stripped or migrated.

#393 remains open for the complete recovery/conflict keyboard journey, all
opener/filter-removal focus cases, browser-menu zoom interaction and an executed
screen-reader pass. Browser-owned zoom API evidence from the preceding shelf
qualification remains a separate result. `HUMAN_TODO.md` is unchanged: outstanding
art, model/runtime and publication choices remain with the owner, and passing
software checks do not decide them.
