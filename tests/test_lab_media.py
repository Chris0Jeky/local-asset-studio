"""Local-only example media: the tracked manifest is the record, the pictures never enter Git.

`examples/nsfw-lab/` and `examples/civitai-intake/` hold adult-lab JPEGs that stay on the owner's PC.
`scripts/validate-repo.py` keeps every `/api/examples/<folder>/<file>` reference answerable from
`examples/<folder>/MANIFEST.json` and keeps image binaries out of the tracked tree; `scripts/lab-media.py`
verifies, restores and indexes the files themselves. These tests run with no pictures present, which is
exactly the state of a fresh clone and of CI.
"""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FOLDERS=('nsfw-lab','civitai-intake')
SOURCES=('presets/nsfw-intel.json','presets/recipes.json','app/static/bundle-showcase.json')
IMAGE_SUFFIXES={'.jpg','.jpeg','.png','.webp','.gif','.bmp','.tif','.tiff','.avif'}
REFERENCE=re.compile(r'/api/examples/('+'|'.join(FOLDERS)+r')/([A-Za-z0-9][A-Za-z0-9._-]*)')
spec=importlib.util.spec_from_file_location('lab_media_fixture',ROOT/'scripts/lab-media.py')
lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)


def manifest(folder):
    return json.loads((ROOT/'examples'/folder/'MANIFEST.json').read_text(encoding='utf-8'))


def run(*argv):
    """scripts/lab-media.py main() with its printed report, so a test can assert on both."""
    out=io.StringIO()
    with redirect_stdout(out): code=lab.main(list(argv))
    return code,out.getvalue()


class ManifestContract(unittest.TestCase):
    def test_every_folder_has_a_version_one_manifest(self):
        for folder in FOLDERS:
            data=manifest(folder)
            self.assertEqual(data.get('version'),1,folder)
            self.assertTrue(data.get('entries'),folder)

    def test_entries_carry_the_evidence_the_pictures_no_longer_do(self):
        """Hash, size, dimensions, job/prompt id, source PNG and an inspection note per picture."""
        for folder in FOLDERS:
            for entry in manifest(folder)['entries']:
                where=(folder,entry.get('id'))
                self.assertRegex(str(entry.get('sha256','')),r'^[a-f0-9]{64}$',where)
                self.assertIsInstance(entry.get('bytes'),int,where);self.assertGreater(entry['bytes'],0,where)
                self.assertIsInstance(entry.get('width'),int,where);self.assertIsInstance(entry.get('height'),int,where)
                self.assertTrue(str(entry.get('note','')).strip(),where)
                self.assertRegex(str(entry.get('file','')),r'^[A-Za-z0-9][A-Za-z0-9._-]*$',where)
                for key in ('job_id','prompt_id','source_png'):
                    self.assertTrue(entry.get(key) is None or str(entry[key]).strip(),(where,key))

    def test_referenced_pictures_all_have_a_manifest_entry(self):
        """The rule scripts/validate-repo.py enforces: a reference resolves to the manifest, not to disk."""
        known={folder:{e['file'] for e in manifest(folder)['entries']} for folder in FOLDERS}
        seen=0
        for source in SOURCES:
            path=ROOT/source
            if not path.is_file(): continue
            for folder,name in REFERENCE.findall(path.read_text(encoding='utf-8')):
                self.assertIn(name,known[folder],source+' references '+folder+'/'+name)
                seen+=1
        self.assertGreater(seen,0,'no local-media references found; the guard would be vacuous')

    def test_no_image_binary_is_tracked_in_the_lab_folders(self):
        tracked=subprocess.check_output(['git','ls-files','-z','examples'],cwd=ROOT).decode().split('\0')
        prefixes=tuple('examples/'+folder+'/' for folder in FOLDERS)
        for name in filter(None,tracked):
            if name.startswith(prefixes):
                self.assertNotIn(Path(name).suffix.lower(),IMAGE_SUFFIXES,'local-only picture committed: '+name)

    def test_the_folders_are_gitignored_for_images(self):
        rules=set((ROOT/'.gitignore').read_text(encoding='utf-8').split())
        for folder in FOLDERS:
            for suffix in ('jpg','jpeg','png','webp'):
                self.assertIn('examples/%s/*.%s'%(folder,suffix),rules)


