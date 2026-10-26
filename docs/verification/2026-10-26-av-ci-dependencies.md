# AV CI dependency setup after the cancelled download attempts

This correction belongs to the AV output-verification candidate in #1658. It
changes the CI dependency setup; it does not qualify the AV tests or renders by
itself.

## Observed failure

The unchanged-head retry in [run 40352170644, job 121682213564](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40352170644/job/121682213564)
checked out merge preview `8be4e6fd0c1755c666e5823ce7872ee955b619d2`:
head `ad5da05c2b5151ee52c2fc99d912f44b31a9c55f` into main
`d89b36f32407482de99ddede5515a2f21919d872`. Its image was Ubuntu 24.04,
`20261012.334.1`, and setup-python selected Python 3.12.15.

The package index update took approximately 16 seconds. Installation then planned
99 new packages and 94.1 MB of downloads. It continued fetching from
`http://azure.archive.ubuntu.com/ubuntu` until the ten-minute job was cancelled:

- The `libcodec2-1.2` request began at 15:57:03 UTC and was ignored at 16:00:01.
- The `libavcodec60` request began at 16:04:42 UTC and was ignored at 16:05:42.
- Cancellation occurred at 16:06:38 UTC, still during dependency acquisition.

The pinned Pillow/MCP installation, AV test command, native demo render and
workbench command never ran. This cancellation is not a passing AV gate. The
original attempt and its single unchanged-head retry remain part of the run
history; the correction does not request another unchanged retry.

## Correction and source basis

The exact image's [APT source configuration](https://github.com/actions/runner-images/blob/ubuntu24/20261012.334/images/ubuntu/scripts/build/configure-apt-sources.sh)
places the Azure HTTP mirror first, followed by Ubuntu's official HTTPS archive
and security servers. Its [APT setup](https://github.com/actions/runner-images/blob/ubuntu24/20261012.334/images/ubuntu/scripts/build/configure-apt.sh)
also documents delayed mirror failover and the role of acquisition limits. The
observed package download stalls occur after a successful index update; simply
retrying the entire job had already reproduced the setup failure.

The workflow now selects `ubuntu-24.04` explicitly and writes a temporary Deb822
source file for `noble`, `noble-updates` and `noble-security` using those official
HTTPS servers. Only these APT invocations use the file; the runner's source
configuration remains intact. `Signed-By` retains Ubuntu's installed archive
keyring. No trust bypass, unauthenticated package option, third-party binary
source or system upgrade is introduced.

[Ubuntu's source-list documentation](https://manpages.ubuntu.com/manpages/noble/man5/sources.list.5.html)
defines the Deb822 format and `Signed-By` selection. The
[APT configuration documentation](https://manpages.ubuntu.com/manpages/noble/man5/apt.conf.5.html)
defines acquisition retries and transport timeouts. The setup permits one
acquisition retry, uses 15-second HTTP/HTTPS transport timeouts, fails on any
index-update error and has a four-minute step budget. The existing ten-minute
job budget stays in place.

Installation uses [`--no-install-recommends`](https://manpages.ubuntu.com/manpages/noble/man8/apt-get.8.html)
to avoid optional packages while retaining FFmpeg's required dependencies. Both
`ffmpeg -version` and `ffprobe -version` must succeed before later steps. The
Python/Pillow/MCP setup, 46-test AV command, rendered demo and workbench commands
are unchanged.

## Local validation and remaining hosted gate

An isolated harness executes the workflow's actual setup shell with recording
command doubles, then passes the emitted source file to real APT
`--print-uris update` with temporary list storage. It performs no downloads or
package installation. It checks that every planned URI uses the two intended
HTTPS servers, that the security suite is included, and that the Ubuntu keyring
selection remains explicit. Separate update and installation failures stop
before later commands. The harness also compares all subsequent workflow steps
against the original AV candidate.

Before the correction, one of three checks failed on the old setup. After it,
all three passed in 0.257 seconds. The extracted setup shell passed `bash -n`;
repository validation and `git diff --check` also passed. These checks establish
configuration and failure handling, not network throughput or native render
success. The changed head still requires a fresh hosted AV run with its real
MCP, FFmpeg tests, demo and workbench gates before merge qualification.

Local evidence is retained under `.runtime/av-ci-dependencies/`, including the
unaltered downloaded job log, `verify_setup.py`, `setup-before.log`,
`setup-after.log` and `validate.log`. The saved job log's SHA-256 is
`e5d1161c1d5e4c30297f528926d0294b0d895e9f92e22d2a2c856c63d43d31a0`.

No generation or owner art acceptance is inferred. Existing owner decisions in
`HUMAN_TODO.md` remain open.
