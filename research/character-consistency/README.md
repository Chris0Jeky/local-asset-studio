# Character consistency research and executable examples

Start at [the programme guide](../../docs/character-consistency/README.md). Goals/waypoints are in [ROADMAP.md](../../docs/character-consistency/ROADMAP.md); the [runbook](../../docs/character-consistency/RUNBOOK.md) gives exact local commands.

- `archive-lock.json` pins all 71 members of the original delivery, including the full report, source images, crops, guide, prompts and historical evidence. Restore it outside Git with `scripts/character_archive.py`.
- `canon.example.json` is a deliberately **draft** supplied-character specification with actual reference hashes. Do not treat it as an owner-approved or commercially cleared original character.
- `pilot.study.json` declares a 12-case, zero-extra-repair feasibility study over existing `qwen-1ref` and `flux-edit` presets. It makes no model-quality or runtime result claim.
- `empty-records.json` demonstrates unmeasured reporting. Generate fresh plans with `scripts/character_study.py plan`; derived plan files and actual runs belong outside Git.
- `OFFLINE-EVIDENCE.json` records the CPU proof; [VALIDATION.md](VALIDATION.md) distinguishes original 65 focused tests, the later numeric-type regression and actual repository CI.

Current Python contracts live in `scripts/character_study.py`, not the archived proposal schema. The source-preserving media utilities live in `scripts/character_media.py`. Neither implementation submits neural work.
