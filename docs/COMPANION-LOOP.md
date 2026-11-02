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
<kokoro-venv>/python scripts/companion_loop.py serve --persona persona.md --memory memory.json [--scene scene.json]
godot --path tools/godot-toon companion.tscn          # model.glb, springs.json, face_sdf.png as for the toon proof
python scripts/companion_loop.py ask "Hi!" "What are you up to?"   # scripted client, one JSON line per turn
```

The persona is a Markdown system prompt. The reply must start with a mood tag (`[happy]`, `[curious]`, `[thinking]`,
`[apologetic]`); a mid-reply tag switches the mood for the following sentences.

**Memory survives restarts.** `memory.json` holds `{"self": [...], "friend": [...], "recent": [...]}`. `self` is the
character's own background (written by you, from the character bible; the model never adds to it). `friend` collects
`[remember: fact]` tags, but only **grounded** ones. One message the user typed in the last four turns must hold every
content word of the fact (suffixes stripped, so "moved"/"moving" and "harbour"/"harbor" match; relation words such as
"name" or "likes" need no support). It must have the same negation, so "I don't love cats" never grounds "loves cats".
Anything it says belongs to someone ("my sister", "his job") must be in the fact too, so a friend's taste is not filed
as the user's. At most two facts per turn. Anything else lands in the turn's `rejected_facts` and is never stored. On
the 2 November A/B this kept "Ana just moved to the harbour town" and "nervous about starting a new job", and rejected
"her favourite colour is blue" (the character's own answer) and "wears blue socks" (invented). The check is lexical: a
fact that uses synonyms is rejected (the safe side). `recent` keeps the last six messages, so a restarted sidecar picks
the conversation up where it stopped. The sidecar holds an exclusive lock on `<memory>.lock` while it runs, so two
sidecars cannot overwrite each other's memory.

**Scene awareness.** `--scene` takes `[{"id": "<set node name>", "say": "how she would describe it", "aliases": [...]}]`.
The descriptions go into the system prompt, so treat `scene.json` like the persona: it is prompt text, and a file from
someone else can steer her. A sentence that names an alias carries `"look": "<id>"`. Godot then turns her head (up to
35°) and eyes to the merged bounds of that node's meshes in `set.glb` while the sentence plays. A prop behind her gets a
glance toward the side of the screen where it shows.

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

## Which model: Gemma 4 12B by default

Same setup for both (ROCm b12032, `-t 4`, the same persona, 20 scripted turns plus 6 real-time turns), 2 November:

| | Gemma 4 12B it QAT q4_0 | Qwen3.5-9B Q4_K_M (unsloth) |
| --- | --- | --- |
| Generation | 57 tok/s | 81 tok/s |
| Enter → first audible word, median (range) | 0.97 s (0.89-1.24) | 0.89 s (0.69-1.10) |
| Format (mood tag first, ≤45 words, no markdown) | 20/20 each | 20/20 each |
| Admitted what it could not know (3 prompts) | 3/3 | 1/3: invented tonight's tide time |
| `[remember]` tags | 3, all correct | 12, one wrong (the character's own favourite colour, filed as the user's), later an invented detail |
| Moods used | happy 14, thinking 5, curious 1 | happy 18, thinking 1, apologetic 1 |

Gemma is the default: fewer persona defects for 0.08 s. Both licences are Apache-2.0. Which one *sounds* more like the
character is a taste call; a blind Versus contest pairs the two models' voiced replies per prompt for the owner. The
grounding guard above would have stopped Qwen's wrong fact.

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

One user, one turn at a time (the server serialises turns across clients), no barge-in (a new line waits until she
finishes). The loopback port has no authentication: any local process can make her speak and, through a reply's
`[remember: …]`, add lines to `memory.json` that later turns read as context. Run it only on a single-user machine.
History is trimmed in blocks (over 12 messages, keep the last 6) so llama-server's prompt cache still matches. Licences: Gemma (Apache-2.0), Kokoro-82M (Apache-2.0),
Rhubarb (MIT), llama.cpp (MIT); a character's persona and voice choice are yours to record. Not verified: other GPUs,
other voices or languages, a physical (microphone) measurement of audio output latency, long sessions beyond 20 turns.
