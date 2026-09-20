# One owner for a complete provider metadata fetch

Follow-up to #433/#438 on the #579 transport stack. This concerns the two public
`fetch_huggingface` and `fetch_civitai` facade operations, not model execution.

## Equal payload hashes do not identify a request

One Hugging Face response body can legitimately answer both a moving revision and
its resolved commit URL. The transport previously shared its current receipt
between calls without owning the complete parse/finalize/result interval. An
interleaved call could replace that receipt while retaining the same payload
hash; the first caller could then export its snapshot beside the second request's
receipt. With caching enabled, a refused second call could instead abort the
first caller's pending cache write.

Each facade fetch now takes a non-blocking, per-transport scope before validating
its provider arguments. The scope lasts through exchange, provider parsing, cache
finalization and copying the receipt into the result. Concurrent or nested facade
calls refuse immediately; they do not wait, retry, clear another call's receipt,
or abort its pending response. Use separate transports for intentional parallel
fetches.

Only the owning operation clears its current receipt on entry or failure. Invalid
arguments, semantic refusal, transport failure, cache-publication failure and
interruptions all release the scope. Cleanup re-raises the original exception,
including an interrupt, rather than swallowing it. Already returned result copies
remain unchanged. The current `receipt` property is unavailable after an owned
fetch fails instead of presenting an older success as the failed call's evidence.

An existing raw response awaiting finalization is also preserved: a refused facade
fetch cannot discard it. Its caller may still finalize or explicitly abort it.

## Exact boundary

The scope is not a general thread-safety guarantee for every method. Direct raw
`transport(request)`, `finalize`, `abort`, attribute mutation and observation of the
mutable current receipt still require caller-managed serialization. Do not mix
those operations concurrently with a facade fetch. It is not a cross-process
cache lock, deadline, queue or synchronization mechanism between transport objects.

A failure after cache publication cannot undo already published bytes. It clears
the current operation state but does not claim rollback or permanent historical
retention. #694 owns immutable payload history; #687 owns HTTP framing; #732 owns
provider claim consistency. Those independent changes are not included here.

## Evidence

Seven regression methods use actual provider parsers and temporary caches, with
fake exchanges only. Event-coordinated threads pause at the real result boundary;
no sleep or performance threshold schedules the interleaving. Tests cover equal
payloads at different request URLs, cache/no-cache overlap, nested cross-provider
calls, stale receipts, argument/identity refusal, raw pending ownership, interrupts,
cache write failure and successful sequential recovery. Threads are released and
joined even on failed assertions.

```sh
python -m unittest tests.test_adult_illustration_source_operation_ownership -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py'
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

No provider is contacted by these fixtures. No model or image bytes, credentials,
installation, generation, training, inventory or promotion authority is introduced.
The parked programme and HUMAN_TODO q-29 remain unchanged.
