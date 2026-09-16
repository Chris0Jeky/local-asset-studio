# Local Asset Studio product direction

**Last reconciled: 15 September 2026**

This document is the concise public product-direction layer. It complements the deeper strategy, research, status, architecture, and implementation records; it does not replace their evidence or turn open work into shipped capability.

## North star

Local Asset Studio should become the most understandable way to operate a powerful local generative-asset stack.

A user should be able to state a creative goal, provide one or more references, understand the route the Studio proposes, make deliberate changes, execute locally, inspect what happened, compare alternatives, accept or refine an output, and export it to a real project without losing provenance or control.

The same safe operation should be available through the UI and a bounded headless/agent interface. Agents may plan, research, compare, and operate within declared capabilities; they must not acquire models, mutate environments, execute expensive jobs, publish assets, or clear licences merely because they discovered a plausible route.

## Product identity

The Studio is not only a ComfyUI skin, model launcher, image gallery, or prompt helper. It is five products sharing one local evidence model.

### 1. Creative cockpit

Goal-led recipes, progressive controls, understandable model/environment choices, previewable plans, and reliable execution for images, video, 3D, edits, refinement, and native finishing.

### 2. Reference intelligence

Multiple references with explicit roles—identity, pose, style, outfit, composition, scene, source material—and a route planner that can reason about conflicts, ambiguity, architecture compatibility, and likely failure modes.

### 3. Workflow Studio

A legible representation of ComfyUI workflows: nodes, connections, controls, validation, previews, reusable components, and the relationship between the editable visual graph and the submitted API graph.

### 4. Qualification laboratory

Bounded trials, comparison plans, immutable source snapshots, compatibility records, benchmark/resource receipts, output review, and promotion gates for models, adapters, nodes, workflows, and settings.

### 5. Asset workspace

Organize accepted and candidate outputs, retain lineage and revision history, plan repairs, preserve accepted regions, and export project-ready artifacts to Krita, Blender, Godot, or other explicit destinations.

## Current reality

The repository already contains credible slices of all five layers:

- a working local Studio and configured ComfyUI environments;
- recipes, presets, prompt helpers, settings knowledge, LoRA slots, environment switching, and local job receipts;
- Workspace and Experiments surfaces;
- reference roles and executed, reviewed edit/Combine routes, including pose skeleton and depth paths (executed and reviewed, not yet qualified across a representative pose/character set);
- curated execution evidence for selected anime/fantasy and other workflows;
- short video, textured-3D, Blender-authored, Krita, and Godot paths;
- validation, benchmarking, profiling, resource, source/provenance, and research infrastructure;
- architecture for guided workflow construction and headless parity.

The product is also carrying real limitations:

- reference composition is inconsistent across architectures and difficult pose families;
- identity, costume, style, anatomy, geometry, and composition can compete rather than combine cleanly;
- many source/model/node findings are research candidates rather than qualified local routes;
- Workflow Studio is incomplete and some active work is split across stacked PRs;
- local installation is configured-machine specific and not a complete reproducible installer;
- model/LoRA provenance and usage rights often remain independently ambiguous;
- generation success is easier to prove than artistic acceptance, consistency, or production readiness;
- AMD/Windows compatibility and resource behavior need route-specific evidence rather than assumptions.

## Priority 1 — reliable multi-reference composition

This is the highest-value creative wall because it determines whether the Studio can reliably transform an idea rather than merely sample one.

### Required capabilities

- role-aware reference assignment and conflict detection;
- useful defaults when prompts are ambiguous, with targeted questions only where the answer changes the route;
- identity, outfit, pose, style, composition, and scene scored independently;
- qualification sets for ordinary, unusual, foreshortened, occluded, contact-heavy, floor, seated, lying, dynamic-action, and multi-character poses;
- skeleton, depth, segmentation, edge/line, dense-correspondence, edit, and hybrid control options where compatible;
- repair plans that distinguish geometry failure from identity drift, anatomy, costume loss, conditioning conflict, or finishing quality;
- accepted-region protection and local retries rather than regenerating everything by default;
- reproducible receipts connecting references, preprocessing, graph, model/adapters, prompt/settings, seed, output, and review.

