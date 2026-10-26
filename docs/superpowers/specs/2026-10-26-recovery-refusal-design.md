# Retained last-refusal explanation

Refs #393. Approved bounded continuation of the existing asset recovery owners.

## Intent and scope

A person returning to an exact unconfirmed metadata command should still see why
its most recent refused POST attempt was refused. Typing, reopening, reloading
and a shelf round-trip must preserve that explanation and every original command
byte, target, revision and newer draft. One refused attempt does not establish
whether an earlier attempt committed. No automatic request is added.

## Approach

Add optional `last_refusal` beside `operation` in the existing version-2 detail or
Library payload. A separate store would create another recovery owner. Nesting
it in `operation` would violate the existing immutable-command checkpoint rule.
Both alternatives are excluded; the top-level carrier was approved by the
coordinator. Old payloads without the field remain valid.

The annotation has exactly these fields: `version: 1`, `workspace_id`,
`request_id`, integer HTTP `status` in 400–499, `message` of 1–1,000 Unicode code
points and at most 4,000 UTF-8 bytes, and integer `observed_at` from 0 through
8,640,000,000,000,000. Optional `code` contains 1–64 ASCII letters, digits,
underscores or hyphens. Workspace and request identities must match a present
pending operation in a version-2 payload. Extra fields, unsupported versions,
invalid identities/types/bounds and annotations without that operation refuse
the record without replacing its retained raw evidence.

## Ownership and integration

The journal owns a synchronous `recordRefusal` operation: read the latest payload,
require the same body and Workspace/request identities, then use the existing
verified write and checkpoint notification. The current request/editor/Workspace
guard remains with the existing POST handler. Explicit mismatching/null/empty
error-envelope identities and `asset_workspace_conflict` do not annotate.
GET errors and unknown receipts do not create or replace a POST explanation.

Carry the annotation explicitly at `rememberAssetDetails()` and the Library
handler's existing journal reconstruction. Avoid implicit merging in every
journal write. The detail handler adopts the returned updated record before its
`finally` retention step. A verified conflict transition, confirmation, explicit
session discard or different command does not inherit the old annotation.
Historical shelf snapshots remain until explicit shelf discard, as they already
do when a current journal is cleared.

Annotation storage failure is secondary: keep the command/draft and original
refusal visible, and say its explanation could not be retained. Never imply the
already attempted request was not sent. Display bounded literal text in existing
recovery panels, using their current focus-preservation behavior. Do not add
focus calls or controls.

## Compatibility and acceptance

Shelf projection/hash/export/import/restore retains the field. An older open tab
has a strict codec and may refuse a newer annotated shelf; its existing raw
evidence preservation remains intact. Document reload/update as the compatibility
boundary instead of weakening validation or silently dropping explanations.

Causal contracts cover both slots, newer drafts, exact bodies, stale/foreign/ABA
ownership, tampering and bounds, storage faults, cleanup and read-only recovery.
Native HTTP/SQLite/browser coverage exercises persistence and literal/focus
behavior. Complete keyboard conflict/lifecycle acceptance, screen readers and
browser-menu interaction remain #393 work. `HUMAN_TODO.md` owner choices remain
unchanged.
