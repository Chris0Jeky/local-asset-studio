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
CLAUSE = re.compile(r"[,;:\u2014](?=\s)")
SPEED = {"happy": 1.04, "curious": 1.0, "thinking": 0.96, "apologetic": 0.94}
MIN_CHARS = 10                                                              # shorter pieces wait for the next sentence
FIRST_CLAUSE = 24              # the first piece may end at a comma once this long: Kokoro's time grows with length
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
    Never cuts inside an open [tag]; a piece shorter than MIN_CHARS is held and joined to the next one. Until the first
    piece is out, a clause of FIRST_CLAUSE characters ending at a comma also counts, so the first audio starts sooner."""

    def __init__(self, emotion="happy"):
        self.buf, self.held, self.emotion, self.facts, self.first = "", "", emotion, [], True

    def _cut(self):
        closed = lambda m: (self.buf.count("[", 0, m.end()) <= self.buf.count("]", 0, m.end())   # not inside a [tag]
                            and self.buf.count("*", 0, m.end()) % 2 == 0)                          # nor a *stage direction*
        ends = [m for m in END.finditer(self.buf) if closed(m)]
        if self.first:
            ends += [m for m in CLAUSE.finditer(self.buf) if closed(m) and len(TAG.sub("", self.held + self.buf[:m.end()]).strip()) >= FIRST_CLAUSE]
        return min(ends, key=lambda m: m.end(), default=None)

    def feed(self, text):
        self.buf += text; out = []
        while True:
            m = self._cut()
            if not m: break
            piece, self.buf = self.buf[:m.end()], self.buf[m.end():]
            s = self._clean(piece)
            if s: out += self._hold(s)
            if out: self.first = False
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


STOP = set("a an the and or but so to of in on at for with from into by as is are was were be been am i me my you your "
           "she her he his they them their it its this that has have had will would can could just very really about some "
           "all not new friend friends user don doesn didn isn aren wasn weren won couldn wouldn haven hasn".split())
RELATION = set("name named called likes like loves love enjoys enjoy favourite favorite wants want plans plan works work "
               "lives live feels feel prefers prefer".split())


NEGATION = re.compile(r"\b(not|no|never|nothing|nobody|cannot)\b|n't\b")
OWNED = re.compile(r"\b(?:my|his|her|their|our)\s+([a-z]+)")


def _stem(w): return re.sub(r"(ing|ed|es|s)$", "", w)[:5] if len(w) > 4 else w


def grounded(fact, said):
    """True when one message the user typed supports a [remember: fact]: it holds every content word of the fact
    (suffixes stripped, so moved/moving and harbour/harbor agree), has the same negation ("I don't love cats" never
    grounds "loves cats"), and whatever it says belongs to someone ("my sister", "his job") is in the fact too, so a
    friend's preference is not filed as the user's. Relation words ('name', 'likes', ...) need no support. Lexical:
    synonyms are rejected (the safe side)."""
    low = lambda t: re.sub(r"'s\b", "", t.lower())
    words = lambda t: [w for w in re.findall(r"[a-z0-9]+", low(t)) if w not in STOP and len(w) > 1]
    content = {_stem(w) for w in words(fact) if w not in RELATION}
    every = {_stem(w) for w in re.findall(r"[a-z0-9]+", low(fact))}
    neg = bool(NEGATION.search(low(fact)))
    for m in said:
        heard = {_stem(w) for w in words(m)}
        if content and content <= heard and bool(NEGATION.search(low(m))) == neg \
                and all(_stem(o) in every for o in OWNED.findall(low(m))): return True
    return False


def lock_memory(path):
    """Hold an exclusive OS lock on <memory>.lock for this process's life (released when it exits), so a second
    sidecar cannot load the same memory and overwrite the first one's updates."""
    f = open(str(path) + ".lock", "a+"); f.seek(0)
    try:
        if os.name == "nt": import msvcrt; msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else: import fcntl; fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: f.close(); raise SystemExit(f"{path} is in use by another companion sidecar")
    return f


