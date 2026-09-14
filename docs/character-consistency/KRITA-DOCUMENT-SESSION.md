# Open-document Krita session

`scripts/character_krita_session.py` prepares a typed request for the optional
Krita extension. It first recomputes the protected edit through
`character_krita._expected`, requires the retained native plan to match that
result, and pins every explicit source, canon, mask, candidate and bundle
artifact it reaches. The request is JSON data, not Python code.

Capture is a user action in Krita. Choose a new folder name that does not exist; the
extension writes its owned source clone, projection, selection and
`snapshot.json` there. It does not save, close or clear the modified state of
the active document. Build a request only after the existing protected package
has been prepared. Keep the capture under the same edit workspace. Use its
`source.png` as the source of the existing actor/edit document and its
`source.kra` for the native package. Retain the canon, masks, candidate and
protected result from the [edit runbook](EDIT-RUNBOOK.md) or
[shared Studio bridge](STUDIO-BRIDGE.md). After the protected result exists:

```console
python scripts/character_krita.py prepare --workspace C:/AI/character-lab/EDIT_WORKSPACE --plan plan.json --bundle prepared --result revision-2/result.json --current-document document.json --native-source captures/revision-1/source.kra --out native-revision-2
python scripts/character_krita_session.py request --workspace C:/AI/character-lab/EDIT_WORKSPACE --snapshot C:/AI/character-lab/EDIT_WORKSPACE/captures/revision-1/snapshot.json --package native-revision-2 --out C:/AI/character-lab/EDIT_WORKSPACE/import-request.json
```

In Krita, use **Tools → Scripts → Capture document**, **Import request**,
**Show source**, and **Show result**. A session belongs to the same open
native document and root node captured by the action. Krita returns fresh Python
wrappers for the same document, so identity uses native equality. Switching documents or
reopening a file requires a fresh capture; the extension never silently adopts
the replacement. Import adds one reversible proposed paint layer only after the
shared session validates the capture, all request pins, and the entire current
unsaved revision. Source/result actions only toggle that proposed layer.

Install is explicit and copies fixed, content-hashed code. It creates no native
process, network request, document, action invocation, generation, save or
restart. Paths must be configured in `config/local.json`; installed files are
immutable and an existing different file aborts the command.

```console
python scripts/character_krita_session.py install --config config/local.json --target runner
python scripts/character_krita_session.py install --config config/local.json --target gui
```

`runner` uses `kritarunner` and `kritarunner_scripts`, copies no desktop entry,
and includes the fixed native proof harness only with `--include-proof`. `gui` uses `krita` and
`krita_scripts`, and writes the matching versioned `.desktop` entry pointing to
the content-hashed package. The command reports all installed paths and hashes.

Enable the optional GUI extension through Krita's Python Plugin Manager. The
installer does not enable it or restart Krita. Each effective source change gets
a different package name. Existing versions and their receipts remain intact;
enable only the version you intend to use. The runner package has no desktop
entry and is not discovered by the GUI Python Plugin Manager.

## Native revision and recovery contract

The session checks actual projection, ordered paint-layer pixels (including
bounded off-canvas extents), metadata and native selection. One current global
selection mask is checked separately against Krita's selection bytes. Unsupported
groups, animation, other mask nodes, blend/color modes and oversized extents
are rejected. Flat RGBA/U8, normal paint layers with the recorded sRGB profile
are supported; this does not establish arbitrary Krita document compatibility.
The selection export is a proposal source, not an approved edit mask.

Import preserves `live-intent.json` before attaching the layer, then writes
`live-result.json` or retains `live-failure.json` in the native package. No
repeated import is allowed from that package. A failed write may leave a partial
proposed layer for inspection; it never deletes the layer or resets the document.
Show source/result preserves each comparison intent and result. A later native
change makes comparison stale and leaves current visibility unchanged. Use native
layer controls to inspect it; do not remove journals to replay the command.

Native imports and comparisons never save or close the active document and never
clear its modified flag. A new proposed layer marks it modified. After inspection,
the user chooses whether and where to save the native document. Captures save and
close only an owned clone. Closing/reopening a file needs a new session; past
generated candidates can be retained, but all effective dependencies must still
match. None of these commands creates more generation allowance.

## Executed evidence and limits

On 13 September 2026 the fixed `session_proof.py` harness exercised this session
through Krita 5.2.16 (`7d9aefc`), Python 3.10.7, using an owned unsaved 384x256
document. `C:/AI/character-lab/native-session-proof-20260913-c` retains the result:

- An off-canvas hidden-layer edit left the visible source unchanged but rejected
  import before any new layer or import intent.
- Restoring that fixture mutation allowed one import. Exact native export checks
  found 4,032 changed pixels and 94,272 preserved pixels, with zero changes outside
  the defined rectangle. Source/result visibility toggles were exact.
- A later edit to the proposed layer blocked comparison and left it visible.
  The original document remained unsaved and modified. Only an owned clone was
  saved for inspection; no user document was closed.
- Independent Pillow decoding matched the native BGRA source/result buffers.
  Both exported images were visually inspected.

The first failure identified Krita's root-level `selectionmask`; a separate
structure probe established its one-channel native representation. The second
fixture failed its old layer-count assertion after that distinction was added.
Both failure folders remain. A separate native identity probe proved different
Python wrappers compare equal for the same document; the menu controller uses
that API instead of object identity.

The final installer package, including its extension registration, also passed
the same native API harness in `native-session-proof-20260913-d-installed`.
Its proof receipt SHA-256 is
`507fd841b7d269ad44016249153985a97196ed287ecf5af4678e43a6d972cf45`;
the adjacent launch receipt pins every installed source and the executable.
The GUI extension has not been installed or enabled in the user's GUI profile.

A separate attempt to exercise real menu actions via `kritarunner` crashed with
Windows status `0xc0000005`. An instrumented second attempt reached
`Krita.openWindow()` and crashed inside `Window.addView()` before capture or any
Studio action ran. Both `native-session-actions-20260913-a` and
`native-session-actions-20260913-b-diagnostic` retain their launch/log evidence.
This is an unresolved native view-binding failure, not a passing GUI proof;
no further action-probe retry was made. The intended window/action interfaces
are documented by [Krita's native API](https://api.kde.org/legacy/krita/html/classWindow.html).

Independent review of that historical native proof identified the non-blocking
dependency-manifest gap in [#225](https://github.com/Chris0Jeky/local-asset-studio/issues/225).
The subsequent [dependency-binding correction](../reconciliation/2026-09-13-krita-dependency-binding.md)
records the full manifest at protected package preparation and requires a live
request to match it before import. Old packages must be prepared anew in a new
output directory for live import; file-based legacy validation is retained.
The correction has synthetic document/package regression evidence, not a new
native or menu proof. Local packages remain cooperative inputs, not signed
authorization against a writer who can replace both package and request.

This proves native API behavior on the stated fixture. The menu/file dialogs,
keyboard interaction, larger documents, neural repair quality, owner acceptance
and rights remain separate checks. Issues #71/#65/#72 remain open. The old
portrait/boot attempts and their execution holds are unaffected.
