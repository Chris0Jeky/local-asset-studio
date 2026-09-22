# Recovery lifecycle inspection design

Refs #393; follows the user's recovery bundle and #698. Keep the existing tab
journal, opt-in shelf and authoritative AssetWorkspace. Add only an explicit
read projection and a lens inside the existing shelf dialog.

The projection reads 1–200 retained IDs in order in one Workspace-checked SQLite
snapshot. Missing rows are explicit. Existing rows expose title, revision,
active/trash state and bounded current membership summaries. No media or review
notes are read by the projection. The receipt owner and response schema remain
unchanged: its ten-row current preview cannot stand in for a full bulk selection.

The lens captures local evidence without restoring or changing it, then issues
GETs for the exact request receipt and current projection. Each is independently
validated. One unavailable response cannot erase the other; equal current fields
cannot confirm an unknown request. The combined view explicitly has two read
instants. Foreign/unknown Workspace identity refuses before reads, and late replies
after dialog close, replacement or Workspace change have no UI authority.

The existing shelf owns local export/discard and dialog focus. Add current-state
inspection buttons and a distinct inspection export without import/commit/retry
controls. Keep stable actions, a live region, bounded text-only rendering and
long-ID wrapping. No metadata, collection, trash, generation or staging mutation
is introduced. Broader editor retry/refusal and full accessibility qualification
remain on #393, not silently represented as completed by this read-only slice.
