# Narration profiles and qualification

Issue: #637. Broader Voice Lab implementation remains #28.

Spoken Briefs now has a durable profile-selection and qualification contract. This separates four concepts that must not be collapsed into one string:

1. **Identity**: the intended reusable speaker and its retained model/reference evidence.
2. **Delivery**: calm briefing, dense technical reading, energetic recap, or risk review.
3. **Producer adapter**: the concrete LAS implementation capable of generating that identity.
4. **Acceptance**: explicit owner-reviewed evidence that a profile is suitable for real use.

The current executable producer is still the pinned Kokoro `af_heart` control. The original `ember-brief-v1` profile is deliberately checked in as `experimental`, `unbound`, and non-runnable. A successful schema validation or model invocation does not promote it.

## Creative direction

`ember-brief-v1` targets warm, clear, low-fatigue narration for dense engineering handoffs, with a brighter fantasy-like spark for summaries and wins. Any media character is a high-level energy reference only. The shipped identity must be original, permission-safe, and retained under its own profile ID.

Desired qualities:

- soothing at ordinary briefing pace;
- crisp consonants and reliable technical terms;
- youthful brightness without a permanently exaggerated performance;
- controlled energy rise for headings, decisions, and positive outcomes;
- calm handling of risks, caveats, paths, and numerical passages;
- consistent identity across separately generated segments;
- minimal harsh sibilance, breath noise, and pitch fatigue over 5–10 minutes;
- natural pauses that tolerate deterministic assembly.

Identity and delivery remain separate. A calm brief and an energetic recap should still sound like the same speaker.

## Checked-in catalogue

`research/voice-profiles/catalog.json` contains non-sensitive, reviewable profile definitions.

| Profile | Status | Adapter | Executable now |
| --- | --- | --- | --- |
| `kokoro-af-heart-control-v1` | `control` | `voice-baseline` | Yes |
| `ember-brief-v1` | `experimental` | `unbound` | No |

Every profile records:

- stable ID, revision, display name, and status;
- identity kind, model/voice metadata, language, and optional reference evidence;
- producer adapter, runnable flag, and stable speaker metadata;
- versioned delivery presets;
- lexicon and mix recipe revisions;
- acceptance state and retained qualification hashes.

The catalogue is bounded UTF-8 JSON and validated with an exact schema. Unknown fields, invalid IDs, malformed hashes, local filesystem paths in reference records, unsupported statuses, and inconsistent acceptance states are rejected.

## Delivery presets

| ID | Intended use | Direction |
| --- | --- | --- |
| `calm-brief` | Default full handoff | Warm, attentive, measured, lightly upbeat; prioritise clarity and low fatigue |
| `dense-technical` | Paths, numbers, architecture, caveats | Slightly slower, restrained pitch range, deliberate punctuation |
| `spark-recap` | TLDR, wins, completed work | Brighter and more animated, while remaining intelligible and controlled |
| `risk-review` | Blockers and uncertainty | Calm, grounded, precise, without theatrical alarm |

The current Kokoro control records these as metadata-only delivery intentions. `speaker_id` is also metadata for recipe identity; it does not cause Kokoro to design or clone another voice.

## Spoken Brief selection

Preview a profile and delivery without submitting generation:

```powershell
.\scripts\speak-handoff.ps1 `
  "C:\LAS\handoffs\<pack>" `
  -ProfileId ember-brief-v1 `
  -DeliveryId calm-brief `
  -PlanOnly
```

Planning an experimental profile is allowed because it only creates an inspectable manifest. Running it is rejected before a Studio client, lock, state file, or `_spoken` directory is created:

```powershell
.\scripts\speak-handoff.ps1 `
  "C:\LAS\handoffs\<pack>" `
  -ProfileId ember-brief-v1
```

The current executable control remains:

```powershell
.\scripts\speak-handoff.ps1 `
  "C:\LAS\handoffs\<pack>" `
  -ProfileId kokoro-af-heart-control-v1 `
  -DeliveryId dense-technical
```

A profile binding is part of the Spoken Brief manifest identity. Changing profile, profile revision, delivery, delivery revision, lexicon, mix recipe, or speaker metadata creates a different manifest and run directory. The exact binding is copied into the final receipt.

## Local profile registry

Accepted references, permission records, local producer details, and owner-reviewed qualification evidence stay outside Git. Supply them through an optional local registry:

```powershell
.\scripts\speak-handoff.ps1 <pack> `
  -ProfileId ember-brief-v1 `
  -DeliveryId calm-brief `
  -ProfileRegistry "C:\LAS\_voice_profiles\profiles.json" `
  -PlanOnly
