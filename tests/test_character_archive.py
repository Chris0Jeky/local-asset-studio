"""Pinned archive intake rejects mutation and never executes archived code."""
import copy
import hashlib
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

from scripts import character_archive as a
from scripts import character_study as c


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.path = self.root / 'bundle.zip'
        self.members = {'character-consistency-kit/research/REPORT.md': b'fixture report',
                        'character-consistency-kit/tools/not_executed.py': b'raise RuntimeError("must not execute")'}
        self.lock = self.make_zip(self.members)

    def make_zip(self, members, symlink=False, duplicate=False):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                for name, data in members.items():
                    if symlink:
                        info = zipfile.ZipInfo(name); info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
                        z.writestr(info, data)
                    else: z.writestr(name, data)
                if duplicate:
                    name = next(iter(members)); z.writestr(name, members[name])
        return {'schema_version': 1, 'kind': 'character_research_archive_lock',
                'archive': {'filename': self.path.name, 'bytes': self.path.stat().st_size, 'sha256': c.file_sha(self.path)},
                'members': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in members.items()},
                'max_uncompressed_bytes': sum(map(len, members.values())),
                'policy': 'Fixture; extract bytes, never execute.'}

    def test_byte_exact_import_without_execution(self):
        out = self.root / 'imported'; receipt = a.import_bundle(self.path, self.lock, out)
        for name, data in self.members.items(): self.assertEqual((out / name).read_bytes(), data)
        self.assertEqual(receipt['members_verified'], 2)
        self.assertFalse(receipt['code_executed_from_archive']); self.assertFalse(receipt['art_accepted'])
        self.assertTrue((out / 'IMPORT-RECEIPT.json').is_file())

    def test_no_clobber(self):
        out = self.root / 'existing'; out.mkdir(); (out / 'keep').write_text('keep')
        with self.assertRaises(FileExistsError): a.import_bundle(self.path, self.lock, out)
        self.assertEqual((out / 'keep').read_text(), 'keep')

    def test_archive_digest_and_size(self):
        with self.path.open('ab') as f: f.write(b'tamper')
        with self.assertRaisesRegex(ValueError, 'Archive digest'): a.import_bundle(self.path, self.lock, self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_member_hash_and_cleanup(self):
        self.lock['members'][next(iter(self.members))]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Member digest'): a.import_bundle(self.path, self.lock, self.root / 'out')
        self.assertFalse((self.root / 'out').exists()); self.assertFalse(list(self.root.glob('.character-import-*')))

    def test_exact_member_set(self):
        name = next(iter(self.lock['members'])); self.lock['max_uncompressed_bytes'] -= self.lock['members'][name]['bytes']; del self.lock['members'][name]
        with self.assertRaisesRegex(ValueError, 'member set'): a.import_bundle(self.path, self.lock, self.root / 'out')

    def test_symlink_members_rejected(self):
        lock = self.make_zip(self.members, symlink=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): a.import_bundle(self.path, lock, self.root / 'out')

    def test_duplicate_members_rejected(self):
        lock = self.make_zip(self.members, duplicate=True)
        with self.assertRaisesRegex(ValueError, 'member set'): a.import_bundle(self.path, lock, self.root / 'out')

    def test_paths_and_case_collisions(self):
        for name in ('../escape', '/absolute', 'character-consistency-kit/../../escape', 'character-consistency-kit/NUL.txt'):
            lock = self.make_zip({name: b'bad'})
            with self.subTest(name=name), self.assertRaises(ValueError): a.import_bundle(self.path, lock, self.root / 'out')
        lock = self.make_zip({'character-consistency-kit/A.md': b'a', 'character-consistency-kit/a.md': b'a'})
        with self.assertRaisesRegex(ValueError, 'Case-colliding'): a.import_bundle(self.path, lock, self.root / 'out')

    def test_boolean_and_bad_totals(self):
        for value in (True, 0, 100000000):
            lock = copy.deepcopy(self.lock); lock['max_uncompressed_bytes'] = value
            with self.assertRaises(ValueError): a.import_bundle(self.path, lock, self.root / 'out')


if __name__ == '__main__': unittest.main()
