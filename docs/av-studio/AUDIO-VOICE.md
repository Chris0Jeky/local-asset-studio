# Audio and voice frontier

Research date: **11 September 2026**. These are primary-source-backed candidates and proposed production experiments, not rankings from audio generated in this session. [The source catalog](../../research/av-studio/catalog.json) records direct maintainer/model-card links. This pass tested editing/rendering with procedural audio, not neural voice or music quality.

## A shortlist worth testing on this workstation

Keep the working Radeon Comfy environment unchanged. Audio models should have separately pinned environments and complete model bundles. A documented CUDA example is not proof of Windows/ROCm compatibility; a working CPU implementation is often a useful first baseline. Measure encoder/model loading, first audio latency, total generation time, peak host/GPU memory and accepted seconds. Do not download every candidate before identifying what the first three fail to do.

| Role | First experiment | Independent comparison |
|---|---|---|
| Original recurring character voice | Qwen3-TTS voice design → accepted reference → reusable voice recipe | VoxCPM2 |
| Expressive Japanese/English dialogue | IndexTTS 2.5 with separate identity/emotion and pronunciation controls | Chatterbox Multilingual or MOSS speech family |
| Cheap batch scratch narration | Kokoro or Piper on CPU | MOSS Nano on an actually supported backend |
| Multi-character dramatic scene | Per-line recorded takes with stable speaker IDs | Fish S2-Pro or MOSS dialogue, separately licensed |
| Local music and editable variations | ACE-Step 1.5 appropriate base/SFT/Turbo variant | Stable Audio3 music variant |
| Isolated designed sounds | Procedural/sample baseline plus Stable Audio3 Small SFX | MOSS SoundEffect2 |
| Video-conditioned Foley | Authored event cue sheet plus one candidate generator | MMAudio versus HunyuanVideo-Foley |
| Text/audio verification | CPU faster-whisper baseline | Qwen3-ASR plus separate forced alignment |

These assignments are recommendations. No candidate is declared the best or automatically installed.

### What materially differs between the voice models

