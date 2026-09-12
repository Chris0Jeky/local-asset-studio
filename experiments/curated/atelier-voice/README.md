# Atelier / follow the light — 12 September 2026

A reproducible scene draft, not an accepted character performance or release asset.
Open it in the local [Scene editor](http://127.0.0.1:8191/av.html?project=f14b08eba5e84375a2c604fd4e3db686).

The original line is “The lantern is ready. Follow the light.” Studio prepared it, then an explicit
Generate action ran the pinned offline Kokoro CPU baseline with built-in `af_heart`. It produced a
2.8-second dry 24 kHz mono PCM16 WAV and a 48 kHz scene copy. The model receipt measures 3.187 seconds
including two seconds of model loading; it excludes Python import, queue and resampling time.
No ComfyUI prompt was submitted for either this voice take or the scene assembly.

The Scene editor combined two existing atelier images and the new voice into 720x1080 at 24 FPS,
with a half-second dialogue offset and half-second dissolve. FFprobe decoded 156 video frames over
6.5 seconds; the retained PCM mix has 312,000 stereo samples at 48 kHz. Browser playback worked with
no JavaScript errors or external browser requests. The completed run added exactly two Studio jobs.

## Inspection notes

I inspected the browser preview and an extracted frame from the second shot. The first shot shows the
witch reading beside a lantern; the second shows the existing fox shrine beneath pink blossoms.
The square shrine source is letterboxed within the portrait canvas. This draft demonstrates assembly
and voice placement; it does not fix the source images' previously noted detail/anatomy imperfections.
Decoded voice/mix statistics contain zero full-scale samples. Those statistics do not establish
perceived loudness or audio quality. The independent offline ASR transcript was “The lantern is ready,
follow the light.” All seven normalized words match; punctuation differs. No human listening,
pronunciation, acting or voice-identity acceptance is recorded. Model/source terms remain separate.

## Reproduction and preserved outputs

- Voice project: `0a0753e11fb44c649106fb97199ed2b5`; job: `5e0982574aa450dd8f8538148fdd67af`.
- Scene: `f14b08eba5e84375a2c604fd4e3db686`, revision 2; render/job: `513bd06980514be5930a9aa981caf8cd`.
- [Voice recipe](voice-recipe.json), [scene recipe](scene-recipe.json), and [separate ASR receipt](transcription.json)
  retain the model, tools, source assets, controls, hashes and measurements. The voice recipe's
  `transcription: not_performed` describes the synthesis runner; ASR was performed later, separately.
- Full outputs remain under `C:/Users/jekyt/source/local-asset-studio/experiments/projects/`:
  voice project `voice/lantern-opening.wav` and `voice/lantern-opening-scene.wav`; scene project
  `renders/513bd06980514be5930a9aa981caf8cd/preview.mp4` and `mix.wav`.
- Browser screenshots, decoded frame, FFprobe result and mutation receipts remain in
  `.runtime/session-2026-09-12/voice-baseline/`. Installed bundles stay outside Git in
  `C:/AI/voice-lab-kokoro/` and `C:/AI/voice-lab-asr/`.

Recipes preserve the existing take and its provenance. Inspect its IDs and files before explicitly
preparing another take; do not repeat an uncertain submission. `HUMAN_TODO.md` retains creative choices.
