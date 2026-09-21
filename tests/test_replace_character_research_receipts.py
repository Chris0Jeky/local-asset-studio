import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "experiments/curated/fantasy-pack-20260916"


def load_script(filename):
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location("test_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Clock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        self.value += 1.0
        return self.value


class ReplaceCharacterResearchReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.single = load_script("pack_replacechar.py")
        cls.chain = load_script("pack_replacechar_chain.py")

    def completed_history(self, prompt_id):
        return {prompt_id: {
            "status": {"status_str": "success", "messages": []},
            "outputs": {"13": {"images": [{"subfolder": "Research", "filename": "out.png"}]}}
        }}

    def test_single_batch_receipts_before_polling_and_terminal_rerun_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); results = root / "results.json"; graphs = root / "graphs"
            prompt_id = "a" * 36; prompt_calls = 0

            def opener(target, timeout):
                nonlocal prompt_calls
                url = getattr(target, "full_url", str(target))
                if url.endswith("/prompt"):
                    prompt_calls += 1
                    return io.BytesIO(json.dumps({"prompt_id": prompt_id}).encode())
                receipt = json.loads(results.read_text(encoding="utf-8"))
                self.assertEqual(receipt[0]["status"], "submitted")
                self.assertEqual(receipt[0]["prompt_id"], prompt_id)
                return io.BytesIO(json.dumps(self.completed_history(prompt_id)).encode())

            record = self.single.run(2026091301, results_path=results, graph_dir=graphs,
                                     open_url=opener, clock=Clock(), sleeper=lambda _: None)
            self.assertEqual(record["status"], "success")
            self.assertEqual(prompt_calls, 1)
            self.assertTrue((graphs / "pack-replacechar-2026091301.graph.json").is_file())
            self.assertEqual(len(json.loads(results.read_text(encoding="utf-8"))), 1)

            def forbidden(*_args, **_kwargs):
                raise AssertionError("a terminal seed must not contact ComfyUI")

            replay = self.single.run(2026091301, results_path=results, graph_dir=graphs,
                                     open_url=forbidden, clock=Clock(), sleeper=lambda _: None)
            self.assertEqual(replay["prompt_id"], prompt_id)
            self.assertEqual(prompt_calls, 1)

    def test_chain_graphs_use_the_documented_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); results = root / "results.json"; graphs = root / "research-graphs"
            prompt_id = "b" * 36

            def opener(target, timeout):
                url = getattr(target, "full_url", str(target))
                if url.endswith("/prompt"):
                    return io.BytesIO(json.dumps({"prompt_id": prompt_id}).encode())
                return io.BytesIO(json.dumps(self.completed_history(prompt_id)).encode())

            self.chain.run("cross", "scene.png", "character.png", 2026091321,
                           results_path=results, graph_dir=graphs,
                           open_url=opener, clock=Clock(), sleeper=lambda _: None)
            self.assertTrue((graphs / "pack-replacechar-cross-2026091321.graph.json").is_file())
            self.assertFalse((root / "pack-replacechar-cross-2026091321.graph.json").exists())

    def test_interrupted_chain_receipt_resumes_without_another_prompt(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); results = root / "results.json"; graphs = root / "graphs"
            prompt_id = "c" * 36
            results.write_text(json.dumps([{
                "group": "chain", "seed": 2026091311, "prompt_id": prompt_id,
                "status": "submitted", "submitted_at": 900.0,
                "image1": "staged.png", "image2": "portrait.png",
                "text": self.chain.TEXT["chain"], "lora": "replace_character_v1_klein.safetensors",
                "size": "832x1216"
            }]), encoding="utf-8")
            urls = []

            def opener(target, timeout):
                url = getattr(target, "full_url", str(target)); urls.append(url)
                self.assertNotEqual(url.rsplit("/", 1)[-1], "prompt")
                return io.BytesIO(json.dumps(self.completed_history(prompt_id)).encode())

            record = self.chain.run("chain", "ignored.png", "ignored.png", 2026091311,
                                    results_path=results, graph_dir=graphs,
                                    open_url=opener, clock=Clock(), sleeper=lambda _: None)
            self.assertEqual(record["status"], "success")
            self.assertEqual(urls, [self.chain.COMFY + "/history/" + prompt_id])
            self.assertEqual(len(json.loads(results.read_text(encoding="utf-8"))), 1)


if __name__ == "__main__":
    unittest.main()
