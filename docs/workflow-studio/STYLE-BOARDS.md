# Style-board setup and recovery

Style-board presets use one to three ordered pictures as **visual encoder inputs**.
They are not Qwen multi-picture instruction routes. `reference_board.min` defines
how many of the authored slots must be filled; the remaining slots are optional and
are pruned before submission. The ordinary Create readiness check and the opt-in
guide use the same minimum rule.

## Proposal and shared-draft semantics

A reviewed setup proposal keeps the main positive and negative wording unchanged.
Each supplied picture is recorded with `role_mode: "style-board"`, its authored
slot role and the preset's declared preprocessing policy. Per-picture
`contribution` and `avoid` text is refused because the board compiler does not add
that text to the prompt. This prevents visual-only board inputs from being silently
reinterpreted as Qwen prompt guidance.

Applying an approved proposal stages only the supplied pictures, then stores a
reference record for every authored slot. Unfilled positions are retained as
explicit `file: null`, `pruned: true` placeholders so save, reload, undo and later
compilation preserve slot order. Board drafts do not invent
`controls.reference` or `controls.last_reference`; those controls belong to the
older singular/two-input routes. Workspace parent assets are retained, while
`parent_by_input` stays empty because a style board is represented by positional
reference records rather than those singular input names.

Proposal construction and application remain separate explicit actions. Neither
operation submits generation, validates artistic usefulness, approves model terms
or proves the native image encoder's crop is suitable for a particular picture.

## Older Production plans

A Production plan created before the positional placeholder change in #327 may
contain the shorter compiled reference list rather than one record per authored
board slot. When such a plan is recovered, Production re-prepares the stored recipe
and compares the resulting graph, controls and recipe identity with the retained
fingerprint. The changed representation fails closed with:

> The recovered recipe changed; create an explicit branch

It does not shift a picture into a different board slot or silently resume with a
new graph. Inspect the retained plan and sources, then create an explicit branch
under current semantics when continued work is intended. No pre-#327 Production
plan using this representation is currently known to exist; absence of a known
plan is not a deletion or migration claim.

## Verification boundary

Repository contracts cover minimum readiness, prompt separation, proposal
identity, staged-byte checks, positional placeholders, reload compilation and the
absence of a generation request. Owner-machine inference, visual crop assessment,
model/runtime compatibility and creative acceptance remain separate evidence.
