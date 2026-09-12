import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image
from scripts import character_media as c

class CardLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        Image.new('RGBA', (40, 50), (20, 60, 80, 255)).save(self.root/'source.png')
        self.data = {'schema_version': 1, 'sheet_id': 'sample-sheet',
          'source': {'path': 'source.png', 'sha256': c.digest(self.root/'source.png'), 'size': [40,50]},
          'panels': [{'id': 'front-view', 'label': 'Front', 'role': 'view', 'box': [1,2,21,32]}]}
    def tearDown(self): self.tmp.cleanup()
    def manifest(self, data=None):
        p = self.root/'manifest.json'
        p.write_text(json.dumps(data if data is not None else self.data))
        return p
    def test_rgba_does_not_imply_transparency(self):
        f=c.facts(self.root/'source.png'); self.assertFalse(f['has_nonopaque_pixels']); self.assertEqual(f['usable_game_alpha'],'absent')
    def test_actual_transparency_count(self):
        im=Image.open(self.root/'source.png'); im.putpixel((0,0),(0,0,0,0)); im.putpixel((1,0),(0,0,0,100)); im.save(self.root/'alpha.png')
        f=c.facts(self.root/'alpha.png'); self.assertEqual(f['nonopaque_pixels'],2); self.assertEqual(f['transparent_pixels'],1)
    def test_crop_dimensions_and_pixels(self):
        r=c.extract(self.root,self.manifest(),self.root/'out'); out=Image.open(self.root/'out/front-view.png')
        self.assertEqual(out.size,(20,30)); self.assertEqual(out.tobytes(),Image.open(self.root/'source.png').crop((1,2,21,32)).tobytes())
        self.assertFalse(r['panels'][0]['engine_ready'])
    def test_source_unchanged(self):
        before=c.digest(self.root/'source.png'); c.extract(self.root,self.manifest(),self.root/'out'); self.assertEqual(before,c.digest(self.root/'source.png'))
    def test_no_clobber(self):
        out=self.root/'out'; out.mkdir(); (out/'important.txt').write_text('keep')
        with self.assertRaises(FileExistsError): c.extract(self.root,self.manifest(),out)
        self.assertEqual((out/'important.txt').read_text(),'keep')
    def test_bad_hash(self):
        self.data['source']['sha256']='0'*64
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_duplicate_id(self):
        self.data['panels']*=2
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_out_of_bounds(self):
        self.data['panels'][0]['box']=[0,0,41,50]
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_negative_coordinates(self):
        self.data['panels'][0]['box']=[-1,0,40,50]
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_empty_crop(self):
        self.data['panels'][0]['box']=[1,0,1,40]
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_boolean_is_not_coordinate(self):
        self.data['panels'][0]['box']=[False,0,10,10]
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_dimension_mismatch(self):
        self.data['source']['size']=[50,40]
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_path_traversal(self):
        with self.assertRaises(ValueError): c.confined(self.root,'../source.png')
    def test_absolute_path(self):
        with self.assertRaises(ValueError): c.confined(self.root,str(self.root/'source.png'))
    def test_windows_drive(self):
        with self.assertRaises(ValueError): c.confined(self.root,'C:/source.png')
    def test_backslash(self):
        with self.assertRaises(ValueError): c.confined(self.root,'sub\\source.png')
    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            target=Path(elsewhere)/'external.png'; Image.new('RGB',(3,3)).save(target)
            try: (self.root/'escape.png').symlink_to(target)
            except OSError: self.skipTest('Symlink creation unavailable')
            with self.assertRaises(ValueError): c.confined(self.root,'escape.png')
    def test_bad_role(self):
        self.data['panels'][0]['role']='approved'
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_bad_id(self):
        self.data['panels'][0]['id']='../../escape'
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_empty_panels(self):
        self.data['panels']=[]
        with self.assertRaises(ValueError): c.load_manifest(self.root,self.manifest())
    def test_png_only(self):
        Image.new('RGB',(4,4)).save(self.root/'wrong.jpg')
        with self.assertRaises(ValueError): c.facts(self.root/'wrong.jpg')
    def make_complete(self):
        self.data['panels']=[]
        for role,n in [('view',4),('portrait',2),('action',7)]:
            for k in range(n): self.data['panels'].append({'id':f'{role}-{k}', 'label':role.title(),'role':role,'box':[0,0,40,50]})
        c.extract(self.root,self.manifest(),self.root/'out')
    def test_compose_checks_hash(self):
        self.make_complete(); Image.new('RGBA',(40,50),'red').save(self.root/'out/view-0.png')
        with self.assertRaises(ValueError): c.compose(self.root/'out',self.root/'review.png')
    def test_compositor_layout_and_no_clobber(self):
        self.make_complete(); r=c.compose(self.root/'out',self.root/'review.png')
        self.assertEqual(r['output_size'],[1800,1330]); self.assertEqual(len(r['placements']),13)
        self.assertFalse(r['neural_inference']); self.assertFalse(r['semantic_approval'])
        with self.assertRaises(FileExistsError): c.compose(self.root/'out',self.root/'review.png')
    def test_unsupported_layout(self):
        c.extract(self.root,self.manifest(),self.root/'out')
        with self.assertRaises(ValueError): c.compose(self.root/'out',self.root/'review.png')


class ProtectedCompositeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source.png'; self.candidate = self.root / 'candidate.png'
        self.mask = self.root / 'mask.png'; self.out = self.root / 'result.png'
        Image.new('RGBA', (4, 4), (31, 52, 76, 129)).save(self.source)
        Image.new('RGBA', (4, 4), (120, 190, 201, 255)).save(self.candidate)
        mask = Image.new('L', (4, 4), 0); mask.putpixel((1, 1), 255); mask.putpixel((2, 2), 128); mask.save(self.mask)

    def test_exact_preservation_and_source_immutability(self):
        before = c.digest(self.source)
        receipt = c.protected_composite(self.source, self.candidate, self.mask, self.out)
        with Image.open(self.source) as source, Image.open(self.candidate) as candidate, Image.open(self.mask) as mask, Image.open(self.out) as output:
            for y in range(4):
                for x in range(4):
                    if mask.getpixel((x, y)) == 0: self.assertEqual(source.getpixel((x, y)), output.getpixel((x, y)))
                    if mask.getpixel((x, y)) == 255: self.assertEqual(candidate.getpixel((x, y)), output.getpixel((x, y)))
        self.assertEqual(receipt['exactly_preserved_pixels'], 14)
        self.assertEqual(receipt['partially_blended_pixels'], 1)
        self.assertEqual(c.digest(self.source), before)
        self.assertFalse(receipt['semantic_approval'])

    def test_empty_and_full_masks_rejected(self):
        for value in (0, 255, 128):
            Image.new('L', (4, 4), value).save(self.mask)
            with self.assertRaises(ValueError): c.protected_composite(self.source, self.candidate, self.mask, self.out)
        self.assertFalse(self.out.exists())

    def test_alpha_is_not_implicitly_a_mask(self):
        Image.new('RGBA', (4, 4), (0, 0, 0, 0)).save(self.mask)
        with self.assertRaises(ValueError): c.protected_composite(self.source, self.candidate, self.mask, self.out)

    def test_dimension_and_profile_mismatch(self):
        Image.new('L', (3, 4), 0).save(self.mask)
        with self.assertRaises(ValueError): c.protected_composite(self.source, self.candidate, self.mask, self.out)
        Image.new('L', (4, 4), 0).save(self.mask)
        Image.new('RGBA', (4, 4)).save(self.candidate, icc_profile=b'fixture profile')
        with self.assertRaisesRegex(ValueError, 'ICC'): c.protected_composite(self.source, self.candidate, self.mask, self.out)

    def test_no_overwrite(self):
        self.out.write_bytes(b'keep')
        with self.assertRaises(FileExistsError): c.protected_composite(self.source, self.candidate, self.mask, self.out)
        self.assertEqual(self.out.read_bytes(), b'keep')

    def test_decoded_results_repeat_in_same_runtime(self):
        first = c.protected_composite(self.source, self.candidate, self.mask, self.out)
        second = c.protected_composite(self.source, self.candidate, self.mask, self.root / 'repeat.png')
        self.assertEqual(first['output_sha256'], second['output_sha256'])


if __name__ == '__main__': unittest.main()
