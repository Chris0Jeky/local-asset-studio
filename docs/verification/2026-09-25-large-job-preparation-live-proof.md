# Live proof: prepare-large-job on the owner's Windows PC (#306)

Date: 25 September 2026. The owner approved the full proof in-session: dry run, refusal cases, counters around `/free`,
and one owned backend restart. The GPU was running the owner's local LLM (`llama-server`) throughout. No generation was
submitted at any step, and every receipt says `generation_submitted: false`.

Raw receipts are gitignored under `.runtime/proof-306/` on the owner's PC. The first 16 hex digits of each file's SHA-256
are listed here. The helper that sent each request is `.runtime/proof-306/run.py`: one same-origin
`POST /api/large-job-preparation` per step, recipe `anima-portrait` with default controls.

## What the proof found before it could pass

The proof ran against `main` as merged in #960. It stopped three times on real defects, each fixed and reviewed before
the next step:

1. **#972: the gate refused everything, even a dry run.** Five old `uncertain` jobs and planned, awaiting-review and
   interrupted plans all counted as active work. The gate now classifies each record:
   - work in flight blocks every action;
   - unresolved work at rest blocks only the restart, and only while the selected ComfyUI still holds its `/history`;
   - work at rest never blocks.
2. **#980: three failed jobs from 11 September still blocked everything.** They kept a submission receipt marked
   `observing`. Such a receipt on a terminal job now blocks only the restart, with the same history check.
3. **#982: available VRAM was misread.** It was taken as `min(vram_free, torch_vram_free)`, which reads 0 on an empty
   card, and ComfyUI's `vram_free` also ignores other processes: the LLM held 11.8 GiB that ComfyUI reported as free.
   Available VRAM is now ComfyUI's `vram_free` minus the other processes' dedicated VRAM, from the Windows GPU counters.
   It is unknown when unmeasured, or when the counters are implausible. During the proof dwm.exe's counter read
   65.9–81.7 GiB on the 15.9 GiB card (#983), so VRAM stayed unknown.

## Steps and receipts

| Step | Configuration | Request | Result | Receipt |
|---|---|---|---|---|
| a | as merged (#960), flags absent | dry run | refused: "Active, partial or uncertain Studio work…" (finding 1) | `b8f5bf34a4d9e0e8` |
| b | after #972 | dry run | refused: three failed jobs with open receipts counted as in flight (finding 2) | `df6a3775518921b3` |
| c | after #980 | dry run | refused `profile_unknown`: no admission profile exists; 9 records block only the restart, 0 block everything | `19a9ca8427c0d2cc` |
| d1 | a synthetic profile (8 GiB VRAM), flags off | dry run, release + restart | completed `dry_run`: planned release and restart; `local_authorization` all false. History probe: 9 × `history_absent`. Nothing called | `0326b817996bb205` |
| d2 | same | real, release | refused `cleanup_disabled` | `70ad91a5d1677a98` |
| e1 | `enable_large_job_resource_cleanup: true` | real, release only | `/free` sent to the verified owned process (PID 59964 plus its creation time) with an idle queue; `measured_relief: false`; stopped at `restart_not_authorized` with `state: unknown` (M2) | `963b82aa4deb7d03` |
| f1 | after #982; the profile needs 64 GiB RAM (more than the PC has) and no VRAM; both flags true | real, release + restart | see below | `ef71484d0377664c` |
| g1 | original `config/local.json` restored byte-for-byte | real, release | refused `profile_unknown`: the command is inert again | `6ce3127fcd938d28` |

**Step f1, the full lifecycle:**
- **Release:** `/free` went to PID 59964 with an idle queue. Deltas: physical RAM −160 MB, commit −152 MB; no relief, because the idle ComfyUI held nothing.
- **History check:** all 9 unresolved records were `history_absent` on the selected backend, so none blocked the restart.
- **Restart:** the owned process 59964 was terminated after identity, queue and switch-gate checks, and PID 65000 was launched. It was ready 38.7 s after the launch intent.
- **Restart deltas:** Windows commit **+2.75 GB** (the retained commit the restart exists to reclaim), physical RAM +136 MB, VRAM unknown.
- **Final:** `restart_insufficient`, `ready: false`, `state: unknown`. This is correct: the synthetic stage needs more RAM than exists.
- **Unrelated processes:** `llama-server` (PID 27164, started 24 Sep 20:38) was untouched. The ComfyUI queue stayed empty.

## What this proves, and what it does not

**Proven on the owner's PC:**
- dry-run non-mutation;
- the refusal cases (no profile, cleanup disabled, restart not authorised);
- the history-gated restart;
- the owned-process identity checks;
- the unknown-after-action receipt state;
- measured counters around `/free` and the restart;
- no impact on an unrelated GPU process.

**Not proven:**
- a release or restart that turns an unsafe decision into a safe one for a real, measured profile. No measured stage-aware admission profile exists yet (#178), and both proof profiles were synthetic;
- any VRAM effect (see #983);
- any throughput claim.

Both flags are absent again in `config/local.json`. The command is off by default.
