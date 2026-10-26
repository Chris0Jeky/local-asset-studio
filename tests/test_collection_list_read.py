"""Bounded collection observations and Library records, without media or model calls."""

import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from workspace import AssetWorkspace, WorkspaceError
from studio_workflow import collection_http


class CollectionListReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AssetWorkspace(Path(self.temp.name))
        self.scope = self.store.asset_page()["workspace_id"]
        with self.store.connection() as db:
            db.executemany(
                "INSERT INTO collections (id,name,description,created_at) VALUES (?,?,?,0)",
                [
                    (f"col-{i:03}", "Same name", "Keep this description")
                    for i in range(105)
                ],
            )

    def test_page_is_bounded_stable_and_read_only(self):
        before = self.store.snapshot()
        statements = []
        original = self.store.connection
        from contextlib import contextmanager

        @contextmanager
        def traced():
            with original() as db:
                db.set_trace_callback(statements.append)
                yield db

        with (
            patch.object(
                self.store, "snapshot", side_effect=AssertionError("Unbounded snapshot")
            ),
            patch.object(self.store, "connection", traced),
        ):
            first = self.store.collection_page(limit=100)
            second = self.store.collection_page(limit=100, cursor=first["next_cursor"])
        self.assertEqual(first["format"], "studio.collection-page/v1")
        self.assertEqual(first["workspace_id"], self.scope)
        self.assertEqual(first["limit"], 100)
        self.assertEqual(len(first["collections"]), 100)
        self.assertEqual(
            [c["id"] for c in second["collections"]],
            [f"col-{i:03}" for i in range(100, 105)],
        )
        self.assertIsNone(second["next_cursor"])
        self.assertTrue(first["observation_only"])
        self.assertFalse(first["generation_submitted"])
        self.assertEqual(
            first["collections"][0],
            {
                "id": "col-000",
                "name": "Same name",
                "description": "Keep this description",
                "revision": 1,
                "count": 0,
            },
        )
        queries = [
            s.upper() for s in statements if "FROM COLLECTIONS AS C" in s.upper()
        ]
        self.assertEqual(len(queries), 2)
        self.assertTrue(all("ORDER BY C.NAME COLLATE NOCASE,C.ID" in s and "LIMIT 101" in s for s in queries))
        self.assertEqual(before, self.store.snapshot())

    def test_pages_follow_name_order_with_an_id_tiebreak_across_cursors(self):
        with self.store.connection() as db:
            db.execute("DELETE FROM collections")
            db.executemany(
                "INSERT INTO collections (id,name,description,created_at) VALUES (?,?,?,0)",
                [("col-1", "banana", ""), ("col-2", "Apple", ""), ("col-3", "cherry", ""),
                 ("col-4", "apple", ""), ("col-5", "Banana", ""), ("col-6", "Date", "")],
            )
        expected = ["col-2", "col-4", "col-1", "col-5", "col-3", "col-6"]  # name NOCASE, then id
        seen, cursor = [], None
        while True:
            page = self.store.collection_page(limit=2, cursor=cursor)
            self.assertEqual(page["order"], "name_nocase_asc_id_asc")
            seen += [c["id"] for c in page["collections"]]
            cursor = page["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(seen, expected)
        self.assertEqual([c["id"] for c in self.store.collection_page(limit=100)["collections"]], expected)

    def test_count_excludes_trash_including_timestamp_zero(self):
        source = Path(self.temp.name) / "image.png"
        source.write_bytes(b"image")
        ids = [
            self.store.register(
                {"id": f"job-{i}", "outputs": [{"filename": "image.png"}]}, 0, source
            )
            for i in range(3)
        ]
        with self.store.connection() as db:
            db.executemany(
                "INSERT INTO collection_assets VALUES (?,?)",
                [("col-000", i) for i in ids],
            )
            db.execute("UPDATE assets SET trashed_at=0 WHERE id=?", (ids[1],))
            db.execute("UPDATE assets SET trashed_at=42 WHERE id=?", (ids[2],))
        self.assertEqual(
            self.store.collection_page(limit=1)["collections"][0]["count"], 1
        )

    def test_bad_limits_cursors_scope_and_mutations_refuse_continuation(self):
        for limit in (0, 101, True, "1", 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.store.collection_page(limit=limit)
        page = self.store.collection_page(limit=1)
        cases = [
            ({"limit": 2, "cursor": page["next_cursor"]}, "collection_cursor_mismatch"),
            ({"workspace_id": "b" * 32}, "asset_workspace_conflict"),
            ({"cursor": "bad"}, "collection_cursor_invalid"),
        ]
        for query, code in cases:
            with self.subTest(code=code), self.assertRaises(ValueError) as caught:
                self.store.collection_page(**query)
            self.assertEqual(caught.exception.code, code)
        raw = json.loads(
            base64.urlsafe_b64decode(
                page["next_cursor"] + "=" * ((-len(page["next_cursor"])) % 4)
            )
        )
        raw["position"]["last"] = "col-099"
        tampered = (
            base64.urlsafe_b64encode(json.dumps(raw).encode()).decode().rstrip("=")
        )
        with self.assertRaises(ValueError):
            self.store.collection_page(limit=1, cursor=tampered)
        with self.store.connection() as db:
            db.execute("UPDATE collections SET name='Changed' WHERE id='col-000'")
        with self.assertRaises(ValueError) as caught:
            self.store.collection_page(limit=1, cursor=page["next_cursor"])
        self.assertEqual(caught.exception.code, "collection_cursor_stale")

    def test_http_get_and_query_validation_do_not_change_status_or_writes(self):
        class Base:
            def _safe_host(self):
                return True

            def _json(self, status, value):
                return status, value

        handler = collection_http.extend_handler(Base)()
        handler.studio = SimpleNamespace(assets=self.store)
        handler.path = "/api/collections?limit=2&workspace_id=" + self.scope
        status, page = handler.do_GET()
        self.assertEqual(status, 200)
        self.assertEqual(len(page["collections"]), 2)
        for query in (
            "limit=0",
            "limit=101",
            "limit=true",
            "limit=1&limit=2",
            "unknown=x",
            "cursor=",
            "limit=%FF",
            "limit=%GG",
            "limit",
            "cursor=" + "a" * 4097,
        ):
            handler.path = "/api/collections?" + query
            status, result = handler.do_GET()
            self.assertEqual(status, 400, query[:60])
            self.assertTrue(result["observation_only"])
        handler.path = "/api/collections?limit=1"
        with patch.object(
            self.store,
            "collection_page",
            side_effect=__import__("sqlite3").OperationalError("private SQL"),
        ):
            status, result = handler.do_GET()
        self.assertEqual(status, 503)
        self.assertNotIn("private", json.dumps(result))
        handler._safe_host = lambda: False
        self.assertEqual(handler.do_GET()[0], 403)

    def test_opt_in_library_projection_and_explicit_selection_preserve_metadata(self):
        source = Path(self.temp.name) / "image.png"
        source.write_bytes(b"image")
        key = self.store.register(
            {
                "id": "job",
                "run_label": "Agent lab",
                "outputs": [{"filename": "image.png"}],
            },
            0,
            source,
        )
        with self.store.connection() as db:
            db.execute("INSERT INTO collection_assets VALUES (?,?)", ("col-000", key))
            db.execute(
                "UPDATE assets SET notes='kept notes',tags='[\"face\"]' WHERE id=?",
                (key,),
            )
        summary = self.store.asset_page()["assets"][0]
        self.assertNotIn("notes", summary)
        page = self.store.asset_page(details=True)
        asset = page["assets"][0]
        self.assertEqual(asset["notes"], "kept notes")
        self.assertEqual(asset["tags"], ["face"])
        self.assertEqual(asset["collections"], ["col-000"])
        self.assertEqual(asset["workspace_id"], self.scope)
        selected = self.store.asset_selection(
            [key, "missing"], workspace_id=self.scope, details=True
        )
        self.assertEqual([i["state"] for i in selected["items"]], ["active", "missing"])
        self.assertEqual(selected["items"][0]["asset"]["source"], asset["source"])
        with self.store.connection() as db:
            db.execute("UPDATE assets SET source=? WHERE id=?", ("x" * 1000000, key))
        page = self.store.asset_page(details=True)
        self.assertEqual(page['assets'], [])
        self.assertEqual([item['id'] for item in page['unavailable_assets']], [key])
        self.assertEqual(page['unavailable_assets'][0]['code'], 'asset_read_unavailable')
        with self.assertRaises(WorkspaceError):
            self.store.asset_selection([key], workspace_id=self.scope, details=True)


if __name__ == "__main__":
    unittest.main()
