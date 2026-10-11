"""Pinning tests for Studio.prune_disabled_loras zero-strength bypass."""
import unittest

from app.server import Studio, StudioError


def three_node_graph(sampler_model_link):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
        "2": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"model": ["1", 0], "lora_name": "slot.safetensors", "strength_model": 0},
        },
        "3": {"class_type": "KSampler", "inputs": {"model": sampler_model_link, "seed": 1, "steps": 5}},
    }


class PruneLorasTests(unittest.TestCase):
    def test_zero_strength_loader_removed_and_rewired(self):
        graph = three_node_graph(["2", 0])
        Studio.prune_disabled_loras(None, graph)
        self.assertNotIn("2", graph)
        self.assertEqual(graph["3"]["inputs"]["model"], ["1", 0])

    def test_impossible_bypass_raises(self):
        graph = three_node_graph(["2", 1])
        with self.assertRaises(StudioError):
            Studio.prune_disabled_loras(None, graph)


if __name__ == "__main__":
    unittest.main()
