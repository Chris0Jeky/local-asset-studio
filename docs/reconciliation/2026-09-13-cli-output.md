# Headless response retention and output preflight — maintenance pass 2

## Scope

Fixes issue #207; a bounded correction under #123, not completion of the broad
agent SDK/MCP workstream. Based on inspected main
`61a8c4e16b8e64b8bdea5a121bec71f2b0758cb8` (tree
`c7e1c8e0857661ce614ba7dd635a4de2beb90062`).

## Reproduced behavior

The legacy top-level workflow CLI issued its request before exclusively opening
`--out`. With an existing destination, an approved `run` still reached the
shared dispatch boundary, then failed locally. The received job result was
omitted from stdout's error. A competing writer after the response, a new
directory, and a partial disk-write failure similarly obscured known results.

The existing file was not overwritten. The same ticket was already protected
against replay; this is not evidence of duplicate generation. The newer `runs`
command already had its own output checks and recovery protocol and is unchanged.

## Command boundary

Before constructing a request, top-level commands with `--out` check that its
path does not exist, including dangling symlinks, and that its parent directory
exists. The final exclusive `open('x')` remains necessary: preflight does not
reserve a filename or guarantee later disk space/permissions.

If export fails **after** a response was obtained, stdout includes the complete
received result plus explicit local-output-failure context. No HTTP retry,
replacement ticket, overwrite, deletion, new worker or store is introduced.
An incomplete file is left intact for inspection. UTF-8 and Python's full-width
integer serialization are retained.

| Outcome | Exit | Machine fields | Required action |
| --- | --- | --- | --- |
| Destination already exists / parent missing | 2 | `code: output_unavailable`, `request_sent: false` | Choose a new path; no request was issued. |
| Response received, output export failed | 2 | `code: local_output_error`, `response_received: true`, `result` | Retain the nested response and original identity. Inspect any partial file. Do not create replacement work. |
| Run response genuinely lost | 3 | Existing uncertain-outcome recovery text | Retain the original ticket; inspect/reconcile the same request. |
| Successful output | Existing status exit | Unchanged response | Continue the existing review/observation flow. |

An exit of 2 alone does not mean no remote work occurred: inspect `code` and
`response_received`. A received response can itself describe an uncertain remote
outcome; returning it faithfully does not turn uncertainty into completion.
Nothing here guarantees persistence when stdout and disk both fail.

## Example

```sh
python -m studio_workflow prepare --recipe recipe.json --out new-ticket.json
python -m studio_workflow run --ticket new-ticket.json --approve --out new-result.json
```

Both destinations must be new files in existing directories. Keep the original
ticket. After a local-output failure, recover the returned `result` from stdout;
a preparation response is still a ticket, and a run response retains its job ID.
Inspect the job using the ordinary status command. Do not prepare another ticket
to compensate for a lost local file.

## Verification

Nine tests use real loopback HTTP and temporary files through the existing inert
shared-worker fixture; no ComfyUI endpoint or GPU is involved. They cover an
existing file, missing parent, dangling symlink, existing directory, a competing
writer after receipt, failed preparation export, partial output, wide-integer
success and genuinely lost run response. Files and response contents are checked,
not only mocked call counts.

Initial six tests on unchanged main: five failures, one pass (the existing
uncertainty behavior). All nine final tests pass. Symlink creation may be skipped
on hosts without that privilege; it ran on this Linux host.

```sh
python -m unittest discover -s tests -p test_workflow_cli_output.py -v
python -m unittest discover -s tests -p 'test_workflow*.py'
python -m unittest discover -s tests
python scripts/validate-repo.py
git diff --check
```

Full Linux suite: **1,498 tests, 15 skipped, zero failures/errors**, 101.322 seconds,
Python 3.13.5 and Node 22.16.0. Untouched main: 1,489 tests, 15 skipped, no failures.
Existing Pillow deprecation and socket ResourceWarnings were not suppressed.
Hosted CI and independent review remain separate evidence.

## Compatibility and rollback

Successful outputs and the newer saved-run commands are unchanged. A received
run response followed by local export failure now returns exit 2 instead of the
misleading generic uncertain-run exit 3, with explicit machine-readable recovery
context. Callers must inspect the returned fields rather than retry on exit alone.
Revert the CLI change to restore previous behavior; no stored-state migration or
runtime change is required. No owner files, approvals or installed packages were
changed by verification.
