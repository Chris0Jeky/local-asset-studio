# Agentic creation evidence lab

## Intent and scope
Turn two supplied research reports into inspectable, source-preserving engineering inputs and a small working evidence toolchain. LAS remains the orchestrator. The existing MCP, qualification, resource-admission, native-export and provenance implementations retain ownership. No new scheduler, unrestricted code socket, agent framework, app route or GPU environment is introduced.

The public repository contains reusable code, source-free synthetic fixtures and a generalized programme. Complete report originals, private character details and actual asset evidence stay in a private local archive/private companion workspace. Importing text does not verify its claims. Existing project decisions override research recommendations; in particular, artistic acceptance is not inferred from metrics.

## Alternatives and decision
1. Documentation only: cheap but does not turn proposals into reproducible evidence.
2. New persistent worker/MCP orchestration stack: duplicates current owners, introduces state/recovery risk before latency has been measured.
3. **Chosen: additive offline evidence lab plus a bounded read-only Blender probe.** Implement report intake, integrity receipts, content-pinned probe intents and structural/image comparison first. Keep native rendering/export integration as the next explicit slice, using current owners. This choice is the implementer's interpretation of the request, not an assertion of a separately approved design.

## Deliverable boundaries
- Import completed Deep Research JSON without executing, browsing or rewriting its source. Preserve exact raw bytes and exact report Markdown; derive separately linked Markdown and a URL index. Retain unknown references. Exclusive output directories, hashes, finite/duplicate-safe JSON, bounded inputs.
- Plan a read-only probe against the executable selected in `config/local.json`. Pin source, executable and script bytes. Plans are non-executable intent records, not admission decisions or execution receipts.
- Inspect base geometry connectivity/coordinates, UVs, weights, morphs, bones, materials and layered/legacy actions without calling mutating ensure APIs. Fail on budget exhaustion, rather than silently truncate. No saves, rendering, repairs or GPU inference.
- Compare declared scene observations and bounded PNG views. Missing evidence is incomplete; different capture contracts are incomparable. Hash mismatches, path escapes and symlinks are refused. Required/hold-out views are supplied independently of the candidate. A technical match is not visual, artistic, native-runtime or distribution acceptance.
- Record hypotheses, contradictory source claims, phased experiments, existing integration seams and actual verification limits.

## Non-goals
No canonical source replacement, live character changes, model download, dependency/driver upgrade, remote asset transfer, paid execution, camera/microphone use, or automatic baseline promotion. A Python subprocess is not an OS sandbox. Hashes establish byte identity, not trust, licensing or authorship.

## Verification
Test-first offline contracts cover tampering, incomplete captures, topology changes at identical counts, changed image pixels, camera mismatch, source preservation, malformed JSON, path traversal, symlinks, duplicate IDs and budget errors. Actual Blender/Windows/AMD execution is separately required and cannot be claimed from fake API fixtures or container tests. Self-review is not independent review.
