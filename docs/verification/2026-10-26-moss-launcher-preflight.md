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

## Canonical path fixture correction

The initial Windows Qwen launcher gate at parent
`fc234d8197273e2ba18cc4322fe09ce604bd68b0` exposed a Windows short-path alias in
the temporary checkout. The MOSS fixture shared that expectation and could also
miss its encoder stat-error injection by comparing a raw alias with the canonical
path used by the launcher. The failed parent job is retained as
[run 40398249108, job 121836946830](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40398249108/job/121836946830);
it is not a passing MOSS or corrected-head qualification.

The MOSS fixture now resolves its injected encoder path before installing the
stat mock, and expects canonical cwd, observed chdir, overlay order, and main
argument. It continues to pass the original path to the launcher. Both reserve
controls and all refusal assertions remain exact. The MOSS production launcher
remains Git blob `04f7db9ecb4c43c700bcd8b66389868d3e97e1b8` unchanged.

A bounded Linux symlink-alias probe against the original MOSS fixture
`295dc9313e696d5709e0afa5d5d32ffec7a1b944` reproduced two positive-control
assertion failures and the missed PermissionError injection (inert main ran, exit
0). With the fixture correction, all four MOSS cases and the three companion Qwen
cases pass through that raw alias: 7 tests in 0.653 seconds, no skips, exit 0. The
ordinary-path control also passes all 7 in 0.729 seconds. The copied real launcher
bytes are identical for baseline and corrected fixture runs. Fresh hosted Windows
and full-suite results must be collected for the newly published head.
