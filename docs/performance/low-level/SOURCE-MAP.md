# Source intake and applicability map

## Source identity and interpretation

User-supplied file: `Local Asset Studio_ Low-Level Engineering Optimisation Audit and Roadmap.pdf`; 33 pages; 304737 bytes; SHA-256 `caeed6ce6442e8c096598c8b71a1b3217a1f1be2ad7f43bba8e6967b76ce335b`.

The PDF remains the source of the recommendations below. This repository package contains a derived analysis, not a replacement or an assertion that its proposed renderer exists. No original PDF, private reference artwork, model binary, process dump or prompt trace is copied into Git.

The report's executive summary and evidence limitations (pp. 1, 32) explicitly state that the detailed repository inspection was not retained. Its main diagrams (pp. 1, 3, 30) describe source assets flowing through geometry/texture compilation, upload, scene visibility and presentation. That is distinct from the currently verified preset-to-ComfyUI generation flow.

The rendered formula on p. 17 is read as **incremental memory / source bytes**, not its reverse; text extraction can reorder the numerator and denominator. A source-file denominator is informative for media decoding but generally a poor denominator for model inference. Tensor/model/workload identity and actual memory domains are needed there.

## Report organisation retained

| PDF pages / section | Source-derived content | Disposition in this repository |
| --- | --- | --- |
| 1–2 Executive summary | Measure first; compiled asset pipeline; prioritised optimisations; cold/warm/steady/oversized workloads; desktop/mobile divergence | Adopt measurement and minimum-copy principles. Translate workloads explicitly; mobile is not an established generation target. |
| 2–6 Repository audit and runtime model | Eight asset-to-frame boundaries; texture arithmetic; duplicate resources; build checklist; compact internal representation; handles/SoA | The source calls these audit actions, not verified files. Retain graphics analysis; map actual Python/Comfy/Workspace boundaries below. |
| 6–8 Geometry, LOD, textures, materials | Deduplication, cache/fetch order, index width, packing, QEM, projected error, mipmaps, BC/ASTC/KTX and material interning | Conditional viewer/export lane. Weight quantisation and attention layouts are different representations and need separate evidence. |
| 8–10 CPU and uploads | Sequential processing, lifetime arenas, minimum-copy ledger, SIMD, coarse parallel jobs, staging-ring lifetimes | Apply bounded Pillow lifetimes now. Native tensor transfer ownership stays in the backend; no Python imitation of a graphics upload ring. |
| 10–13 GPU residency and submission | Byte budgets, fence-safe eviction, culling, state sorting, instancing, indirect draws, backend-specific policies | Adapt the budgeting principle through #178. Do not destroy backend tensors or vendor-viewer resources from Studio. |
| 13–18 Profiling methodology | Fixed corpus; detailed phases; CPU/GPU/I/O/memory tools; counter timelines; amplification; stable trace scopes | Reuse existing resource receipts and add only qualified operator detail (#364). Tool support must match the exact OS/backend. |
| 18–25 Tailored/frontier proposals | Versioned content cache, progressive tiers, LOD error, residency/copy ledgers, meshlets, adaptive policies, independent chunks | Separate deterministic media derivatives, exact conditioning reuse and hypothetical graphics chunks. No common untyped cache. |
| 25–28 Risk, compatibility and testing | Fidelity and performance independent; malformed/extreme inputs; corruption, disk-full, device loss; distributions | Adopt. Preserve all-channel RGBA checks, source identity, unknown outcomes and explicit derivative policies. |
| 29–31 Roadmap and milestones | Instrumentation → compiled representation → residency/async transfer → conditional GPU-driven rendering | Preserve as the source's graphics sequence. Repository-specific work and gates are in ROADMAP. |
| 32–33 Evidence base and limitations | R1–R14 bibliographic references and limitations; final optimisation order | Retain as research leads. A bibliography entry is not an inspected version or proof of installed support. |

## Technique-by-technique disposition

**Existing** means a verified primitive exists, not that the whole recommendation is complete. **Adapt** means the implementation below is a new proposal derived from the source.

| Technique | Disposition / owner | Required evidence before promotion |
| --- | --- | --- |
| Cold/warm benchmarks and counters | Existing observer/reducer/receipt/comparison modules; #302 remains finite execution and workstation evidence owner | Exact identities, coverage, all failures, observer overhead |
| Content-addressed canonical source assets | Existing Workspace; do not create a duplicate store | Source snapshot consistency and immutable handles |
| Compiled media/preview derivatives | Adapt under #177 | Full transform/version keys, byte caps, corruption and invalidation tests |
| Exact conditioning reuse | Adapt under #11/#35 | Complete nested conditioning, actual graph node revision and ordered reference semantics |
| Texture resize, mipmaps, block compression, KTX2/Basis | Conditional #15/#24/#177 | Exact viewer/engine support, colour/alpha/normal quality and measured residency |
| Mesh indexing/deduplication/cache/fetch/overdraw ordering | Conditional #15/#24 | Preserve seams, tangents, topology and export semantics; measure actual target |
| 16-bit indices, packed attributes, quantised vertices | Conditional #15/#24 | Boundary counts and supported formats; separate from tensor dtype |
| QEM, progressive meshes, screen-space-error LOD, impostors | Deferred until a measured graphics case | Selected/zoomed asset fidelity, silhouette and actual pixel error |
| Resource handles, dense arrays, SoA, lifetime arenas | Adapt locally where ownership and profiles justify | No speculative rewrite of Python objects or Workspace schema |
| Sequential reads, minimum copies and bounded scratch | Ready #362/#363 | Exact results plus actual allocation/latency evidence |
| SIMD/WASM/native decoding | Deferred pending profile | CPU bottleneck, packaging/support and scalar-correctness baseline |
| Coarse parallel tasks | Adapt through #178, not a new worker pool | Peak simultaneous live bytes and generation interference, not core count alone |
| Persistent upload ring, async transfer, fence retirement | Backend/graphics adapter only | Actual supported stream/fence lifetime and transfer overlap; no premature reuse |
| CPU/GPU budgets and eviction | Existing admission/owner boundaries; extend #178/#306 | Physical RAM, commit, allocator and device metrics remain distinct |
| Material canonicalisation, shader variant reduction, state sorting | Conditional viewer/export lane | Actual pipeline-switch/compile bottleneck |
| Frustum/occlusion/Hi-Z/BVH/instancing/indirect drawing | Deferred graphics implementation | Actual scene-scale and submission evidence; no controller renderer rewrite |
| Meshlets/mesh shaders/GPU-driven culling | Research only | Measured ordinary culling/batching insufficiency, fallback, capability matrix |
| Adaptive optimisation profile | Adapt #176/#178/#305 | Explicit reviewable policies; fresh admission outranks historical advice |
| Independently decompressible chunk storage | Deferred format design | A real range/chunk consumer and workload benefit before new binary format |
| Virtual/sparse textures and DirectStorage/GPU decompression | Research only | Huge-asset use case, supported API/driver and isolated proof |
| Separate fidelity/performance gates and corrupt-input tests | Adopt | No quality reduction, metadata leak or source mutation hidden as performance |

## Verified repository map

All paths below were read directly or identified in the pinned repository's own architecture/issue records. Files marked **inspected** were read in this pass; this is not a claim to have profiled their runtime.

| Boundary | Current evidence | Consequence |
| --- | --- | --- |
| Runtime and execution | **Inspected** `CLAUDE.md`, `AGENTS.md`, `.agent-harness/tier.json`: Python ThreadingHTTPServer; `Studio.prepare`, `_work`, `_request`; isolated backend ownership | Studio orchestrates; ComfyUI owns tensor execution. No new queue. |
| Source and derivatives | **Inspected architecture** identifies `app/workspace.py` SQLite/content-addressed store and `app/review_media.py` | Extend these owners; a compiled-cache proposal is not permission to replace them. |
| Review decode | **Inspected** `app/review_media.py:decode`, `make_preview`, `render_sheet` | Always invokes no-op-capable EXIF transpose before RGBA conversion; #362 is a discriminating copy reduction. |
| Protected edits | **Inspected** `scripts/character_edit_pixels.py:changed_mask`, `_verify_bundle`, `render` | Full-size difference/split buffers; separate full byte comparisons remain in bundle verification. #363 only changes scratch comparison. |
| Observation/evidence | **Inspected** `docs/performance/README.md`, ROADMAP; code search found `resource_probe.py`, `job_resources.py`, `resource_receipts.py`, `resource_comparison.py` and their CLI consumers | Reuse delivered collection and comparison. No new always-on profiler. |
| Media growth | Live #177; review notes #360/#361 | Pagination, derivative cache, all-crops retention and base64 request amplification remain separate issues. |
| Verification | **Inspected** `.github/workflows/check.yml` | Full offline lifetime suite and `validate-repo.py` are existing gates. |
| Workstation facts | **Inspected** CURRENT_STATE and HUMAN_TODO | Page-file configuration/restart is recorded complete. Do not recycle the historical unresolved-reboot advice. No fresh machine observation here. |

Initial open PR snapshot: #334 and its child #337 (disclosures), #340 (operating model). Telemetry/reference stacks mentioned in later review issues were already merged at the inspected baseline. Recheck remote state before each publication; this table is a dated capture, not a live dashboard.

## Additional primary-source verification (not claims from the PDF)

Accessed 14 September 2026. These explain mechanisms; installed support still requires a local probe.

- Pillow [ImageOps.exif_transpose](https://pillow.readthedocs.io/en/latest/reference/ImageOps.html): default non-in-place operation returns a copy even when no transpose is needed. Directly supports #362; exact-version parity is tested.
- PyTorch [profiler](https://docs.pytorch.org/docs/stable/profiler.html): supported activities are queryable; shape/stack tracing adds overhead and shape capture can retain tensor references. Short tracing windows must be measured separately from baseline execution.
- PyTorch [HIP semantics](https://docs.pytorch.org/docs/main/notes/hip.html): HIP deliberately reuses `torch.cuda` interfaces. A CUDA-labelled Python API is not NVIDIA hardware evidence.
- PyTorch [pinned/nonblocking transfers](https://docs.pytorch.org/tutorials/intermediate/pinmem_nonblock.html): transfer strategy is workload-dependent and consumer synchronisation matters. Do not assume more pinned memory is safe or faster on a 32 GB host.
- AMD [versioned Windows 7.2.1 matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityrad/windows/windows_compatibility.html): lists RX 9070 XT/gfx1201 and a specific framework/Python combination; notes that the whole ROCm stack is not present. Its migration notice points to unified documentation from Core SDK 7.13.0. This is a historical version matrix, **not a declaration that 7.2.1 is the latest release** or permission to upgrade.

The PDF's R1–R14 cover glTF, quantisation, KTX/Basis, Vulkan, D3D12/PIX, Metal, meshoptimizer, Garland/Heckbert, Hoppe, RenderDoc, Nsight, Radeon GPU Profiler, Linux perf and DirectStorage. They are retained as the graphics research bibliography; this pass does not certify every reference, formula threshold, hardware capability or estimator in that catalogue.
