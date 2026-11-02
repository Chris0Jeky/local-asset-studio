import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import time
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

    def test_first_piece_may_end_at_a_long_enough_clause(self):
        out, _ = self.feed_all("[happy] Oh, hello there, it is so lovely to see you, really. Come in, sit down.")
        self.assertEqual(out, [("Oh, hello there, it is so lovely to see you,", "happy"),   # "Oh," / "Oh, hello there," too short
                               ("really. Come in, sit down.", "happy")])                    # later commas never cut

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
        srv, url, seen = stub_llm([{"content": "[happy] Hello there, Ana! Nice to meet you. "}, {"content": "[curious] Do you sail? [remember: friend is Ana]"}])
        voice, events = FakeVoice(), []
        try:
            brain = cl.Brain(url, voice, self.tmp, self.tmp / "persona.md", self.tmp / "memory.json")
            done = brain.respond("Hi, I'm Ana", events.append)
            brain.respond("Again", events.append)
        finally: srv.shutdown(); srv.server_close()
        kinds = [e["type"] for e in events if e["type"] != "token"]
        self.assertEqual(kinds[:4], ["sentence", "sentence", "sentence", "done"])
        first = [e for e in events if e["type"] == "sentence"][:3]
        self.assertEqual([(e["text"], e["emotion"]) for e in first],
                         [("Hello there, Ana!", "happy"), ("Nice to meet you.", "happy"), ("Do you sail?", "curious")])
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

    def test_voice_failure_still_finishes_the_turn_after_the_stream(self):
        class Broken(FakeVoice):
            def say(self, text, path, speed=1.0): raise OSError("disk full")
        srv, url, _ = stub_llm([{"content": "[happy] One sentence here. "}, {"content": "Two sentences here."}])
        events = []
        try: done = cl.Brain(url, Broken(), self.tmp, self.tmp / "persona.md", self.tmp / "memory.json").respond("Hi", events.append)
        finally: srv.shutdown(); srv.server_close()
        self.assertIn("disk full", done["ms"]["error"]); self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(done["reply"], "[happy] One sentence here. Two sentences here.")   # the stream ran to its end first

    def test_storage_failures_still_send_done(self):
        srv, url, _ = stub_llm([{"content": "[happy] Lovely to meet you, Ana! [remember: friend is Ana]"}])
        events = []
        brain = cl.Brain(url, FakeVoice(), self.tmp, self.tmp / "persona.md", self.tmp / "memory.json")
        brain.run = self.tmp / "missing-run-dir"                                  # turns.jsonl append fails
        brain.memory_path = self.tmp / "no-such-dir" / "memory.json"               # memory save fails
        try: done = brain.respond("I'm Ana", events.append)
        finally: srv.shutdown(); srv.server_close()
        self.assertEqual(events[-1]["type"], "done"); self.assertIn("save_error", done["ms"])
        self.assertEqual(len(brain.history), 2)

    def test_concurrent_clients_take_turns(self):
        class Slow(FakeVoice):
            def say(self, text, path, speed=1.0): time.sleep(0.05); return super().say(text, path, speed)
        srv, url, seen = stub_llm([{"content": "[happy] Hello there, friend."}])
        brain = cl.Brain(url, Slow(), self.tmp, self.tmp / "persona.md", self.tmp / "memory.json")
        try:
            ts = [threading.Thread(target=brain.respond, args=(f"line {k}", lambda e: None)) for k in range(2)]
            for t in ts: t.start()
            for t in ts: t.join()
        finally: srv.shutdown(); srv.server_close()
        self.assertEqual(sorted(len(r["messages"]) for r in seen), [2, 4])            # the second turn saw the first one
        self.assertEqual([m["role"] for m in brain.history], ["user", "assistant", "user", "assistant"])

    def test_history_is_trimmed_in_blocks(self):
        srv, url, seen = stub_llm([{"content": "[happy] Sure thing, friend."}])
        brain = cl.Brain(url, FakeVoice(), self.tmp, self.tmp / "persona.md", self.tmp / "memory.json")
        try:
            for k in range(8): brain.respond(f"line {k}", lambda e: None)
        finally: srv.shutdown(); srv.server_close()
        self.assertEqual([len(r["messages"]) for r in seen], [2, 4, 6, 8, 10, 12, 14, 8])   # 12 kept, then cut to 6
        self.assertNotIn("[remember", "".join(m["content"] for m in seen[-1]["messages"]))


