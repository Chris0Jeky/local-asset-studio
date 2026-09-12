# Recovering character-edit evidence without another generation

This is the focused #71 follow-up to the [Studio bridge](STUDIO-BRIDGE.md), not a
new executor or a native Krita plugin. It tightens three contracts: candidate
publication, the optional image-reference slot, and declared actor contacts.

## Candidate publication

`collect` still validates the existing Production plan, deterministic stage/job
ownership, single output, known prompt ID, exact recipe, Workspace asset hash and
image dimensions. It performs only GET requests. It now publishes the image and
receipt as one directory rather than making `candidate-0/` visible before its
receipt exists.

```text
existing completed job / known prompt / Workspace asset
                         |
                validate and download (GET only)
                         |
           .candidate-0-<unique staging name>/
              candidate.png + receipt.json
              exclusive writes, file fsync
                         |
          read back bytes + receipt; recheck sources
                         |
         rename sibling directory under command.lock
                         |
                   candidate-0/
              candidate.png + receipt.json
```

The receipt points to the final path, never the random staging path. It is bounded
by the same JSON byte limit used when reading receipts. Files are checked again
before publication. Changes to the source, mask, canon, references or handoff
while downloading/writing block publication. The original generation, source
image, allowance, prompt IDs and project are not modified.

A failed staging directory is retained as evidence. The next explicitly requested
collection revalidates the authoritative existing Studio job and writes a fresh
staging pair. It does **not** trust, repair or silently adopt partially written
staging files, start a model, or spend another allowance. This deliberately trades
some retained disk use for simple, inspectable recovery; there is no automatic
cleanup or retry loop.

### What to do after interruption

| Observed state | Action |
| --- | --- |
| `.candidate-0-*` exists, but `candidate-0/` does not | Preserve the staging directory and rerun the same `collect` command after addressing the storage error. Original dependencies and the recorded Studio job must still validate. |
| `command.lock` remains after a killed process | Confirm that the recorded process is no longer running **and no bridge writer is active**. PID absence alone is not a universal PID-reuse guarantee. Remove only that stale lock, preserving all journals and outputs, then rerun `collect`. The client never steals a lock. |
| `candidate-0/` contains both the verified image and receipt | Publication succeeded. Inspect it and continue with `compose`; another collection remains a no-overwrite error. A lost command response is not permission to regenerate. |
| An older client left a partial final `candidate-0/` | It remains blocked and unchanged. Inspect/preserve it and the original Studio job before any manual filesystem repair. This change does not automatically migrate legacy partial final directories. |
| Current source/mask/canon/handoff differs | Do not force collection or rehash evidence to bypass validation. Preserve the completed job; reconcile the actual document revision before another edit. |

The existing commands and receipt schema are unchanged:

```console
python scripts/character_edit_bridge.py status --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json
python scripts/character_edit_bridge.py collect --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json --index 0
python scripts/character_edit_bridge.py compose --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json --index 0 --current-document document.json --out recovered-proposal
```

Use the actual workspace/handoff names. `recovered-proposal` must be a new output
location. `compose` verifies the current exported document, not unsaved native
Krita state.

### Filesystem boundary

The temporary directory is created securely as a sibling of the destination, so
publication does not cross filesystems. Cooperating bridge commands hold the
existing exclusive `command.lock`. Existing files, directories and symlink
entries at the final destination are rejected, including a destination found on
the second check immediately before rename. The implementation uses `os.rename`,
not an overwrite-oriented `os.replace` for candidate directories.

This is an ordinary local-filesystem process-interruption contract. It does not
claim power-loss durability of directory entries, special/network-filesystem
semantics, or race-free protection against an unrelated process deliberately
modifying the same directory outside the bridge lock. Python documents POSIX
successful rename atomicity and differing Windows destination-exists behavior;
the Windows CI lane tests the bridge's supported operation rather than inferring
it from Linux alone. File `fsync` is not a universal directory/power-loss proof.

Primary API references: [Python os.rename](https://docs.python.org/3/library/os.html#os.rename),
[os.fsync](https://docs.python.org/3/library/os.html#os.fsync), and
[tempfile.mkdtemp](https://docs.python.org/3/library/tempfile.html#tempfile.mkdtemp).

## Reference roles: one composition slot, one identity slot

The supported native projection is exactly:

```text
qwen-2ref: [current source crop: composition, actor reference: identity]
qwen-3ref: [current source crop: composition, actor reference: identity,
           optional actor reference: costume OR style OR pose]
```

Prepare can receive the actor's identity/optional inputs in either authored order;
it emits identity first. A second `composition` reference is rejected before
creating a handoff directory or making an HTTP request. Handoff validation also
checks exact slot order and the optional role, including when a caller recomputes
the JSON hash. Hash consistency does not certify the slot semantics.

The offline document schema can still describe composition references for other
future routes. It is this single-actor Studio bridge that lacks that optional
capability. References are never silently dropped or relabelled. Older invalid
handoffs are refused, not automatically migrated or used to create fresh budgets.

## Actor contacts: relationships and regions must agree

For both scenario and interaction plans, each contact region must describe a
connected group in the explicitly declared **undirected contact graph**. Every
declared contact between target actors must be covered by at least one region.
Contact relationships involving an unchanged actor are outside this target check;
regions still cannot silently include unchanged actors.

Examples:

| Declared contacts | Region actors | Result |
| --- | --- | --- |
| A-B | B-C | Rejected: the region does not describe the declared pair. |
| A-B | A-B-C | Rejected: C has no declared connection inside the region. |
| A-B and B-C | A-B-C | Valid joint review scope; it does **not** invent A-C contact. |
| A-B and B-C | A-B only | Rejected: B-C lacks a review region. |
| A-B and C-D | A-B-C-D | Rejected: split disconnected groups into separate regions. |
| A-B | B-A, repeated for two different joints | Valid: contact is undirected and multiple local review regions are allowed. |

Scene-only plans with no contact declarations or regions still work. A scenario
that adds contact regions must explicitly declare the intended pair(s). Existing
scenario fixtures were corrected to omit incidental, undeclared contact regions;
positive interaction and scene tests are retained. Rehashed plans go through the
same validation in `check_plan`.

This validates internal proposal consistency, not limb geometry, collision,
physical contact in generated pixels or native multi-actor conditioning. The live
Studio bridge remains single-actor; true scene execution is still #71.

## Verification and remaining gates

See [EDIT-RECOVERY-VERIFICATION.md](EDIT-RECOVERY-VERIFICATION.md) for the causal
failure counts and actual tests. The new path-filtered Windows workflow runs the
character-edit suite with synthetic inputs, local HTTP, real file publication and
an intentionally terminated collector. No model or native application is installed.

Native unsaved-document synchronization, real anatomy/costume acceptance,
cross-revision campaign budgets and the separately tracked definitive
project-creation rejection protocol remain open. Neither successful collection
nor exact protected pixels imply artistic approval. `HUMAN_TODO.md` is unchanged.
