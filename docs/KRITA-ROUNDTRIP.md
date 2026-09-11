# Krita OpenRaster roundtrip

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
