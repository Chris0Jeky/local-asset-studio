# Bundle guidance: exact resource inventory

Issue #184. Inspected/tested base: main
`06bd93aed2f019cb978eb5795e9f116cfb7ff749` (the uploaded ZIP had the same Git tree).

## What was missing

The settings explainer recognized generic input names but not reviewed
class/input storage roles or `preset.model_files`. With an empty guidance KB,
`anime-complete` omitted its face detector and upscaler. `hidream-o1-concept`
reported no resources or uncovered resources despite nine authored companion
files. An empty coverage list therefore did not mean everything was covered.

## Correction and contract

`studio_workflow/model_contracts.py` now owns the existing folder allow-list and
reviewed loader-role map. Model inventory/readiness and the pure explainer reuse
these constants. This moves metadata only, not installer or execution policy.
Standalone model scripts explicitly add the repository root as an entry-point
path; they continue to work outside the repository working directory.

Class-specific roles take precedence over existing generic fields. In particular,
`CLIPVisionLoader.clip_name` belongs under `clip_vision`, not `text_encoders`.
Detector/upscaler `model_name` inputs use their reviewed classes; arbitrary custom
`model_name` values still do not acquire guessed folders. Custom directory-loader
companions are represented by their explicit catalog declarations.

The report has one resource row per exact portable relative path. Identical
basenames in different folders remain different resources. Each row retains:

- `bindings`: every authored node/input and its individually observed activity;
- `sources`: graph-input locations and/or the declaring preset;
- the existing identity/pin fields and legacy first-binding `node`/`input` fields.

Resource-targeted claims inspect every relevant binding, not just the first one.
A declaration-only resource has unknown activity and no invented node binding.
Declaring a graph-bound inactive LoRA does not reactivate it. A declaration-only
LoRA also prevents the explainer from claiming that every adapter is inactive.
Malformed declarations fail explicitly instead of looking like complete coverage.

None of this reads installed model bytes, changes controls, installs anything,
prepares a ticket or submits generation. `catalog_pin` remains a catalog claim,
not newly verified installed-file identity. Resource coverage is not model advice,
artistic acceptance or licensing approval.

## Verification and repeatable checks

Run from the repository root:

```sh
python -m unittest discover -s tests -p 'test_bundle_guidance*.py'
python -m unittest discover -s tests -p 'test_preset_model*.py'
python -m unittest discover -s tests
python scripts/validate-repo.py
python -m studio_workflow.guidance --help
```

Linux / Python 3.13.5 / Node 22.16.0 results:

| Check | Result |
| --- | --- |
| Untouched main full suite | 1,463 tests, 15 skipped; no failures |
| Initial 10 resource regression methods on unchanged code | 13 expected failed assertions/subtests |
| Guidance HTTP/CLI/policy/resource suite after fix | 45 passed |
| Preset model readiness/occupied-destination suites | 29 passed |
| Full suite with all 12 new resource/import/entry-point methods | 1,475 tests, 15 skipped; no failures |
| Repository validation | 66 graphs/bindings, 121 pinned assets, 86 LoRA names; passed |

The class-specific anime resources are now present and uncovered when no claim
exists. All nine declared HiDream companions are present and uncovered. Tests
also cover duplicate paths with multiple strength targets, inactive adapters,
unknown activity, ambiguous pins through existing tests, same basenames across
folders, Windows separators in graph inputs and non-mutating evaluation.

The import test simulates an unrelated installed `app` package and confirms the
pure explainer does not import runtime inventory/server modules. Three model
entry points are tested with isolated Python from another working directory.
Existing Pillow/socket warnings were not hidden. Skipped optional cases and
actual model/runtime behavior are not claimed as verified.

Rollback is a normal code revert; no user configuration or persistent schema changed.
