# P36 current-authority implementation plan

**Goal:** keep every character-family transition anchored to the exact accepted concept, while checking current Studio authority and retaining all licence facts at export.

**Architecture:** retain the previous P36 kernel byte for byte at its pinned PR head; add independent semantic vetoes, a read-only Workspace adapter, durable attempt reservations, and a guarded draft exporter. The prototype never submits a generation. Its admission records are evidence for a future Studio worker integration, never transferable permission to submit later.

**Stack:** Python 3.12+, standard-library SQLite/JSON/hashlib, existing Pillow and jsonschema for the retained prototype. No runtime install or upgrade. No C++ compilation.

## Kill criteria first

- Any required root-relative identity failure, missing view, unknown observation, stale concept, or semantic side swap blocks the next stage.
- An old acceptance receipt cannot outlive a withdrawn or changed Workspace acceptance, changed card canon/revision, changed media, or a mismatched Workspace.
- Any unresolved reserved/submitting/uncertain attempt blocks a fresh attempt, including attempts that produced no artifact or prompt ID. Failed attempts require an explicit observed terminal resolution; no automatic retry.
- Same-byte reuse cannot discard different source or licence facts. Conflicts block export for reconciliation.
- A schema-valid draft is not a current-Unreal-import admission. The existing importer lacks transactional and authority guards; this run must never claim direct import readiness.

## Reuse and decisions

Pinned baseline: Studio `0270760a3d4fd9e005a1788bba59d8242b77c2f4`. Earlier P36 PR #2046 remains unmerged at `80b274e8dde6b0333c4d39a9473f6e15e41f38e1`; its graph, pixel proxy, exporter, fixtures, schema and regression tests are retained with exact hashes in `UPSTREAM.json`. This makes the fixed-base branch reproducible without a hidden dependency on another unmerged branch. New modules compose the kernel rather than changing it. The old export CLI is a historical baseline; adoption uses the new guarded entry point.

An accepted character card is not assumed: `app/characters.py` deliberately allows any image as canon. The adapter therefore reads `asset_acceptances` independently and binds each required artifact to a live `local-user` acceptance for the intended stage use. These are local declarations, not authenticated signatures. No check infers licence clearance from art acceptance.

Alternatives considered: another offline receipt engine would duplicate #2046; immediately wiring the web server/worker would widen this prototype and require real-machine queue qualification. A bounded real-SQLite adapter with explicit next integration steps gives testable progress while preserving the requested run-local scope.

## Task and interface ledger

- [x] 1. Retain the pinned prior kernel and source inventory; audit current consumer hazards.
- [x] 2. `studio_authority.py`: `capture_authority(experiments, family, binding, *, stages)` reads the actual schema without instantiating/migrating Workspace; validates live asset/card/acceptance rows, retained jobs and bytes. `check_transition(...)` recomputes the old graph gate plus current authority and semantic vetoes.
- [x] 3. `attempt_ledger.py`: reserve an immutable request identity in a local SQLite ledger before a caller could dispatch; unresolved reservation blocks another request. A matching request is idempotent evidence, never a new submission. Resolution is bound to exact retained job evidence.
- [x] 4. `sheet_identity.py`: recompute the retained proxy then apply exact anatomical-side/semantic checks under a frozen concept-bound policy. Cosmetic contexts can change only named costume anchors; identity anchors remain mandatory.
- [x] 5. `export_guard.py`: `build_guarded_manifest(...)` rejects conflicting repeated-file facts before the retained exporter deduplicates, then adds explicit consumer admission limitations under the existing root extension.
- [x] 6. `prove.py`: one offline command runs inherited and new tests, real Workspace fixture cases and deterministic evidence; outputs go under a fresh `.runtime/` directory. Store compact summaries and SHA-256 manifests on the branch.
- [ ] 7. Publish source-backed first-character gates, cross-repo adoption and an additive plan on Lumenfold issue #3175. Run the repository proving commands and inspect every README-linked deliverable before marking ready.

## Review focus

Test withdrawal after capture, wrong Workspace with the same asset ID, changed bytes after a green report, stale/forged acceptance subject, uncertain no-output jobs, duplicate licence provenance, requested costume-context substitution, malformed/nonfinite JSON, path aliases and cross-process duplicate reservation. A green snapshot can become stale immediately: final Studio worker and Lumenfold importer must reread authority at their own mutation boundary. This run provides no authenticated remote authority protocol and no native transaction.

## Evidence limits

Synthetic drawings and SQLite records are software fixtures. All character output claims remain planned; implemented tests do not establish perceptual recognition, Sable acceptance, rig quality, Windows/AMD performance, or Unreal playability. Existing owner choices remain open. Reports distinguish configured-machine historical receipts from this Linux run.
