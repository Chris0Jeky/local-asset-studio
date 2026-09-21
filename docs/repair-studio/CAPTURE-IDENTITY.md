# Repair source capture identity

## Scope

This is a bounded follow-up to #244's existing normalized source intake and #245's
existing transform/packet path. It does not replace either pipeline. Main
`f8fcc40f7388c23d13309c20c2776017a20004b2` already includes the source, panel and
pixel-transform implementation; #279's remaining artistic/native acceptance is
not a request to build another compositor.

`scripts/repair_source.py::read_bounded` now refuses detected file changes during
capture before its caller decodes or publishes a normalized packet. Successful
capture still returns immutable bytes: replacement of the original pathname
*after* that capture does not make downstream normalization silently reread it.
The existing byte/hash/pixel provenance and no-clobber publication are unchanged.

## Read contract

1. Validate an exact, nonnegative integer byte limit.
2. Inspect a regular file and refuse a declared size above that limit before
   opening or allocating its contents.
3. Open read-only; use nonblocking open where supported so a regular-file-to-FIFO
   swap cannot wait indefinitely for a writer.
4. Compare device, inode, size and nanosecond modification time between the path
   observation and the opened descriptor before reading.
5. Read at most `limit + 1` bytes once. Retain the existing exact byte-limit check.
6. Compare descriptor identity/size/modification/change time before and after the
   read, compare the same path facts before and after capture, and require the
   returned byte count to equal the original observed size.
7. Close the descriptor on every failure, including an exception before stream
   ownership transfers. A detected change refuses; no partial packet is created.

Change time is compared only within its path-stat or descriptor-stat API domain.
The path and descriptor APIs need not report the same change-time interpretation
on every supported Python/Windows combination. It is not used as the cross-domain
identity key.

The source-input default deliberately continues to follow a symlink. Packet
members use the existing `reject_symlink=True` policy: reject symlink/reparse
metadata before opening and use no-follow open where available. This is not an
ancestor traversal policy or a blanket symlink ban on original user inputs.

## Evidence and limits

The initial eight test methods produced six assertion failures against main. The
14-method final capture suite covers replacement between stat and open; in-place
rewrite; growth and truncation; exact and exceeded limits; invalid limits; empty
files; explicit link policy; reparse metadata; same-domain change-time drift;
different path/descriptor change times; descriptor cleanup; and both an existing
FIFO and a regular file swapped for a FIFO. The swap runs in a bounded subprocess
so a regression to blocking open cannot hang the test runner. POSIX-only cases
skip explicitly on Windows; link-creation tests skip when the environment denies
that capability.

```console
python -m unittest discover -s tests -p 'test_repair_source_capture_identity.py' -v
python -m unittest discover -s tests -p 'test_repair_*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The existing **Repair intake contracts** workflow already runs the full repair
pattern on Ubuntu and Windows; no workflow or runtime dependency is added here.
The final PR records exact-head local and hosted results separately.

This detects the tested local races; it is not a filesystem snapshot, cross-process
writer lock, sandbox or authentication boundary. A hostile process able to restore
all observed metadata, manipulate parent traversal, or exploit filesystem identity
limitations is outside the guarantee. The check does not guarantee bytes remain
unchanged after capture, that a future read returns the same bytes, or that a
normalized image is artistically acceptable. No model execution, geometry change,
colour-policy change, private-media publication or HUMAN_TODO decision is included.
