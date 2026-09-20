"""Production-path contracts for exact integer repository metadata."""
import contextlib
import copy
import io
import json
import runpy
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-repo.py"
CATALOG = ROOT / "presets" / "catalog.json"
LIBRARY = ROOT / "models" / "library.json"
_REAL_READ_TEXT = Path.read_text


def _read_json(path):
    return json.loads(_REAL_READ_TEXT(path, encoding="utf-8"))


def _run_validator(overrides=None):
    replacements = {
        Path(path).resolve(): content for path, content in (overrides or {}).items()
    }

    def read_text(candidate, *args, **kwargs):
        replacement = replacements.get(Path(candidate).resolve())
        if replacement is not None:
            return replacement
        return _REAL_READ_TEXT(candidate, *args, **kwargs)

    with mock.patch.object(
        Path,
        "read_text",
        autospec=True,
        side_effect=read_text,
    ), contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(
            str(VALIDATOR),
            run_name="__repo_validator_integer_contract__",
        )


class ExactIntegerPayloadTests(unittest.TestCase):
    def test_current_repository_payload_still_validates(self):
        _run_validator()

    def test_graph_output_slot_rejects_boolean_alias(self):
        catalog = _read_json(CATALOG)["presets"]
        selected = None
        for preset in catalog:
            graph_path = (ROOT / preset["graph"]).resolve()
            graph = _read_json(graph_path)
            for node_id, node in graph.items():
                for field, value in node.get("inputs", {}).items():
                    if (
                        isinstance(value, list)
                        and len(value) == 2
                        and value[0] in graph
                        and type(value[1]) is int
                    ):
                        selected = (preset["id"], graph_path, graph, node_id, field, value)
                        break
                if selected:
                    break
            if selected:
                break
        self.assertIsNotNone(selected, "fixture needs one real graph connection")
        preset_id, graph_path, graph, node_id, field, value = selected
        changed = copy.deepcopy(graph)
        changed[node_id]["inputs"][field] = [value[0], True]

        with self.assertRaisesRegex(
            AssertionError,
            rf"{preset_id}.*{node_id}.*{field}.*output slot.*integer",
        ):
            _run_validator({graph_path: json.dumps(changed)})

    def test_variant_dimension_rejects_boolean_alias_even_on_permissive_grid(self):
        document = _read_json(CATALOG)
        selected = next(
            preset for preset in document["presets"] if preset.get("width")
        )
        selected["dimension_limits"] = [0, 1_000_000]
        selected["dimension_multiple"] = 1
        selected.setdefault("variants", []).append(
            {
                "name": "boolean-width-fixture",
                "controls": {"width": True},
            }
        )

        with self.assertRaisesRegex(
            AssertionError,
            rf"{selected['id']}.*boolean-width-fixture.*width.*integer",
        ):
            _run_validator({CATALOG: json.dumps(document)})

    def test_asset_byte_count_rejects_boolean_alias(self):
        library = _read_json(LIBRARY)
        self.assertTrue(library["assets"], "fixture needs one real pinned asset")
        asset = library["assets"][0]
        asset["bytes"] = True

        with self.assertRaisesRegex(
            AssertionError,
            rf"{asset['id']}.*bytes.*positive integer",
        ):
            _run_validator({LIBRARY: json.dumps(library)})


if __name__ == "__main__":
    unittest.main()
