"""Repository gate for `.cjs` contracts.

Every tracked contract under `tests/`, `docs/`, `tools/` or `app/static/` must be named by a tracked Python
runner under `tests/`/`scripts/` or by an executable line in a GitHub Actions workflow. PR #583 shipped two
contract files that no wrapper and no lane ever ran: they were green because nothing executed them.

This is deliberately a wiring check, not proof of control flow. Comments, Python docstrings, workflow
`paths:` entries, untracked scratch files and this module's own sentinels cannot vouch for a contract. A
wrapper can still mention a filename on a skipped or unreachable path; #624 retains that semantic boundary.
"""
import ast
import io
import re
import subprocess
import tempfile
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()
CONTRACT_ROOTS = ('tests/', 'docs/', 'tools/', 'app/static/')
RUNNER_ROOTS = ('tests/', 'scripts/')
WORKFLOW_ROOT = '.github/workflows/'
CONTRACT_FLOOR = 40  # a scan that stops matching must fail loudly, not pass vacuously
SENTINELS = ('tests/frontend_handoffs.cjs', 'tests/continuation_core.cjs',
             'tools/gltf-validation/validate.cjs')


def tracked_paths():
    """Return the repository index, excluding untracked scratch and ignored dependency trees."""
    raw = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT)
    return tuple(sorted(path for path in raw.decode('utf-8').split('\0') if path))


def contracts():
    found = {}
    for rel in tracked_paths():
        if not rel.endswith('.cjs') or not rel.startswith(CONTRACT_ROOTS):
            continue
        path = ROOT / rel
        if not path.is_file():
            raise AssertionError(f'tracked contract is absent from the checkout: {rel}')
        found[rel] = path
    return found


PATHS_ENTRY = re.compile(r"-\s*['\"][^'\"]*['\"]\s*\Z")  # workflow `paths:` entry: fires a lane, runs nothing
_DOCSTRING_OWNERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _without_python_docstrings(text):
    """Blank actual module/class/function docstrings while preserving executable string literals."""
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    for node in ast.walk(tree):
        if not isinstance(node, _DOCSTRING_OWNERS) or not node.body:
            continue
        first = node.body[0]
        if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            continue
        for index in range(first.lineno - 1, first.end_lineno):
            lines[index] = '\n' if lines[index].endswith('\n') else ''
    return ''.join(lines)


def _python_executable_text(text):
    text = _without_python_docstrings(text)
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    without_comments = tokenize.untokenize(
        token for token in tokens if token.type != tokenize.COMMENT
    )
    return '\n'.join(line.rstrip() for line in without_comments.splitlines() if line.strip())


def _workflow_code(line):
    """Remove one YAML trailing comment without treating `#` inside quotes as a comment."""
    single = double = escaped = False
    index = 0
    while index < len(line):
        character = line[index]
        if double:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                double = False
        elif single:
            if character == "'":
                if index + 1 < len(line) and line[index + 1] == "'":
                    index += 1
                else:
                    single = False
        elif character == '"':
            double = True
        elif character == "'":
            single = True
        elif character == '#' and (index == 0 or line[index - 1].isspace()):
            return line[:index]
        index += 1
    return line


def executable_text(text, python):
    """Return text capable of naming an executed contract, excluding comments and trigger-only paths."""
    if python:
        return _python_executable_text(text)
    lines = []
    for raw in text.splitlines():
        line = _workflow_code(raw).rstrip()
        if not line.strip() or PATHS_ENTRY.match(line.strip()):
            continue
        lines.append(line)
    return '\n'.join(lines)


def runner_text(path):
    return executable_text(path.read_text(encoding='utf-8', errors='strict'), path.suffix == '.py')


def runners(exclude_self=True):
    found = {}
    for rel in tracked_paths():
        python = rel.endswith('.py') and rel.startswith(RUNNER_ROOTS)
        workflow = (rel.startswith(WORKFLOW_ROOT)
                    and (rel.endswith('.yml') or rel.endswith('.yaml')))
        if not (python or workflow) or (rel == SELF and exclude_self):
            continue
        path = ROOT / rel
        if not path.is_file():
            raise AssertionError(f'tracked runner is absent from the checkout: {rel}')
        found[rel] = runner_text(path)
    return found


def names(text):
    """Every `.cjs` basename present on executable text, matched on a path boundary."""
    return {match.group(1) for match in re.finditer(r'(?:^|[^\w.\-])([\w.\-]+\.cjs)', text, re.M)}


class ContractDiscoveryTests(unittest.TestCase):
    def test_the_scan_actually_finds_contracts_and_runners(self):
        found, ran = contracts(), runners()
        self.assertGreaterEqual(
            len(found), CONTRACT_FLOOR,
            f'only {len(found)} tracked .cjs contracts discovered under {CONTRACT_ROOTS}',
        )
        self.assertGreaterEqual(len(ran), 1, 'no tracked runner files discovered')
        self.assertIn(SELF, runners(exclude_self=False),
                      'the self-exclusion no longer matches this file, so it silently excludes nothing')
        self.assertNotIn(SELF, ran, 'the discovery module must not vouch for its own sentinels')
        for sentinel in SENTINELS:
            self.assertIn(sentinel, found, f'{sentinel} exists but the tracked contract scan missed it')

    def test_contract_basenames_are_unique(self):
        """Bare-basename wrapper references are safe only while every contract basename is unique."""
        by_name = {}
        for rel in contracts():
            by_name.setdefault(Path(rel).name, []).append(rel)
        clashes = {name: paths for name, paths in by_name.items() if len(paths) > 1}
        self.assertEqual(clashes, {}, f'duplicate .cjs basenames make wiring ambiguous: {clashes}')

    def test_every_cjs_contract_is_named_by_a_python_module_or_ci_lane(self):
        executed = set().union(*(names(text) for text in runners().values()))
        orphans = [rel for rel, path in contracts().items() if path.name not in executed]
        self.assertEqual(
            orphans, [],
            'these tracked .cjs contracts are never named by executable text under tests/, scripts/ or '
            '.github/workflows/: ' + ', '.join(orphans)
            + '. Wire each into a Python wrapper or workflow step, or delete it.',
        )

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
    """Syntactic ways the gate could vouch for a contract nothing runs."""

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

    def test_hash_inside_a_quoted_value_is_not_cut_as_a_workflow_comment(self):
        line = 'run: "node tests/real.cjs # literal argument"  # tests/probe.cjs is not wiring'
        self.assertEqual(names(executable_text(line, False)), {'real.cjs'})

    def test_python_docstrings_are_not_wiring(self):
        source = '"""tests/probe.cjs is documented here."""\nsubprocess.run([node, "tests/real.cjs"])\n'
        self.assertEqual(names(executable_text(source, True)), {'real.cjs'})


if __name__ == '__main__': unittest.main()
