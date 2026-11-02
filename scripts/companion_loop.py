"""Local talking-companion loop (docs/COMPANION-LOOP.md): a llama-server token stream is cut into sentences, each sentence
is voiced by a pinned Kokoro bundle with mouth cues taken from Kokoro's own phoneme durations (or Rhubarb), and every
finished sentence goes to a Godot client (tools/godot-toon/companion.gd) as one NDJSON line over loopback TCP while the
next sentence is still generating. Text input only.

  python scripts/companion_loop.py serve --persona P.md --memory M.json [--llm http://127.0.0.1:8090] [--port 8095]
  python scripts/companion_loop.py ask "line" ["line" ...]      # scripted client: one JSON summary per turn

Client -> server: {"type": "say", "text": "..."}       Server -> client, per turn:
  {"type": "token", "text": "..."}                     raw deltas (chat bubble)
  {"type": "sentence", "turn", "i", "text", "emotion", "wav", "cues", "lead_s", "audio_s", "ms": {...}}
  {"type": "done", "turn", "user", "reply", "emotion", "facts", "ms": {...}, "sentences": [...]}
"""
import argparse, hashlib, http.client, json, os, queue, re, socket, socketserver, subprocess, threading, time, wave
from pathlib import Path
from urllib.parse import urlparse

KOKORO = Path(r"C:\AI\voice-lab-kokoro")
RHUBARB = Path(r"C:\AI\rhubarb-lip-sync-1.14.0\app\Rhubarb-Lip-Sync-1.14.0-Windows\rhubarb.exe")
EMOTIONS = ("happy", "curious", "thinking", "apologetic")
TAG = re.compile(r"\[\s*(%s)\s*\]" % "|".join(EMOTIONS), re.I)
REMEMBER = re.compile(r"\[\s*remember\s*:\s*([^\]]*)\]", re.I)
END = re.compile(r"[.!?\u2026]+[\"')\u201d\u2019]*(?=\s)")
SPEED = {"happy": 1.04, "curious": 1.0, "thinking": 0.96, "apologetic": 0.94}
MIN_CHARS = 14                                                              # shorter pieces wait for the next sentence
KEEP_LEAD, KEEP_TAIL = 0.04, 0.22                                           # seconds of silence kept around each sentence
FRAME = 600 / 24000                                                         # one Kokoro duration unit (hop 600 at 24 kHz)
VISEME_LEAD = 0.05             # pred_dur cues trail the audio envelope by 40-60 ms (6/6 bench sentences): shift them earlier
# Kokoro/misaki phoneme -> Rhubarb mouth shape (A closed MBP, B teeth/EE, C open EH/AE, D wide AA, E rounded AO/ER,
# F puckered UW/OW/W, G F/V, H L, X rest). Length marks and spaces keep the shape before them, stress marks take the
# next phoneme's (Kokoro gives the stress token real time at the vowel onset); punctuation rests.
SHAPES = {**dict.fromkeys("mbp", "A"), **dict.fromkeys("tdnkgɡszʃʒʤʧjhŋθðɹɾʔTiJ", "B"), **dict.fromkeys("ɛæəɪᵊeA", "C"),
          **dict.fromkeys("ɑaʌIW", "D"), **dict.fromkeys("ɔɜɝɚY", "E"), **dict.fromkeys("uʊwO", "F"),
          **dict.fromkeys("fv", "G"), "l": "H"}
KEEP, STRESS = set("ːʲ "), set("ˈˌ")


def phoneme_cues(phonemes, durations, offset=0.0):
    """Rhubarb-style mouthCues from Kokoro's phoneme string and pred_dur (BOS + one duration per phoneme + EOS)."""
    cues, t, shape = [], offset + durations[0] * FRAME, "X"
    for i, (ph, d) in enumerate(zip(phonemes, durations[1:-1])):
        if ph in STRESS: ph = next((q for q in phonemes[i + 1:] if q not in STRESS), " ")
        shape = shape if ph in KEEP else SHAPES.get(ph, "X")
        end = t + d * FRAME
        if end > t:
            if cues and cues[-1]["value"] == shape: cues[-1]["end"] = round(end, 3)
            else: cues.append({"start": round(t, 3), "end": round(end, 3), "value": shape})
        t = end
    return cues