### Success evidence

A route is not “good at pose transfer” because a few attractive outputs exist. Qualification should report:

- pose/geometry match;
- subject identity retention;
- costume/detail retention;
- style match;
- anatomy and contact plausibility;
- scene/composition adherence;
- retry count and intervention cost;
- runtime/VRAM/RAM behavior;
- failure distribution across the named pose family;
- reviewer acceptance and limitations.

## Priority 2 — Workflow Studio and headless parity

The UI should become a first-class workflow authoring environment without creating a second incompatible graph system.

### Direction

- import and inspect existing ComfyUI graphs;
- discover installed nodes and their schemas from the selected environment;
- expose typed ports, controls, defaults, limits, previews, and connections;
- support templates, reusable subgraphs/components, groups, variants, and controlled overrides;
- validate missing nodes/models, incompatible types, cycles, unsupported dynamic behavior, and environment drift;
- preserve graph/source identity and produce deterministic API submissions;
- show a plan/diff before a workflow changes an environment or starts an expensive job;
- serialize the same safe operation for CLI/API/agent use;
- keep research, acquisition, installation, activation, execution, acceptance, and publication as distinct capabilities.

### Non-goal

The Studio should not reimplement every ComfyUI feature before it can add value. Begin with the nodes and graph patterns used by qualified Studio routes, then expand from measured authoring friction.

## Priority 3 — qualification and source intelligence

The project needs a small, trustworthy route portfolio more than a large candidate list.

### Source layer

- immutable snapshots for model cards, repositories, releases, files, terms, checksums, and compatibility claims;
- explicit publisher/authenticity uncertainty;
- no automatic download/install/execute authority;
- diffable changes and expiry/recheck rules;
- separate technical compatibility from legal/commercial clearance.

### Qualification layer

For each exact version/route, record:

- intended role and excluded roles;
- architecture and environment;
- prompt grammar, quality/rating tokens, negatives, sampler, scheduler, steps, guidance, and resolution;
- compatible LoRA, ControlNet, adapter, edit, and multi-reference techniques;
- AMD/Windows and pinned Linux comparison where useful;
- VRAM, RAM, time, fallback/offload behavior, and crash/recovery evidence;
- representative success, failure, and uncertain outputs;
- provenance and usage-rights notes;
- evidence state and next disconfirming test.

### Portfolio rule

Prefer one qualified primary route and one meaningful fallback per creative role. Additional candidates should enter only when they address a measured gap.

## Priority 4 — performance and reliability as product features

Optimisation should improve throughput without making evidence less trustworthy or the computer unusable.

- measure end-to-end and stage-level time, peak/steady VRAM, host RAM, transfers, cache behavior, and recovery;
- distinguish warm/cold runs and compile/model-load cost;
- support resource profiles such as fastest, balanced, background-friendly, and memory-safe;
- use process isolation, queue admission, cancellation, and cleanup receipts;
- qualify precision, attention, tiling, batching, caching, compilation, and backend changes per route;
- retain paired benchmark trials, uncertain results, and environment identity;
- fail safely around process/PID reuse, partial evidence, OOM, interrupted writes, and stale environment state.

A lower benchmark number is not a product win if output quality, reproducibility, system responsiveness, or recovery degrades.

## Priority 5 — accepted asset lifecycle

Generation is only the beginning of a useful asset.

- distinguish candidate, accepted, rejected, superseded, and project-ready states;
- retain accepted output, source job, reference set, review, and transformations;
- allow small repairs without erasing identity or accepted regions;
- record external native-tool edits and the handoff contract;
- support character sheets, views, poses, expressions, costumes, animation frames, and project packs as linked asset families;
- make comparison and regression review easier than opening folders manually;
- prevent refinement from silently inheriting stale or unrelated prompts/references;
- export manifests with dimensions, colour/alpha, files, checksums, provenance, and intended target.

