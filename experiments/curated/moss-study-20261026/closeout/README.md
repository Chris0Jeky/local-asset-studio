# Session closeout: three follow-up renders and a blind reread

The owner requested finishing and saving the work before closing the session.
The first Tifa follow-up group completed: **3 of the 12 planned jobs**, with three
unique prompt IDs, exact exported recipes and inspected outputs. The other nine
jobs were **never submitted**. Combined with the original study, this is **42
distinct completed images**, not 54: the blind exercise rereads existing pictures.
No result is owner-accepted by this record.

## Completed follow-up

[Receipts](followup-receipts.json), [three exact recipes](recipes/) and
[three agent pre-reviews](followup-judgements.jsonl) bind the executed Tifa seed
`2026102604` baseline, mikkoani 0.9 and fuller-bust wording. Settings remain
1024×1536, 30 steps, Euler / sgm_uniform, CFG 3 and an empty negative. Model pins
were checked before the batch; full file identities and template were checked
before each submission. Retained JSON is LF-normalized; separate export hashes
retain the original exported bytes.

**Receipt-label clarification, 26 October:** the retained `model_pins.scope` string
in `followup-receipts.json` says "five-job character batch". This historical label
does not define the number of follow-up executions: the receipt's three job
records and their hashes are the recorded scope. It supplies no evidence of two
additional runs or a new hash-verification event. The raw receipt is preserved.

All three are agent-rated keep, with minor glove/fingertip boundary ambiguity.
Recognition anchors remain clear. Fuller-bust wording gives a modest apparent
change; the torso angle also changes, so this is not a precise size measurement.
Mikko changes linework, presentation and silhouette, while the reviewer assigns
the same style-score bucket as the baseline on this franchise prompt. These
results do not establish multi-seed repeatability or a universal style winner.
All three originals and full-resolution face/hand regions were inspected by the
reviewer, and the coordinator viewed all three originals.

The private [follow-up gallery](E:/local-asset-studio-labs/moss-20261026/evidence/followup/gallery.html)
links each full-size picture and recipe. Original ComfyUI outputs also remain in
`C:/AI/experiments/moss-image/ComfyUI/output/Studio/`; no image bytes enter Git.

## Independent blind reread

Twelve original-study images (baseline, Mikko and Mikko + Impasto in each of four
scene/seed groups) were copied byte-for-byte to anonymous filenames. The mapping
was frozen before judging and withheld from the fresh reviewer. PNG metadata was
not inspected. The reviewer checked all 12 originals, 36 face/hand regions and
six outfit regions, plus 12 revised crop views: 42 final regions / 54 crop views.

[Raw blind judgments](blind-judgements.jsonl), [mapping](blind-map.json),
[reviewer summary](blind-summary.md) and [paired comparison](blind-comparison.json)
preserve the evidence. The [original-rating calculation](paired-score-analysis.json)
also retains every paired score. Entries below are wins / ties / losses for the
right-hand treatment against the left, **four matched pairs per row**:

| Comparison | Original style | Blind style | Blind adherence |
| --- | --- | --- | --- |
| baseline → Mikko | 4 / 0 / 0 | 4 / 0 / 0 | 0 / 1 / 3 |
| baseline → Mikko + Impasto | 1 / 3 / 0 | 4 / 0 / 0 | 0 / 2 / 2 |
| Mikko → Mikko + Impasto | 0 / 1 / 3 | 0 / 4 / 0 | 1 / 3 / 0 |

The Mikko style direction repeats, but the original Impasto penalty does not.
Garment adherence remains a separate tradeoff; there is no overall-image winner
established here. The raters differ as well as label visibility, so differences
cannot be attributed solely to blinding. Ratings are ordinal and subjective;
ties do not mean identical anatomy. These are the same four scene/seed cells,
not eight independent pairs, and no significance or training-membership claim is made.

## Runtime, QA and publication

The normal foreground Studio command in supervised session `85734` succeeded
after an earlier ad hoc detached launcher was rejected by automatic approval
review. Switching used Studio's existing guarded MOSS route. An initial runner
path error and a physical-memory admission refusal occurred **before any job
submission**; neither was a generation failure or an uncertain POST.

One observed physical-memory reading fell to approximately 0.01 GiB during
loading. The finite controller was stopped to prevent further submissions; its
three allowed jobs had already been submitted and all completed. No cancellation
or repeated prompt was needed. Stopping only the proven owned, idle MOSS PID
41400 released its cached memory (1.42 → 10.08 GiB available). The process-only MCP
report found zero provable orphans; no foreign process or OS setting was changed.

The final snapshot confirms 42 completed jobs, 42 unique prompt IDs, four original
Production plans awaiting subjective review, and no queued/incomplete execution.
MOSS was stopped after its queue was empty; the owned Studio PID 14368 then ended
through its supervised Ctrl+C session. Ports 8191/8198 are free. Shared Python,
Torch and installed ComfyUI source were unchanged. Rendering was local.

The discovered intake-test race was repaired separately in
[#1670](https://github.com/Chris0Jeky/local-asset-studio/pull/1670), merge
`f7ed2dd05ed269f163c6f7b4f88857bde1a80a4b`, closing #1669. Its final-head CI passed
6,113 tests / 79 skips in 1,005.191 seconds, with no retained thread/child at
shutdown. Controlled scheduling passed after the fix; omitting the release in
memory still failed. These checks qualify that test change, not this art's quality.

## Exact resume point

Keep the [frozen follow-up plan](../followup-plan.json) unchanged. Its first group,
Tifa seed `2026102604`, is complete. Only the remaining three groups are unsubmitted:
Tifa `2026102605`, Yor `2026102604`, Yor `2026102605`, three variants each. Consult
the retained job IDs before any resume; never repeat an uncertain submission.
Recheck model/template identity, queue ownership and resource headroom before
starting. Memory pressure under concurrent host use needs attention before another
batch; do not lower the existing guards or alter installed runtime packages.

The eight Kromoss comparisons remain NOT RUN: its checkpoint partial and exhausted
transfer-attempt budget remain tracked in [#1662](https://github.com/Chris0Jeky/local-asset-studio/issues/1662).
`HUMAN_TODO.md` still owns art acceptance and Make-look choices. The owner requested session closeout; neither remaining plan is a scheduled
background job.