class Splitter:
    """Feed streamed text; get back finished sentences with the mood in force and any [remember: ...] facts.
    Never cuts inside an open [tag]; a piece shorter than MIN_CHARS is held and joined to the next one."""

    def __init__(self, emotion="happy"):
        self.buf, self.held, self.emotion, self.facts = "", "", emotion, []

    def feed(self, text):
        self.buf += text; out = []
        while True:
            m = next((m for m in END.finditer(self.buf) if self.buf.count("[", 0, m.end()) <= self.buf.count("]", 0, m.end())), None)
            if not m: break
            piece, self.buf = self.buf[:m.end()], self.buf[m.end():]
            s = self._clean(piece)
            if s: out += self._hold(s)
        return out

    def flush(self):
        s = self._clean(self.buf); self.buf = ""
        s = " ".join(x for x in (self.held, s) if x); self.held = ""
        return [(s, self.emotion)] if s else []

    def _hold(self, s):
        s = " ".join(x for x in (self.held, s) if x)
        if len(s) < MIN_CHARS: self.held = s; return []
        self.held = ""; return [(s, self.emotion)]

    def _clean(self, piece):
        tags = TAG.findall(piece)
        if tags: self.emotion = tags[-1].lower()
        self.facts += [f.strip() for f in REMEMBER.findall(piece) if f.strip()]
        piece = REMEMBER.sub("", TAG.sub("", piece))
        piece = re.sub(r"\*[^*]*\*", "", piece).replace("*", "")         # stray stage directions are not spoken
        return re.sub(r"\s+", " ", piece).strip()


def leading_silence(samples, rate=24000, threshold=0.02):
    for i, v in enumerate(samples):
        if abs(v) > threshold: return i / rate
    return len(samples) / rate


def llm_stream(url, messages, **params):
    """Yield content deltas from llama-server's OpenAI-compatible streaming endpoint."""
    u = urlparse(url); conn = http.client.HTTPConnection(u.hostname, u.port, timeout=120)
    body = {"messages": messages, "stream": True, "temperature": 0.8, "top_p": 0.95, "max_tokens": 140,
            "chat_template_kwargs": {"enable_thinking": False}, **params}
    conn.request("POST", "/v1/chat/completions", json.dumps(body), {"Content-Type": "application/json"})
    r = conn.getresponse()
    if r.status != 200: body = r.read()[:300]; conn.close(); raise RuntimeError(f"llama-server {r.status}: {body!r}")
    for raw in r:
        line = raw.decode("utf-8").strip()
        if not line.startswith("data: ") or line == "data: [DONE]": continue
        for ch in json.loads(line[6:]).get("choices", []):
            text = (ch.get("delta") or {}).get("content")
            if text: yield text
    conn.close()


