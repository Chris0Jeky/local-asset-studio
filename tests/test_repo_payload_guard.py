"""Hold the two enumerations of runtime output folders in step.

`.gitignore` keeps generated `experiments/` output out of the working tree; `scripts/validate-repo.py`
refuses to see the same paths tracked in Git. Both lists are hand-written, and #589 recorded what happens
when only one of them learns about a new folder: #570's `experiments/pose-artifacts/` was in neither, so a
pose render dirtied `git status` with untracked user data that a `git add -A` would have committed.

Green means every ignored `experiments/` folder is also refused by the payload guard and vice versa. It does
not prove that either list is complete with respect to the code that writes those folders.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITIGNORE = ROOT / '.gitignore'
VALIDATOR = ROOT / 'scripts/validate-repo.py'


def ignored_experiment_dirs():
    """Directory rules under `experiments/` in .gitignore, as prefixes ('experiments/runs/')."""
    found = set()
    for line in GITIGNORE.read_text(encoding='utf-8').splitlines():
        rule = line.strip()
        if not rule or rule.startswith('#') or rule.startswith('!'): continue
        if rule.startswith('experiments/') and rule.endswith('/'): found.add(rule)
    return found


def guarded_prefixes():
    """The OPERATIONAL_PREFIXES tuple literal from scripts/validate-repo.py, read as source text."""
    source = VALIDATOR.read_text(encoding='utf-8')
    match = re.search(r"^OPERATIONAL_PREFIXES=\(([^)]*)\)", source, re.M)
    assert match, 'scripts/validate-repo.py no longer declares a module-level OPERATIONAL_PREFIXES tuple'
    return {value for value in re.findall(r"'([^']+)'", match.group(1))}


class RuntimeFolderParity(unittest.TestCase):
    def test_lists_are_non_empty(self):
        """A parse that silently returns nothing would make every comparison below vacuous."""
        self.assertTrue(ignored_experiment_dirs()); self.assertTrue(guarded_prefixes())

    def test_every_ignored_experiments_folder_is_payload_guarded(self):
        missing = ignored_experiment_dirs() - guarded_prefixes()
        self.assertEqual(missing, set(), 'ignored in .gitignore but not refused by scripts/validate-repo.py: ' + repr(sorted(missing)))

    def test_every_guarded_experiments_prefix_is_ignored(self):
        guarded = {prefix for prefix in guarded_prefixes() if prefix.startswith('experiments/')}
        missing = guarded - ignored_experiment_dirs()
        self.assertEqual(missing, set(), 'refused by scripts/validate-repo.py but not ignored in .gitignore: ' + repr(sorted(missing)))

    def test_pose_artifacts_is_covered(self):
        """#589: the folder studio_workflow/pose_artifact_store.py writes must be in both lists."""
        store = (ROOT / 'studio_workflow/pose_artifact_store.py').read_text(encoding='utf-8')
        directory = re.search(r'^DIRECTORY = "([^"]+)"', store, re.M)
        self.assertIsNotNone(directory, 'pose_artifact_store.py no longer declares DIRECTORY')
        prefix = 'experiments/' + directory.group(1) + '/'
        self.assertIn(prefix, ignored_experiment_dirs()); self.assertIn(prefix, guarded_prefixes())


if __name__ == '__main__':
    unittest.main()
