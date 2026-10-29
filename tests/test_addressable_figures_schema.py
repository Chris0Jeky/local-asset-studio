"""Figure child rows stay bound to the Workspace assets row shape; no generation here."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('asset_workspace', Path(__file__).parents[1] / 'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(workspace)

from studio_workflow import addressable_figures as figures
import test_addressable_figures as fixture

# New crop results are active work, even when their parent was deliberately archived.
# Leave archived_at NULL; do not copy the parent's independent organization state.
LEFT_TO_WORKSPACE = frozenset(("tags", "favorite", "review", "notes", "trashed_at", "archived_at", "metadata_revision", "run_label", "prompt_excerpt"))


class FigureChildSchemaTests(unittest.TestCase):
    def test_insert_columns_and_helpers_match_workspace(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        store = workspace.AssetWorkspace(Path(temp.name))
        with store.connection() as db:
            info = list(db.execute("PRAGMA table_info(assets)"))
        names = {row["name"] for row in info}
        for column in figures.ASSET_INSERT_COLUMNS:
            self.assertIn(column, names, f"figure child column {column!r} is not in Workspace assets")
        required = {row["name"] for row in info if row["notnull"] == 1 and row["dflt_value"] is None}
        self.assertTrue(required <= set(figures.ASSET_INSERT_COLUMNS),
                        f"figure children must set NOT NULL columns {sorted(required - set(figures.ASSET_INSERT_COLUMNS))}")
        leftover = names - set(figures.ASSET_INSERT_COLUMNS)
        self.assertEqual(leftover, set(LEFT_TO_WORKSPACE),
                         f"assets columns left to Workspace defaults changed to {sorted(leftover)}; decide whether figure children must set the new column")
        for helper in figures.WORKSPACE_HELPERS:
            self.assertTrue(callable(getattr(workspace.AssetWorkspace, helper, None)),
                            f"Workspace helper {helper!r} is missing or not callable")


    def test_cropped_children_start_active_without_unarchiving_the_parent(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); store = workspace.AssetWorkspace(root)
        parent, source = fixture.register_sheet(store, root)
        identity = store.snapshot()["workspace_id"]
        original = source.read_bytes()
        store.update({"workspace_id": identity, "ids": [parent], "action": "archive",
                      "request_id": "archive-before-figure-crop", "expected_revisions": {parent: 0}})
        before = store.get(parent)
        result = figures.split_figures(store, {
            "workspace_id": identity, "asset_id": parent,
            "request_id": "crop-from-archived-parent", "parent_sha256": before["sha256"],
            "rectangles": [{"x": 0, "y": 0, "width": 5000, "height": 10000}],
            "require_non_overlapping": True,
        })
        self.assertEqual(store.get(parent), before, "Derivation does not change the parent's Archive state")
        self.assertEqual(source.read_bytes(), original)
        child = store.get(result["created"][0])
        self.assertIsNone(child["archived_at"])
        self.assertEqual(child["metadata_revision"], 0)
        self.assertEqual(child["lineage"], [parent])
        self.assertEqual([row["id"] for row in store.asset_page()["assets"]], [child["id"]])
        self.assertEqual([row["id"] for row in store.asset_page(filters={"archive": "archived"})["assets"]], [parent])
        self.assertFalse(result["generation_submitted"])


if __name__ == "__main__":
    unittest.main()