class Voice:
    """Kokoro (pinned offline bundle, CPU) loaded once, plus Rhubarb's phonetic recogniser per sentence."""

    def __init__(self, out_dir, kokoro=KOKORO, rhubarb=RHUBARB):
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HOME=str(Path(kokoro) / "hf-home"))
        import numpy, torch
        from kokoro import KPipeline
        from kokoro.model import KModel
        b = json.loads((Path(kokoro) / "bundle.json").read_text(encoding="utf-8"))
        for e in b["files"].values():
            if hashlib.sha256(Path(e["path"]).read_bytes()).hexdigest() != e["sha256"]: raise SystemExit("Kokoro bundle integrity failure")
        torch.set_num_threads(6); self.np = numpy
        model = KModel(repo_id=b["model_id"], config=b["files"]["config"]["path"], model=b["files"]["model"]["path"]).to("cpu").eval()
        self.pipe = KPipeline(lang_code="a", repo_id=b["model_id"], model=model, device="cpu")
        self.voice, self.out, self.rhubarb = b["files"]["voice"]["path"], Path(out_dir), Path(rhubarb)
        self.say("Hello.", self.out / "warmup.wav")                       # first call builds caches; keep it off the clock

    def say(self, text, path, speed=1.0):
        """Write the sentence as 24 kHz PCM16 with its silences trimmed; return (audio, phoneme mouthCues)."""
        chunks = list(self.pipe(text, voice=self.voice, speed=speed))
        audio = self.np.concatenate([c.audio.detach().cpu().numpy() for c in chunks]).astype(self.np.float32)
        lead = int(max(0.0, leading_silence(audio) - KEEP_LEAD) * 24000)    # Kokoro pads ~0.35 s up front: dead latency
        cues, at = [], -lead / 24000 - VISEME_LEAD
        for c in chunks:
            if c.pred_dur is not None: cues += phoneme_cues(c.phonemes, [int(x) for x in c.pred_dur], at)
            at += len(c.audio) / 24000
        tail = int(max(0.0, leading_silence(audio[::-1]) - KEEP_TAIL) * 24000)
        audio = audio[lead:len(audio) - tail]
        pcm = (self.np.clip(audio, -1, 1) * 32767).astype("<i2")
        with wave.open(str(path), "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm.tobytes())
        return audio, [c for c in cues if c["end"] > 0]

    def lipsync(self, path, text):
        dialog = Path(path).with_suffix(".txt"); dialog.write_text(text, encoding="utf-8")
        cues = Path(path).with_suffix(".cues.json")
        subprocess.run([str(self.rhubarb), "-q", "-f", "json", "-r", "phonetic", "-d", str(dialog), "-o", str(cues), str(path)],
                       capture_output=True, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return json.loads(cues.read_text(encoding="utf-8"))["mouthCues"]


class Brain:
    def __init__(self, llm, voice, run_dir, persona, memory, visemes="kokoro"):
        self.llm, self.voice, self.run, self.visemes = llm, voice, Path(run_dir), visemes
        self.persona, self.memory_path = Path(persona).read_text(encoding="utf-8").strip(), Path(memory)
        self.memory = json.loads(self.memory_path.read_text(encoding="utf-8")); self.history, self.turn = [], 0
        self.memory.setdefault("self", []); self.memory.setdefault("friend", [])

    def system(self):
        s = self.persona + "\n\nWhat you remember:\n" + "\n".join("- " + f for f in self.memory["self"])
        if self.memory["friend"]: s += "\nAbout your friend:\n" + "\n".join("- " + f for f in self.memory["friend"])
        return s

    def respond(self, text, send):
        t0 = time.perf_counter(); ms = lambda: round((time.perf_counter() - t0) * 1000)
        self.turn += 1; turn = self.turn
        messages = [{"role": "system", "content": self.system()}, *self.history[-12:], {"role": "user", "content": text}]
        sentences, split, raw, stamps = queue.Queue(), Splitter(), [], {}

        def produce():
            try:
                for delta in llm_stream(self.llm, messages):
                    stamps.setdefault("first_token", ms()); raw.append(delta); send({"type": "token", "text": delta})
                    for s in split.feed(delta): sentences.put((s, ms()))
                for s in split.flush(): sentences.put((s, ms()))
                stamps["llm_done"] = ms()
            except Exception as e: stamps["error"] = repr(e)
            sentences.put(None)

        threading.Thread(target=produce, daemon=True).start()
        i, out = 0, []
        while (item := sentences.get()) is not None:
            (s, emotion), t_split = item
            wav = self.run / f"t{turn:02d}-s{i}.wav"
            audio, cues = self.voice.say(s, wav, SPEED.get(emotion, 1.0)); t_tts = ms()
            if self.visemes == "rhubarb": cues = self.voice.lipsync(wav, s)
            t_lip = ms()
            ev = {"type": "sentence", "turn": turn, "i": i, "text": s, "emotion": emotion, "wav": str(wav), "cues": cues,
                  "lead_s": round(leading_silence(audio), 3), "audio_s": round(len(audio) / 24000, 3),
                  "ms": {"split": t_split, "tts": t_tts, "lipsync": t_lip}}
            send(ev); out.append(ev); i += 1
        reply = "".join(raw)
        if split.facts:
            self.memory["friend"] += [f for f in split.facts if f not in self.memory["friend"]]
            self.memory_path.write_text(json.dumps(self.memory, indent=2) + "\n", encoding="utf-8")
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        done = {"type": "done", "turn": turn, "user": text, "reply": reply, "emotion": split.emotion, "facts": split.facts,
                "ms": {**stamps, "total": ms()}, "sentences": [{k: e[k] for k in ("text", "emotion", "lead_s", "audio_s", "ms")} for e in out]}
        with (self.run / "turns.jsonl").open("a", encoding="utf-8") as f: f.write(json.dumps(done) + "\n")
        send(done)
        return done


def serve(args):
    run = Path(args.runs).resolve() / time.strftime("%Y%m%d-%H%M%S"); run.mkdir(parents=True)
    brain = Brain(args.llm, Voice(run, args.kokoro, args.rhubarb), run, args.persona, args.memory, visemes=args.visemes)
    lock = threading.Lock()

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            def send(ev):
                with lock: self.wfile.write((json.dumps(ev) + "\n").encode("utf-8")); self.wfile.flush()
            send({"type": "hello", "run": str(run)})
            for line in self.rfile:
                try: msg = json.loads(line)
                except ValueError: continue
                if msg.get("type") == "say" and str(msg.get("text", "")).strip(): brain.respond(str(msg["text"])[:500], send)

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), Handler) as srv:
        print(json.dumps({"ready": True, "port": args.port, "run": str(run)}), flush=True); srv.serve_forever()


def ask(args):
    s = socket.create_connection(("127.0.0.1", args.port)); f = s.makefile("rwb")
    json.loads(f.readline())
    for line in args.lines:
        t0 = time.perf_counter(); first = None; f.write((json.dumps({"type": "say", "text": line}) + "\n").encode()); f.flush()
        while (ev := json.loads(f.readline()))["type"] != "done":
            if ev["type"] == "sentence" and first is None: first = round((time.perf_counter() - t0) * 1000)
        print(json.dumps({"user": line, "reply": ev["reply"], "client_first_sentence_ms": first, **ev["ms"]}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("serve"); a.add_argument("--llm", default="http://127.0.0.1:8090"); a.add_argument("--port", type=int, default=8095)
    a.add_argument("--visemes", choices=("kokoro", "rhubarb"), default="kokoro")
    a.add_argument("--persona", required=True); a.add_argument("--memory", required=True)
    a.add_argument("--runs", default=".runtime/companion"); a.add_argument("--kokoro", default=str(KOKORO)); a.add_argument("--rhubarb", default=str(RHUBARB))
    b = sub.add_parser("ask"); b.add_argument("lines", nargs="+"); b.add_argument("--port", type=int, default=8095)
    args = p.parse_args(); serve(args) if args.cmd == "serve" else ask(args)
