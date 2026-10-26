# Review workflow follow-ups — 26 October 2026

This maintenance slice follows the reviewed integration order [#1645](https://github.com/Chris0Jeky/local-asset-studio/pull/1645) → [#1643](https://github.com/Chris0Jeky/local-asset-studio/pull/1643) → [#1638](https://github.com/Chris0Jeky/local-asset-studio/pull/1638) → [#1644](https://github.com/Chris0Jeky/local-asset-studio/pull/1644). Its commits retain the separate causal fixes. GitHub remains authoritative for their current heads, checks, review and merge disposition.

## Quick checks and saved answers

[#1211](https://github.com/Chris0Jeky/local-asset-studio/issues/1211) gains the remaining interaction corrections after Character/Background check sets and Create-card counts:

- Repainting a dialog check or reason chip restores focus to that same control. Typing in a field does not move focus to a chip.
- Dirty-state, save and handoff guards compare normalized tag sets. Cycling an answer back to the saved set no longer leaves a false unsaved edit because the tags moved in the draft. Actual text changes still count, invalid new check tags remain editable, and an uncertain command keeps its original retry bytes.
- A comparison candidate whose metadata has not been observed says **Saved checks not loaded** and offers **Load saved checks**. The explicit read resolves only that candidate ID. It neither answers a check nor changes the comparison outcome. Missing assets have an unavailable state; late reads cannot repaint another Workspace or plan or overtake a confirmed receipt.
- Create cards keep their **Loaded checks** scope. They count only IDs on the loaded Library page, using each ID's canonical confirmed metadata; separately resolved off-page assets are excluded.

The metadata browser fixture now supplies the jobs mapping expected by family reads, eliminating its background `AttributeError` without changing production behavior.

## Look attribution and result diagnostics

[#1225](https://github.com/Chris0Jeky/local-asset-studio/issues/1225) now carries the prepared Look through setup checkpoints, restores and same-recipe reruns. A proposal that replaces the recipe explicitly discloses removal of its Look attribution. Server and client review the same change, and lineage comparison includes the Look.

Historical attribution accepts a bounded recorded ID, name, revision and options; submitting a new run still uses the current Look admission and revision checks. Retaining a historical record does not authorize an unavailable or changed live Look.

Make's single and comparison result views show the existing left/right detail diagnostic with Look attribution. The diagnostic is a measured image characteristic, not a text-legibility verdict or owner approval of the artwork. No Night Shift calibration render was made in this maintenance pass.

## Grid browser reliability

[#1648](https://github.com/Chris0Jeky/local-asset-studio/issues/1648) was caused by two sort transitions being asserted before their new page reads settled. Production intentionally declines to repaint a page whose query does not match the current controls. The test now waits for the page query to match and the refresh/search work to finish at each transition.

A bounded `--response-delay-ms` fixture option delays only the page-read endpoint. The existing normal and 400 ms CI cases both run the grid journey. The behavioral assertions and deadlines remain in place. Removing either wait independently reproduces its corresponding failure; this is not a blanket thumbnail delay.

## Download recovery and transport

The separate [download-integrity evidence](2026-10-26-model-download-integrity.md) records [#1633](https://github.com/Chris0Jeky/local-asset-studio/issues/1633): complete retained-file paths, actionable recovery fields, peer validation before TLS, direct/CONNECT certificate tests and the redirect-close characterization. The existing model-intake Linux/Windows matrix now also runs install safety, download transport and redirects, including when those tests or their TLS fixtures change.

## Source filtering before pagination

The bounded [#1627](https://github.com/Chris0Jeky/local-asset-studio/issues/1627) slice applies Mine/Agent source selection in SQLite before the page limit. The existing exact `Make · ` prefix still marks personal work. Omitted or All-source API filters retain the prior response shape and cursor identity; Mine and Agent queries have distinct cursor identities. HTTP, CLI and MCP admit the same choices. The Library keeps the chosen source on empty pages and preserves checkbox selection when changing source.

The source-filter implementer passed 63 reader/client/bridge Python contracts, 20 HTTP/frontend/metadata tests, four new frontend groups, 14 existing pagination contracts and 41 Library contracts. Independent review ran the identical four new frontend groups against the unchanged script and reproduced four failures. A native fixture with 101 newer agent assets and three older personal assets passed nine checks, while the existing Library journey passed all 43. Both reported no page errors. The existing asset-detail browser workflow now includes the new source fixture and retains its artifact. The [Workspace guide](../WORKSPACE.md) keeps the broader paging issue open.

## CI scheduling

`Check studio` previously ran the same heavy suite on every branch push and again on the associated pull-request event. It now runs on pull requests, pushes to `main` or tags, and explicit manual dispatch. A concurrency group replaces superseded runs for the same PR or ref. The full suite, resource-leak checks, 1,200-second hosted budget, checkout/tree provenance, repository validator and read-only permissions are unchanged.

This follows GitHub's documented [event filters](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#on) and [concurrency behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency). Standalone branches can still request qualification through manual dispatch or a draft PR.

## Verification and limits

Root's combined quick-check browser run passed **28 checks**, with zero page errors and no generation submissions. The 390 px unloaded and 1,440 px loaded comparison states were visually inspected; the saved-answer action and keyboard focus fit. The corrected grid journey independently passed **44 checks with 400 ms page delays**, zero page errors and no generation. The grid implementer also passed the normal-response case and demonstrated both failing controls by removing the respective wait.

Independent Look review passed **59 focused Python tests**, plus **18 Make**, **24 Vary**, **9 proposal** and **13 setup-apply** JavaScript contracts. Root also passed the combined metadata wrapper's three tests, the production comparison and typed-draft contracts, all 30 workbench handoff contracts and repository validation. The integrated download modules passed **115 tests in 5.443 seconds**, with five existing platform skips on this Linux checkout.

These are local scoped measurements. Published-head CI logs, checkout trees, full-suite verdicts and actual merge-tree comparisons belong in the PR conversation; a previous-head success is not a substitute. The native Windows matrix is a separate gate. No installed runtime was modified or started, no model weights were downloaded, and no generation was submitted.

The earlier combined integration tree, before these follow-ups, ran 6,052 tests locally in 960.761 seconds with four failed direct-peer subtests and 42 skips. Its old redirect test inherited this host's proxy configuration and therefore exercised the proxy exception instead of a direct peer. The same unchanged two-test module passed with only proxy environment variables removed. The #1633 follow-up explicitly isolates proxy configuration and independently covers direct and proxy TLS; its focused 115-test run passed with the normal host environment. This retained failure is not presented as a successful full-suite gate.

[#2](https://github.com/Chris0Jeky/local-asset-studio/issues/2) still needs an actual same-seed 8/20-step render comparison and a new reference-edit trial; its native loading crash and uncertain prompt remain unresolved. [#1627](https://github.com/Chris0Jeky/local-asset-studio/issues/1627) remains the broader paging follow-up; the stale-cursor and collection sort items already fixed by #1628 are distinguished in its issue discussion. `HUMAN_TODO.md` is unchanged: art acceptance, Kromoss/MOSS choices, parallax review and existing publication/runtime decisions remain with the owner.
