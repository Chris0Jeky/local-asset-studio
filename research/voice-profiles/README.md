# Voice profile data contracts

This directory contains only non-sensitive, reviewable inputs for Local Asset Studio narration-profile selection and qualification.

## Files

- `catalog.json` defines the checked-in Kokoro control and the experimental `ember-brief-v1` target.
- `evaluation-set.json` defines the shared, ordered audition script used by deterministic qualification plans.

Neither file contains model weights, generated audio, reference recordings, absolute local paths, device observations, or owner qualification results.

## Catalogue identity

A profile record has a stable ID and monotonically increasing integer revision. Its canonical SHA-256 covers the complete record, including:

- identity and model metadata;
- producer adapter and runnable state;
- speaker metadata;
- delivery presets;
- lexicon revision and entries;
- mix recipe;
- acceptance evidence.

A Spoken Brief manifest binds the selected profile hash, delivery hash, lexicon hash, mix hash, and effective speaker metadata. Those values therefore participate in run identity and final receipt evidence.

## Local registry

Private or machine-specific records belong under an ignored `_voice_profiles/` directory. Supply a registry with `--profile-registry` or PowerShell `-ProfileRegistry`.

Replacing a checked-in profile requires:

```json
{
  "id": "ember-brief-v1",
  "revision": 2,
  "supersedes_profile_sha256": "the exact currently resolved profile hash"
}
```

The replacement must contain the complete strict profile schema. A stale hash, unchanged revision, duplicate ID, unsupported field, malformed hash, filesystem path masquerading as an asset ID, or inconsistent acceptance state is rejected.

The compare-and-swap link prevents one local experiment from silently overwriting evidence produced from another revision.

## Current execution boundary

Only `kokoro-af-heart-control-v1` is executable today. It resolves to the existing `voice-baseline` adapter and pinned `af_heart` bundle.

`ember-brief-v1` is intentionally `experimental`, `unbound`, and non-runnable. It can be selected in `plan` mode to prove deterministic manifest binding, but `run` refuses it before creating local run state or contacting Studio.

A later accepted record still needs a producer adapter that genuinely implements its model and reference identity. Do not relabel the Kokoro adapter as a Qwen, IndexTTS, cloned, or designed voice.

## Qualification data

Generate the immutable qualification plan locally:

```powershell
python scripts/voice_profile_qualification.py plan ember-brief-v1 `
  --output .\_voice_profiles\ember-plan.json
```

After permission-safe local trials, validate the report:

```powershell
python scripts/voice_profile_qualification.py validate `
  .\_voice_profiles\ember-plan.json `
  .\_voice_profiles\ember-report.json
```

The plan is zero-generation metadata. Report validation checks exact plan/profile/evaluation identities, candidate coverage, finite measurements, per-line machine and owner findings, the Kokoro control, multiple non-control candidates, and a 300–600 second owner-reviewed long-form take.

The normalized result is evidence for a later local profile revision. It does not modify `catalog.json`, create a producer adapter, or certify subjective quality automatically.
