"""#1714: the Studio reads its running commit from .git once, without a shell, and never fails when git info is missing."""
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
import build_info

A, B, C = 'a' * 40, 'b' * 40, 'c' * 40


class BuildInfoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding='utf-8')

    def test_normal_repo_loose_ref_and_detached_head(self):
        self.write(self.root / '.git/HEAD', 'ref: refs/heads/main\n'); self.write(self.root / '.git/refs/heads/main', A + '\n')
        self.assertEqual(build_info.head_sha(self.root), A)
        self.write(self.root / '.git/HEAD', B + '\n'); self.assertEqual(build_info.head_sha(self.root), B)

    def test_packed_refs_when_no_loose_ref(self):
        self.write(self.root / '.git/HEAD', 'ref: refs/heads/main\n')
        self.write(self.root / '.git/packed-refs', f'# pack-refs with: peeled\n{C} refs/heads/other\n{A} refs/heads/main\n^{B}\n')
        self.assertEqual(build_info.head_sha(self.root), A)

    def test_worktree_gitdir_file_reads_own_head_and_common_refs(self):
        common = self.root / 'main/.git'; wt_git = common / 'worktrees/wt'; wt = self.root / 'wt'
        self.write(wt / '.git', f'gitdir: {wt_git}\n'); self.write(wt_git / 'HEAD', 'ref: refs/heads/feature\n'); self.write(wt_git / 'commondir', '../..\n')
        self.write(common / 'packed-refs', f'{B} refs/heads/feature\n')
        self.assertEqual(build_info.head_sha(wt), B)
        self.write(common / 'refs/heads/feature', C + '\n'); self.assertEqual(build_info.head_sha(wt), C)

    def test_relative_gitdir_file(self):
        self.write(self.root / 'real/HEAD', A + '\n'); self.write(self.root / 'wt/.git', 'gitdir: ../real\n')
        self.assertEqual(build_info.head_sha(self.root / 'wt'), A)

    def test_missing_or_unreadable_git_is_none_without_spawning_git(self):
        with patch.object(build_info.subprocess, 'run', side_effect=AssertionError('no shell')):
            self.assertIsNone(build_info.head_sha(self.root))
            self.assertIsNone(build_info.head_sha(self.root / 'absent'))
            self.write(self.root / '.git', 'not a gitdir pointer')
            self.assertIsNone(build_info.head_sha(self.root))

    def test_unresolvable_ref_falls_back_to_git_once_and_tolerates_failure(self):
        self.write(self.root / '.git/HEAD', 'ref: refs/heads/gone\n')
        with patch.object(build_info.subprocess, 'run', return_value=type('R', (), {'stdout': B + '\n'})()) as run:
            self.assertEqual(build_info.head_sha(self.root), B); self.assertEqual(run.call_count, 1)
        with patch.object(build_info.subprocess, 'run', side_effect=OSError('no git')): self.assertIsNone(build_info.head_sha(self.root))

    def test_build_info_has_sha_and_utc_start(self):
        info = build_info.build_info(self.root)
        self.assertIsNone(info['sha']); self.assertEqual(datetime.fromisoformat(info['started_at']).utcoffset().total_seconds(), 0)


if __name__ == '__main__': unittest.main()
