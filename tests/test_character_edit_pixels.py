import copy
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from PIL import Image, ImageDraw
from scripts import character_edit as ed, character_edit_pixels as px
from scripts.character_edit_demo import create
from scripts.character_study import file_sha, read_json, sha, write_json
ROOT=Path(__file__).resolve().parents[1]

class EditPixels(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'job'; create(self.root)
        self.plan=read_json(self.root/'plan.json')
    def ref(self,name): return {'path':name,'sha256':file_sha(self.root/name)}
    def rebuild(self):
        self.plan=ed.make_plan(self.plan['document'],self.plan['intent'],self.plan['catalog'])
    def refresh(self,field,name):
        self.plan['intent'][field]=self.ref(name); self.rebuild()
    def patch(self,name='candidate.png',out='result-new'):
        return px.apply(self.root,self.plan,'prepared',self.ref(name),out)
    def test_exact_scope(self):
        receipt=self.patch(); self.assertEqual(0,receipt['outside_mask_changed_pixels']); self.assertEqual(0,receipt['protected_changed_pixels'])
        self.assertEqual(4032,receipt['changed_pixels']); self.assertFalse(receipt['semantic_approval'])
    def test_same_runtime_repeatability(self):
        self.patch(out='one'); self.patch(out='two')
        self.assertEqual(file_sha(self.root/'one/result.png'),file_sha(self.root/'two/result.png'))
    def test_source_unchanged(self):
        before=file_sha(self.root/'source.png'); self.patch(); self.assertEqual(before,file_sha(self.root/'source.png'))
    def test_stale_source_bytes(self):
        (self.root/'source.png').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.patch()
    def test_changed_reference(self):
        (self.root/'amber-reference.png').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.patch()
    def test_changed_canon(self):
        (self.root/'violet-design.json').write_text('{}')
        with self.assertRaises(ValueError): self.patch()
    def test_wrong_candidate_digest(self):
        with self.assertRaises(ValueError): px.apply(self.root,self.plan,'prepared',{'path':'candidate.png','sha256':'0'*64},'new')
    def test_empty_mask(self):
        Image.new('L',(384,256),0).save(self.root/'mask2.png'); self.refresh('edit_mask','mask2.png')
        with self.assertRaises(ValueError): px.prepare(self.root,self.plan,'new')
    def test_inverse_mask_not_assumed(self):
        Image.new('RGBA',(384,256),(0,0,0,0)).save(self.root/'mask2.png'); self.refresh('edit_mask','mask2.png')
        with self.assertRaises(ValueError): px.prepare(self.root,self.plan,'new')
    def test_protection_overlap(self):
        Image.new('L',(384,256),255).save(self.root/'protect2.png'); self.refresh('protect_mask','protect2.png')
        with self.assertRaises(ValueError): px.prepare(self.root,self.plan,'new')
    def test_soft_protection_rejected(self):
        Image.new('L',(384,256),127).save(self.root/'protect2.png'); self.refresh('protect_mask','protect2.png')
        with self.assertRaises(ValueError): px.prepare(self.root,self.plan,'new')
    def test_non_target_actor_auto_protected(self):
        self.plan['intent']['protect_mask']=None; self.plan['intent']['context_box']=[0,0,384,256]
        m=Image.new('L',(384,256)); ImageDraw.Draw(m).rectangle((230,80,250,100),fill=255); m.save(self.root/'mask2.png'); self.refresh('edit_mask','mask2.png')
        with self.assertRaisesRegex(ValueError,'non-target actor'): px.prepare(self.root,self.plan,'new')
    def test_mask_outside_context(self):
        self.plan['intent']['context_box']=[50,96,70,140]; self.rebuild()
        with self.assertRaisesRegex(ValueError,'beyond context'): px.prepare(self.root,self.plan,'new')
    def test_candidate_size(self):
        Image.new('RGBA',(88,88)).save(self.root/'small.png')
        with self.assertRaises(ValueError): self.patch('small.png')
    def test_candidate_mode(self):
        Image.new('L',(88,96)).save(self.root/'gray.png')
        with self.assertRaises(ValueError): self.patch('gray.png')
    def test_profile_mismatch(self):
        Image.new('RGBA',(88,96)).save(self.root/'profile.png',icc_profile=b'fixture-profile')
        with self.assertRaises(ValueError): self.patch('profile.png')
    def test_matching_profile_preserved(self):
        with Image.open(self.root/'source.png') as im: im.save(self.root/'profile-source.png',icc_profile=b'fixture-profile')
        self.plan['document']['source']=self.ref('profile-source.png')
        self.plan['intent']['document_sha256']=sha(self.plan['document']); self.rebuild()
        px.prepare(self.root,self.plan,'profile-bundle')
        Image.new('RGBA',(88,96),(10,20,30,255)).save(self.root/'profile.png',icc_profile=b'fixture-profile')
        px.apply(self.root,self.plan,'profile-bundle',self.ref('profile.png'),'profile-result')
        with Image.open(self.root/'profile-result/result.png') as result: self.assertEqual(b'fixture-profile',result.info['icc_profile'])
    def test_noop_remains_unreviewed(self):
        r=self.patch('prepared/context.png'); self.assertEqual(0,r['changed_pixels']); self.assertTrue(r['warnings']); self.assertEqual('unreviewed',r['review_state'])
    def test_output_refuses_overwrite(self):
        before=file_sha(self.root/'revision-2/result.png')
        with self.assertRaises(ValueError): self.patch(out='revision-2')
        self.assertEqual(before,file_sha(self.root/'revision-2/result.png'))
    def test_prepare_refuses_overwrite(self):
        with self.assertRaises(ValueError): px.prepare(self.root,self.plan,'prepared')
    def test_output_escape(self):
        with self.assertRaises(ValueError): self.patch(out='../outside')
    def test_output_parent_symlink(self):
        try: (self.root/'link').symlink_to(Path(self.temp.name),target_is_directory=True)
        except OSError: self.skipTest('Symlink permission unavailable')
        with self.assertRaises(ValueError): self.patch(out='link/out')
    def test_input_symlink_escape(self):
        external=Path(self.temp.name)/'external.png'; external.write_bytes((self.root/'candidate.png').read_bytes())
        try: (self.root/'link.png').symlink_to(external)
        except OSError: self.skipTest('Symlink permission unavailable')
        with self.assertRaises(ValueError): self.patch('link.png')
    def test_bundle_edited(self):
        (self.root/'prepared/context.png').write_bytes(b'wrong')
        with self.assertRaises(ValueError): self.patch()
    def test_rehashed_bundle_pixel_forgery(self):
        path=self.root/'prepared/context.png'; Image.new('RGBA',(88,96),(1,1,1,255)).save(path)
        b=read_json(self.root/'prepared/bundle.json'); b['files']['context.png']['sha256']=file_sha(path)
        b['bundle_sha256']=sha({k:v for k,v in b.items() if k!='bundle_sha256'})
        (self.root/'prepared/bundle.json').unlink(); write_json(self.root/'prepared/bundle.json',b)
        with self.assertRaisesRegex(ValueError,'pixels/profile'): self.patch()
    def test_bundle_float_alias(self):
        b=read_json(self.root/'prepared/bundle.json'); b['transform']['context_box'][0]=50.0
        b['bundle_sha256']=sha({k:v for k,v in b.items() if k!='bundle_sha256'})
        (self.root/'prepared/bundle.json').unlink(); write_json(self.root/'prepared/bundle.json',b)
        with self.assertRaises(ValueError): self.patch()
    def test_bundle_another_plan(self):
        self.plan['intent']['id']='changed-intent'; self.rebuild()
        with self.assertRaises(ValueError): self.patch()
    def test_padding_not_written_to_canvas(self):
        r=self.patch(); self.assertEqual([0,0,1,3],r['transform']['padding_ltrb'])
        with Image.open(self.root/'source.png') as src, Image.open(self.root/'result-new/result.png') as dst:
            self.assertEqual(src.getpixel((137,189)),dst.getpixel((137,189)))
    def test_hidden_rgb_changes_detected(self):
        a=Image.new('RGBA',(2,2),(1,1,1,0)); b=a.copy(); b.putpixel((1,1),(4,5,6,0))
        self.assertEqual(1,px.changed_mask(a,b).histogram()[255])
    def test_binary_masks_random_pixel_invariance(self):
        rng=random.Random(1245)
        for _ in range(40):
            a=Image.frombytes('RGBA',(16,16),rng.randbytes(1024)); b=Image.frombytes('RGBA',(16,16),rng.randbytes(1024))
            mask=Image.frombytes('L',(16,16),bytes(rng.choice([0,255]) for _ in range(256)))
            result=Image.composite(b,a,mask)
            for old,new,m in zip(a.getdata(),result.getdata(),mask.getdata()):
                if m==0: self.assertEqual(old,new)
    def test_soft_edit_mask_stays_inside_scope(self):
        with Image.open(self.root/'edit-mask.png') as m: m.point(lambda x: 128 if x else 0).save(self.root/'soft.png')
        self.refresh('edit_mask','soft.png'); px.prepare(self.root,self.plan,'soft-bundle')
        result=px.apply(self.root,self.plan,'soft-bundle',self.ref('candidate.png'),'soft-result')
        self.assertEqual(0,result['outside_mask_changed_pixels'])
    def test_exif_requires_explicit_normalization(self):
        exif=Image.Exif(); exif[274]=6
        Image.new('RGBA',(88,96)).save(self.root/'rotated.png',exif=exif)
        with self.assertRaisesRegex(ValueError,'EXIF'): self.patch('rotated.png')
    def test_apng_rejected(self):
        a=Image.new('RGBA',(88,96),(1,2,3,255)); b=Image.new('RGBA',(88,96),(3,2,1,255))
        a.save(self.root/'animated.png',save_all=True,append_images=[b],duration=100,loop=0)
        with self.assertRaises(ValueError): self.patch('animated.png')
    def test_cli_prepare_and_apply(self):
        cmd=[sys.executable,str(ROOT/'scripts/character_edit_pixels.py'),'prepare','--workspace',str(self.root),
             '--plan',str(self.root/'plan.json'),'--out','cli-prepared']
        run=subprocess.run(cmd,capture_output=True,text=True); self.assertEqual(0,run.returncode,run.stderr)
        cmd=[sys.executable,str(ROOT/'scripts/character_edit_pixels.py'),'apply','--workspace',str(self.root),
             '--plan',str(self.root/'plan.json'),'--out','cli-result','--bundle','cli-prepared',
             '--candidate','candidate.png','--candidate-sha256',file_sha(self.root/'candidate.png')]
        run=subprocess.run(cmd,capture_output=True,text=True); self.assertEqual(0,run.returncode,run.stderr)

if __name__=='__main__': unittest.main()