## Evidence states

Public and UI wording should use a small, consistent ladder:

- **planned** — architecture or task exists; no executable proof;
- **implemented** — code/path exists and passes declared structural tests;
- **executed** — a bounded local job completed with a receipt;
- **reviewed** — a person assessed the output against declared criteria;
- **qualified** — representative tests support a named role within explicit limitations;
- **project-accepted** — an owner accepted the asset for a concrete use;
- **cleared** — relevant provenance/licence/terms were reviewed for that intended use.

No state should be inferred from another. A route can be executed but not reviewed, visually accepted but not cleared, or structurally implemented but unqualified on the configured AMD machine.

## Agent authority model

Agents should be able to:

- inspect local catalogues, environments, workflows, receipts, and documentation;
- search approved external sources through explicit research tools;
- propose reference roles, routes, settings, comparison plans, repairs, and exports;
- create draft workflow documents and bounded task bundles;
- run read-only validation and evidence checks;
- execute only when the relevant capability and resource budget are explicitly granted.

Agents should not implicitly:

- download or install models/nodes;
- switch or mutate environments;
- launch expensive or long jobs;
- train, fine-tune, or publish;
- overwrite accepted assets;
- disclose private references or outputs;
- assert licence clearance or artistic acceptance;
- convert an external claim into a qualified local fact.

## Experience principles

- Start from the desired outcome, not a model name.
- Show useful defaults first and expert controls progressively.
- Explain why a route is recommended and what it may lose.
- Keep the raw workflow inspectable.
- Make the cost and evidence state visible before execution.
- Preserve previous work and accepted assets.
- Turn failures into reusable information.
- Keep “unknown” honest and actionable.

## Measures that matter

- accepted outputs per bounded attempt, by role;
- reference-role adherence and failure distribution;
- time and interventions from intent to accepted asset;
- successful repair rate without full regeneration;
- reproducibility of accepted jobs;
- resource cost and system usability under each profile;
- fraction of candidate routes promoted, rejected, or left uncertain with evidence;
- headless/UI parity for qualified workflows;
- model/node/environment drift caught before expensive execution;
- native-export success and project integration friction.

Counts of installed models, generated files, nodes, issues, or benchmark runs are supporting inventory, not product success.

## What to avoid

- a model warehouse without qualification;
- a prompt library detached from exact versions and routes;
- hidden downloads, installs, environment changes, or cloud calls;
- one giant “verified” flag that mixes execution, quality, and licence state;
- separate UI and agent implementations that drift;
- chasing every frontier model before the current route portfolio is understandable;
- treating attractive cherry-picked outputs as consistency evidence;
- destructive refinement or regenerating accepted regions by default;
- expanding video/audio/3D breadth while image/reference fundamentals remain unreliable;
- universal abstractions that erase architecture-specific prompt/control semantics.

## Horizons

### H1 — dependable creative cockpit

Unify reference planning, clear routes, evidence-aware execution, workspace continuation, and accepted-asset handling for the current qualified portfolio.

### H2 — visual workflow authoring

Deliver useful ComfyUI graph inspection/editing for Studio-owned patterns with safe validation and headless parity.

### H3 — qualification operating system

Make model/source/node research, immutable evidence, AMD compatibility, benchmark/resource proof, and promotion decisions repeatable.

### H4 — consistent character and interaction production

Character sheets, difficult poses, multi-character scenes, costume continuity, scoped repair, and animation preparation with representative evidence.

### H5 — complete local asset production

Images, motion, audio/voice, 3D, native editing, game/creative-tool export, asset families, provenance, and project-ready package QA under one inspectable local workflow model.

These are horizons, not release promises. The current strategy bundle, `CURRENT_STATE.md`, `docs/STATUS.md`, issue tracker, and exact PR evidence remain authoritative for implementation state.
