"""Figure child rows stay bound to the Workspace assets row shape; no generation here."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('asset_workspace', Path(__file__).parents[1] / 'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(workspace)

from studio_workflow import addressable_figures as figures

LEFT_TO_WORKSPACE = frozenset(("tags", "favorite", "review", "notes", "trashed_at", "metadata_revision", "run_label", "prompt_excerpt"))


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


if __name__ == "__main__":
    unittest.main()
