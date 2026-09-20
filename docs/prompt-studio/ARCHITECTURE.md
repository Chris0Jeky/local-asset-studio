# Intent compiler and a more general Studio

The durable object should be what the user intends to make, not a prompt string tuned to one checkpoint. This proposal extends the existing asset and audiovisual project work without another queue, model manager or editor rewrite. The implementation is a bounded first slice, not the complete architecture below.

## Pipeline and ownership

`brief + references + embedded claims → proposed observations → CreativeIntent → model/graph profile → compiled fields and control plan → explicit review → existing executor → result and acceptance → reusable evidence`

**CreativeIntent** owns subject, action, composition, style, motion, voice/sound direction, exact speech/lyrics, reference roles, avoidance terms, constraints and locks. **Profiles** own dialect, supported inputs, slots, native fields and budgets. **Bindings** own exact graph locations and template identity. **Executions** own resolved weights/nodes/runtime/seed and actual outputs. **Acceptance** owns the brief-relative judgement. These records should link by immutable hashes but remain distinct.

The helper is an analyst, not a controller. It proposes named field changes, observable reference descriptions and unknowns. The deterministic compiler handles syntax, constraints and unsupported fields. This avoids depending on a small language model to remember every backend rule, tool permission and graph shape in one free-form answer.

The supplied core preserves the complete brief even when a profile cannot use a field. It never silently truncates or deletes exclusions. Native token counts remain null until an actual tokenizer can measure them; character caps are application budgets, not fake token counts. Exact speech and lyrics are separate data, not prose the helper is free to improve.

## Profile engineering

Each production profile should eventually pin checkpoint lineage, prediction type, encoder/tokenizer revisions, graph fingerprint, node contract, sampler/distillation variant, actual negative-conditioning behaviour and permitted control mechanisms. A family name alone is too broad. A profile may map to several validated execution bundles, but the chosen bundle must remain explicit.

For LoRAs, use a compatibility tuple and source-backed trigger metadata. Never invent a trigger token because a file has a descriptive name. Add adapters independently and compare them against an unchanged base. Tags, phrase weighting, prompt scheduling and regional conditioning require the exact parser/node implementation; syntax resembling another tool's convention is not proof of support.

The shipped 12 profiles are reviewed projections and contain scope notes. They are not pinned model-install locks or universal claims about every derivative. Unknown profiles and incompatible tasks fail rather than falling back to generic prose. A syntax profile's success cannot remove an existing runtime block such as H3's crash guard.

## Reference roles and reverse prompting

Each reference carries an ID, byte hash, kind, role and take/ignore instructions. Pose evidence may propose action/composition/motion, not a replacement identity. Style evidence may propose style/palette/light/mood, not copy the reference's subject. These restrictions reduce accidental cross-contamination; they cannot mathematically disentangle a generator or prevent a model from lying about its evidence source.

Embedded metadata is untrusted source evidence. Visual reconstruction is an inference. User requirements take priority over both. Let the user choose faithful reconstruction, extracting only selected design traits, or a deliberate creative variation. Keep observed and inferred properties distinct. A model cannot infer a unique seed/checkpoint/lens/prompt from pixels.

Hard alpha, exact protected regions, pose contact, frame timing, geometry or rig requirements need the appropriate asset pipeline. The compiler returns unresolved structural-control diagnostics rather than promise that more prompt words enforce them. A constraint remains an acceptance test after compilation.

## Shared editing and progressive disclosure

Begin with “what are you making?”, optional references and a model-specific preview. Expose only relevant controls, then allow advanced access to the full intent, source trace and graph. Reference roles and locked details should be visible. An unfamiliar technical choice should have a concrete effect description and a reversible default, not a wall of unexplained sliders.

Manual edits, CLI actions and agent proposals should use the same revisioned commands. The implemented proposal API checks the expected intent revision, accepts an explicit field subset and returns a new copy plus reversible operations. It is not a database transaction, authenticated signature or multi-client lock. The later shared project service must perform real compare-and-swap and persist approval/history.

The delivered page extends the normal Studio handler and delegates normal routes unchanged. Startup binds the loopback port before creating Studio, then attaches the same Studio instance to the extended handler; it has no model calls on load and does not submit generation. The local helper is CLI-only for now. Live reference upload/binding, one-click proposal generation, saved intent projects and typed MCP tools should attach to existing issues21/22/30 rather than create competing systems.

## Efficient local execution

Use pure compilation before neural analysis. Reuse a prior accepted intent when only the target model changes. Reuse accepted image observations when pixels, crop/matte policy and analyzer version are unchanged. Run the smallest helper that meets the task; escalate only uncertain or failed cases. Release helper residency before large diffusion/video jobs on the single GPU.

The adapter verifies installed model identity, sends one bounded request, requests unload and optionally caches the exact request/model digest. Image analysis gets at most three resized references; original hashes and processing are recorded. The helper cannot download a model, follow an arbitrary URL, call tools or submit a media job. Its per-workspace lock is not a system-wide GPU reservation; a shared resource scheduler remains future integration work.

A production cache key needs all effective inputs: full brief/reference hashes, selected crops, analysis preprocessing, helper model/template/runtime, profile when profile-specific advice is requested, and parser version. Generation cache keys additionally include graph, weights, adapters, schedules and output settings. Do not call a cache hit valid merely because the original text matches. The current cache is capped at64 records and requires explicit eviction.

## Generality without an unbounded framework

Treat model prompts as one adapter type among many: layer edits, timeline commands, geometry operations, voice takes, music sections and engine exports have their own input/output contracts. The same intent may branch into a painted portrait, layered puppet or rigged character. Preserve intermediate representations so changes can target the cheapest appropriate stage.

Add capability descriptors with state: researched, installed, schema-tested, executed, accepted. Include supported inputs/outputs, references, resource requirements and reversible operations. Compose only compatible stages; an image-to-mesh model's output is not automatically a rig or a playable animation. Keep environment setup and creator permissions separate from prompt quality.

The architectural test is one shared asset request expressed through several supported paths, with visible tradeoffs and retained results. The acceptance metric is useful output per total effort, not the length of the prompt or the number of tools invoked.

## Validation and promotion

Unit-test schema, Unicode, locks, reference roles, budgets, profile mappings, metadata bounds and stale bindings. Contract-test exact installed node schemas and local runner APIs. Benchmark actual generations separately with fixed briefs, unchanged baselines and rejected outputs. Use native tokenizer measurements before enforcing token limits. Maintain migration tests when profile or IR schemas change.

Only promote a helper/profile combination after it improves a task-specific benchmark and passes a held-out set. Human preference may guide optimization, but critical requirements stay hard checks. Limit repair attempts; identify whether a defect belongs to wording, reference conditioning, graph settings, model capability or deterministic finishing before changing anything.
