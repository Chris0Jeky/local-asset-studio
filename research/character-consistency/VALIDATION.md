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
The planning CLI produced the expected 12-case draft. With restored original references, preflight
reported only the unapproved canon while retaining `submission_authorized: false`.

The owner supplied the original ZIP path. The importer verified all 71 members and 27,336,577 expanded
bytes against the lock and restored them under `C:/AI/character-lab/windows-proof-20260912/original/`.
All 33 newly extracted crops were compared against decoded source rectangles and matched exactly.
All three source sheets are opaque. The standard card composed twice with identical bytes under
Pillow 12.3.0 on Windows (SHA-256 `14d4ba19337a616693042a865fd54314ce9da17531837ee10ce4fa19666c2054`).
Its bytes differ from the earlier runtime's card; cross-platform byte identity is not promised.
Visual inspection found retained crop fragments, as in the original review artifact; it is not a
cleaned sprite sheet. No neural inference, archived-code execution or approval occurred. Raw logs and
reports are preserved under `.runtime/session-2026-09-12/character-review/` and the external proof root.
