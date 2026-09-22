# Explicit narration registry updates

The version-2 registry implements #671's local revision and replay contract. It
stores commands and their derived receipts together in one bounded JSON file.
Current profiles are reconstructed from that history and the exact checked-in
catalogue. Reading never locks, writes, migrates or repairs the registry.

Choose an existing private directory (for example `_voice_profiles`) and inspect
the proposed registry path. A missing registry is an empty journal over the
catalogue; inspection does not create a file or directory.

```powershell
python scripts/voice_profile_registry_cli.py --registry _voice_profiles/registry.json inspect
python scripts/voice_profile_registry_cli.py --registry _voice_profiles/registry.json update --command _voice_profiles/update.json
python scripts/voice_profile_registry_cli.py --registry _voice_profiles/registry.json receipt revision-a
```

An update command contains exactly:

```json
{
  "schema_version": 1,
  "request_id": "revision-a",
  "expected_registry_sha256": "<registry_sha256 returned by inspect>",
  "expected_profile_sha256": "<SHA-256 of the exact current profile>",
  "profile": "<complete replacement profile object>"
}
```

The placeholders illustrate the fields; replace them with hashes and a validated
profile object before running `update`. Python callers can use
`voice_profile.profile_digest(current_profile)` to compute the predecessor hash.
The replacement must retain the existing profile ID, strictly increase its
integer revision, and set `supersedes_profile_sha256` to the current profile hash.
Version 2 updates existing catalogue identities; adding unrelated identities or
migrating a legacy registry is outside this command.

The first local revision names the catalogue profile. The next revision names
the exact preceding local profile. Both expected digests are compared under an
OS-held cross-process lock. A stale writer cannot consume its request ID or
publish a profile. Competing commands from one predecessor have one winner.
If the file changes while a caller waits for the lock, that call refuses even
when the bytes match; the caller can inspect and explicitly retry.

Each accepted request retains its full command and a deterministic receipt with
its sequence, command digest, previous registry/profile digests and resulting
profile digest. Reusing an ID with different content refuses. Replaying the exact
command returns the original receipt, including after later revisions or a
process restart. This does not submit narration or repeat inference.

## Storage and failure outcomes

- Commands are bounded to 256 KiB. Journals are bounded to 256 transitions and
  4 MiB. A full journal refuses new commands while preserving historical replay;
  accepted IDs are never pruned into reuse.
- The lock uses Windows byte-range locking or POSIX `flock`, has a bounded
  timeout, and is released by the OS after process death. Its `.lock` file stays
  in place; deleting it is not a recovery procedure.
- Registry and lock paths reject symbolic links, reparse points, non-regular
  files and hard links. Parent directories must already exist. Reads compare
  path and open-handle identities and bound the bytes actually read.
  Windows callers must use canonical long paths: short filename aliases are
  refused before ownership can split across differently named lock files.
- Before publication, commands and receipts are encoded into one file, flushed
  with `fsync` in the same directory, and published with `os.replace`. Identity,
  catalogue and lock ownership are rechecked before replacement and before
  acknowledgement. POSIX also flushes the parent directory. Windows proves
  process-crash recovery; sudden power-loss directory durability is not claimed.
- A failure before replacement preserves the prior registry. A process crash
  during the pending write may leave `.registry.json.pending-*` evidence;
  readers ignore it and never automatically promote it.
- Once replacement is attempted, a lost response, changed path, directory-flush
  failure or unlock failure may return **unconfirmed**. Keep the original
  command and request ID. Inspect its receipt, then replay that exact command to
  reconcile. Do not mint a replacement request merely because acknowledgement
  was lost.

CLI exit codes are 0 for a successful read/update, 2 for refusal and 3 for an
unconfirmed publication. A missing receipt is `result: null`, not approval for
another command. The contract coordinates cooperating writers and detects
observed external changes; it does not authenticate filesystem contents or
prevent arbitrary external actors from replacing the files.

## Compatibility and evidence

Version-1 catalogue-bound overlays remain readable under their existing rules.
The update command refuses them without implicit migration. Spoken Briefs can
resolve version-2 profiles through the same read-only profile selector. Producer,
qualification, permission and human listening requirements are unchanged.

Local Windows proof: 77 voice-profile tests pass (five filesystem capability or
POSIX-only skips), and 121 Spoken Brief tests pass (seven existing optional
dependency skips). These include actual competing processes, process death after
flush/replacement, lost replies, external replacement, CLI restart/replay, strict
JSON and receipt tampering. Full-suite, independent-review and hosted evidence
belong to the PR; no audio or live generation was performed for this change.
