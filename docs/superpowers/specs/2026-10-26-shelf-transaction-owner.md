# One transactional owner for the local recovery shelf

Refs #825 and #392. Approved by the publication coordinator and independently
reviewed before production edits. The coordinator owns shelf UI changes; the
recovery lane owns the shelf core, adapters, native fixtures and causal evidence.

## Established defect

Hosted Ubuntu artifact 12667150927 at Library head `12ff7692` retained two
successful writers from generation 4, followed by only Tab B's generation-5
viewpoint. The original exactly-one-writer assertion remains unchanged.

A focused native Chromium 141 reproduction on unchanged shelf SHA-256
`8a18dc2f80bac6cd3974bf7788b455e9d7f322ca519f6ffc37ac2617df778441`
reproduced this in its first controlled race. Trace marks identify separate
renderer processes 163261 and 163289. The same exclusive Web Lock serialized the
callbacks: A exited at 29.1 ms; B entered at 29.6 ms but read generation 4 twice,
wrote generation 5 at 34.3 ms, and received A's storage event only at 35.4 ms.
The failure is stale cross-renderer storage visibility, not overlapping lock
callbacks. A timer, yield or additional localStorage read cannot prove a fix.

The [HTML storage specification](https://html.spec.whatwg.org/multipage/webstorage.html)
does not define cross-agent-cluster localStorage interaction. Chromium describes
its renderer cache and asynchronous propagation in its
[storage implementation notes](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/modules/storage/README.md).
The [IndexedDB transaction lifecycle](https://w3c.github.io/IndexedDB/#transaction-lifecycle)
provides the required atomic comparison and write within one readwrite scope.

## Current owner and atomic boundary

Keep the shelf bundle codec and all existing 20-record, 256 KiB record and 2 MiB
bundle bounds. One IndexedDB entry owns current recovery:
`{version: 1, raw: <exact bundle string>, legacy_digest: <SHA-256 or null>}`.
An initialized empty bundle remains an entry; deleting the final record cannot
remigrate older evidence.

Read the observed entry, validate/decode, and compute the candidate bundle and
hashes outside a transaction. A single readwrite transaction reads the entry,
compares the complete observed state, and queues its replacement synchronously
inside that request callback. No cryptographic promise or arbitrary await keeps
the transaction open. Resolve success only after transaction completion. Initial
creation compares absence in the same transaction. All append, update, import,
discard, capacity and acknowledgement operations use this same boundary.

Web Locks remain bounded cooperative coordination. They are not the storage
authority. IndexedDB unavailable, blocked, aborted, quota or readback failure
must refuse without an unlocked or localStorage fallback. Late handles close;
transaction failures preserve the prior entry and session journal. A dependent
metadata POST remains gated by the existing checkpoint owner.

## Preserved legacy compatibility

Before initialization, reads may inspect the bounded older localStorage bundle
without importing records. The first explicit mutation or enabled checkpoint
strictly validates that snapshot and atomically creates the current owner from
it. Original localStorage bytes remain untouched and separately exportable.

Ordinary updates retain the original `legacy_digest`. A newly observed mismatch
throws `code: asset_recovery_legacy_changed` and an opaque `review` token binding
the inspected full current state and legacy digest. Current shelf-dependent
mutations pause; both copies remain available for raw export. No automatic merge,
clear, repair or migration occurs. Future or malformed current state is preserved
and refused, with bounded raw evidence still exportable when readable.

The existing older client cannot be made transactional retroactively: until
reloaded it can still write its own preserved localStorage copy. Those writes
cannot overwrite the new IndexedDB owner. Divergence detection is delayed until
that browser sees the legacy write, so no immediate cross-store coherence is
claimed. The UI asks users to close or reload older tabs.

An explicit confirmed **Continue with current shelf** action calls
`acceptLegacy(review)`. The token must belong to that store, the newly observed
legacy digest must still match the inspected digest, and the atomic transaction
must still match the captured complete current entry. Only `legacy_digest`
changes. Current and older raw bytes remain identical. A further legacy write
quarantines again. No read, reload, retry or checkpoint acknowledges implicitly.

## API and verification

The existing `create({storage, locks, crypto, lockTimeoutMs})` shape remains;
`storage` supplies legacy bytes. The default backend is IndexedDB. Tests may
explicitly inject an atomic backend with `read()` returning `[]` for absence or
`[value]` for a present entry, and `compareAndSwap(expectedEntry, nextState)`.
Native `getAll(key, 1)` preserves stored null/undefined as corrupt evidence instead
of confusing it with absence. Production never silently chooses
the old implementation. Existing injected-memory contracts adapt to that API
and remain component evidence only.

`raw()` is asynchronous and bypasses compatibility/codec refusal for current
raw export; before initialization it returns the legacy bytes. `legacyRaw()`
reads the older bytes independently, even if the current owner is unavailable.
The UI awaits both, reports failed reads truthfully, and scopes tokens/completions
to its current dialog and refresh owner.

Native tests must retain renderer/lock evidence and assert both API outcomes and
actual stored winner bytes/generation. Cover initial creation, append, delete,
capacity, failed initialization, transaction abort/quota, legacy migration and
acknowledgement races. Adapt native fixture storage inspection, clear and fault
injection to the current owner; inert substitutions stay explicitly labeled.
The exact-head Ubuntu and Windows gates remain mandatory before merge; #392's
broader keyboard/assistive-technology acceptance is not closed by this fix.
