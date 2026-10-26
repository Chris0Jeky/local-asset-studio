# Direct MOSS launcher preflight — 26 October 2026

PR #1668 added the MOSS encoder implementation to the manager's nonempty-file
readiness contract. Direct invocation of `scripts/moss-launch.py` still checked
only whether that encoder path was a file. A disposable checkout with an empty
`comfy/text_encoders/moss_image.py` therefore reached an inert `main.py`, despite
the manager correctly refusing the same checkout.

The launcher now applies the same stat-only nonempty-file check as the Qwen
launcher. Missing, empty, or unstatable encoder support produces the existing
argparse refusal before changing directory, modifying the import path, or
executing main. No input staging or model work is added.

## Causal qualification

Baseline launcher Git blob: `71888d29badb778831bb38baf64eb5da22b812d0`, read through
the GitHub connector at `e98985c40de39800383b9051e58bcb2f764f31f6` and verified
against the materialized bytes. The four new tests run a copied real launcher
in a separate Python process over disposable inert files, with paths containing
spaces. No installed checkout, listener, package, model, or GPU is accessed.

| Case | Original launcher | Corrected launcher |
| --- | --- | --- |
| Missing encoder | Existing refusal; control passes | Refusal, exit 2, no directory change or main |
| Empty encoder | Reaches inert main, exit 0; regression fails | Refusal, exit 2, no directory change or main |
| Encoder stat raises PermissionError | Unhandled error, exit 1; regression fails | Existing refusal, exit 2, no directory change or main |
| Complete checkout | Control passes | Exact arguments, port 8198, overlay order, cwd and existing input preserved |

The complete control covers both default reserve `2` and explicit reserve `1.25`.
The stat-failure test injects one encoder-path error in the disposable child;
it does not depend on host-specific file permissions. The real `chdir` call is
observed so a refusal cannot silently change directory before failing.

The baseline run has two failures and two passing controls. After the guard,
**4 tests pass in 0.432 seconds, no skips, exit 0**, on Python 3.12.14/Linux. Logs and
source identities remain in the session's ignored/scratch qualification evidence.
No full local repository suite is claimed by this isolated launcher proof.

## Hosted gate and limits

The existing Windows runtime-safety lane now runs `test_moss_launcher.py` and
triggers on that file and `scripts/moss-launch.py`. It keeps the preceding Qwen
change's exact-head checkout/logging, every existing command, Windows runner,
and ten-minute budget. Removing only the two trigger pairs and the new test step
reconstructs the previous workflow byte-for-byte.

Fresh hosted Windows and full-suite qualification are required on the published
head. A nonempty stat result does not prove readable/importable Python, compatible
nodes, valid model hashes, or inference. Manager admission, process ownership,
launch arguments, model files, installed ComfyUI, and shared packages are unchanged.
