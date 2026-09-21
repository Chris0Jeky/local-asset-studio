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
        for slot in (True, False, 1.0):
            with self.subTest(slot=slot):
                changed = copy.deepcopy(graph)
                changed[node_id]["inputs"][field] = [value[0], slot]
                with self.assertRaisesRegex(
                    AssertionError,
                    rf"{preset_id}.*{node_id}.*{field}.*output slot.*integer",
                ):
                    _run_validator({graph_path: json.dumps(changed)})
        changed[node_id]["inputs"][field] = [value[0], 0]
        _run_validator({graph_path: json.dumps(changed)})
        changed[node_id]["inputs"][field] = ["unknown-source", False]
        with self.assertRaisesRegex(AssertionError, "output slot.*integer"):
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
        for value in (True, False, 0, 1.0):
            with self.subTest(value=value):
                asset["bytes"] = value
                with self.assertRaisesRegex(
                    AssertionError,
                    rf"{asset['id']}.*bytes.*positive integer",
                ):
                    _run_validator({LIBRARY: json.dumps(library)})
        asset["bytes"] = 1
        _run_validator({LIBRARY: json.dumps(library)})

    def test_i2v_mode_dimensions_reject_aliases_on_permissive_grid(self):
        for key, value in (("width", True), ("height", False), ("height", 1.0)):
            with self.subTest(key=key, value=value):
                document = _read_json(CATALOG)
                preset = next(p for p in document["presets"] if p.get("i2v_modes"))
                preset["dimension_limits"] = [0, 1_000_000]
                preset["dimension_multiple"] = 1
                mode = preset["i2v_modes"][0]
                mode["controls"][key] = value
                with self.assertRaisesRegex(AssertionError, rf"{preset['id']}.*i2v mode.*{key}.*integer"):
                    _run_validator({CATALOG: json.dumps(document)})

    def test_recipe_dimensions_reject_aliases_on_permissive_grid(self):
        path = ROOT / "presets" / "recipes.json"
        for key, value in (("width", True), ("height", False), ("width", 1.0)):
            with self.subTest(key=key, value=value):
                document = _read_json(CATALOG)
                recipes = _read_json(path)
                recipe = next(r for r in recipes["recipes"] if "width" in r.get("controls", {}))
                preset = next(p for p in document["presets"] if p["id"] == recipe["preset_id"])
                preset["dimension_limits"] = [0, 1_000_000]
                preset["dimension_multiple"] = 1
                recipe["controls"][key] = value
                with self.assertRaisesRegex(AssertionError, rf"{recipe['id']}.*{key}.*integer"):
                    _run_validator({CATALOG: json.dumps(document), path: json.dumps(recipes)})

    def test_local_media_byte_counts_require_positive_exact_integers(self):
        path = ROOT / "examples" / "nsfw-lab" / "MANIFEST.json"
        document = _read_json(path)
        entry = document["entries"][0]
        for value in (True, False, 0, 1.0):
            with self.subTest(value=value):
                entry["bytes"] = value
                with self.assertRaisesRegex(AssertionError, rf"nsfw-lab.*{entry['file']}.*positive integer"):
                    _run_validator({path: json.dumps(document)})
        entry["bytes"] = 1
        _run_validator({path: json.dumps(document)})

    def test_local_media_schema_version_requires_integer_one(self):
        path = ROOT / "examples" / "nsfw-lab" / "MANIFEST.json"
        document = _read_json(path)
        for value in (True, False, 1.0):
            with self.subTest(value=value):
                document["version"] = value
                with self.assertRaisesRegex(AssertionError, "nsfw-lab.*integer version 1"):
                    _run_validator({path: json.dumps(document)})


if __name__ == "__main__":
    unittest.main()
