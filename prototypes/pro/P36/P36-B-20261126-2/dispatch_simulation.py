"""Offline simulated Comfy port and process-crash driver; contains no HTTP client."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import sys

sys.dont_write_bytecode = True
import pipeline as p


class SimulationPort:
    """Count every callback, including duplicates; never deduplicate for the caller."""
    def __init__(self, path, *, mode='accept', conditions=None):
        self.path = Path(path).absolute()
        p.require(self.path.resolve().is_relative_to((p.REPO_ROOT / '.runtime').resolve())
                  and not any(p.linked(x) for x in (self.path, *self.path.parents)), 'Simulation port must be under .runtime/')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        self.conditions = {'backend_ready': True, 'budget_allowed': True, 'lease_held': True}
        if conditions is not None: self.conditions.update(conditions)
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS callbacks (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id TEXT NOT NULL, body_sha256 TEXT NOT NULL)')

    def check_conditions(self, intent):
        return {'scope': 'simulation-only', **self.conditions}

    def submit_once(self, attempt_id, body):
        p.require(self.mode in ('accept', 'lost-response', 'malformed'), 'Unsupported simulation mode')
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute('PRAGMA synchronous=FULL')
            cursor = db.execute('INSERT INTO callbacks(attempt_id,body_sha256) VALUES (?,?)', (attempt_id, p.digest(body)))
            number = cursor.lastrowid
        if self.mode == 'lost-response': raise OSError('Synthetic remote effect recorded; response lost')
        if self.mode == 'malformed': return {'prompt_id': None}
        return {'prompt_id': 'simulation-prompt-' + str(number)}

    def count(self):
        with sqlite3.connect(self.path, timeout=10) as db:
            return db.execute('SELECT count(*) FROM callbacks').fetchone()[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    worker = commands.add_parser('worker')
    for name in ('context', 'ledger', 'attempt-id', 'port'):
        worker.add_argument('--' + name, required=True)
    worker.add_argument('--mode', choices=('accept', 'lost-response', 'malformed'), default='accept')
    worker.add_argument('--crash-at', choices=('after-claim', 'after-marker', 'after-callback', 'after-receipt'))
    args = parser.parse_args(argv)
    import dispatch_coordinator as coordinator
    import dispatch_simulation as simulation
    try:
        context = p.load_json(args.context)
        p.require(type(context) is dict and set(context) == {'experiments', 'family', 'binding', 'asset_root',
            'semantic_policy', 'annotations', 'intent', 'studio_root'}, 'Invalid explicit simulation context')
        def checkpoint(name):
            if name == args.crash_at: os._exit(73)
        result = coordinator.dispatch_once(args.ledger, args.attempt_id,
            port=simulation.SimulationPort(args.port, mode=args.mode), _checkpoint=checkpoint, **context)
        sys.stdout.buffer.write(p.canonical_bytes(result))
        return 0 if result['passed'] else 2
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
        sys.stdout.buffer.write(p.canonical_bytes({'passed': False, 'error': str(error), 'generation_submitted': False}))
        return 2


if __name__ == '__main__': raise SystemExit(main())