class Brain:
    """One conversation. memory.json: {"self": [bible facts], "friend": [grounded facts], "recent": [last messages]};
    it survives restarts. scene: [{"id", "say", "aliases"}] objects around the character; a sentence naming one carries
    its id as "look"."""

    def __init__(self, llm, voice, run_dir, persona, memory, visemes="kokoro", scene=()):
        self.llm, self.voice, self.run, self.visemes, self.scene = llm, voice, Path(run_dir), visemes, list(scene)
        self.persona, self.memory_path = Path(persona).read_text(encoding="utf-8").strip(), Path(memory)
        self.memory = json.loads(self.memory_path.read_text(encoding="utf-8")); self.turn = 0
        for k in ("self", "friend", "recent"): self.memory.setdefault(k, [])
        self.history = list(self.memory["recent"])                          # pick the conversation up after a restart
        self.lock = threading.Lock()                                        # one turn at a time across all clients

    def system(self):
        s = self.persona + "\n\nWhat you remember:\n" + "\n".join("- " + f for f in self.memory["self"])
        if self.memory["friend"]: s += "\nAbout your friend:\n" + "\n".join("- " + f for f in self.memory["friend"])
        if self.scene: s += "\n\nAround you right now (mention them naturally when it fits):\n" + "\n".join("- " + o["say"] for o in self.scene)
        return s

    def look(self, sentence):
        low = sentence.lower()
        return next((o["id"] for o in self.scene if any(re.search(r"\b%s\b" % re.escape(a.lower()), low) for a in o["aliases"])), None)

    def respond(self, text, send):
        with self.lock: return self._respond(text, send)

    def _respond(self, text, send):
        t0 = time.perf_counter(); ms = lambda: round((time.perf_counter() - t0) * 1000)
        self.turn += 1; turn = self.turn
        if len(self.history) > 12: self.history = self.history[-6:]       # in blocks: a sliding window misses the prompt cache
        messages = [{"role": "system", "content": self.system()}, *self.history, {"role": "user", "content": text}]
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
        try:
            while (item := sentences.get()) is not None:
                (s, emotion), t_split = item
                wav = self.run / f"t{turn:02d}-s{i}.wav"
                audio, cues = self.voice.say(s, wav, SPEED.get(emotion, 1.0)); t_tts = ms()
                if self.visemes == "rhubarb": cues = self.voice.lipsync(wav, s)
                t_lip = ms()
                ev = {"type": "sentence", "turn": turn, "i": i, "text": s, "emotion": emotion, "wav": str(wav), "cues": cues,
                      "lead_s": round(leading_silence(audio), 3), "audio_s": round(len(audio) / 24000, 3), "look": self.look(s),
                      "ms": {"split": t_split, "tts": t_tts, "lipsync": t_lip}}
                send(ev); out.append(ev); i += 1
        except Exception as e:                                              # a voice failure still ends the turn with done
            stamps["error"] = repr(e)
            while sentences.get() is not None: pass                         # let the stream finish before done goes out
        reply = "".join(raw)
        said = [m["content"] for m in self.history if m["role"] == "user"][-3:] + [text]
        kept = [f for f in split.facts if grounded(f, said)][:2]              # only what the user actually said
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        self.memory["friend"] += [f for f in kept if f not in self.memory["friend"]]
        self.memory["recent"] = self.history[-6:]
        try:                                                                # persistence failing must not swallow done
            tmp = self.memory_path.with_name(f"{self.memory_path.name}.{os.getpid()}.tmp")   # never truncate the only copy
            tmp.write_text(json.dumps(self.memory, indent=2) + "\n", encoding="utf-8"); os.replace(tmp, self.memory_path)
        except OSError as e: stamps["save_error"] = repr(e)
        done = {"type": "done", "turn": turn, "user": text, "reply": reply, "emotion": split.emotion, "facts": kept,
                "rejected_facts": [f for f in split.facts if f not in kept],
                "ms": {**stamps, "total": ms()}, "sentences": [{k: e[k] for k in ("text", "emotion", "lead_s", "audio_s", "ms")} for e in out]}
        try:
            with (self.run / "turns.jsonl").open("a", encoding="utf-8") as f: f.write(json.dumps(done) + "\n")
        except OSError as e: done["ms"]["save_error"] = repr(e)
        send(done)
        return done


def serve(args):
    run = Path(args.runs).resolve() / time.strftime("%Y%m%d-%H%M%S"); run.mkdir(parents=True)
    held = lock_memory(args.memory)                                       # stays open: the lock lives as long as we do
    scene = json.loads(Path(args.scene).read_text(encoding="utf-8")) if args.scene else ()
    brain = Brain(args.llm, Voice(run, args.kokoro, args.rhubarb), run, args.persona, args.memory, visemes=args.visemes, scene=scene)
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
    a.add_argument("--persona", required=True); a.add_argument("--memory", required=True); a.add_argument("--scene")
    a.add_argument("--runs", default=".runtime/companion"); a.add_argument("--kokoro", default=str(KOKORO)); a.add_argument("--rhubarb", default=str(RHUBARB))
    b = sub.add_parser("ask"); b.add_argument("lines", nargs="+"); b.add_argument("--port", type=int, default=8095)
    args = p.parse_args(); serve(args) if args.cmd == "serve" else ask(args)
