# Repaired PNG imports retain their Workspace identity

## Scope

This is a bounded follow-up to [#1837](https://github.com/Chris0Jeky/local-asset-studio/issues/1837).
[Merged PR #1856](https://github.com/Chris0Jeky/local-asset-studio/pull/1856)
implemented PNG repair import, retained lineage and parent bytes, and explicitly
left the stale Workspace check and other work open. A successful comparison
journey does not prove the repair-import mutation uses the same identity.

Parented HTTP imports now require exactly one `workspace_id` query value. The
route reads the bounded PNG body, then passes the supplied identity to
`Studio.import_image(expected_workspace_id=...)`. The existing Workspace scope
check runs before upload copies or asset/job registration. Missing, empty,
malformed, duplicate and stale identities refuse without creating files, jobs
or assets. A replacement identity discovered after body reading also refuses.

The page confirms the parent through the existing selected-ID observation before
sending the PNG. The original Workspace, privacy and detail epochs, parent hash,
and metadata receipt observation must still match. A Workspace or privacy A-B-A
transition cannot revive an earlier confirmation. The server retains its PNG,
privacy, parent and note validation. Completion/error text is shown in the detail
dialog only while the captured observation still owns it.

Ordinary unparented HTTP imports keep the existing request and call shape.
The Studio argument is optional for trusted internal callers, including Krita
bring-back. This change does not widen image formats or change Krita sessions.

## Executed local evidence

- The new missing-identity HTTP regression failed against the previous code:
  the route returned 201 and created a repair instead of refusing it.
- Thirteen of sixteen Node cases failed against the previous page code. The
  complete shipped repair script, exercised with a controlled DOM and transport,
  posted before parent confirmation; held Workspace/privacy/detail/hash cases
  therefore failed their no-import assertion. All sixteen cases now pass.
- `PYTHONPATH=/tmp/las-test-deps:tests python -m unittest test_import_repaired_version test_edit_in_krita test_frontend_handoffs test_server_request_bodies test_http_security -v`
  passed **73 tests, no skips**, in 31.693 seconds. This includes thirteen repaired
  import tests and the real Node wrapper. The temporary dependency path belongs
  to this cloud checkout; an ordinarily configured checkout can omit it.
- The existing `test_server.py` import/upload selection passed **five tests**;
  `test_ci_browser_dependencies.py` passed **five tests**, with no skips.
- A disposable loopback server using the new browser fixture's handler passed
  eight HTTP checks: missing/empty/duplicate/stale identity, replacement during
  body read, current import, selected-ID confirmation and scoped metadata.
  Refusals preserved the non-database file digest map, job IDs and asset IDs.
- Python AST, JavaScript syntax and repository validation passed. The production
  upload, privacy and retained-parent rules remain exercised by existing tests.

## Hosted proof still required

`tests/asset_repair_import_browser.py` uses the shipped page, real temporary
Studio and HTTP import route. It covers held confirmation across A-B-A scope
changes, navigation, dialog close and source hash replacement; real HTTP
refusals; regular/private import; editor note and unreviewed child; unchanged
parent records/bytes; and retained family linkage after reopening Studio.
It captures wide/narrow views and serializes browser errors on failure.

The existing Linux family-browser lane runs this fixture and uploads its report
and captures. Its pinned browser installation, job budget and other gates are
unchanged. Chromium was unavailable in this local environment after the normal
installer failed, so this checkpoint does **not** claim a browser pass. The new
exact-head hosted browser result and complete integrated suite remain pending.

## Remaining acceptance

#1837 remains open for its explicitly retained editor-note/repair labeling,
JPEG/WebP, Bin-restoration, unchanged-pixel warning and additional entry points.
The broader #243, owner-parked #1832 and HUMAN_TODO decisions remain open. These
synthetic checks establish runtime behavior; they establish no generation,
native-application, art acceptance or model licensing result.
