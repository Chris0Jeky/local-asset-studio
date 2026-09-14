# Run the non-executing proposal scaffold

Requirements: Python 3.12+ standard library. No ComfyUI, Pillow, model, native editor, account key or network connection is needed. Run from the repository root, or use absolute script and proposal paths from another directory.

```console
python scripts/repair_proposal.py describe
python scripts/repair_proposal.py validate research/repair-studio/hand-proposal.json
python scripts/repair_proposal.py validate research/repair-studio/contact-proposal.json
python -m unittest discover -s tests -p "test_repair_proposal.py" -v
```

`describe` exposes the bounded vocabulary and outstanding runtime checks. `validate` reads only the explicitly named JSON file, prints a structured report and writes no file. Exit 0 means declarations are internally consistent; exit 2 indicates a validation/IO error or unsupported CLI invocation. It never means a source was repaired, a mask checked or execution authorized.

Successful reports always contain:

```json
{
  "status": "declarations_valid",
  "executable": false,
  "authority": "none",
  "pixel_validation": "not_performed"
}
```

The actual report additionally includes a canonical proposal SHA-256, rational crop-to-work mapping, review requirements and required runtime checks. The hash identifies declared data; it authenticates no reviewer and verifies none of the image/mask hashes. The synthetic examples intentionally have no associated source images or approved character canon.

## Schema boundaries

The exact root fields are `schema`, `source`, `mode`, `context`, `instances`, `targets`, `references`, `contacts`, `masks`, `intent`, `limits` and `strategies`. All are required; unknown fields fail. Use `studio.repair-proposal/v0` exactly. The checker is the normative source for this narrow draft format; do not maintain a second divergent JSON Schema or turn the format into a Production job.

Canonical masks use `source-L-coverage-v1`: edit/write are full-source L coverage, protection is binary L with 255 protected, and subject is an optional separately interpreted selection/matte. Only their SHA-256 declarations are present; no pixel validation is performed. Optional protection/subject entries can be null. Supplying RGBA inverse alpha as the encoding is refused rather than guessed.

Crop boxes use exclusive right/bottom coordinates on the declared normalized source. Scale is a positive rational pair. Padding is left/top/right/bottom; alignment is explicit. The checker computes rounded resized dimensions and actual rational x/y maps but does not resample. A v0 reconstruction proposal records intent only; expanded outpaint canvas and real masks require a later native plan.

Instance IDs must be unique. References bind to existing instances and ordered roles. A contact repair must include its declared participants and contact boxes within scope. Actual geometric correctness, undeclared contacts and cross-panel ownership cannot be inferred by this checker.

Limits are declarations, not campaign registrations or reservations. `native` means a manual/native action with no hidden AI request; a native AI generation would still require a registered image-producing adapter. Global upscaling cannot be included in a localized exact-preservation proposal: create a separate remaster stage.

## Local focused verification

The initial minimal interface was exercised against 39 tests: 28 assertion failures and 10 missing-behavior errors, with one non-mutation check already passing. The implemented scaffold then passed all 39 tests locally, including real subprocess CLI calls from another working directory. This is missing-feature red/green evidence, not a claim that an existing production repair was broken.

Tests cover strict fields/types, false authority, version/mask confusion, digest syntax, bounds, rational transforms, rounding/alignment, instance/reference identity and ordering, coupled contacts, unseen reconstruction, mode conflicts, finite caps, duplicate/nonfinite/deep/oversized JSON and structured CLI errors. Their fixtures do not contain images or a neural backend. Full hosted repository verification is a separate PR record.

For subsequent app/catalog implementation, use the existing full proving commands:

```console
python -m unittest discover -s tests
python scripts/validate-repo.py
```

## Continue with actual repair work

Read `../character-consistency/STUDIO-BRIDGE.md` and `CAMPAIGN-BUDGETS.md` for the existing real client. Its approved canon, actual source/mask files, exact native templates and explicit registered allowance are prerequisites. Do not pass a v0 synthetic example to that client or create a new campaign to bypass an old unknown/exhausted run.

Implement #244 next, followed by #245/#248 and the first #251 journey. The current proposal checker needs no server route or UI loading change. Removing it leaves active generation behavior unchanged.
