# Reliability contract and adversarial verification

Design and requirement IDs for #243/#257. The v0 checker only exercises declaration-level portions; full pixel, execution, browser and native proofs belong to their existing owners. A small green unit suite cannot certify the whole pipeline.

## Invariants and traceability

| ID | Requirement | Owner issue | Proof required |
|---|---|---|---|
| R-SOURCE | Originals retained; normalization explicit; hash and geometry coherent | #244 | Bounded real-file intake, orientation/alpha fixtures, no-clobber publication |
| R-SCOPE | Only reviewed effective write support may change | #245 | Every protected/outside pixel compared, including feather/scale and alpha |
| R-MASK | Selection, transparency, model mask and write/protection are distinct | #245/#246 | Polarity, null/empty/full, overlap, thin-edge and writable-padding failures |
| R-GEOMETRY | All crop/scale/pad/native transforms explicit | #245/#248 | Fiducials and odd-size corner/centre tests through real adapter |
| R-INSTANCE | References and patches bind to correct repeated instance | #249 | Swapped actor/slot, repeated canon, stale costume and contact closure |
| R-CONTACT | Coupled geometry is reviewed together | #249 | Hand-prop/handshake fixtures, visible continuity and local occlusion |
| R-OWNER | One authoritative project/campaign/worker | #250/#65 | Concurrent real Production reservation and ownership tests |
| R-UNKNOWN | Uncertain effects never gain automatic replay | #250/#123 | Accepted POST/lost reply, restart and explicit observation recovery |
| R-BUDGET | Image and analysis work is bounded and visible | #250/#178 | Cross-revision/per-case caps, failure/unknown/warmup accounting |
| R-REVISION | Stale source, masks or native document cannot apply | #251/#71/#225 | Actual native unsaved/hidden changes and shared service revisions |
| R-READ | Read/preview/navigation cannot submit expensive work | #251 | Actual browser/CLI HTTP call accounting |
| R-QUALITY | Intended change, preservation and acceptance are separate | #257/#66/#72 | Positive, no-op, occluded and wrong-edit controls with review |
| R-EXPORT | Finishing preserves a master and uses its own contract | #256 | Reopen/export/scale/alpha/tile tests and final-size inspection |

These IDs are stable acceptance references; they are not all implemented in the scaffold. A hash of a proposal does not satisfy R-SOURCE, R-OWNER or R-QUALITY.

## Fault matrix

| Injection point | Required behavior |
|---|---|
| Source replaced during capture | No mixed hash/geometry claim; bounded retained capture or explicit failure |
| Decode bomb / unsupported frame/profile | Refuse before unbounded work; original retained |
| Mask polarity reversed / generated matte supplied as edit | Explicit format/scope failure, no job |
| Effective blur overlaps protected face | New scope required, not silent subtraction or write |
| Native resize differs from declared transform | Adapter blocked; candidate retained for diagnosis |
| Before durable request intent | No accepted request identity is fabricated |
| After intent, before sending | Resolve using existing command journal; never infer remote execution |
| Server accepts, response lost/truncated | Preserve same request/project/prompt evidence; observe only |
| Candidate returned after document changed | Retain candidate, reject apply to newer source |
| Job partly succeeds then fails | Collect proven prefix if supported; unknown/never-submitted tail distinct |
| Full disk during result publication | Original and receipts remain; partial result not promoted |
| Two clients reserve last allowance | Existing transaction admits at most permitted work |
| Runtime/model changes while queued | Fresh dispatch preflight rejects stale plan |
| Native document hidden layer changes | Existing revision guard blocks import even if projection looks identical |
| Process dies during import/compare | Retain native journal; no blind duplicate layer import |
| Wrong but sharp hand passes preservation | Creative check fails; not an accepted repair |
| Correct hand has occluded digits | Critic abstains/not_visible rather than hallucinating a defect |
| Global upscale alters every pixel | Evaluate remaster derivative, not false local-preservation failure/success |

Run transport/filesystem/native faults against the real existing owner wherever possible. Stub only the expensive neural boundary, and label those tests as non-neural. A fake second state machine proving its own behavior does not prove Production recovery.

## Verification levels

**Declaration:** strict bounded JSON, types, IDs, role references, mode conflicts, proposed contact closure and rational geometry. Implemented in the v0 scaffold. It does not load source/mask files.

**Deterministic media:** actual bytes, crop/mask support, profiles, effective transforms, exact source composition and immutable publication. Extend existing character-media/pixel tests.

**Protocol/integration:** actual Handler, Workspace, Production and bridge paths with controlled Comfy responses; count requests, reservations and artifacts. Reuse current recovery and storage tests.

**Native/browser:** actual origin, native documents and saved/reopened assets with source hashes and screenshots. Distinguish inert browser fixtures, Krita API harness and real GUI keyboard/menu workflows.

**Visual task:** approved finite experiments with real model outputs, failure retention and human review. A completed job advances execution evidence only. Never add numerical pass counts from one level to another as though all tested anatomy.

## Threat and failure model

The product is a single-user loopback application with trusted local filesystem ownership, not a hostile multi-user render farm. Nonetheless, source files, image metadata, model cards, prompts, generated JSON and workflow imports are untrusted content. They cannot authorize a command, change a dependency policy or waive a mask check.

Use existing path confinement, bounded decode, registered model/node templates, loopback/origin controls and explicit native tool configuration. No arbitrary eval/shell/URL execution from a repair proposal. Keep private artwork, absolute paths, receipts and model weights outside public Git. A malicious local writer can replace all linked records; content hashes are integrity labels, not signed owner authority.

Shared packages, runtime restarts and driver/page-file changes are not automatic remediation for a memory failure. Observe actual RAM/commit/VRAM and use qualified envelopes. Error text and probe logs may contain local paths; project public summaries should be redacted without discarding private evidence.

## Resource and retry discipline

Set explicit candidate, per-case, campaign, analysis-call and elapsed limits before Start. Every materialized candidate and failed/unknown image attempt participates in the authoritative accounting; a different seed or plan name cannot reset credit. Do not silently run detectors, VLMs or matting on every UI render. Check runtime state again when queued work becomes eligible.

Retain known remote identities. Read retries may be bounded and labelled; creation/Start retries require the existing idempotency/recovery contract. Unknown cancellation is not a refund. User-directed local abandonment preserves uncertainty and cannot certify that the remote job never happened.

## Release rule and rollback

Mechanical invariants must have zero known violations in their qualified support envelope. Quality is reported per named task with uncertainty, not a blanket 100% claim. A failed critical preservation, ownership or revision fixture blocks that route. An experimental low-yield model remains explicitly experimental or manual-only, not silently promoted.

Rollback disables the new adapter/policy projection and preserves all old sources, revisions and receipts. New contracts are additive/versioned; do not rewrite old campaign identities or reinterpret legacy masks. Keep a reproducible failing packet, exact native pins and last accepted master. Removing this architecture/scaffold PR changes no active runtime path because it is not wired into the server.
