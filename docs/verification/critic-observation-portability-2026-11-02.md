# Critic evidence checkout portability — 2 November 2026

Follow-up to the initial 83-test receipt in `critic-observation-2026-11-02.json`.
The publication review found that the repository's `* text=auto` rule did not pin
JSONL checkout line endings. With `core.autocrlf=true`, the retained observation
bytes became CRLF, invalidating their SHA-256 despite unchanged semantic data.

## Causal experiment and fix

A new test creates an isolated Git repository with the actual root attributes,
the new scoped attributes when present, and the two retained evidence files. It
stages them, removes only those temporary copies and checks them back out with
`core.autocrlf=true`. Before the fix, exact-byte comparison failed for
`observations.jsonl`. After adding `research/agentic-creation/.gitattributes`, both
that record and the compressed source patch retain their exact bytes.

Only these two paths receive new rules: LF for the pinned JSONL; binary for the
compressed patch. No global Git configuration, unrelated file format, source
manifest, production threshold or runtime setting changes. This is a real Git
checkout test on the Linux test host with Windows-style conversion enabled,
**not a native Windows or Blender qualification**.

## Verification

The final focused set now passes **84 tests, zero skips**, with ResourceWarnings
as errors: 69 critic/policy/study tests (4.348 s), 13 sentinel adapter tests
(0.027 s), and 2 archive/checkout tests (0.012 s). The new round-trip test failed
before the attribute fix and passed afterwards. The earlier local snapshot and
native-dispatch-stub limitations remain unchanged. Hosted exact-head CI and
independent review are separate gates.

Run the new regression with:

```console
python -Werror::ResourceWarning -m unittest discover -s tests -p "test_critic_research_archive.py" -v
```

Git is already a repository tool dependency. The test starts no renderer, model,
network client, or shared-workspace operation; all Git writes are in its temporary
repository. No generated media or private assets were added.

## Reference

[Git's gitattributes manual](https://git-scm.com/docs/gitattributes), checked
2 November 2026, documents per-path `eol=lf` and text/binary attribute behavior.
The observed before/after failure, rather than the documentation alone, proves
this particular retained-file defect and its repair.
