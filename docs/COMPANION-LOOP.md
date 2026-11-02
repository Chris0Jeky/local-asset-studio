# Companion loop: type a line, a toon character answers in voice

Built and measured on 2 November 2026 (R&D night, suzu-companion lane) with Suzu, the original SFW character from
[ANIME-TOON-KIT.md](ANIME-TOON-KIT.md). Everything runs locally. Input is typed text only; no microphone.
Lab media (WAVs, captures, logs) stays outside Git.

| Piece | Runs in | Does |
| --- | --- | --- |
| llama-server (llama.cpp) | GPU | OpenAI-compatible streaming chat; any instruct GGUF |
| `scripts/companion_loop.py serve` | the Kokoro venv (Python 3.12, torch CPU, kokoro 0.9.4) | Cuts the token stream into sentences, voices each with the pinned Kokoro bundle while the next is still generating, and sends `{text, emotion, wav, cues}` per sentence as NDJSON on loopback TCP 8095 |
| `tools/godot-toon/companion.tscn` | Godot 4.7.2 | Chat box, sentence queue, mouth driven from the audio clock, mood expressions, wave on greetings, nod, gaze |

## Run it

```bash
llama-server -m model.gguf --device ROCm0 -ngl 999 -c 4096 -np 1 -t 4 --reasoning-budget 0 --port 8090
<kokoro-venv>/python scripts/companion_loop.py serve --persona persona.md --memory memory.json
godot --path tools/godot-toon companion.tscn          # model.glb, springs.json, face_sdf.png as for the toon proof
python scripts/companion_loop.py ask "Hi!" "What are you up to?"   # scripted client, one JSON line per turn
```

The persona is a Markdown system prompt. The reply must start with a mood tag (`[happy]`, `[curious]`, `[thinking]`,
`[apologetic]`); a mid-reply tag switches the mood for the following sentences. `[remember: fact]` is stripped from
speech and appended to `memory.json` (`{"self": [...], "friend": [...]}`), which feeds the next turn's system prompt.
Godot reads an optional `res://set.glb` (toon-dressed) and `res://companion.json` (name, position, yaw, camera).
`--demo=lines.txt` types each line and waits for the reply; `--log=turns.jsonl` records per-turn timings. Under
`--write-movie` it paces game time to the wall clock and writes `<log>-mouth.csv` (mouth openness per frame).

## Mouth cues from Kokoro, not Rhubarb

Kokoro already predicts one duration per phoneme (`pred_dur`, 600 samples = 25 ms per unit). `phoneme_cues()` maps
each misaki phoneme to a Rhubarb mouth shape (A-H, X), so the Godot side keeps Rhubarb's cue format. Stress marks take
the next phoneme's shape: Kokoro gives the stress token real time at the vowel onset. Measured on six sentences against
the audio RMS envelope (10 ms grid):

| Track | Cost per sentence | Best lag | Correlation at 0 ms |
| --- | --- | --- | --- |
| Rhubarb 1.14 phonetic | 530-670 ms (mostly start-up) | -40..+150 ms | mean 0.27 |
| Kokoro pred_dur, raw | 0 ms | +40..+60 ms (6/6 late) | mean 0.13 |
| Kokoro pred_dur, shifted 50 ms earlier (`VISEME_LEAD`) | 0 ms | -10..+10 ms | mean 0.33 |

Rhubarb pocketSphinx took 3.8 s on a 7.6 s line. `--visemes rhubarb` keeps the Rhubarb path.

## Measured (RX 9070 XT, 32 GB, Gemma 4 12B it QAT q4_0, ROCm build b12032)

- **Enter → first audible word** (Godot real-time window, WASAPI, 6 scripted turns): 1.01-1.64 s, median ~1.2 s, with
  `-t 4` on llama-server; 1.19-1.88 s with its default 14 threads, which compete with Kokoro on the CPU.
- **Stages for the first sentence:** first token 0.3-1.2 s (median 0.65 s, grows with history), first sentence text at
  0.4-0.8 s, Kokoro 0.5-0.8 s for it. The full LLM reply takes 1.2-2.5 s; the rest is audio playback.
- **Rendered lip sync** (Movie Maker capture, logged mouth openness vs the captured audio): -4 ms and -13 ms on two
  45-47 s captures (mouth very slightly ahead), correlation peak at zero lag.
- **Persona, 20 scripted turns:** mood tag first 20/20, under 45 words 20/20, no markdown 20/20, a question back 19/20,
  never called itself an AI or assistant, admitted 3/3 unknowns in character, recalled the user's name at turn 18.
  Moods were mostly happy (16/20); `apologetic` was never chosen in that run.

Latency levers, in the order they paid off: trim Kokoro's ~0.35 s leading silence; take mouth cues from Kokoro instead
of Rhubarb (~0.55 s); ask the persona for a short first sentence; give llama-server fewer CPU threads. The first piece
may also end at a comma once 24 characters long, but Gemma's opening sentences rarely contain one.

## Traps

- **Vulkan was 8× slow after a host crash.** The same b12032 Vulkan build and model that benchmarked 71 tok/s earlier
  gave 4.6-8.5 tok/s after a hard freeze and reboot (`-fa on` made it worse: 2.9-8 tok/s), while the ROCm build gave
  61 tok/s. Benchmark both before blaming the model.
- Godot strips `--write-movie` from `OS.get_cmdline_args()`; use `Engine.get_write_movie_path()`.
- llama-server's default thread pool competes with a CPU TTS: `-t 4` cut the first-word time by ~0.3 s.

## Limits

One user, one turn at a time, no barge-in (a new line waits until she finishes). The loopback port has no
authentication: any local process can make her speak. Licences: Gemma (Apache-2.0), Kokoro-82M (Apache-2.0),
Rhubarb (MIT), llama.cpp (MIT); a character's persona and voice choice are yours to record. Not verified: other GPUs,
other voices or languages, a physical (microphone) measurement of audio output latency, long sessions beyond 20 turns.
