"""Discovery gate for the `.cjs` frontend contracts: every contract file under `tests/` or `docs/` must be
executed by some Python module under `tests/`/`scripts/` or by a step in a `.github/workflows/` lane.

PR #583 shipped two contract files that no wrapper and no lane ever ran: they were green because nothing
executed them. This asserts wiring, never behaviour — a wired contract can still be wrong, a contract named
only inside a Python comment does not count, and this module excludes itself so its own sentinels cannot
vouch for a contract."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()
CONTRACT_GLOBS = ('tests/**/*.cjs', 'docs/**/*.cjs')
RUNNER_GLOBS = ('tests/**/*.py', 'scripts/**/*.py', '.github/workflows/*.yml', '.github/workflows/*.yaml')
CONTRACT_FLOOR = 40  # a glob that stops matching must fail loudly, not pass vacuously
SENTINELS = ('tests/frontend_handoffs.cjs', 'tests/continuation_core.cjs')


def contracts():
    found = {}
    for pattern in CONTRACT_GLOBS:
        for path in ROOT.glob(pattern): found[path.relative_to(ROOT).as_posix()] = path
    return dict(sorted(found.items()))


def runner_text(path):
    text = path.read_text(encoding='utf-8', errors='ignore')
    if path.suffix != '.py': return text
    return '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))


def runners():
    found = {}
    for pattern in RUNNER_GLOBS:
        for path in ROOT.glob(pattern):
            rel = path.relative_to(ROOT).as_posix()
            if rel != SELF: found[rel] = runner_text(path)
    return dict(sorted(found.items()))


class ContractDiscoveryTests(unittest.TestCase):
    def test_the_scan_actually_finds_contracts_and_runners(self):
        found, ran = contracts(), runners()
        self.assertGreaterEqual(len(found), CONTRACT_FLOOR, f'only {len(found)} .cjs contracts discovered; the globs {CONTRACT_GLOBS} stopped matching')
        self.assertGreaterEqual(len(ran), 1, f'no runner files discovered; the globs {RUNNER_GLOBS} stopped matching')
        self.assertNotIn(SELF, ran, 'the discovery module must not vouch for its own sentinels')
        for sentinel in SENTINELS: self.assertIn(sentinel, found, f'{sentinel} exists but the contract scan missed it')

    def test_contract_basenames_are_unique(self):
        """Wrappers name contracts both by path (`tests/x.cjs`) and bare (`Path(__file__).with_name('x.cjs')`),
        so a duplicated basename would let one file's wiring vouch for another's."""
        names = {}
        for rel in contracts(): names.setdefault(Path(rel).name, []).append(rel)
        clashes = {name: paths for name, paths in names.items() if len(paths) > 1}
        self.assertEqual(clashes, {}, f'duplicate .cjs basenames make wiring ambiguous: {clashes}')

    def test_every_cjs_contract_is_executed_by_a_python_module_or_a_ci_lane(self):
        ran = runners()
        orphans = [rel for rel, path in contracts().items() if not any(path.name in text for text in ran.values())]
        self.assertEqual(orphans, [], 'these .cjs contracts are never executed — nothing under tests/, scripts/ or .github/workflows/ names them, so they are silently green: '
                         + ', '.join(orphans) + '. Wire each into a Python wrapper (see tests/test_workbench_handoff_guards.py) or a workflow step, or delete it.')


if __name__ == '__main__': unittest.main()