class LabMediaTool(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.folder=self.root/'examples/nsfw-lab';self.folder.mkdir(parents=True)
        self.payload=b'not really a jpeg, but the hash is the contract'
        self.entry={'id':'a-cell','file':'a-cell.jpg','sha256':hashlib.sha256(self.payload).hexdigest(),
                    'bytes':len(self.payload),'width':832,'height':1216,'job_id':'job-1','prompt_id':'prompt-1',
                    'cell':'a-cell','source_png':'Studio/Anima_00001_.png','note':'Extra fingers on the bed hand.'}
        self.write([self.entry])

    def write(self,entries):
        (self.folder/'MANIFEST.json').write_text(json.dumps({'version':1,'folder':'nsfw-lab','entries':entries}),encoding='utf-8')

    def place(self,raw=None):
        (self.folder/'a-cell.jpg').write_bytes(self.payload if raw is None else raw)

    def verify(self):
        return run('verify','--repo-root',str(self.root),'--folder','nsfw-lab')

    def test_verify_passes_when_the_file_is_present_and_hashes(self):
        self.place();code,report=self.verify()
        self.assertEqual(code,0,report);self.assertIn('1 ok',report)

    def test_verify_reports_a_missing_file(self):
        code,report=self.verify()
        self.assertEqual(code,1,report);self.assertIn('MISSING',report);self.assertIn('nsfw-lab/a-cell.jpg',report)

    def test_verify_reports_a_file_whose_bytes_changed(self):
        self.place(b'different bytes entirely');code,report=self.verify()
        self.assertEqual(code,1,report);self.assertIn('CORRUPT',report)

    def test_verify_names_the_restore_command_when_something_is_wrong(self):
        code,report=self.verify()
        self.assertIn('lab-media.py restore',report)

    def test_restore_from_a_git_ref_rewrites_the_exact_bytes(self):
        git=self.git_repo();self.assertFalse((self.folder/'a-cell.jpg').is_file())
        code,report=run('restore','--repo-root',str(self.root),'--folder','nsfw-lab','--from-ref',git)
        self.assertEqual(code,0,report);self.assertIn('RESTORED',report)
        self.assertEqual((self.folder/'a-cell.jpg').read_bytes(),self.payload)

    def test_restore_refuses_bytes_that_do_not_match_the_manifest_hash(self):
        git=self.git_repo();self.write([dict(self.entry,sha256='0'*64)])
        code,report=run('restore','--repo-root',str(self.root),'--folder','nsfw-lab','--from-ref',git)
        self.assertEqual(code,1,report);self.assertIn('do not match the manifest sha256',report)
        self.assertFalse((self.folder/'a-cell.jpg').is_file(),'a failed restore must not leave a wrong file behind')

    def test_restore_says_why_it_cannot_rebuild_without_a_source(self):
        self.write([dict(self.entry,source_png=None)])
        code,report=run('restore','--repo-root',str(self.root),'--folder','nsfw-lab','--comfy-output',str(self.root/'nowhere'))
        self.assertEqual(code,1,report);self.assertIn('no source PNG',report)

    def test_index_writes_a_contact_sheet_that_survives_a_missing_file(self):
        code,report=run('index','--repo-root',str(self.root),'--folder','nsfw-lab')
        self.assertEqual(code,0,report)
        page=(self.folder/'index.html').read_text(encoding='utf-8')
        self.assertIn('a-cell.jpg',page);self.assertIn('job-1',page)
        self.assertIn('lab-media.py restore',page);self.assertIn('Extra fingers on the bed hand.',page)
        self.assertIn('onerror=',page)

    def test_index_escapes_manifest_text_instead_of_emitting_markup(self):
        self.write([dict(self.entry,note='<script>alert(1)</script>')])
        run('index','--repo-root',str(self.root),'--folder','nsfw-lab')
        page=(self.folder/'index.html').read_text(encoding='utf-8')
        self.assertNotIn('<script>alert(1)</script>',page);self.assertIn('&lt;script&gt;',page)

    def git_repo(self):
        """Commit the picture in a throwaway repo so --from-ref has a ref to read it from."""
        self.place()
        for command in (['init','-q'],['config','user.email','t@example.com'],['config','user.name','t'],
                        ['add','-A'],['-c','commit.gpgsign=false','commit','-qm','media']):
            subprocess.run(['git']+command,cwd=self.root,check=True,capture_output=True)
        (self.folder/'a-cell.jpg').unlink()
        return 'HEAD'


if __name__=='__main__':
    unittest.main()
