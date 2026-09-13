# Shared character edit campaign allowance

Independent edit revisions currently create generic Production projects with
independent caps. Add an explicit immutable campaign registration and a v2 edit
handoff that consumes its shared root budget. Existing v1 handoffs and study
budgets keep their current identities and behavior.

## Contract

- A canonical offline campaign receipt has a distinct opaque campaign ID,
  budget owner, 1..64 attempt cap, schema/kind and canonical SHA. Creating the
  file grants no Studio allowance and makes no network call.
- Explicit POST `/api/production/campaigns` registers the receipt and its budget
  in one existing Production database transaction. An exact repeat is idempotent;
  a different receipt for the same ID is rejected. GET by ID supports recovery.
  Registration reserves zero stages and queues nothing.
- A v2 bridge handoff pins the campaign artifact and canonical campaign identity.
  Local validation retains all existing source/canon/mask/reference file checks.
- The typed import carries the complete handoff, canonical edit plan, canonical
  campaign, ordered uploaded filenames and project name. Server validation is
  JSON-only plus existing uploaded/Comfy-input byte checks; the server gains no
  arbitrary workspace filesystem access. Canonical plan identity is distinct
  from the local raw plan file hash.
- The server verifies plan/handoff/campaign cross-bindings, current preset and
  raw template, derives the project ID from campaign ID plus edit-plan SHA, and
  requires the already registered `character-edit:<campaign_id>` budget. It
  never creates a missing campaign while staging. The registered manifest and
  allowance are rechecked in the project insertion transaction.
- Existing explicit Start reserves actual stages transactionally across all
  revisions. Interrupted, failed and uncertain starts retain reservations.
  The handoff's repair slots remain a planning constraint; this slice does not
  add a separate global repair-slot allocation system.

## Proof and execution

Use inert fixtures through the real Handler and Production storage: registration
creates no jobs; unknown campaigns cannot stage; two revisions share a cap;
concurrent Starts cannot exceed it; reopen preserves reservations; rehashed
cross-binding changes and duplicate imports fail before materialization; legacy
v1 and study roots remain isolated. Prove local file freshness separately from
pure server validation. Run focused tests, the serial full suite, validator and
one independent review before normal T2 PR gates.

This implements accounting without registering a real campaign, granting new
pilot credit, restarting Studio or submitting generation. A future live campaign
needs an owner-selected cap/membership and the existing runtime conditions.
