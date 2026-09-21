# Review-first handoff inbox

This command-line slice supports #638 and #639. It discovers and retains previews;
it does **not** create a Production project, submit TTS, load a model, or grant
approval to a later process. Studio aggregate projects, Start/download controls,
and the profile-selector integration remain separate work. #636's existing
`speak-handoff.ps1` is still the explicit generation command.

## Use

From the repository root (PowerShell or another shell):

```powershell
python scripts/spoken_brief_inbox.py "C:\Users\you\Documents\handoffs" scan
python scripts/spoken_brief_inbox.py "C:\Users\you\Documents\handoffs" list
python scripts/spoken_brief_inbox.py "C:\Users\you\Documents\handoffs" preview <candidate-id>
python scripts/spoken_brief_inbox.py "C:\Users\you\Documents\handoffs" ignore <candidate-id>
python scripts/spoken_brief_inbox.py "C:\Users\you\Documents\handoffs" --interval 10 watch
```

`scan` takes two observations separated by two seconds. A continuously changing
file remains unpublished until its identity, size and content hash stay unchanged
for the settling period. `watch` polls every five seconds by default; its interval
is restricted to 5–3600 seconds. Stop it with Ctrl+C. It is a separate process, so
its failure cannot stop Studio's worker. There is no automatic-generation mode.

The default state is `<root>/_spoken-inbox.json`. Optional `--state <file>` and
`--speaker-id <metadata-id>` go **before** the subcommand. A custom state directory
must already exist. `list` and `preview` do not create state or lock files.

The summary shows source paths/hashes, pending or ignored status, older related
candidates, omission counts, segment/batch counts and an approximate duration
range. Duration is estimated from 120–200 words per minute plus planned pauses;
it is not a measured chapter boundary. `preview` additionally returns the exact
UTF-8 source snapshot and full compiler manifest.

The current producer is the built-in Kokoro `af_heart` control. `speaker_id` is
metadata, **not** a custom/cloned identity. Profile contracts in the #653 stack
must be integrated before this inbox can select or approve another producer.

## Identity and recovery

Within one root/compiler/speaker binding, identical source bytes yield one
candidate, even when two pack paths contain them. Aliases are retained. A changed
hash creates a new candidate linked to earlier candidates from that pack;
`COMPRESSED.md` superseding `INDEX.md` is also linked. Old source text, manifests
and Ignore decisions are preserved. Generated audio is never opened or modified.

Discovery prefers `COMPRESSED.md`, then `INDEX.md`, in each directory including
the configured root. An existing but unreadable/invalid preferred file is a
visible refusal: it never silently falls back to different content. Empty,
invalid UTF-8, oversized, non-regular or non-narratable sources remain visible as
refusals. Refusals describe the latest scan; accepted candidates are durable.

Restart loads candidates and decisions, but discards observation timers. Two
fresh observations are required before publishing newly observed content.
Persisted JSON rejects duplicate keys, non-standard numeric constants, malformed
segment records and mismatched source/manifest identities. It is a local record,
not an authenticated signature: an owner who rewrites all evidence can replace
it. A preview must not itself become generation authority.

## Filesystem and resource limits

Only regular files below the configured local root are candidates. Discovery
rejects symlinks, Windows reparse points/junctions, and linked ancestors rather
than resolving them away. It compares path and open-handle identities around
bounded reads; detected replacement or a preferred-source race is refused.
Directories beginning with `.` or `_` are not traversed, including output folders.
This is a local-workstation boundary, not a sandbox against an adversarial OS or
a same-user process with unrestricted access to every ancestor.

Each scan visits at most 2048 entries and six nested directory levels. Inputs
retain the compiler's 512 KiB limit. The scan stops after its 16 MiB source budget
(with at most one additional bounded capture). The inbox holds at most 64
candidates, 16 source aliases per candidate, 128 visible refusals and 16 MiB of
serialized state. Capacity never silently evicts accepted candidates. Archive a
full inbox explicitly and select another state file; that begins a new dedupe
history, not a continuation of the old one.

An OS-held nonblocking lock serializes cooperating writers; it releases on
process death. The adjacent `.lock` file is intentionally retained. Writes use a
flushed same-directory temporary file and atomic replacement, with parent
fsync where supported. State content, root/parent identity and lock inode are
checked again before replacement. A detected external edit is not overwritten.
Noncooperating writers must still not modify the state during an update; no
filesystem API here promises a compare-and-swap against hostile external writers.
A corrupt state file is never silently reset. Failed replacement leaves the
previous state intact; a failure after replacement can leave a committed update
without an acknowledgement, which a subsequent read observes.

## Privacy and proof

The inbox contains full handoff text and absolute root/source paths. Keep it and
its lock file outside Git and do not attach it to a PR. No handoffs, generated
voice audio, model files or reference recordings are included in this change.

Run the focused contracts with:

```powershell
python -m unittest discover -s tests -p "test_spoken_brief*.py" -v
```

Real-file fixtures cover partial writes, same-size rewrites, atomic rename,
deduplication, changed-source preservation, restart, invalid input, quotas,
concurrent writers, state corruption, write failure and replacement during open.
A Windows-only test creates a real directory junction. These are discovery and
persistence checks, not real model, pronunciation or listening-quality evidence.
