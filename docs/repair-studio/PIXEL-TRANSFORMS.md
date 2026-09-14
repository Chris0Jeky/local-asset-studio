# Scaled repair contexts and protected composites

The offline transform command prepares a scaled context from a checked character
edit plan and a verified normalized source packet. Given a separately supplied
candidate, it reconstructs that context and its masks, maps the unpadded candidate
back to source coordinates, and publishes a new composite. Every RGBA sample
outside effective write coverage and at explicit protection remains identical to
the source, including RGB hidden under zero alpha.

This implements the mechanical transform portion of issue #245. It does not
perform neural inference, prove a model preserved registration, approve artwork,
reserve generation credits, or admit a packet to a native editor. Native/model
registration (#248), guided Studio use (#251), repair allocation and accepted real
repairs remain open under #243. A same-sized model output can still move a face or
hand; a canvas-size check cannot prove its alignment.

## Try the complete synthetic example

Run from the repository root, choosing a new output folder:

```powershell
python scripts/repair_transform_demo.py --out C:/AI/character-lab/scaled-repair-demo
```

The example creates two diagram characters, the original legacy fixture, a
normalized source packet, `transform-plan.json`, `transform-request.json`,
`scaled-context/`, an intentionally full-canvas test candidate, and
`scaled-result/`. Open `scaled-comparison.png` to compare the original, prepared
context, candidate and protected composite. These are synthetic CPU pixels; no
model, Studio service, native application or source artwork is needed. An existing
output directory is refused, and a failed partial directory remains available for
inspection. Choose another name to run again.

## Bind your own existing edit plan

First use [source intake](SOURCE-INTAKE.md) to normalize the original PNG into a
new source packet. Create or recompile the ordinary character edit plan so its
document source names that packet's `normalized.png` and matches its encoded hash
and oriented canvas. Canon/reference dependencies and masks stay bound by the
existing plan. A raw EXIF-oriented source is not silently substituted here.

The external request has exactly these fields:

```json
{
  "schema": "studio.repair-transform-request/v1",
  "plan_sha256": "<checked plan digest>",
  "source_packet": {
    "path": "normalized-source",
    "receipt_sha256": "<hash of captured receipt.json bytes>",
    "normalized_sha256": "<hash of normalized.png bytes>"
  },
  "authored_write": {"path": "edit-mask.png", "sha256": "<plan mask digest>"},
  "protection": {"path": "protect-mask.png", "sha256": "<plan protection digest>"},
  "transform": {
    "version": "straight-rgba-bilinear-v1",
    "box": [50, 96, 137, 189],
    "scale": [3, 2],
    "padding": [2, 1, 3, 1],
    "alignment": 1
  }
}
```

The box must equal the checked plan's context box. `protection` must be null when
the plan has no protection artifact. Paths inside the request are relative to the
workspace, not the shell's current directory. Scaling is a positive integer
numerator/denominator from one quarter through four; padding is left/top/right/
bottom. Boolean, float, unknown and unsupported fields are rejected.

These commands also work when invoked by absolute script path from another
directory. With the example above as a workspace, PowerShell can run:

```powershell
$repairRoot = 'C:/AI/character-lab/scaled-repair-demo'
$repairRequest = "$repairRoot/transform-request.json"
$repairHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $repairRequest).Hash.ToLowerInvariant()
python scripts/repair_pixel_transforms.py prepare --workspace $repairRoot --plan "$repairRoot/transform-plan.json" --request $repairRequest --request-sha256 $repairHash --out prepared-again
$candidateHash = (Get-FileHash -Algorithm SHA256 -LiteralPath "$repairRoot/scaled-candidate.png").Hash.ToLowerInvariant()
python scripts/repair_pixel_transforms.py apply --workspace $repairRoot --plan "$repairRoot/transform-plan.json" --request $repairRequest --request-sha256 $repairHash --bundle prepared-again --candidate scaled-candidate.png --candidate-sha256 $candidateHash --out composed-again
```

Keep the external request and its expected hash together. Editing only a bundle's
recorded request, mask or file digest cannot replace this external authority.
Preparation never submits the resulting context to a model. Supplying a candidate
does not establish where it came from or authorize a new generation.

## Raster policy and retained evidence

- The `straight-rgba-bilinear-v1` operation resizes the four encoded RGBA channels
  separately using Pillow bilinear sampling. It preserves supported colour chunks
  verbatim, without claiming linear-light blending or colour certification. A
  candidate must have the exact same colour chunks and be normalized RGBA.
- Exact rational geometry records half-up integer dimensions, actual axis scales,
  pixel-centre mappings, explicit padding and the Pillow version. Source and
  working canvases are bounded to 24 million pixels. Masks use 8-bit grayscale L:
  zero preserves; every nonzero value, including one, contributes write coverage.
  Protection is binary, with 255 forbidding edits. Mask colour/EXIF/transparency
  metadata is refused. Default source intake still rejects grayscale sources.
- Coverage is resized forward and back to compute the effective source mask.
  Both authored and effective masks are checked against the plan's context,
  contacts, protection and other actors. Expansion into an excluded region fails;
  it is not silently clipped. Dilation and feather are not supported in this
  version. Conservative max-filter protection before nearest sampling keeps thin
  source protection in every positive bilinear footprint, sometimes excluding
  extra work pixels. Work write/protection conflicts require a revised scope.
- Work padding is never writable. Candidate padding is stripped before inverse
  resampling. An unchanged prepared interior, including a padding-only edit,
  returns the exact original pixels and a no-op warning. It is not reported as a
  successful correction.
- A bundle retains six PNG buffers: context, work write/protection, authored write,
  effective write and source protection. Its receipt binds the external request,
  source normalization, geometry, operation revision and encoded/decoded hashes.
  Apply reconstructs every buffer and the entire receipt before publication.
  Byte equality deliberately binds preparation and application to the same
  recorded Pillow producer; prepare a new revision after changing that dependency.
- Source, masks and candidate are bounded captures; their verified captures supply
  the pixels. Published packets use exclusive new directories and completed receipt
  markers. This is a cooperative local-writer contract, not a hostile-filesystem
  or power-loss guarantee. Partial packets and unrelated files are not deleted.

Bundles use `studio.repair-transform-bundle/v1`; composites use
`studio.repair-transform-result/v1`. They stay separate from legacy character edit
bundles/results, whose schemas and default pixel behavior are unchanged. Legacy
bridge/Krita admission remains unsupported. Receipts always retain unreviewed
state, no semantic approval and no neural inference by these commands. The
composite records candidate identity, changed/preserved counts, effective coverage
and no-op state; mechanical preservation is separate from visual acceptance.

## Proving checks

```powershell
python -m unittest discover -s tests -p 'test_repair_*transform*.py'
python -m unittest discover -s tests -p 'test_character_edit*.py'
python -m unittest discover -s tests -p 'test_repair_source*.py'
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The tests use real synthetic PNGs, an independent bilinear sample and protection
footprint oracle, exact hidden-RGB preservation, fractional coverage, odd geometry,
non-target expansion refusal, altered/rehashed packet rejection, bounded metadata,
no-clobber/partial packets, capture races and the actual CLI. They do not measure
neural repair, artistic quality, user acceptance or performance on real artwork.
