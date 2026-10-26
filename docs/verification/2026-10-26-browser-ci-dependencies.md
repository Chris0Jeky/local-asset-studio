# Bounded Chromium dependency setup — 26 October 2026

## Observed hosted blocker

The GitHub job logs and step conclusions below were read through the connected
GitHub tools. These cancellations do not qualify the skipped application tests.

| Workflow / attempt | Hosted job | Observed result |
| --- | --- | --- |
| Recipe shortlist, attempt 1 | [run 40357013551 / job 121692085000](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40357013551/job/121692085000) | Chromium dependency installation was cancelled after slow Azure Ubuntu package downloads; all three browser proof steps were skipped. |
| Recipe shortlist, attempt 2 | [same run / job 121698691660](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40357013551/job/121698691660) | The unchanged checkout again exhausted its budget during dependency installation; all three browser proof steps were skipped. |
| Asset conflict envelope, Ubuntu | [run 40357013531 / job 121692086072](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40357013531/job/121692086072) | APT update stalled on the runner mirror path and installation was cancelled about 15 minutes later; the unit and native browser proof steps were skipped. |
| Guided journey, attempt 1 | [run 40357013262 / job 121692083827](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40357013262/job/121692083827) | Installation consumed about 8 minutes 49 seconds of the 10-minute job. Both initial unit-test steps passed; the first native journey was cancelled and the later browser steps were skipped. |
| Restyle ownership, Ubuntu | [run 40357121704 / job 121692468346](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40357121704/job/121692468346) | Installation was cancelled before any behavioral test. The log records `fonts-freefont-ttf` from 16:17:26 to 16:20:39 UTC and continued Azure downloads until cancellation at 16:24:56 UTC. |

The two Recipe attempts and Guided attempt checked out GitHub's synthetic merge
`ecb37effd4d2850c72ce1cd8a9f8862c5f1cabc1`, containing recovery head
`7af9f26bcfadeea86cbf84608fe62527c65544d4`. The conflict job checked out that
recovery head directly. Restyle checked out Library head
`12ff76929dea86b847a17382632368d87a051f3f` directly. These are historical failed
attempts, not evidence for a subsequently corrected head.

## Scoped correction

The initial correction applied the helper to Recipe shortlist, asset conflict
envelope, guided journey, and Restyle ownership. Their Linux runners are pinned to
Ubuntu 24.04. The existing job limits remain 8 minutes for both Recipe jobs,
15 minutes for conflict envelope, and 10 minutes for Guided and Restyle. Existing
test commands, package pins, checkout settings, assertions, and artifact settings
are retained. The Windows jobs retain their original Playwright install command.

Subsequent applications are qualified separately for the
[recovery shelf](2026-10-26-shelf-transaction-qualification.md) and
[asset-detail browser](2026-10-26-asset-detail-dependencies.md). The measurements
below remain evidence for the original helper implementation.

[`scripts/ci-install-chromium.sh`](../../scripts/ci-install-chromium.sh) creates
temporary Deb822 sources for `noble`, `noble-updates`, and `noble-security` using
the official archive/security HTTPS hosts and the installed Ubuntu archive
signing keyring. It does not edit the runner's APT configuration. The temporary
configuration selects only those sources, sets one retry, 15-second HTTP/HTTPS
timeouts, and treats incomplete APT updates as failures. Its temporary
`Dir::Etc::parts` and `Dir::Etc::main` settings prevent later system snippets from
overriding these options.

Playwright 1.57.0's [dependency installer](https://github.com/microsoft/playwright/blob/v1.57.0/packages/playwright-core/src/server/registry/dependencies.ts)
uses its own sudo transition when invoked as a normal user. The helper instead
invokes only `install-deps` through `sudo -n env APT_CONFIG=…`, using the selected
Python executable's absolute path. The temporary configuration therefore reaches
the root dependency process after sudo's environment reset. A separate
`playwright install chromium` runs as the normal runner user.

The dependency process has a 150-second deadline and 10-second kill grace; the
browser download has a 60-second deadline and 10-second kill grace. Their total
maximum of 230 seconds fits inside the new four-minute installation step, while
preserving the existing job budgets. A dependency failure or timeout stops the
helper before browser installation; the original exit status is retained and the
temporary configuration is removed.

## Local evidence and limits

The five tests in
[`tests/test_ci_browser_dependencies.py`](../../tests/test_ci_browser_dependencies.py)
execute the helper with controlled sudo, timeout, and Python commands. The sudo
stub deliberately removes inherited `APT_CONFIG`; the test therefore requires
the explicit post-sudo environment assignment. The tests inspect real
`/usr/bin/apt-config dump` output and execute real `/usr/bin/apt-get --print-uris`
with isolated temporary state to verify source selection without fetching or
installing packages. Temporary paths contain spaces.

The causal sequence was retained locally: five failures before the helper
existed, then four passes and one failure when the real APT configuration exposed
an ambient `Acquire::Retries` value of 5 overriding the requested 1, then all five
passes after isolating system configuration snippets. The final run passed all
five tests in 0.788 seconds, with no skips. It covers effective source/options,
signing-key selection, normal-user browser installation, both command deadlines,
dependency failure/timeout, browser failure, exit propagation, and cleanup.

Additional checks passed: `bash -n scripts/ci-install-chromium.sh`,
`python scripts/validate-repo.py` (93 graphs/bindings, 187 pinned assets, 160 LoRA
names), and a byte-for-byte workflow comparison against base
`d914cb874dc94cd0c8010590452730bd1c49526d` after reversing only the specified runner,
trigger, helper-check, and install-step substitutions. `git diff --check` also
passed. Raw hosted logs and the local red/green outputs are retained under
`.runtime/browser-ci-dependencies/` in the working checkout.

No local package or browser installation was performed for this correction. The
stubbed deadline test checks command bounds and failure propagation; it does not
measure a real download or exercise the real privileged process termination.
Fresh hosted execution at the corrected PR head remains the authority for actual
download completion and the unchanged application tests. This maintenance slice
does not itself qualify or close the recovery, Library, or annotation work.
