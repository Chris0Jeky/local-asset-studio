"""Real SQLite contention at the journal-mode boundary, never a Studio runtime."""
import concurrent.futures
from contextlib import closing
import multiprocessing
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_workspace import workspace


CONNECT = sqlite3.connect


def initialize_process(root, gate, queue):
    try:
        queue.put({'ready': True})
        if not gate.wait(10):
            raise TimeoutError('Constructor gate not released')
        store = workspace.AssetWorkspace(root)
        with store.connection() as db:
            queue.put({'mode': db.execute('PRAGMA journal_mode').fetchone()[0],
                       'columns': [r['name'] for r in db.execute('PRAGMA table_info(assets)')]})
    except BaseException as exc:
        queue.put({'error': repr(exc)})


class WorkspaceInitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / 'workspace' / 'assets.sqlite3'
        self.database.parent.mkdir()

    def rollback_database(self):
        db = CONNECT(self.database)
        db.execute('CREATE TABLE sentinel (value TEXT)')
        db.execute("INSERT INTO sentinel VALUES ('preserve me')")
        db.commit()
        return db

    def observe_connections(self, busy_seen, calls, *, readonly=False):
        class ObservedConnection(sqlite3.Connection):
            def execute(self, sql, *args):
                if 'journal_mode' in sql.lower():
                    calls.append(sql)
                try:
                    return super().execute(sql, *args)
                except sqlite3.OperationalError as exc:
                    if getattr(exc, 'sqlite_errorcode', None) == sqlite3.SQLITE_BUSY:
                        busy_seen.set()
                    raise

            def executescript(self, sql):
                if 'journal_mode' in sql.lower():
                    calls.append(sql)
                try:
                    return super().executescript(sql)
                except sqlite3.OperationalError as exc:
                    if getattr(exc, 'sqlite_errorcode', None) == sqlite3.SQLITE_BUSY:
                        busy_seen.set()
                    raise

        def connect(path, **kwargs):
            # Real short SQLite wait exposes the same early-busy class as a WAL
            # lock upgrade that bypasses the busy handler. No exception is invented.
            kwargs.update(timeout=0.02, factory=ObservedConnection)
            if readonly:
                return CONNECT(Path(path).as_uri() + '?mode=ro', uri=True, **kwargs)
            return CONNECT(path, **kwargs)
        return connect

    def test_real_wal_busy_waits_for_reader_then_initializes(self):
        holder = self.rollback_database()
        holder.execute('BEGIN')
        holder.execute('SELECT * FROM sentinel').fetchall()
        busy, calls = threading.Event(), []
        errors = []
        def construct():
            try:
                workspace.AssetWorkspace(self.root)
            except BaseException as exc:
                errors.append(exc)
        try:
            with patch.object(workspace.sqlite3, 'connect', self.observe_connections(busy, calls)):
                thread = threading.Thread(target=construct)
                thread.start()
                observed = busy.wait(3)
                holder.rollback(); holder.close(); holder = None
                thread.join(5)
                self.assertFalse(thread.is_alive(), 'Initialization did not finish after releasing the reader')
            self.assertTrue(observed, 'Fixture never caused a real SQLITE_BUSY')
            self.assertEqual(errors, [], 'Transient WAL contention must not reject a legitimate client')
            self.assertGreaterEqual(len(calls), 2)
            store = workspace.AssetWorkspace(self.root)
            with store.connection() as db:
                self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
                self.assertEqual(db.execute('SELECT value FROM sentinel').fetchone()[0], 'preserve me')
        finally:
            if holder is not None:
                holder.close()

    def test_real_lock_timeout_is_bounded_and_retryable_on_later_open(self):
        holder = self.rollback_database()
        holder.execute('BEGIN'); holder.execute('SELECT * FROM sentinel').fetchall()
        busy, calls = threading.Event(), []
        try:
            with patch.object(workspace, 'WAL_INITIALIZATION_TIMEOUT', 0.15, create=True), \
                 patch.object(workspace.sqlite3, 'connect', self.observe_connections(busy, calls)):
                started = time.monotonic()
                with self.assertRaises(sqlite3.OperationalError) as caught:
                    workspace.AssetWorkspace(self.root)
                elapsed = time.monotonic() - started
            self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_BUSY)
            self.assertGreaterEqual(elapsed, 0.10, 'Rejected before allowing bounded recovery')
            self.assertLess(elapsed, 2.0, 'Busy handling exceeded its bounded test deadline')
            self.assertGreaterEqual(len(calls), 2)
        finally:
            holder.close()
        self.assertEqual(workspace.AssetWorkspace(self.root).snapshot()['assets'], [])

    def test_parallel_threads_and_reopen_share_one_schema(self):
        for fresh in (True, False):
            gate = threading.Barrier(6)
            def construct(_):
                gate.wait(timeout=5)
                return workspace.AssetWorkspace(self.root).snapshot()
            with concurrent.futures.ThreadPoolExecutor(6) as pool:
                results = list(pool.map(construct, range(6)))
            self.assertTrue(all(r == {'assets': [], 'collections': []} for r in results))
        with closing(CONNECT(self.database)) as db:
            names = [r[1] for r in db.execute('PRAGMA table_info(assets)')]
            self.assertEqual(names.count('metadata_revision'), 1)

    def test_separate_processes_initialize_fresh_store(self):
        context = multiprocessing.get_context('spawn')
        gate, queue = context.Event(), context.Queue()
        processes = [context.Process(target=initialize_process, args=(str(self.root), gate, queue)) for _ in range(4)]
        try:
            for process in processes:
                process.start()
            ready = [queue.get(timeout=15) for _ in processes]
            self.assertTrue(all(r.get('ready') for r in ready), ready)
            gate.set()
            results = [queue.get(timeout=15) for _ in processes]
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
            self.assertTrue(all(r.get('mode') == 'wal' for r in results), results)
            self.assertTrue(all(r['columns'] == results[0]['columns'] for r in results))
        finally:
            gate.set()
            for process in processes:
                if process.is_alive():
                    process.terminate(); process.join(5)
                if process.pid is not None:
                    process.close()
            queue.close(); queue.join_thread()

    def test_readonly_and_corrupt_databases_are_not_retried(self):
        self.rollback_database().close()
        busy, calls = threading.Event(), []
        original = self.database.read_bytes()
        with patch.object(workspace.sqlite3, 'connect', self.observe_connections(busy, calls, readonly=True)):
            with self.assertRaises(sqlite3.OperationalError) as caught:
                workspace.AssetWorkspace(self.root)
        self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_READONLY)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.database.read_bytes(), original)
        self.database.write_bytes(b'not a database; preserve these bytes')
        calls.clear()
        with patch.object(workspace.sqlite3, 'connect', self.observe_connections(busy, calls)):
            with self.assertRaises(sqlite3.DatabaseError) as caught:
                workspace.AssetWorkspace(self.root)
        self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_NOTADB)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.database.read_bytes(), b'not a database; preserve these bytes')

    def test_wal_setup_restores_callers_busy_timeout_and_starts_no_transaction(self):
        with closing(CONNECT(self.database)) as db:
            db.execute('PRAGMA busy_timeout=137')
            workspace.AssetWorkspace._enable_wal(db)
            self.assertEqual(db.execute('PRAGMA busy_timeout').fetchone()[0], 137)
            self.assertFalse(db.in_transaction)

    def test_later_schema_error_is_not_retried_and_can_be_reopened(self):
        calls = []
        class SchemaFailure(sqlite3.Connection):
            def executescript(self, sql):
                calls.append(sql)
                self.execute('CREATE TABLE preserved_partial (value INTEGER)')
                exc = sqlite3.OperationalError('synthetic disk I/O error at schema setup')
                exc.sqlite_errorcode = sqlite3.SQLITE_IOERR
                raise exc
        with patch.object(workspace.sqlite3, 'connect', lambda *a, **k: CONNECT(*a, factory=SchemaFailure, **k)):
            with self.assertRaisesRegex(sqlite3.OperationalError, 'disk I/O'):
                workspace.AssetWorkspace(self.root)
        self.assertEqual(len(calls), 1)
        reopened = workspace.AssetWorkspace(self.root)
        with reopened.connection() as db:
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='preserved_partial'").fetchone())
            self.assertEqual(sum(r['name']=='metadata_revision' for r in db.execute('PRAGMA table_info(assets)')), 1)
        self.assertEqual(reopened.snapshot()['assets'], [])

    def test_unsupported_journal_mode_cannot_report_ready(self):
        with patch.object(workspace.sqlite3, 'connect', lambda *a, **k: CONNECT(':memory:')):
            with self.assertRaisesRegex(workspace.WorkspaceError, 'WAL'):
                workspace.AssetWorkspace(self.root)

    def test_invalid_database_path_preserves_directory(self):
        self.database.mkdir()
        with self.assertRaises(sqlite3.OperationalError):
            workspace.AssetWorkspace(self.root)
        self.assertTrue(self.database.is_dir())

    def test_interruption_closes_connection_without_retry(self):
        connections = []
        class Interrupted(sqlite3.Connection):
            def execute(self, sql, *args):
                if 'journal_mode' in sql.lower():
                    raise KeyboardInterrupt('interrupted at WAL')
                return super().execute(sql, *args)
            def executescript(self, sql):
                if 'journal_mode' in sql.lower():
                    raise KeyboardInterrupt('interrupted at WAL')
                return super().executescript(sql)
        def connect(*args, **kwargs):
            result = CONNECT(*args, factory=Interrupted, **kwargs)
            connections.append(result)
            return result
        with patch.object(workspace.sqlite3, 'connect', connect):
            with self.assertRaises(KeyboardInterrupt):
                workspace.AssetWorkspace(self.root)
        self.assertEqual(len(connections), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            connections[0].execute('SELECT 1')
        self.assertEqual(workspace.AssetWorkspace(self.root).snapshot()['assets'], [])


if __name__ == '__main__':
    unittest.main()
