# Preset model requirements and installation actions

Checkpoint: 13 September 2026, baseline `aebe10c58c7fa3ce8f89276740096eaf98c2cc20`.
Implements the concrete #104/#116 requirements within #9. This is software evidence,
not a new model installation, workstation inventory capture or successful inference.

## Reconciliation

HiDream/runtime and experiment issues #2/#3 still retain their live comparison scope.
The intake publication and graph-validation changes are already on main; neither is
reimplemented. #104 is still reproducible: health only checked `_name` enums and did
not consult declared `model_files`, while inspection omitted `.patch` and selected
curated pins by basename. #116 is also present: the dependency panel offered Install
for any missing pinned file, even when the library would refuse that file type.

The concurrently open continuation PR #164 owns source-bound handoffs. This change
only touches dependency/readiness and installation-action regions in the shared
server and main-page script. It adds no continuation, queue or recipe store.

## One read-only projection

`app/model_requirements.py` projects existing catalog graphs, explicit `model_files`,
reviewed loader class/input folder mappings, and the existing ModelLibrary manifest.
`Studio.preset_requirements` selects the preset's actual backend model root. Both
`inspect_preset` and health use that projection; Production preflight consumes the
same inspection result and refuses an unresolved path before constructing `Path`.

The rules are deliberately narrower than universal model discovery:

1. A known loader's class **and** input name determine its folder. CLIPVisionLoader
   and CLIPLoader both have `clip_name`, but their folders are different.
2. Explicit portable `model_files` declarations cover custom loaders and companions,
   including Fooocus `.patch` files. A uniquely matching declared path may resolve an
   otherwise unknown loader; ambiguous declarations do not choose one arbitrarily.
3. Curated pins attach by **exact relative path**, not basename. Duplicate exact-path
   pins do not grant an arbitrary installation target. An unknown loader is never
   identified from a conveniently matching library filename.
4. Unsupported weight-looking inputs remain inspectable with `folder`, `path` and
   `present` set to null and a diagnostic. Ordinary text/prompt/output-prefix fields
   are not treated as weights just because their text ends in a model suffix.
5. Native Windows selection separators normalize to portable separators; traversal,
   absolute/drive/stream paths and noncanonical declarations refuse. Observed child
   links/junctions and inaccessible paths produce unknown availability, not a usable
   path or an Install action. Configured-root resolution is inherited; this is not a
   hostile-OS sandbox or an atomic filesystem guarantee.

The current full-catalog regression checks that every discovered model selection has
an explicit location. It does not invent custom-node adapters from schemas and does
not claim every possible extension input is supported. Add a reviewed mapping or an
explicit declaration when introducing a new loader.

## Observation and UI contract

Each requirement returns `file`, `folder`, `path`, `present`, `note`, `asset_id`,
`source`, `installable`, and `install_note`.

| Field/state | Meaning |
| --- | --- |
| `present: true` | A regular nonempty file was observed; no content hash or inference was checked. |
| `present: false` | The exact location is missing, empty or not a regular file. |
| `present: null` | The folder/location or its availability could not be established. |
| `installable: true` | A unique valid pin passed the existing installer policy for this model root. |
| `install_note` | Why installation is unavailable; pin-only kinds, absent sources and a different backend root are distinguished. |

Health reads the manifest once and shares a per-call file-observation cache across
presets. It does not run recursive inventory scans, hash weights, start installers,
create model folders or switch environments. The next health call observes files
again. Existing cached schema discovery remains unchanged. Non-`_name` model enums
are checked too; file presence cannot override a live loader enum's disagreement.
One active endpoint's schema is not applied to a different backend's presets.
Schema-fetch failure still reports `schema_available: false`, even when local files
are present. Known local missing files remain visible on an online endpoint with an
unavailable schema. Offline endpoint behavior keeps its existing offline response.

The legacy `missing_models` response also carries explicit unresolved diagnostics so
old UI consumers cannot interpret unknown dependencies as ready. The dependency
panel renders missing versus unknown instructions, copies only a real path, and
shows Install only for **false presence + an asset ID + boolean true eligibility**.
Models cards also fail closed when eligibility is missing or not a boolean true.
The delegated click listener ignores disabled installation controls. The server's
existing install gate remains authoritative; this does not widen allowed sources or
file formats. Selecting another backend is still an explicit separate operation.

## Tests and execution boundary

```sh
python -m unittest discover -s tests -p 'test_preset_model*.py' -v
node tests/preset_model_readiness.cjs
python tests/preset_model_browser.py --out .runtime/preset-model-browser
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The new ordinary test suite has 23 tests, including a Node contract wrapper. Tests use
real Studio/ModelLibrary, actual temporary files and real loopback Handler responses;
Comfy transport and process startup are inert. Cases include removed and empty patches,
cache disagreement, exact-path collisions, unknown/ambiguous mappings, pin-only and
unsourced files, invalid/linked paths, permission errors, inactive backends, one-pass
observation reuse, full-catalog path coverage and read-only failure behavior. An actual
pin-only install HTTP request refuses before changing any file or queue.

The first 12 backend regressions were also run against the original implementation:
nine failed/error and three passed. With the new implementation all 23 ordinary
new tests pass locally. The existing 50-test server suite passes locally as well.
The dedicated CI runs those contracts plus ModelLibrary tests on Linux and Windows.
The opt-in browser driver reuses the existing synthetic API fixture and actual static
files at 1440px and 390px, checks keyboard focus and zero model mutations, and captures
screenshots. Local browser navigation was blocked with ERR_BLOCKED_BY_ADMINISTRATOR;
its hosted result must be read from CI, not inferred from Node/HTTP tests.

A complete tracked-source archive of the pinned baseline was retrieved through a
short-lived branch-scoped GitHub artifact for these local tests. It contains no ignored
workstation state, models or secrets. The local git baseline is only a comparison aid,
not a claim of cloned upstream history. Hosted CI supplies Python 3.12 integration.

No workstation model, GPU, download, config, queue, approval or system operation was
performed. In current HUMAN_TODO, q-4's owner-controlled restart is already recorded as
complete; this work does not reopen it. Presence, source authenticity, model terms,
actual inference and creative approval remain separate evidence.

## Primary references

Read 13 September 2026:
- Python 3.12 pathlib: https://docs.python.org/3.12/library/pathlib.html
  documents path/status queries, symlink resolution and Windows junction checks.
- Existing local contracts: `app/model_library.py` (`install_block`, folder registry),
  `app/download_contracts.py` (portable paths and pins), `presets/catalog.json` and
  its exact API graphs. Folder adapters here are reviewed declarations, not evidence
  derived merely from a native socket name or a public model card.
