# Voice profile data contracts

This directory contains only non-sensitive, reviewable inputs for Local Asset Studio narration-profile selection and qualification.

## Files

- `catalog.json` defines the checked-in Kokoro control and the experimental `ember-brief-v1` target.
- `evaluation-set.json` defines the shared, ordered audition script, including the same-text calm/spark contrast pair.
- `qualification-policy.json` defines the repository-owned candidate, producer-family, reference, measurement, contrast, and long-form acceptance policy.

These files contain no model weights, generated audio, reference recordings, absolute local paths, device observations, or owner qualification results. Every persisted JSON input is bounded, UTF-8 decoded, and rejected when it contains duplicate keys or non-standard `NaN`/`Infinity` constants.

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

## Local catalogue overlay

Private or machine-specific records belong under an ignored `_voice_profiles/` directory. Supply a registry with `--profile-registry` or PowerShell `-ProfileRegistry`.

Overlaying a checked-in profile requires:

```json
{
  "id": "ember-brief-v1",
  "revision": 2,
  "supersedes_profile_sha256": "the exact checked-in catalogue profile hash"
}
```

The overlay must contain the complete strict profile schema. A hash for different checked-in catalogue bytes, unchanged revision, duplicate ID, unsupported field, malformed hash, filesystem path masquerading as an asset ID, or inconsistent acceptance state is rejected.

This is a catalogue-drift guard, not a mutable compare-and-swap registry. Resolution always starts from the checked-in catalogue and applies at most one local record per profile ID. The resolver does not retain local predecessor state or serialize competing file writers; issue #671 tracks that stronger mutation boundary.

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

The plan is zero-generation metadata, but its hash is not treated as policy authority. Report validation independently reloads `qualification-policy.json` and `evaluation-set.json`, checks their ID/revision/hash, and requires the generated plan to reproduce their exact candidates, producer families, adapters, reference requirements, measurements, contrast pair, line set, and 300–600 second long-form bounds. A locally rehashed weakened plan is rejected.

Each measured candidate retains exact producer family, adapter, model ID and revision, runtime/configuration hashes, and permission-safe reference hashes when required. Acceptance needs the Kokoro control, at least two measured non-control candidates, an accepted selectable route, and another measured non-control route from a different producer family. The selected route also needs paired `calm-brief` and `spark-recap` takes over identical text, with identity consistency and delivery control reviewed separately from ASR differences.

The normalized result is evidence for a later local catalogue overlay. It does not modify `catalog.json`, create a producer adapter, install a model, or certify subjective quality automatically.