**Qwen3-TTS** exposes distinct VoiceDesign, CustomVoice and Base variants. The valuable pipeline for this studio is designing an original voice, selecting a clean reference, then reusing that identity across new lines rather than redesigning the speaker each time. Its language coverage includes Japanese and several European languages. Use the exact model card and interface, not a generic TTS loader. [Official project](https://github.com/QwenLM/Qwen3-TTS).

**IndexTTS 2.5**, released August 2026, is more relevant than stale IndexTTS2 tutorials. It separates speaker and emotion references and adds language-specific pronunciation controls, including Japanese Kana. Its documented duration factor offers delivery scaling; do not interpret that as a guaranteed exact phoneme schedule. Some older IndexTTS2 paper capabilities were not enabled in that release, so preserve version-specific configuration. [Official README](https://github.com/index-tts/index-tts).

**VoxCPM2** adds multilingual design/cloning and 48kHz generation. Its linked split-model llama.cpp-omni path is worth investigating for alternative local backends; it is not evidence that every acoustic component runs on Vulkan or ROCm. Preserve the exact text/acoustic model split and backend versions. [Official project](https://github.com/OpenBMB/VoxCPM).

**MOSS** is a family rather than a single universal checkpoint: small Nano, dialogue, voice design, realtime speech and SoundEffect are separate routes. Investigate Nano as a low-cost baseline and the larger local speech models for explicit delivery controls. Avoid transferring memory or latency claims from one family member to another. [Official family](https://github.com/OpenMOSS/MOSS-TTS).

**Fish S2-Pro** is an expressive multi-speaker candidate, but its model card uses the Fish Audio Research License, with separate commercial arrangements. Keep it available as a researched option without labelling it MIT or silently treating research permission as commercial permission. [Model card](https://huggingface.co/fishaudio/s2-pro).

**Chatterbox** offers a smaller expressive lane; Turbo and Multilingual are not interchangeable language/configuration choices. Keep its built-in PerTh watermark and provenance information through the pipeline. [Official repository](https://github.com/resemble-ai/chatterbox). **Kokoro** is useful as a small narration baseline, not a substitute for every style/control feature. [Card](https://huggingface.co/hexgrad/Kokoro-82M). **Piper** remains a CPU-oriented option; the engine licence and each voice's terms are separate records. [Maintained engine](https://github.com/OHF-Voice/piper1-gpl).

## Build a Voice Lab, not just a text box

The proposed record has four independent parts:

- **Identity:** stable speaker ID, voice-design description, accepted clean references, transcript, model/codec revision, reference hashes and applicable permission record.
- **Performance:** exact line ID/text, language, pronunciation lexicon, intended emotion, pace, breaths/reactions, target duration window, previous/next-line context.
- **Take:** generation settings and seed where meaningful, source waveform, actual duration, rejected alternatives, alignment and review findings.
- **Mix treatment:** gain, EQ, compression, de-essing, room/reverb, spatial position and bus routing. This must not rewrite the stored dry take.

For example, “make the reply quieter and more hesitant” can branch the performance while retaining identity. “Move the reply 250ms later” is an editorial change, not a synthesis request. “Make it sound like the observatory” is normally a treatment/mix change, not a reason to contaminate the reference voice with room reverberation.

Start with six original lines: a neutral statement, a question, a short reaction, a proper name, a long sentence and a phrase in the required second language. Compare two takes per configuration. Check pronunciation, omitted/repeated words, identity drift, unnatural joins and performance, then record correction time. Automated ASR agreement is useful but cannot certify voice similarity, acting or naturalness.

Cloning references should be authorised, recorded as local assets and kept clean. Original designed voices avoid the dependency on locating suitable clips of an existing actor. Preserve the user's recorded authorisations at their actual scope; do not invent new blanket restrictions or assume that one model's permission applies to every unrelated reference or service.

## Dialogue, translation, captions and lips

Proposed production chain:

`script with stable line IDs → cast voices → draft takes → ASR comparison → approve text/pronunciation/performance → forced alignment → captions and mouth cues → dry stems → mix → scene playback`

**Qwen3-ASR** and its separate aligner serve different functions. Transcription estimates what was said; forced alignment locates a supplied transcript in audio. Do both when evaluating generated speech, rather than force-aligning the intended script and calling that a word-accuracy check. [Official project](https://github.com/QwenLM/Qwen3-ASR).

**faster-whisper** is useful for CPU/int8 work; its documented GPU acceleration is CTranslate2/CUDA, not automatically the working Torch/ROCm stack. [Project](https://github.com/SYSTRAN/faster-whisper). **WhisperX** adds alignment/diarization orchestration with additional model requirements. Speaker diarization identifies segments; it does not itself identify a real person. [Project](https://github.com/m-bain/whisperX).

**Rhubarb** provides a CLI and timed mouth-shape JSON. Map those cues to the actual 2D mouth drawings or VRM/Blender expressions; preserve neutral/blink/emotional channels separately. Its recognizer/language assumptions require testing, especially beyond English. Mouth amplitude alone is not a phoneme sequence. [Project](https://github.com/danielswolf/rhubarb-lip-sync).

Dubbing requires a language-specific script, pronunciation, timing budget, takes and captions. Keep line IDs stable across languages; split long cues instead of shrinking type until it is unreadable. Prefer rephrasing or modest performance changes to extreme time stretching. Never time-stretch narration and music with one undifferentiated setting. Subtitle sidecars should survive video export; animated burned-in text is an optional presentation branch.

## Music: useful editing matters more than another complete song

**ACE-Step1.5** is especially worth trialling because the project documents AMD paths and exposes multiple editing-oriented configurations. Its XL4B release is separate from the low-memory base selection. The feature matrix distinguishes base, SFT and Turbo: extraction, adding a layer and completion must be checked for the exact variant. [Project](https://github.com/ace-step/ACE-Step-1.5).

For the studio, store musical intent: original motif, tempo, key, meter, instrumentation, energy curve and section boundaries. Generate a short audition, then retain an accepted segment and derive intro/loop/outro or low/high-intensity alternatives. Enforce sample-exact loop boundaries after musical review. A waveform with a zero crossing is not necessarily a musically seamless loop.

Separate an original multitrack project from estimated stems separated out of a final mix. Do not label the latter lossless source tracks. Test bass/percussion leakage, phase behaviour and summed reconstruction. For game music, use coherent layers sharing meter, duration and harmonic progression rather than independently generated tracks that happen to claim the same BPM.

**DiffSinger plus OpenUtau** is a distinct path when notes, syllables, pitch curves and editable vocal performance matter. Keep the score/project and voicebank configuration; a generated mixed song does not provide this structure automatically. [DiffSinger](https://github.com/openvpi/DiffSinger), [OpenUtau](https://github.com/openutau/OpenUtau). Voice conversion, singing synthesis and TTS should be separate capabilities with explicit input/output contracts, not three labels on one interface.

## Sound design and Foley

**Stable Audio3 Small SFX** is a current candidate for sound generation/editing/continuation. Resolve the inference variant rather than its `-base` training counterpart, and retain the gated Community and encoder terms. [Model card](https://huggingface.co/stabilityai/stable-audio-3-small-sfx). Video-conditioned candidates **MMAudio** and **HunyuanVideo-Foley** should be compared against an authored cue sheet; MMAudio's code and checkpoint licences differ. [MMAudio](https://github.com/hkchengrex/MMAudio), [Foley](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley).

The higher-value pipeline is often hybrid: exact procedural click or transient, recorded texture, generated body/tail, then deterministic layering. An agent should classify a sound as one-shot, repeating ambience, sustained loop, voiced reaction or musical event before selecting a tool. Preserve attack, body and decay where later tuning is valuable. Do not generate a new sound when a licensed existing UI click already satisfies the brief; [Kenney's Interface Sounds](https://kenney.nl/assets/interface-sounds) is a concrete CC0 starting pack.

For an opening door, derive hinge/impact timestamps from the scene or animation events, then create cue variants and audition in context. Do not assume a video-conditioned generator will place every contact correctly. For a sword effect, separate swipe, metallic body, impact and tail; retain independent gains and spatial treatment. For ambience, create several variants and crossfade/resequence under runtime control rather than ship one obvious six-second loop.

**SAM Audio** separates a target specified by text, visual context or timing; it is not a new-sound generator. Use target/residual comparisons to identify damage and leakage. [Project](https://github.com/facebookresearch/sam-audio). **DeepFilterNet** is a cleanup option, while **Pedalboard** provides programmable effects and plugin integration; preserve dry originals and exact processing settings. [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet), [Pedalboard](https://github.com/spotify/pedalboard).

## Mixing, mastering and delivery

Use dialogue, music, FX and ambience buses with documented ordering and automation. Add cue-based ducking or sidechain compression deliberately; a static reduction and a compressor have different audible behaviour. Save the dry stem, processed stem and master. Keep natural timing and reverb tails; do not cut every file immediately at its last voiced sample.

The delivered prototype standardises preview audio to48kHz PCM16 WAV and records sample peak, RMS, DC and full-scale samples. Those checks are **not** LUFS, intersample true peak, perceptual quality, denoising accuracy or a listening test. A production adapter should add measured loudness/true-peak reports with a delivery-specific target rather than a universal streaming number. Retain 24bit/float masters in the later production path; the current16bit interchange is a deliberately limited preview contract.

For game delivery, linear edits are only half the job: expose event IDs, concurrency limits, random variants, surface types, distance falloff, music-state transitions and localization lookup. Test the selected engine's audio buses and platform limitations; Godot's web Sample/Stream paths do not have identical effect behaviour. [Godot audio buses](https://docs.godotengine.org/en/stable/tutorials/audio/audio_buses.html).
