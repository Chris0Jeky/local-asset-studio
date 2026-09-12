# Validation ledger — 12 September 2026

The original 65 focused tests passed in the local partial staging directory. A subsequent review found Python equality aliases (`True == 1`, `1.0 == 1`, `0 == False`) could bypass exact plan-object comparison while retaining the original outer hash. The new regression produced three expected failures against the initial implementation. Comparing canonical JSON bytes fixed all three; **66 focused tests then passed**, zero skips.

This is input-contract hardening, not an authentication claim. A caller can still invent a new canon/plan/reviewer attestation; trusted execution and actual approval policy belong to the shared coordinator.

The 66 focused tests are in `test_character_archive.py`, `test_character_media.py`, `test_character_study.py`, and `test_character_integrity.py`. Two additional `test_character_repo_contract.py` tests use the real repository's existing brief validator and qwen-1ref/flux-edit templates. They are run by normal GitHub CI; they were not run in the partial local directory, which lacked the full private checkout. Consult the PR/check logs for the actual full-suite outcome rather than counting those two as locally passed.

CPU work also restored all 71 original archive members, compared all 33 new crops to their decoded source rectangles, inspected actual opaque alpha, and composed the standard review card twice with identical bytes in the same runtime. The review image was visually inspected as a labelled opaque comparison artifact; adjacent source fragments remain visible in some rectangular crops, as documented. It is not new neural art or a cleaned game-ready sprite sheet.

No new image model inference, model installation, user-PC browser test, live queue operation, owner creative approval, rights clearance or engine acceptance occurred in this implementation session. Current-state historical workstation results elsewhere in the repository are not attributed to this slice.

## Subsequent Windows integration - 12 September 2026

After integration with main `fcd3e7504b4676580e32bdae40202f104d402630`, the full local suite ran 589 tests:
579 passed and 10 skipped; repository validation passed. The character subset ran 68 tests, with
67 passing and one symlink-creation skip. Both real-repository contract tests passed locally.
The planning CLI produced the expected 12-case draft and preflight reported the unapproved canon and
three missing original references while retaining `submission_authorized: false`.

The original ZIP was not found in Downloads. The available field guide embeds JPEG previews, so it
cannot establish restoration of the locked original PNGs. No archive restoration, original-source
pixel comparison, neural inference or approval is claimed for this Windows follow-up. Raw logs and
reports are preserved under `.runtime/session-2026-09-12/character-review/`.
