# Open-document Krita session

`scripts/character_krita_session.py` prepares a typed request for the optional
Krita extension. It first recomputes the protected edit through
`character_krita._expected`, requires the retained native plan to match that
result, and pins every explicit source, canon, mask, candidate and bundle
artifact it reaches. The request is JSON data, not Python code.

Capture is a user action in Krita. Choose a new, empty capture folder; the
extension writes its owned source clone, projection, selection and
`snapshot.json` there. It does not save, close or clear the modified state of
the active document. Build a request only after the existing protected package
has been prepared:

```console
python scripts/character_krita_session.py request --workspace C:/AI/character-lab/EDIT_WORKSPACE --snapshot C:/AI/character-lab/captures/revision-3/snapshot.json --package native-revision-3 --out C:/AI/character-lab/captures/revision-3/import-request.json
```

In Krita, use **Tools → Scripts → Capture document**, **Import request**,
**Show source**, and **Show result**. A session belongs to the same open
document object and root node captured by the action. Switching documents or
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
and does not include the future native proof harness. `gui` uses `krita` and
`krita_scripts`, and writes the matching versioned `.desktop` entry pointing to
the content-hashed package. The command reports all installed paths and hashes.

The focused tests prove request tampering and a changed pinned source reject
before session import, that installation refuses changed files, and that plugin
registration has no startup action. They are not evidence that this extension
has loaded in a particular Krita installation, that a real native document has
been edited, or that any candidate is creatively accepted or licensed.
