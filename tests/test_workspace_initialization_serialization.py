"""Same-process Workspace initialization must not overlap SQLite setup."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_workflow import collection_commands
from test_workspace import workspace


class WorkspaceInitializationSerializationTests(unittest.TestCase):
    def test_second_constructor_waits_until_first_schema_migration_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_migrate = threading.Event()
            release_first = threading.Event()
            second_enable = threading.Event()
            second_ready = threading.Barrier(2)
            enable_count = 0
            count_lock = threading.Lock()
            original_enable = workspace.AssetWorkspace._enable_wal
            original_migrate = collection_commands.migrate

            def observed_enable(db):
                nonlocal enable_count
                with count_lock:
                    enable_count += 1
                    if enable_count == 2:
                        second_enable.set()
                return original_enable(db)

            def held_migrate(db):
                if not first_migrate.is_set():
                    first_migrate.set()
                    if not release_first.wait(5):
                        raise TimeoutError("First migration was not released")
                return original_migrate(db)

            results = []
            errors = []

            def construct():
                try:
                    results.append(workspace.AssetWorkspace(root).snapshot())
                except BaseException as exc:
                    errors.append(exc)

            def construct_second():
                second_ready.wait(timeout=5)
                construct()

            with patch.object(workspace.AssetWorkspace, "_enable_wal", side_effect=observed_enable), \
                 patch.object(collection_commands, "migrate", side_effect=held_migrate):
                first = threading.Thread(target=construct)
                second = threading.Thread(target=construct_second)
                first.start()
                try:
                    self.assertTrue(first_migrate.wait(5), "First constructor never reached migration")
                    second.start()
                    second_ready.wait(timeout=5)
                    self.assertFalse(
                        second_enable.wait(0.5),
                        "Second constructor entered WAL setup before first initialization finished",
                    )
                finally:
                    release_first.set()
                    first.join(5)
                    if second.ident is not None:
                        second.join(5)

            self.assertFalse(first.is_alive(), "First constructor did not finish")
            self.assertFalse(second.is_alive(), "Second constructor did not finish")
            self.assertEqual(errors, [])
            self.assertEqual(enable_count, 2)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
