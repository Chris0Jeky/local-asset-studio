# Local voice baseline

Open **Voice baseline** from the Studio header. Enter a take name, a stable fictional speaker ID,
and up to six original lines (one per paragraph). **Prepare take** pins the model files and tools;
**Generate CPU take** explicitly queues inference on the existing Studio worker. Opening the page
or preparing a take does not synthesize anything. Completed dry and scene-ready WAVs appear in
Workspace and on the take's audition/download controls. Use the 48 kHz copy with Scene editor assets.

The first supported voice is Kokoro's built-in American English `af_heart`. Speaker IDs organize
recipes; they do not design or clone a voice. Acting direction, alignment and independent transcription
are unsupported. Listening, pronunciation and character performance remain review decisions.

## Isolated installation

This host has a dedicated Python 3.12.10 and CPU environment under `C:/AI/voice-lab-kokoro/`.
It does not share ComfyUI packages. `bundle.json` records the absolute environment Python, full model
revision, size/SHA256 of config/model/voice files, package versions and model terms. Configure its
absolute path as `voice_baseline_bundle` in ignored `config/local.json`, alongside an explicit `ffmpeg`
executable path. Restart an idle Studio to load configuration. A missing bundle leaves the page usable
for inspection and disables Prepare.

The installed [Kokoro-82M model](https://huggingface.co/hexgrad/Kokoro-82M) is pinned to
`f3ff3571791e39611d31c381e3a41a3af07b4987`. The local metadata records the model card's Apache-2.0
license; this is provenance, not approval of a generated character or a downstream use. Inference uses
local config, weights and `af_heart.pt`, with Hugging Face/Transformers offline flags and blocked Python
socket connection methods. English G2P's spaCy `en_core_web_sm` must already be installed; the first job
does not install it. Runtime versions and complete installation receipts live beside the bundle.

## Limits and recovery

A take has at most 2,000 text characters and 120 seconds of generated samples. The owned inference
process has a 180-second deadline; the separate FFmpeg resample step has 60 seconds. Cancellation
terminates owned processes and preserves the request, logs and partial files. Failed or interrupted
takes are retained for inspection; prepare a new take to try again. An explicitly requested resume is
shown only for an interrupted plan proven unstarted: no request file, attempt record, owned job,
published artifact or voice-output directory may exist. Studio never resumes inference or repeats an uncertain
attempt. A full recipe is saved before execution and attached to Workspace outputs. Model/config/voice
bytes and runner/Python/FFmpeg executable hashes are checked at Prepare and Start. At both boundaries,
the configured isolated Python runs a bounded metadata-only child that uses `importlib.metadata`; it does
not import the model or Torch, download packages, or claim to hash the complete environment. Observed
distribution versions must match both the bundle manifest and the versions observed at Prepare.

Cancellation checks run before publication and the final terminal commit is atomic with a stop request.
Only when every planned voice output has completed Workspace publication does an accepted stop record that
cancellation was too late; published and failed outputs remain retained for inspection.
Controlled success, failure and cancellation paths finalize the nested attempt. An abrupt process death
can still leave its last durable attempt state as `running`; recovery treats that as unproven and never
repeats inference.

Dry output is 24 kHz mono PCM16. The scene copy is resampled to 48 kHz mono PCM16 with no loudness
normalization or other mix processing. Receipts retain exact text, graphemes, phonemes, file hashes,
sample counts and timing. Decoded sample peak/RMS/DC/clipping statistics do not establish LUFS,
true peak, intelligibility or perceived quality.

## Executed evidence — 12 September 2026

The isolated bundle produced six original lines in one offline CPU run. A separate real Chromium151
Studio fixture then prepared and explicitly generated “The lantern is ready. Let us begin.”, registered
both WAVs, and played the scene copy. Its 2.85-second output has 68,400 dry samples and 136,800 scene
samples, with zero full-scale samples. Page load and Prepare caused no inference; the browser made
two explicit POSTs and had no JavaScript errors, external browser requests or ComfyUI requests.
Desktop and 390 px layout were checked. The disposable fixture adapts Host/Origin only to its ephemeral
port; product loopback guards have separate HTTP tests. Raw proof is retained in
`.runtime/session-2026-09-12/voice-baseline/`; installation proof remains under `C:/AI/voice-lab-kokoro/`.
Playback was exercised, but no human listening acceptance or independent transcription is recorded.
Optional creative choices remain in `HUMAN_TODO.md`.

A separate isolated faster-whisper base.en CPU check transcribed the six installation takes offline
without regenerating them. It matched 63 of 64 normalized words: the name `Mira` became `Mayra` in
the raw ASR transcript (one substitution, zero insertions/deletions). This is transcription agreement,
not proof of correct pronunciation or acting. Its pinned bundle and full comparison receipt live under
`C:/AI/voice-lab-asr/`; the built-in Studio take runner does not yet invoke ASR. The browser fixture's
different 2.85-second line has no independent transcription in that receipt.
