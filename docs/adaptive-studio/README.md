# Adaptive Studio: experience strategy

**18 September 2026 | Proposed architecture and review artifacts, not shipped capability.**

## Direction

Build a creative workbench that changes its assistance to match the task, without changing the user's work underneath them. Put a distinctive, optionally living environment around that workbench, not through its controls. Make local operation the normal experience, not the degraded version of a cloud product.

The immediate design is **one draft, several task lenses, independently chosen presentation**:

- **Task:** create, edit, combine references, transfer pose, build a sheet, repair, animate, compare, review, export, or construct a workflow.
- **Assistance:** Guided, Studio, Expert. These change explanation and disclosure, never permissions or model capability.
- **Layout:** Focus, Studio, and a proposed comparison/sequence Bench when the task benefits from it.
- **Skin:** Atelier, Arcade, Sakura, Retro Anime, Minimal Pro, or Sci-Fi Noir.
- **Ambience:** Still, Subtle, or Cinematic, subject to accessibility, device activity and explicit media permission.

Do not multiply these choices into separate editors. Do not infer intent from someone's wallpaper. Do not interpret a selected task as permission to replace the current recipe, upload a reference, install a model or start a job.

## What this package contains

| Document | Decision it enables |
| --- | --- |
| [EVIDENCE.md](EVIDENCE.md) | What exists, what the user requested, and what is only a proposal |
| [UX-SPEC.md](UX-SPEC.md) | Workflow-specific workspaces, contextual support and discoverability |
| [ARCHITECTURE.md](ARCHITECTURE.md) | State ownership, bridge contracts and deterministic UI projection |
| [STACK-ADR.md](STACK-ADR.md) | Whether and how to introduce TypeScript, Vue and Vite |
| [AMBIENCE.md](AMBIENCE.md) | Connected/local ambience, parallax, loading and motion policy |
| [ROADMAP.md](ROADMAP.md) | Independently reviewable implementation slices and evaluation gates |
| [SOURCES.md](SOURCES.md) | Primary-source research and limits of the inspiration audit |

Companion review slices add `assets/` for the production wishlist and `lab/` for a zero-backend interaction specification. They must not be imported by the production shell. These companion paths are planned until their own PRs land.

## Relationship to current work

The live review snapshot found #540 (Focus workshop) open at `d8b91de643c81cc3395e6721209f47251726edee` and #541 (Studio/skins/prototype) open at `79fc552dea3dbb07c989235d7f22bf5025a26280`. They are implementation proposals, not assumed mainline behavior. This strategy is an additive documentation branch from main `eb3fc1e1665f109d90086ad3b3dbe1f5f10dd14b`. It does not modify those PRs or depend on their merge for its documents to be reviewed.

The existing owner qualification remains #539. This package expands the next design horizon; it does not replace the v1 acceptance criteria or close that issue. Existing `HUMAN_TODO.md` decisions remain unchanged.

## Recommended order

First qualify the workbench foundation. Then make existing state available through a typed, read-only presentation boundary. Trial a task guide and recipe discovery island against the existing controls. Only after that trial should a framework own more of Create. Produce a small art pilot after the interaction hierarchy is accepted; acquire the wider wishlist in waves, not in one expensive generation batch.

The strongest visual candidate is **Retro Anime: Night Shift**, an original late-night animation workshop with a distant city, soft CRT light, and a restrained rose/cyan palette. A calm daylight counterpart uses the same composition. Both can be local files. A connection can enable approved optional motion, but losing connectivity must not remove the studio's identity or imply lost work.

## Decisions reserved for Chris

Choose the preferred pilot world after reviewing the written art direction; confirm whether a maintainer-only frontend build step is acceptable; decide whether remote decorative media should ever be enabled. Proposed defaults are Retro Anime as an optional pilot, static local ambience, no remote media, no automatic audio, and incremental Vue only after a measured spike. These are recommendations, not recorded owner approvals.
