# Krita OpenRaster roundtrip

## Edit a Library picture and bring it back

In an opened Library picture, **Edit in Krita** opens a separate working PNG.
Studio shows its exact path. Edit and save that PNG, wait for saving to finish,
then press **Bring back from Krita**. The changed picture is imported as an
unreviewed repair linked to its original, with the same Regular or Private
classification.

If you use **Save As** to keep layers in a `.kra` or another editable format,
keep that file and also export a PNG over the working PNG Studio opened.
Bring back reads only that named PNG: an unchanged PNG does not mean your
editable document has no changes. Studio does not search for files saved
elsewhere. To bring back a PNG exported to another location, choose it under
**Import repaired version** instead.

The PNG must be complete, at most 20 MiB and at most 40 megapixels. A truncated
PNG or a file changed/replaced while Studio reads it is refused with guidance
to let Krita finish saving and retry. Refusal creates no repair and does not
change the edit session. The read checks file identity, size and timestamps,
requires the complete final IEND chunk and CRC, verifies the PNG and decodes its pixels; it cannot lock Krita or predict a save
that starts after that snapshot was read.

Each edit session remembers every successfully imported byte hash across
Studio restarts. Bringing back save A, then B, then A offers the original repair
for A without importing it again. Older sessions that only remember their last
import preserve that receipt when their history is extended; earlier receipts
already overwritten by old versions cannot be reconstructed. A malformed
session is refused as an unavailable edit (HTTP 400), preserving its files.

Working PNGs, session JSON, editable siblings and Krita backups are retained.
Automatic pruning is a follow-up for issue #1864: a retention and recovery
policy must account for unsaved native editing and editable documents that may
exist only in this directory before deletion is safe. This fix does not infer
that an imported PNG makes a `.kra` disposable. Native GUI save/export behavior
still needs an owner run on the configured Krita installation; automated tests
use synthetic PNGs and mock application launch.

## Export layered artwork

Use **Workspace → select images → Create native export → Layered artwork ·
ORA / Krita**. Leave **Save and reopen in local Krita** checked, name the layers,
prepare the plan and explicitly Start it in Experiments. The original images,
ORA, KRA, reopened PNG and logs are included in the native source pack.

`scripts/krita_roundtrip.py` is a narrow native-file proof adapter. It validates
a bounded OpenRaster archive, snapshots it into a newly created output directory,
uses the configured Krita executable twice, and retains the KRA, PNG, command
logs and failure record. It invokes the documented batch-export form:

```text
krita input.ora --export --export-filename roundtrip.kra
krita roundtrip.kra --export --export-filename export.png
```

Krita documents this command-line export form for Windows as well as Linux and
macOS, including conversion by output filename extension. See the [official
command-line manual](https://docs.krita.org/en/reference_manual/linux_command_line.html).
The adapter supplies absolute owned paths, normal Windows Qt batch export with a
hidden process (`STARTF_USESHOWWINDOW`/`SW_HIDE` plus `CREATE_NO_WINDOW`), no
shell, a fixed 90-second timeout, and no scripts, macros or caller command text.
It removes any inherited `QT_QPA_PLATFORM` override because Krita's offscreen Qt
platform crashed in the local proof. The CLI intentionally uses only its fixed
default configured path; a trusted coordinator may call
`execute(..., configured_krita=...)` after it has validated its own configuration.

```powershell
python scripts/krita_roundtrip.py preflight
python scripts/krita_roundtrip.py roundtrip C:\work\layers.ora --out C:\work\new-krita-proof
```

The result records OpenRaster and KRA ZIP members, available layer attributes,
native KRA preview dimensions, and the PNG dimensions after reopening the KRA.
It rejects mismatched dimensions and preserves every owned failure file. It does
not inspect UI state, editing behavior, color management, masks/groups/blend
semantics beyond listed metadata, or pixel/art acceptance.

The owned ORA snapshot is hash-checked against the inspected source before any
Krita command. A source changed during preparation is retained as a failed
attempt, preventing its old metadata from being attached to different bytes.

## Evidence in this slice

The adapter and synthetic ORA boundary are unit-tested with a mocked Krita
process. The local executable at `C:\Program Files\Krita (x64)\bin\krita.exe`
preflighted with SHA-256
`fed1f4556a3ead6bce3926c44fa2e20a38211a2c49b3b4f5acd05aea6e0a58d6` on 11
September 2026. An initial 1×1 offscreen attempt exited `0xC0000005` before
creating a KRA; its source snapshot, argv log and failure receipt remain in the
ignored worktree runtime evidence. A separate hidden normal-Windows batch proof
then converted a valid 64×64 two-layer ORA to KRA, reopened that KRA to PNG,
found both named paint layers in `maindoc.xml`, and matched all reopened PNG RGBA
pixels to the known merged source. That proves this fixed path on this installed
Krita version only. It does not establish UI behavior, color-management fidelity,
or art acceptance. No installer was run. A successful local `roundtrip` result
is the condition that sets `native_kra_save_reopen_proved` to true for that one
output directory.
