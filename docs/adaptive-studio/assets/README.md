# Frontend asset production kit

**154 planned requests. No media has been produced, acquired, cleared or installed by this kit.**

This is a production wishlist, not 154 image-generation prompts to execute in one batch. It includes scene masters, derivatives, code/vector work, real tutorial captures and optional sound. Shared profiles supply delivery targets; every catalogue row adds an individual subject, placement, production method, dependency and acceptance test.

## Use the kit

```sh
python docs/adaptive-studio/assets/brief.py validate
python docs/adaptive-studio/assets/brief.py list
python docs/adaptive-studio/assets/brief.py show retro-anime-master
python docs/adaptive-studio/assets/test_brief.py
```

The reader is standard-library Python, reads only this directory and prints text. It has no model, network, media conversion, installation, registration or GitHub action. `show` assembles the complete brief with inherited world/profile requirements. Actual production remains a separately selected future session.

| File | Purpose |
| --- | --- |
| [catalog.csv](catalog.csv) | Stable, individually selectable asset requests |
| [profiles.json](profiles.json) | Shared world directions, output targets, fallbacks and budgets |
| [ART-DIRECTION.md](ART-DIRECTION.md) | Coherent worlds and composition/canon rules |
| [DELIVERY-SPEC.md](DELIVERY-SPEC.md) | File/rendition/loop/layer contracts and acceptance |
| [SESSION-HANDOFF.md](SESSION-HANDOFF.md) | Copy/paste next-session instruction and provider/tool routes |
| [receipt-template.json](receipt-template.json) | Empty receipt template; actual source/output fields are deliberately null |
| [brief.py](brief.py) | Read-only brief assembly and inventory checks |
| [test_brief.py](test_brief.py) | Offline inventory, dependency, CLI and planned-state tests |

## Inventory

| Family | Requests | What it covers |
| --- | ---: | --- |
| Environments | 60 | Six worlds, each with master, hero, wall, quiet alternative, poster, three aligned layers, loop and picker card |
| Workflow illustrations | 16 | Every W01-W16 lens in the UX specification |
| Empty/error/recovery states | 14 | Distinct internet, API, backend, source, media and operation states |
| Reference examples | 8 | Identity, pose, style, outfit, composition, light, background and a functional vector mask overlay |
| UI foundations | 10 | Icons, tokens, buttons, fields, cards, tabs, badges, dialogs, textures and loading blocks |
| Optional guide | 8 | Consistent nonhuman folio/star expressions |
| Real tutorials | 10 | Actual UI recordings after the relevant workflows are qualified |
| Promotion/showcase | 8 | Truthful product compositions, theme previews and release materials |
| Optional audio | 6 | Short cues and ambient beds, silence by default |
| Motion specifications | 6 | Code-defined disclosure, crossfade, parallax, focus, loading and pause |
| Controlled sample sets | 8 | Original source packs with explicit example-only provenance |
| **Total** | **154** | Requests, not files, purchased licences, generations or estimated cost |

## Production waves

P0 has 25 requests: 6 Retro Anime scene/still derivatives, 4 core workflow vignettes, 5 necessary helper states and 10 code/vector foundations. P1 has 18: Retro Anime layers/loop, 8 reference examples and 6 motion specifications. P2 has 69 broader environment/workflow/tutorial/sample requests. P3 has 42 optional guide, sound, promotion and additional moving-world requests.

These are prioritization proposals, not approved work. P0 is already larger than a sensible first art batch. Start with **one anchor and a few derivatives**, for example `retro-anime-master`, `retro-anime-quiet`, `retro-anime-hero`, `retro-anime-poster`, `retro-anime-card`, `state-blank` and `state-source-required`. Resolve the anchor first; derive crops instead of paying for disconnected new scenes. Add motion only after the still pack works in the actual editor.

## Dependencies and exclusions

An `anchor` is a required approved input, never a filename the agent should invent. Layer extraction, quiet edits and loops reuse the scene master. Posters/cards/crops should not drift into independently generated worlds. Tutorial captures require the real application behavior, not an image of fictional controls. UI foundations remain code/vector design; the mask example is not an actual model mask contract.

The full kit intentionally includes far-future and optional requests. A small coherent world integrated into a legible editor is more valuable than a warehouse of unrelated decorative assets. Existing source artwork and private outputs must not be republished automatically. Read the [architecture](../ARCHITECTURE.md), [motion policy](../AMBIENCE.md) and [source register](../SOURCES.md) before implementation or acquisition.

## Evidence for this kit

The offline reader tests passed 10 cases after an initial missing-reader failure. They check all 154 requests resolve, IDs/profiles/dependencies, duplicate/cyclic/unknown references, planned-state boundaries, code-versus-capture routing, and read-only CLI behavior. These are documentation/tooling tests, not media-quality, real UI, source-rights or GPU evidence.
