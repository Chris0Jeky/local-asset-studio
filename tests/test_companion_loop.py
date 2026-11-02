import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import companion_loop as cl


def stub_llm(deltas, status=200):
    """Loopback stand-in for llama-server's streaming chat endpoint; records each request body."""
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(status); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            if status != 200: self.wfile.write(b"boom"); return
            for d in deltas:
                self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": d}]}).encode() + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n")

        def log_message(self, *a): pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}", seen


class FakeVoice:
    def __init__(self): self.said, self.lipsynced = [], []
    def say(self, text, path, speed=1.0):
        self.said.append((text, speed)); return [0.0] * 240 + [0.5] * 2400, [{"start": 0.0, "end": 0.1, "value": "D"}]
    def lipsync(self, path, text): self.lipsynced.append(text); return [{"start": 0.0, "end": 0.1, "value": "B"}]


class SplitterTest(unittest.TestCase):
    def feed_all(self, text, step=1):
        s = cl.Splitter(); out = []
        for i in range(0, len(text), step): out += s.feed(text[i:i + step])
        return out + s.flush(), s

    def test_streamed_sentences_carry_mood_and_facts(self):
        out, s = self.feed_all("[curious] Oh! A visitor? I was just inking the cove. Do you like starfish? [remember: friend is Ana]")
        self.assertEqual(out, [("Oh! A visitor?", "curious"), ("I was just inking the cove.", "curious"), ("Do you like starfish?", "curious")])
        self.assertEqual(s.facts, ["friend is Ana"])

    def test_mood_changes_mid_reply_and_short_pieces_join_the_next(self):
        out, _ = self.feed_all("[happy] Yes! That's lovely. [apologetic] But sorry, I can't come today.", step=3)
        self.assertEqual(out, [("Yes! That's lovely.", "happy"), ("But sorry, I can't come today.", "apologetic")])

    def test_never_cuts_inside_an_open_tag_and_drops_stage_directions(self):
        s = cl.Splitter()
        self.assertEqual(s.feed("Sure. [remember: likes tea. "), [])                  # "Sure." held (short), tag still open
        self.assertEqual(s.feed("And cake] *waves* See you at the pier tomorrow! "), [("Sure. See you at the pier tomorrow!", "happy")])
        self.assertEqual(s.facts, ["likes tea. And cake"])

    def test_flush_emits_a_short_tail(self):
        out, _ = self.feed_all("[thinking] Hmm")
        self.assertEqual(out, [("Hmm", "thinking")])


class PhonemeCuesTest(unittest.TestCase):
    def test_shapes_timing_stress_lookahead_and_merging(self):
        # "ˈO, mˈæp": BOS 2 frames, then one duration per phoneme, EOS
        cues = cl.phoneme_cues("ˈO, mˈæp", [2, 3, 4, 1, 1, 2, 3, 1, 4, 2])
        f = cl.FRAME
        self.assertEqual([c["value"] for c in cues], ["F", "X", "A", "C", "A"])
        self.assertAlmostEqual(cues[0]["start"], 2 * f, places=3)                     # the stress mark takes O's shape
        self.assertAlmostEqual(cues[0]["end"], 9 * f, places=3)
        self.assertAlmostEqual(cues[1]["end"], 11 * f, places=3)                      # "," rests; the space keeps it
        self.assertAlmostEqual(cues[-1]["end"], 21 * f, places=3)

    def test_offset_shifts_every_cue_and_zero_durations_vanish(self):
        cues = cl.phoneme_cues("ab", [1, 0, 2, 1], offset=-0.5)
        self.assertEqual(cues, [{"start": round(-0.5 + cl.FRAME, 3), "end": round(-0.5 + 3 * cl.FRAME, 3), "value": "A"}])


class LlmStreamTest(unittest.TestCase):
    def test_yields_content_only_and_disables_thinking(self):
        srv, url, seen = stub_llm([{"reasoning_content": "secret"}, {"content": "[happy] Hi"}, {}, {"content": " there."}])
        try: self.assertEqual("".join(cl.llm_stream(url, [{"role": "user", "content": "hey"}])), "[happy] Hi there.")
        finally: srv.shutdown(); srv.server_close()
        self.assertTrue(seen[0]["stream"]); self.assertFalse(seen[0]["chat_template_kwargs"]["enable_thinking"])

    def test_non_200_raises(self):
        srv, url, _ = stub_llm([], status=503)
        try:
            with self.assertRaises(RuntimeError): list(cl.llm_stream(url, []))
        finally: srv.shutdown(); srv.server_close()


class BrainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "persona.md").write_text("You are Suzu.", encoding="utf-8")
        (self.tmp / "memory.json").write_text(json.dumps({"self": ["You map tide pools."]}), encoding="utf-8")

    def test_sentences_stream_before_done_and_facts_persist(self):
        srv, url, seen = stub_llm([{"content": "[happy] Hello, Ana! Nice to meet you. "}, {"content": "[curious] Do you sail? [remember: friend is Ana]"}])
        voice, events = FakeVoice(), []
        try:
            brain = cl.Brain(url, voice, self.tmp, self.tmp / "persona.md", self.tmp / "memory.json")
            done = brain.respond("Hi, I'm Ana", events.append)
            brain.respond("Again", events.append)
        finally: srv.shutdown(); srv.server_close()
        kinds = [e["type"] for e in events if e["type"] != "token"]
        self.assertEqual(kinds[:3], ["sentence", "sentence", "done"])
        first = [e for e in events if e["type"] == "sentence"][:2]
        self.assertEqual([(e["text"], e["emotion"]) for e in first], [("Hello, Ana! Nice to meet you.", "happy"), ("Do you sail?", "curious")])
        self.assertEqual(first[0]["cues"][0]["value"], "D"); self.assertEqual(voice.lipsynced, [])   # Kokoro cues, no Rhubarb
        self.assertEqual(first[0]["lead_s"], 0.01); self.assertEqual(first[0]["audio_s"], 0.11)
        self.assertEqual(voice.said[0][1], cl.SPEED["happy"])
        self.assertEqual(done["facts"], ["friend is Ana"])
        self.assertEqual(json.loads((self.tmp / "memory.json").read_text(encoding="utf-8"))["friend"], ["friend is Ana"])
        system = seen[1]["messages"][0]["content"]                                      # the second turn sees memory and history
        self.assertIn("You map tide pools.", system); self.assertIn("friend is Ana", system)
        self.assertEqual([m["role"] for m in seen[1]["messages"]], ["system", "user", "assistant", "user"])
        self.assertEqual(len((self.tmp / "turns.jsonl").read_text(encoding="utf-8").splitlines()), 2)

    def test_rhubarb_mode_replaces_the_cues(self):
        srv, url, _ = stub_llm([{"content": "[thinking] Let me check the chart."}])
        voice, events = FakeVoice(), []
        try: cl.Brain(url, voice, self.tmp, self.tmp / "persona.md", self.tmp / "memory.json", visemes="rhubarb").respond("Tide?", events.append)
        finally: srv.shutdown(); srv.server_close()
        self.assertEqual([e["cues"][0]["value"] for e in events if e["type"] == "sentence"], ["B"])

    def test_llm_failure_still_finishes_the_turn(self):
        srv, url, _ = stub_llm([], status=500)
        events = []
        try: done = cl.Brain(url, FakeVoice(), self.tmp, self.tmp / "persona.md", self.tmp / "memory.json").respond("Hi", events.append)
        finally: srv.shutdown(); srv.server_close()
        self.assertIn("error", done["ms"]); self.assertEqual(events[-1]["type"], "done")


if __name__ == "__main__":
    unittest.main()
