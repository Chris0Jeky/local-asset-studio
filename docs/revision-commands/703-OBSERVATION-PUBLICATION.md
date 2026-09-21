# Ordinary observation state publication (#703)

## Boundary

Ordinary Resume observation owns an existing retained prompt identity. It must durably publish the exact queued observation state before giving the in-memory job or worker queue ownership of that state. A failed persistence attempt must not leave a live `queued` record with no queue item.

The correction is stacked on #701. It does not change which jobs are eligible for observation-only admission, stopped-tracking behavior, resource-hold policy, backend switching, prompt identities, receipt interpretation, allowance accounting or generation authority.

## Publication protocol

The command builds a prospective top-level job state without mutating the live record. It writes only `state.json`; the immutable recipe and workflow are not rewritten merely to queue observation. After a successful atomic replacement, the same prospective state is published to memory and one `observe` item is queued.

An `OSError` can occur after replacement even though the exact intended state is already durable. The command therefore reads `state.json` after such an error:

- exact prospective state: treat publication as committed, publish memory and queue exactly once;
- old, missing, malformed or different state: propagate the failure, preserve the prior live record and queue nothing.

This is reconciliation of exact retained evidence, not a claim that several files form one filesystem transaction. The operation never submits `/prompt`, replaces a job identity, releases resources, refills a budget or silently retries generation.

## Regression coverage

Temporary-store tests inject failures immediately before and immediately after `state.json` replacement. They cover unresolved known prompts, terminal receipt reconciliation, a later explicit retry, exact recipe/workflow retention, and two concurrent callers after an ambiguous post-replacement error. All fixtures use inert backends and assert zero backend requests.

Merge order: **#701, then this #703 correction**.
