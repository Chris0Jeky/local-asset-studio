"""Discovery gate for the `.cjs` frontend contracts: every contract file under `tests/` or `docs/` must be
executed by some Python module under `tests/`/`scripts/` or by a step in a `.github/workflows/` lane.

PR #583 shipped two contract files that no wrapper and no lane ever ran: they were green because nothing
executed them. This asserts wiring, never behaviour — a wired contract can still be wrong. What does not
count as wiring: a whole-line comment, a workflow `paths:` trigger entry (it fires the lane, it does not
run the file), a basename that is only a tail of a longer one (`core.cjs` inside `continuation_core.cjs`),
and this module's own text, which is excluded so its sentinels cannot vouch for a contract. A trailing
comment after real code does still count — the known hole, pinned in MatchingRules rather than claimed shut."""
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()
CONTRACT_GLOBS = ('tests/**/*.cjs', 'docs/**/*.cjs')
RUNNER_GLOBS = ('tests/**/*.py', 'scripts/**/*.py', '.github/workflows/*.yml', '.github/workflows/*.yaml')
CONTRACT_FLOOR = 40  # a glob that stops matching must fail loudly, not pass vacuously
SENTINELS = ('tests/frontend_handoffs.cjs', 'tests/continuation_core.cjs',
             'tools/gltf-validation/validate.cjs')


def contracts():
    found = {}
    for pattern in CONTRACT_GLOBS:
        for path in ROOT.glob(pattern): found[path.relative_to(ROOT).as_posix()] = path
    return dict(sorted(found.items()))


PATHS_ENTRY = re.compile(r"-\s*['\"][^'\"]*['\"]\s*\Z")  # a workflow `paths:` entry: fires the lane, runs nothing


def executable_text(text, python):
    """The lines that could actually execute something: no comments, and for a workflow no bare quoted
    list entry, which is how `on: pull_request: paths:` names a file it fires on but never runs."""
    lines = [line for line in text.splitlines() if not line.lstrip().startswith('#')]
    if not python: lines = [line for line in lines if not PATHS_ENTRY.match(line.strip())]
    return '\n'.join(lines)


def runner_text(path):
    return executable_text(path.read_text(encoding='utf-8', errors='ignore'), path.suffix == '.py')


def runners(exclude_self=True):
    found = {}
    for pattern in RUNNER_GLOBS:
        for path in ROOT.glob(pattern):
            rel = path.relative_to(ROOT).as_posix()
            if rel != SELF or not exclude_self: found[rel] = runner_text(path)
    return dict(sorted(found.items()))


def names(text):
    """Every .cjs basename the text executes. Matched on a path boundary so `core.cjs` is not read out of
    `continuation_core.cjs`; a duplicate basename would still be ambiguous, hence the uniqueness test."""
    return {match.group(1) for match in re.finditer(r'(?:^|[^\w.\-])([\w.\-]+\.cjs)', text, re.M)}


class ContractDiscoveryTests(unittest.TestCase):
    def test_the_scan_actually_finds_contracts_and_runners(self):
        found, ran = contracts(), runners()
        self.assertGreaterEqual(len(found), CONTRACT_FLOOR, f'only {len(found)} .cjs contracts discovered; the globs {CONTRACT_GLOBS} stopped matching')
        self.assertGreaterEqual(len(ran), 1, f'no runner files discovered; the globs {RUNNER_GLOBS} stopped matching')
        self.assertIn(SELF, runners(exclude_self=False), 'the self-exclusion no longer matches this file, so it silently excludes nothing')
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
        executed = set().union(*(names(text) for text in runners().values()))
        orphans = [rel for rel, path in contracts().items() if path.name not in executed]
        self.assertEqual(orphans, [], 'these .cjs contracts are never executed — nothing under tests/, scripts/ or .github/workflows/ names them, so they are silently green: '
                         + ', '.join(orphans) + '. Wire each into a Python wrapper (see tests/test_workbench_handoff_guards.py) or a workflow step, or delete it.')

    def test_untracked_contracts_do_not_enter_the_repository_gate(self):
        """Scratch files and ignored node_modules trees are not repository contracts."""
        handle = tempfile.NamedTemporaryFile(dir=ROOT / 'tests', suffix='.cjs', delete=False)
        path = Path(handle.name)
        try:
            handle.write(b"throw new Error('untracked scratch');\n"); handle.close()
            relative = path.relative_to(ROOT).as_posix()
            self.assertNotIn(relative, contracts())
        finally:
            handle.close(); path.unlink(missing_ok=True)


class MatchingRules(unittest.TestCase):
    """Ways this gate could vouch for a contract nothing runs."""

    def test_a_basename_is_never_read_out_of_a_longer_one(self):
        self.assertEqual(names('subprocess.run([node, "tests/continuation_core.cjs"])'), {'continuation_core.cjs'})
        self.assertEqual(names('subprocess.run([node, "tests/core.cjs"])'), {'core.cjs'})
        self.assertEqual(names("run: node --test tests/a.cjs tests/b.cjs"), {'a.cjs', 'b.cjs'})

    def test_a_commented_out_invocation_is_not_wiring(self):
        self.assertEqual(executable_text('    # node tests/probe.cjs\nreal = 1\n', True), 'real = 1')
        self.assertEqual(executable_text('      # - run: node tests/probe.cjs\n      - run: true\n', False), '      - run: true')

    def test_a_workflow_paths_entry_is_not_wiring(self):
        lane = "on:\n  pull_request:\n    paths:\n      - 'tests/probe.cjs'\n      - \"tests/other.cjs\"\njobs:\n  x:\n    steps:\n      - run: node tests/real.cjs\n"
        self.assertEqual(names(executable_text(lane, False)), {'real.cjs'})

    def test_a_trailing_comment_is_not_wiring(self):
        self.assertEqual(names(executable_text('real = 1  # tests/probe.cjs is wired below\n', True)), set())
        self.assertEqual(names(executable_text('run: true  # node tests/probe.cjs\n', False)), set())

    def test_python_docstrings_are_not_wiring(self):
        source = '"""tests/probe.cjs is documented here."""\nsubprocess.run([node, "tests/real.cjs"])\n'
        self.assertEqual(names(executable_text(source, True)), {'real.cjs'})


if __name__ == '__main__': unittest.main()
