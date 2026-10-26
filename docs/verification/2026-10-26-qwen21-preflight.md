# Qwen 2.1 encoder presence before backend switching — 26 October 2026

Refs #1661. This correction changes the existing Qwen presence gate and its
repository launcher. It does not modify an installed ComfyUI checkout, packages,
model files, the default profile, process ownership or generation behavior.

## Reproduction

The live issue identified a source mismatch: the Qwen launcher refused a checkout
without `comfy/text_encoders/qwen_image21.py`, while Studio readiness checked only
the entry point, package overlay and three model files. Both production files
were byte-identical on authoritative main
`b4515ca73e274e07b5642616d3f5e26289880432` and the integrated MCP source
`8d077d772ae24bf53a054e30d5b87bdee00436ec`. The final tail starts on the subsequent
fixture-only parent `deb6091` (#1666); that parent does not change these owners.

A disposable probe reproduced the mismatch through `BackendManager.switch()`.
Workers, process discovery, endpoint observations and execution were inert spies;
the launcher source used a temporary checkout. No installed service was touched.

| Encoder file | Original readiness | Original switch admission | Original direct launcher |
| --- | --- | --- | --- |
| Missing | Ready | Created one worker, scanned configured processes five times and observed endpoints ten times | Refused with exit 2 before main |
| Empty | Ready | Same incorrect admission | Reached the inert main |
| Nonempty fixture | Ready | Complete-checkout control admitted | Reached the inert main |

The empty-file probe also found that the direct launcher's `is_file()` check
accepted a zero-byte encoder module. The new regressions exercise both boundaries.

## Correction and causal checks

`backend_contracts.readiness()` now includes the encoder module as a regular,
nonempty file through its existing stat-only requirement loop. Both the public
switch admission and existing worker-side recheck already use that owner; no
`BackendManager` control flow or state store was added. The direct launcher checks
the same nonempty marker, treating an unreadable stat as unavailable, before
input staging, path changes or `main.py` execution.

Before production changes, the final backend regression run had **five assertion
failures** across eight Qwen tests: missing/empty admission, missing/empty worker
rechecks, and the requirement-list assertion. The complete-checkout and existing
ownership/launch controls passed. The three direct-launcher tests had **one
failure**: empty modules incorrectly reached main; missing and complete controls
already passed. After the owner corrections, all eight Qwen backend checks and
all three direct-launcher checks pass.

The admission cases assert no worker creation, configured-process/listener
inspection, endpoint request, selected-profile change or switch-state byte
change. The worker cases remove or empty the module after admission and require
the normal failed operation record before any process work or launch. The
subprocess launcher tests copy the actual repository launcher into a disposable
miniature repository and run an inert `main.py`; invalid checkouts create no
input directory, and the complete control retains the exact launch arguments and
existing input bytes while staging a new inert reference.

Two harness observations remain separate from product evidence. The initial
sandbox baseline could not identify its own test process, so its switch control
refused; the unchanged three-test baseline passed with narrowly scoped test
process access. The first worker regression used a mock PID that could not be
serialized; it was replaced with a realistic inert PID and independent
missing/empty cases before the final five-failure causal run. Neither observation
caused a production guard or assertion to be relaxed.

## Executed qualification

| Command | Result |
| --- | --- |
| `python -m unittest discover -s tests -p 'test_backend*.py' -v` | 146 passed, no skips; includes the eight Qwen backend checks |
| `python -m unittest discover -s tests -p 'test_qwen21*.py' -v` | 7 passed, no skips; includes the three direct-launcher checks |
| `python -m unittest discover -s tests -p test_studio_launcher_race.py -v` | 9 run: 2 passed, 7 skipped because PowerShell is unavailable |
| `python -m unittest discover -s tests -p test_gpu_lease_launcher.py -v` | 15 run: 14 passed, 1 skipped because PowerShell is unavailable |
| `python scripts/validate-repo.py` | Passed: 93 graphs/bindings, 187 pinned assets, 160 LoRA names |
| `git diff --check` | Passed |

The focused runs use Python 3.12 and disposable files/process doubles. Raw probe,
red/green, earlier fixture-error and qualification logs are retained locally in
`.runtime/qwen21-preflight/`. The coordinator owns complete-suite and Windows
hosted qualification on the published integrated head; no new local full-suite
pass or hosted result is claimed by this checkpoint.

The presence report still leaves `hash_verified` and `runtime_compatible` unknown.
A nonempty source file is not proof of valid Python, node support, a compatible
runtime or successful inference. No model download, installed-runtime change,
live backend switch or GPU generation occurred. Existing `HUMAN_TODO.md` decisions
and broader Qwen/model-output acceptance remain unchanged.
