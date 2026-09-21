# Soothing narration voice profile brief

Issue: #637. This is the creative and measurement brief for the reusable voice that should eventually replace the built-in Kokoro control in Spoken Briefs.

## Direction

The listening target is warm, clear and low-fatigue for dense engineering handoffs, with a bright, playful fantasy spark available for summaries and wins. Megumin is a useful reference for the desired energy contrast, not the identifier of the shipped profile. The engineering target is an original LAS voice with its own stable name, retained recipe/reference provenance and explicit owner acceptance.

Working profile ID: `ember-brief-v1`.

Desired qualities:

- soothing at ordinary briefing pace;
- crisp consonants and reliable technical terms;
- youthful brightness without a permanently exaggerated performance;
- controlled energy rise for headings, decisions and positive outcomes;
- calm handling of risks, caveats and long numerical passages;
- consistent identity across separately generated 15–30 second segments;
- minimal harsh sibilance, breath noise and pitch fatigue over 10 minutes;
- natural pauses that tolerate deterministic assembly.

Avoid making “more anime” one undifferentiated slider. Identity and delivery are separate. A calm briefing and an energetic recap should retain the same speaker.

## Proposed delivery presets

| ID | Use | Direction |
| --- | --- | --- |
| `calm-brief` | Default full handoff | Warm, attentive, measured, lightly upbeat; prioritise clarity and low fatigue |
| `dense-technical` | Paths, numbers, architecture and caveats | Slightly slower, restrained pitch range, deliberate punctuation |
| `spark-recap` | TLDR, wins and completed work | Brighter and more animated, but still intelligible and not shouted |
| `risk-review` | Blockers and uncertainty | Calm, grounded and precise; no theatrical alarm |

These are performance recipes. They must not redesign the identity on every segment.

## Candidate sequence

1. Use Qwen3-TTS VoiceDesign to explore original identity descriptions and retain every exact model/revision/seed/configuration.
2. Select a clean accepted reference and move to the model's appropriate reusable Base/CustomVoice path so later lines condition on a stable identity rather than redesigning it.
3. Compare one genuinely different expressive route, initially IndexTTS 2.5 or VoxCPM2 when its exact Windows/AMD or CPU path is measured.
4. Keep the pinned Kokoro `af_heart` baseline as the cheap control for speed, intelligibility and resource use.

A candidate is not “better” merely because a six-line audition is charming. It must survive an assembled 5–10 minute handoff.

## Shared evaluation script

Every candidate/configuration uses the same stable line IDs and text:

1. `neutral`: “The implementation is ready for review, and no generation will repeat automatically.”
2. `question`: “Should we merge the migration before the queue recovers, or keep the two changes separate?”
3. `reaction`: “Great, that closes the blocker.”
4. `names`: “Taskdeck, NavSentinel, Local Asset Studio, ComfyUI, Qwen three TTS, and pull request six hundred and thirty-six.”
5. `numbers`: “The run produced seventeen segments, forty-eight kilohertz mono audio, and a SHA two hundred and fifty-six receipt.”
6. `path`: “Open the handoffs folder, select COMPRESSED dot M D, and inspect the spoken output directory.”
7. `long`: one 350–500 character paragraph with a decision, rationale, caveat and next action.
8. `contrast`: the same recap in `calm-brief` and `spark-recap` to measure delivery control without identity drift.

Then render one real, permission-safe 5–10 minute handoff through the Spoken Brief compiler and assembler.

## Measurements

Record per configuration:

- model and codec identity, exact revisions and file hashes;
- runtime package versions and backend;
- cold load and first-audio latency;
- total generation time and real-time factor;
- peak host memory, VRAM and committed memory;
- generated seconds and accepted seconds;
- omitted/repeated/substituted words from independent transcription;
- correction and regeneration time;
- cross-segment identity drift;
- join naturalness with the standard pauses;
- owner ratings from 1–5 for clarity, warmth, fatigue, identity, expressive control and overall preference.

Automated transcription can flag words. It cannot certify voice similarity, acting quality, naturalness or comfort.

## Acceptance gate

`ember-brief-v1` becomes the Spoken Brief default only when all of these are recorded:

- the owner accepts the identity from the retained audition evidence;
- one 5–10 minute assembled brief is listened to end to end;
- no unexplained omission or repetition remains in accepted segments;
- proper names and recurring project terms have an explicit lexicon or spoken-form rule;
- separate `calm-brief` and `spark-recap` takes retain recognisably the same identity;
- performance and memory fit the workstation without mutating the shared image-generation environment;
- reference source, transcript, hashes and permission scope are retained locally;
- dry audio and mix treatment remain separate;
- the profile is labelled `accepted`, not inferred from a successful model invocation.

## Proposed retained profile record

```json
{
  "schema_version": 1,
  "id": "ember-brief-v1",
  "status": "experimental",
  "identity": {
    "producer": "qwen3-tts-custom-voice",
    "model_revision": "full pinned revision",
    "reference_asset_id": "local content-addressed asset",
    "reference_sha256": "sha256",
    "reference_transcript": "exact transcript"
  },
  "delivery_presets": {
    "calm-brief": {"instruction": "retained exact direction"},
    "spark-recap": {"instruction": "retained exact direction"}
  },
  "lexicon_revision": "sha256",
  "mix_recipe_revision": "sha256",
  "evidence": {
    "audition_project_ids": [],
    "long_form_manifest_sha256": null,
    "owner_review": "unreviewed"
  }
}
```

The profile belongs in ignored/local evidence until its schema and sensitive-reference handling are implemented. Reference recordings, model weights and generated audition audio do not belong in Git.
