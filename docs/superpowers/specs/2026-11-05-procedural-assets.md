# Procedural assets in the Studio

## Intent

Make the eight existing procedural asset generators discoverable and usable from Local Asset Studio. The factory, level assembler and labelled-dataset tools currently live behind command-line entry points. This slice connects the factory to the same explicit planning, execution and Library workflow used for other native assets.

## Chosen approach

Reuse `scripts/procgen_factory.py` unchanged through a bounded native adapter and Production's existing queue. A schema-driven page reads the authored generator descriptions, parameter defaults, bounds and constraints. Preparing saves a pinned plan; Start remains a separate action on the project. This avoids duplicating generator logic or creating a second executor. A catalog-only page was considered but would leave the build handoff disconnected; a new simulation engine is outside the existing capability and this slice.

## Contract

- Discover all eight generators even when Blender is not installed. Explain missing Blender, Node/Khronos validator and optional Godot setup before preparation.
- Accept only a generator, name, numeric parameters, optional contact sheet and explicit Godot verification choice. Do not accept scripts, executable paths or output directories from HTTP.
- Pin resolved parameters, factory/schema/adapter source identities and configured executable identities. Changed pins require a new plan before execution.
- Persist the plan and an owned attempt marker before invoking the factory. Keep failed and uncertain attempts; inspection/recovery never reruns them.
- Publish GLB LODs and the optional contact sheet into the regular Library only after output hashes and retained completion evidence agree. Downloadable BLEND, recipe, report and diagnostics keep their identities.
- A build without Godot verification is visibly incomplete technical verification. A completed native process does not imply artistic acceptance or universal engine readiness.
- Use the shared worker and existing lease admission. Do not contact ComfyUI or start a native process on page load, discovery, validation or preparation.
- Preserve regular-only advanced-workflow privacy boundaries.

## Scope and remaining work

The factory's room kit, prop, shrine, lighthouse room, pier, coastal path, tide pools and market street are included. Level assembly, labelled datasets, spring simulation, new generators and changes to geometry/shading remain separate. This change supplies HTTP and the existing CLI for agent use; additional SDK/MCP wrappers may follow after the shared contract is qualified.

## Evidence

Tests use inert generated fixtures for native boundaries and real filesystem, SQLite and HTTP behavior. They must not be described as Blender or Godot qualification. Native asset/art review remains owner-run.