class StageDirectionTest(unittest.TestCase):
    def test_a_period_inside_asterisks_does_not_cut(self):
        s = cl.Splitter(); out = s.feed("This is a long sentence. *waves. Happily* Another sentence follows. ") + s.flush()
        self.assertEqual(out, [("This is a long sentence.", "happy"), ("Another sentence follows.", "happy")])


class GroundedFactTest(unittest.TestCase):
    # Real [remember] tags from the 2 Nov A/B (Gemma 4 12B and Qwen3.5-9B), against what the user had typed.
    def test_facts_the_user_said_are_kept(self):
        self.assertTrue(cl.grounded("Ana's name is Ana and she just moved to the town.", ["I'm Ana. I just moved to the harbour town."]))
        self.assertTrue(cl.grounded("her name is Ana", ["Hi Suzu!", "I'm Ana.", "Do you remember my name?"]))
        self.assertTrue(cl.grounded("friend is nervous about starting a new job tomorrow", ["I'm a bit nervous about starting my new job tomorrow."]))
        self.assertTrue(cl.grounded("loves the harbor at night", ["I love the harbour, especially at night."]))   # spelling, inflection

    def test_invented_facts_are_rejected(self):
        self.assertFalse(cl.grounded("her favourite colour is blue", ["What's your favourite colour?"]))   # Suzu's answer, not the user's
        self.assertFalse(cl.grounded("Ana wears blue socks", ["Thanks, Suzu. I should go now. See you tomorrow!"]))
        self.assertFalse(cl.grounded("her name is", ["I'm Ana."]))                                          # nothing to support


class MemoryAndSceneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "persona.md").write_text("You are Suzu.", encoding="utf-8")
        (self.tmp / "memory.json").write_text(json.dumps({"self": ["You map tide pools."]}), encoding="utf-8")

    def brain(self, url, **kw): return cl.Brain(url, FakeVoice(), self.tmp, self.tmp / "persona.md", self.tmp / "memory.json", **kw)

    def test_only_grounded_facts_are_stored_and_the_conversation_survives_a_restart(self):
        srv, url, seen = stub_llm([{"content": "[happy] Lovely to meet you, Ana! [remember: friend is Ana] [remember: her favourite colour is blue]"}])
        try:
            done = self.brain(url).respond("Hi, I'm Ana", lambda e: None)
            self.brain(url).respond("Still there?", lambda e: None)                   # a fresh process, same memory file
        finally: srv.shutdown(); srv.server_close()
        self.assertEqual((done["facts"], done["rejected_facts"]), (["friend is Ana"], ["her favourite colour is blue"]))
        mem = json.loads((self.tmp / "memory.json").read_text(encoding="utf-8"))
        self.assertEqual(mem["friend"], ["friend is Ana"]); self.assertEqual(mem["self"], ["You map tide pools."])
        self.assertEqual([m["content"] for m in seen[1]["messages"][1:3]], ["Hi, I'm Ana", done["reply"]])   # history reloaded
        self.assertEqual(len(mem["recent"]), 4)

    def test_scene_objects_reach_the_prompt_and_a_mention_carries_a_look(self):
        scene = [{"id": "window_glass", "say": "the big window over the harbour", "aliases": ["window", "harbour"]},
                 {"id": "stool", "say": "a little stool", "aliases": ["stool"]}]
        srv, url, seen = stub_llm([{"content": "[happy] Look out of the window at the boats! I love sketching here, really."}])
        events = []
        try: self.brain(url, scene=scene).respond("What can you see?", events.append)
        finally: srv.shutdown(); srv.server_close()
        self.assertIn("the big window over the harbour", seen[0]["messages"][0]["content"])
        self.assertEqual([e["look"] for e in events if e["type"] == "sentence"], ["window_glass", None])


if __name__ == "__main__":
    unittest.main()