```

A local profile can overlay a checked-in catalogue profile only when it carries:

- the same stable profile ID;
- a strictly higher integer revision than the checked-in profile;
- `supersedes_profile_sha256` equal to the exact checked-in catalogue profile hash.

This guard detects catalogue drift: a local overlay prepared for different checked-in profile bytes is refused. It is not a mutable registry compare-and-swap operation, a persisted local revision chain, or a concurrent-writer lock. Each resolution starts from the checked-in catalogue and then applies at most one local record per profile ID. Replacing the registry file is an external operator action; two competing writers are not serialized by the resolver. Issue #671 tracks a genuine local CAS update boundary if that stronger property is needed.

New local profile IDs must not claim to supersede an unknown catalogue record.

Local `_voice_profiles/` directories are ignored by Git. Store model weights, recordings, generated takes, reports, absolute paths, and sensitive permission evidence there, not in the checked-in catalogue.

## Deterministic qualification plan

Create a zero-generation plan:

```powershell
python scripts/voice_profile_qualification.py plan ember-brief-v1 `
  --output "C:\LAS\_voice_profiles\ember-plan.json"
```

The command does not start Studio, inspect a device, install a package, download a model, or submit inference. It records:

- the exact profile binding and hash;
- the shared evaluation-set hash and stable line IDs;
- candidate IDs and roles;
- required measurement fields;
- the 300–600 second long-form review boundary;
- `generation_submitted: false`;
- a canonical plan SHA-256.

The proposed programme includes:

1. `qwen3-voice-design-v1` for original identity exploration;
2. `qwen3-reusable-reference-v1` for stable accepted-reference reuse;
3. `indextts-2-5-expressive-v1` as an independent expressive comparison;
4. `kokoro-af-heart-control-v1` as the cheap built-in control.

The plan defines the candidates. Workstation measurements determine which are actually available and useful. The current validator requires the Kokoro control and at least two measured non-control candidates. Model-family independence remains an owner/reviewer judgement until producer-family identity is represented directly in the report schema.

## Shared evaluation set

`research/voice-profiles/evaluation-set.json` is immutable input to one qualification plan. It covers:

- neutral technical narration;
- a question;
- a short positive reaction;
- project and model names;
- numbers and acronyms;
- a path-like instruction;
- a long decision/rationale/caveat passage;
- delivery contrast.

Every measured candidate must cover the exact ordered line set. A report cannot omit or reorder lines without failing validation.

## Report validation

After local trials, validate the retained report:

```powershell
python scripts/voice_profile_qualification.py validate `
  "C:\LAS\_voice_profiles\ember-plan.json" `
  "C:\LAS\_voice_profiles\ember-report.json"
```

Per candidate, the validator requires:

- stable candidate ID and `measured` status;
- exact configuration SHA-256;
- finite, non-negative load, first-audio, generation, memory, generated-duration, accepted-duration, and correction measurements;
- every evaluation line in exact order;
- audio and independent-transcript hashes;
- substitution, insertion, deletion, and empty-output evidence;
- owner ratings for clarity, warmth, fatigue, identity, and delivery;
- an explicit accepted/rejected decision and notes.

Aggregate acceptance requires:

- the measured Kokoro control;
- at least two measured non-control candidates;
- a selected measured non-control candidate;
- a 5–10 minute long-form manifest and audio hash;
- owner confirmation that the long-form file was heard end to end;
- identity-consistency, pronunciation, fatigue, and acceptance review;
- a retained UTC decision timestamp and rationale.

NaN, infinity, booleans disguised as numeric values, negative measurements, duplicate candidates, incomplete hashes, incomplete line coverage, out-of-range long-form duration, and decisions selecting an unmeasured or control candidate are rejected.

Validation returns a normalized acceptance summary with the report hash and long-form hashes. It does not mutate the source report or update the local registry automatically.

## Promotion gate

`ember-brief-v1` should move from `experimental` to `accepted` only when all of these are true:

- the owner accepts the original identity from retained audition evidence;
- a reusable producer path is pinned to an exact model revision and runtime;
- reference source, transcript, bytes, and permission scope are retained locally;
- one 5–10 minute assembled handoff is heard end to end;
- no unexplained omission or repetition remains in accepted segments;
- proper names and recurring project terms have explicit spoken-form rules;
- calm and spark deliveries retain recognisably the same identity;
- resource use fits the workstation without mutating the shared image-generation environment;
- dry audio and mix treatment remain separate;
- every delivery promoted with the profile is marked `qualified`;
- the local overlay names the exact checked-in catalogue profile it replaces.

Even an accepted local record is not executable until LAS has a producer adapter matching that identity. The current `voice-baseline` adapter remains tied to the pinned Kokoro control; it must not be relabelled as Qwen, IndexTTS, or `ember-brief-v1`.

## Evidence boundary

The offline contracts prove profile parsing, canonical hashes, catalogue-bound overlay validation, delivery binding, qualification-plan identity, report validation, CLI forwarding, manifest/receipt propagation, and refusal before side effects.

They do not prove:

- that a model is installed or compatible with the workstation;
- the speed or memory use of a real model;
- that independent transcription is accurate;
- that an identity sounds original, consistent, pleasant, or low-fatigue;
- that pronunciation or performance has been accepted;
- that a custom producer adapter exists;
- that local registry file writers are serialized or form a durable predecessor chain.

Those require local retained evidence and human listening. Broader producer, audition, replacement, alignment, and dialogue tooling remains #28; transcript and pronunciation workflow remains #641; stronger registry mutation semantics remain #671.
