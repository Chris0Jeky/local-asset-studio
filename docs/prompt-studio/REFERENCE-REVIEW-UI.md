# Review reference descriptions without editing JSON

Open **Prompt Lab → Review your references**. This is the browser review half of
#333/#336's local reference assistant. It consumes the saved analysis JSON from
that assistant; **it does not yet run Analyze from the browser**.

## Use

1. Open the saved analysis JSON (raw report or helper envelope, at most 128 KiB).
2. Select the exact original PNG/JPEG/WebP pictures used for that analysis. Order
   and filenames may differ: SHA-256 matching establishes which picture is which.
   Changed, missing, duplicate or extra files produce a visible refusal.
3. Read the interpretation, choose each picture's role, and select/edit the traits
   to transfer. Role changes remove incompatible selections rather than relabeling
   them silently. Suggested tags are opt-in. Uncertain traits need an explicitly
   edited description. Original observations remain unchanged.
4. **Preview changes** checks the original bytes and current brief through the
   local review API. Read the reference replacement count and before/after fields.
   The current instruction remains unless you select its replacement checkbox.
5. **Apply to brief** updates the existing Prompt Lab draft. **Undo reference apply**
   restores its prior snapshot only while the applied draft is still unchanged.
   A later manual edit is never overwritten by Undo. **Export review receipt**
   retains the original analysis, source/selection evidence, before/after intent,
   assumptions and unanswered questions, without embedding image bytes.

The manual brief/reference controls remain available. Selected files and panel
state last only in this tab; there is no hidden autosave or shared project store.
A new analysis does not replace the current brief. Late file reads, original
hashing and HTTP previews are rejected after newer selections or draft edits.
Only an explicit Apply can change the brief; import, preview and navigation make
zero helper or image-generation calls. File object URLs are released on replacement
and page exit. The API receives original bytes only for local validation, without
publishing files or staging them to ComfyUI.

## Existing owner, not a parallel draft

`StudioPromptDraft` in `prompt-lab.js` owns capture/match/apply/undo over the actual
intent and form. The panel is a client of that owner. Capture includes the form's
current values even before an input event, profile, local revision and full JSON.
The preview echoes its exact base intent, avoiding a second JavaScript
implementation of Python's canonical-number hashing. Changed base/profile/revision
or changed report/selection invalidates Apply. Applying twice is refused. Validation stays single-flight while a late reply is
outstanding; changing a selection cannot start another expensive source check.
Reselecting an edited trait retains the description shown in its input. Existing
duplicate tags and comma-containing tag/avoid values survive unchanged display.

The raw analysis file is parsed by the existing strict server decoder, not by a
browser parse/stringify round trip that could hide duplicate fields. Untrusted
labels/descriptions are rendered with text nodes, not HTML. Source paths are
shown as evidence, never opened as server paths or evaluated as commands.

These are **in-session conflict guards**, not server compare-and-swap or cross-tab
shared revisions. #38 still owns persisted intent/proposal history and shared
agent commands. #35/#178 still own safe scheduled Analyze and resource admission;
`idle_confirmed` from the CLI is not exposed as web authority. #232/#335 own native
setup application. The current text-only Create bridge must not drop these
references just to make a profile compile. Four analyzed images are not four
native Qwen slots, and descriptions are not geometric pose control.

## Qualification

Run `python -m unittest discover -s tests -p 'test_reference_*.py'`, the existing
Prompt Studio tests, JavaScript syntax checks and `python tests/reference_review_browser.py`.
The browser driver serves the real Prompt Lab files through the real prompt HTTP
extension, with synthetic original images and no Studio/model instance. It checks
desktop/390px, keyboard apply, hash matching after filename/order changes, inert
markup, edited traits, stale apply, undo, retained receipt and no inference/generation.
The Prompt Studio workflow runs the reference contracts on Linux and Windows,
plus the actual browser driver on Linux. Full-suite and repository-validator gates
remain unchanged.

Local container Chromium has an administrator URL blocklist, so live navigation
there is not qualification evidence; its policy was left unchanged. Hosted browser
results and logs are recorded on the PR. Synthetic browser/HTTP results do not
establish local VLM understanding, AMD performance, successful repair or art acceptance.
HUMAN_TODO q-7/q-25/q-26 and all existing generation allowances remain unchanged.
