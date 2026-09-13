# Save a protected edit as a new Krita revision

`scripts/character_krita.py` carries an existing protected edit result into a
saved KRA as one additional paint layer. The source KRA stays unchanged. The
command rechecks the current exported document, plan, references, masks, bundle,
candidate and result, then opens a private copy in the configured Krita runner.
It does not generate a candidate or change an open GUI document.

The initial supported contract is deliberately narrow: opaque, profile-free PNG
intake; a matching RGBA/U8 KRA using `sRGB-elle-V2-srgbtrc.icc`; at most 16 million
canvas pixels; 1–31 flat, normal, non-animated paint layers. Groups, masks,
animation and other color spaces require a different adapter. The native source
projection must exactly match the edit plan's source. Unsaved GUI changes are
outside this saved-file contract: save and export a fresh document first.

## Configure and prepare

Set absolute `kritarunner` and `kritarunner_scripts` paths in `config/local.json`.
The latter must be the script search directory of the configured runner. On the
tested Windows installation it is `%APPDATA%/kritarunner/pykrita`, distinct from
the normal Krita GUI plugin directory. `config/example.json` shows the keys.

The explicit install command copies only the repository's fixed native module
under a name containing its full SHA-256. It adds no `.desktop` autoload entry,
does not overwrite another module, and accepts no caller script or command text.
The execute command also performs this idempotent installation check.

```console
python scripts/character_krita.py install --config config/local.json
python scripts/character_krita.py prepare --workspace C:/AI/character-lab/EDIT_WORKSPACE --plan plan.json --bundle prepared --result revision-2/result.json --current-document document.json --native-source native-source/roundtrip.kra --out native-revision-2
```

Supply a workspace that already contains a valid protected result from
[`character_edit_pixels.py`](EDIT-RUNBOOK.md) or the existing Studio bridge.
All artifact/package arguments are workspace-relative. The output directory must
be new. Preparation performs no native execution. It retains the source KRA
copy, full source/result pixels, a binary-coverage edit overlay and a plan that
hashes every input. A soft write mask is already resolved by the protected
compositor; the native layer receives the exact final colors only where pixels
actually changed.

## Execute once and inspect

```console
python scripts/character_krita.py execute --workspace C:/AI/character-lab/EDIT_WORKSPACE --package native-revision-2 --config config/local.json
python scripts/character_krita.py status --workspace C:/AI/character-lab/EDIT_WORKSPACE --package native-revision-2
```

Execution persists and flushes `native-intent.json` before launching a fixed
argument list with a 120-second timeout and a hidden Windows process. It opens
only the retained source copy, adds the proposed layer above the existing stack,
reads back its pixels and compares the native projection with the planned result.
It checks each original layer's canvas pixels and recorded metadata, hides the
new layer to prove source restoration, restores it, saves `edited.kra`, closes
and reopens the file, and exports `reopened.png` for an independent pixel check.

Inspect the new KRA and PNG alongside the original, mask and candidate. The
receipt records original and resulting layers, file hashes, canvas/profile and
native checks. Every result stays `unreviewed`, with `semantic_approval: false`
and `neural_inference: false`. This packaging step does not validate a canon's
semantic contents or promote a production asset. The candidate's generation
receipt and human creative review remain separate.

`status` reports `prepared`, `uncertain`, `failed` or `completed`. A result is
completed only when required native checks, output hashes and decoded PNG pixels
validate. Exit code zero alone is insufficient: the tested runner can return
zero after Python failure. Any recorded attempt prevents execute from running
again. Preserve an uncertain or failed package and diagnose it; do not delete its
intent or outputs to make it executable. A deliberately changed implementation
may be tested in a new synthetic package after a diagnosed failure, retaining
the old package. This is not permission to bypass another operation's budget or
approval block.

## Executed proof and limits

On 13 September 2026, the authored two-actor CPU fixture was converted to a KRA
using the existing ORA roundtrip and then passed through this adapter on Krita
5.2.16 (`7d9aefc`). Workspace: `C:/AI/character-lab/native-edit-proof-20260913`.
The successful package is `native-revision-3`; the earlier package remains as
failure evidence. Its edit plan SHA-256 is
`2cdd570193731500688abb838ad40cbeac9b875910bdcad4bceeec140e13bb8c`.

- Exactly **4,032** selected costume pixels changed; **94,272** canvas pixels
  remained exact, including the second figure and background.
- The original KRA hash remained unchanged. Its one original layer retained its
  canvas-pixel hash and recorded name, type, visibility, opacity and lock state.
- Hiding the additional layer restored the original projection. The saved KRA
  reopened with the expected result; the exported PNG was compared pixel for
  pixel and visually inspected with the synthetic before/after image.
- `edited.kra`: SHA-256
  `0617f237ba15932c2766aa8e9698d71b5ec55d89700728e5e58b7c44e3823347`;
  `reopened.png`: SHA-256
  `d589d542257bc604f5791366b253fb17f768d602461d0aa13dfcfccfee3eebc5`.

The first native attempt stopped because this installed Python binding returned
`None` from `setPixelData` despite writing the bytes. A separate owned-copy probe
proved the write by reading the data back; the adapter now uses that direct
check. Both the failed package and probe are retained. No installed Krita or
ComfyUI package was edited or upgraded.

This proves one native saved-file edit path, not neural anatomy correction,
costume design quality, multilayer/large-canvas reliability, off-canvas layer
preservation, an interactive editor plugin or finished-character acceptance.
The existing private portrait/boot attempts and their budgets are untouched.
Run the CPU fault contracts with
`python -m unittest tests.test_character_krita tests.test_character_edit_pixels`.

API references: [Krita Node](https://api.kde.org/legacy/krita/html/classNode.html)
and [Document](https://api.kde.org/legacy/krita/html/classDocument.html).
