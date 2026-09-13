# Open-document Krita edits

Issue #71 requires the human and agent to edit the same native document. The
existing protected compositor and saved-file runner establish exact patch pixels,
but cannot notice an unsaved change in the open canvas. This design implements
that missing native boundary. The owner's ongoing implementation authorization
and #71 supply the scope; it does not authorize another model attempt.

The optional Krita extension exposes explicit Capture, Import, Show source and
Show result actions. A shared Python session object operates on the selected
native document. It retains a random session identity and fingerprints the actual
canvas, ordered layers and selection. It never saves, closes or clears the
modified flag of the user's document. A capture writes a new artifact directory;
an owned clone supplies the source KRA. No network listener, polling executor,
generation action, automatic candidate selection or second document database is
added. Agents prepare the same typed import request consumed by the menu action.

Source, canon, masks and candidate remain governed by the existing edit plan,
protected compositor and `character_krita.prepare`. A live request pins that
native package and the captured session. Before adding a paint layer the native
session verifies the full live revision, the package's exact source/result and
the captured source KRA identity. Intent is retained before any canvas mutation.
A lost response cannot authorize a second import. An operation failure retains
its proposed layer and evidence for inspection; it does not erase user work.

The new layer is reversible by visibility. Readback proves its exact pixels and
source restoration. Compare commands require the current post-operation revision
and the same document/session; changes to hidden layers, selection, layer order,
pixels or metadata make the request stale. No command removes a layer, saves over
a file, resets native undo history or silently adopts a reopened document.

Supported input is the existing flat, normal, non-animated RGBA/U8 contract with
`sRGB-elle-V2-srgbtrc.icc`, opaque source/result and at most 16 million canvas
pixels. Unknown layer features or unbounded extents reject before import. Native
source pixels outside the canvas are included in the revision guard. Selection
coverage is inspected and exported explicitly, never inferred as an approved
write mask. The existing compositor controls writable pixels.

Prove causal stale-state and failed-write behavior with fake native objects,
then run the same session commands with real Krita APIs on a disposable authored
document, including an unsaved hidden-layer change. Retain native outputs and
receipts. A mechanical native result is not neural repair quality, owner
acceptance, rights clearance or completion of all #71 requirements.

The alternative of extending only the saved-file runner cannot detect unsaved
changes. A second native inference plugin would duplicate Studio ownership. This
session adapter reuses both existing boundaries and leaves campaign-wide edit
budgets and measured neural repair yield in #65/#72.

API references: [Document](https://api.kde.org/legacy/krita/html/classDocument.html),
[Node](https://api.kde.org/legacy/krita/html/classNode.html),
[extensions](https://docs.krita.org/en/user_manual/python_scripting/krita_python_plugin_howto.html).
