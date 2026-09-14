"""Actual normalized-source, layout, preview and crop integration fixtures."""
import copy
from io import BytesIO
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts import repair_source as source
from scripts import repair_panels as p


class RepairPanelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.packet=self.root/'source'
        self.original=self.root/'image.png'
        with Image.new('RGBA',(35,27)) as im:
            im.putdata([(x*7,y*8,(x+y)*3,0 if x==2 else 100 if y==3 else 255) for y in range(27) for x in range(35)])
            im.save(self.original)
        source.capture(self.original,self.packet)

    def call(self,name,*args,**kwargs):
        self.assertTrue(callable(getattr(p,name,None)),name+' is not implemented')
        return getattr(p,name)(*args,**kwargs)

    def layout(self):
        return self.call('grid',self.packet,rows=2,columns=3,gutter=[2,3])

    def write_layout(self,value):
        path=self.root/'layout.json'; path.write_text(json.dumps(value),encoding='utf-8'); return path

    def extract(self,layout=None):
        path=self.write_layout(layout or self.layout()); digest=source.digest(path.read_bytes())
        out=self.root/'extracted'; report=self.call('extract',self.packet,path,out,digest)
        return path,out,report

    def test_grid_is_bound_to_both_normalized_source_and_receipt(self):
        layout=self.layout()
        self.assertEqual(layout['source']['sha256'],source.digest((self.packet/'normalized.png').read_bytes()))
        self.assertEqual(layout['source']['receipt_sha256'],source.digest((self.packet/'receipt.json').read_bytes()))
        self.assertEqual(len(layout['panels']),6)
        self.assertEqual(len({v['instance_id'] for v in layout['panels']}),6)
        self.assertTrue(all(v['canon_id'] is None for v in layout['panels']))
        self.assertEqual(layout['panels'][0]['box'],[0,0,10,12])
        self.assertEqual(layout['panels'][-1]['box'],[24,15,35,27])

    def test_authored_grid_region_preserves_aspect_without_stretch(self):
        layout=self.call('grid',self.packet,rows=1,columns=2,gutter=[1,0],region=[3,4,32,21])
        self.assertEqual([v['box'] for v in layout['panels']],[[3,4,17,21],[18,4,32,21]])

    def test_invalid_grid_cannot_make_zero_sized_or_excessive_panels(self):
        for kwargs in ({'rows':0,'columns':2},{'rows':True,'columns':2},{'rows':9,'columns':8},
                       {'rows':1,'columns':4,'gutter':[20,0]}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError): self.call('grid',self.packet,**kwargs)

    def test_actual_pixels_alpha_and_metadata_are_preserved_in_every_crop(self):
        _,out,report=self.extract()
        with Image.open(self.packet/'normalized.png') as master:
            for entry in report['panels']:
                with Image.open(out/entry['path']) as crop, master.crop(entry['box']) as expected:
                    self.assertEqual(crop.size,expected.size)
                    self.assertEqual(crop.tobytes(),expected.tobytes())
                    self.assertEqual(entry['pixel_sha256'],source.digest(expected.tobytes()))
        self.assertFalse(report['neural_inference']); self.assertEqual(report['review_state'],'unreviewed')
        self.assertEqual(self.call('verify_extraction',self.packet,out),report)

    def test_same_canon_can_be_reused_but_instances_cannot(self):
        layout=self.layout()
        for entry in layout['panels']: entry['canon_id']='shared-canon'
        self.extract(layout)
        layout['panels'][1]['instance_id']=layout['panels'][0]['instance_id']
        with self.assertRaises(ValueError): self.call('validate_layout',layout,source.load_packet(self.packet)[1],source.load_packet(self.packet)[2])

    def test_overlap_must_match_explicit_pair_declarations(self):
        layout=self.layout(); layout['panels'][1]['box']=[5,0,20,12]
        path=self.write_layout(layout)
        with self.assertRaises(ValueError): self.call('extract',self.packet,path,self.root/'bad',source.digest(path.read_bytes()))
        self.assertFalse((self.root/'bad').exists())
        layout['overlaps']=[['panel-01','panel-02']]
        self.extract(layout)

    def test_stale_or_spurious_overlap_annotation_is_rejected(self):
        layout=self.layout(); layout['overlaps']=[['panel-01','panel-06']]
        path=self.write_layout(layout)
        with self.assertRaises(ValueError): self.call('preview',self.packet,path,self.root/'preview')

    def test_boolean_coordinates_duplicate_panels_and_unknown_keys_fail(self):
        for change in ('boolean','duplicate','unknown'):
            layout=self.layout()
            if change=='boolean': layout['panels'][0]['box'][0]=False
            elif change=='duplicate': layout['panels'][1]['id']=layout['panels'][0]['id']
            else: layout['approved']=True
            path=self.write_layout(layout)
            with self.subTest(change=change),self.assertRaises(ValueError): self.call('preview',self.packet,path,self.root/'preview')

    def test_changed_source_or_receipt_is_not_silently_rebased(self):
        for key in ('sha256','receipt_sha256'):
            layout=self.layout(); layout['source'][key]='0'*64
            path=self.write_layout(layout)
            with self.assertRaises(ValueError): self.call('preview',self.packet,path,self.root/'preview')

    def test_extract_requires_exact_previewed_layout_bytes(self):
        path=self.write_layout(self.layout()); old=source.digest(path.read_bytes())
        path.write_text(path.read_text()+'\n')
        with self.assertRaises(ValueError): self.call('extract',self.packet,path,self.root/'out',old)
        self.assertFalse((self.root/'out').exists())

    def test_preview_is_a_derivative_and_not_art_acceptance(self):
        path=self.write_layout(self.layout()); before=(self.packet/'normalized.png').read_bytes()
        report=self.call('preview',self.packet,path,self.root/'preview')
        self.assertEqual(report['layout_sha256'],source.digest(path.read_bytes()))
        self.assertFalse(report['neural_inference']); self.assertEqual(report['review_state'],'unreviewed')
        self.assertTrue((self.root/'preview'/'preview.png').is_file())
        self.assertEqual((self.packet/'normalized.png').read_bytes(),before)
        self.assertTrue(report['warnings'])

    def test_crop_edges_are_reported_without_inventing_missing_anatomy(self):
        _,_,report=self.extract()
        self.assertIn('left',report['panels'][0]['source_edges'])
        self.assertEqual(report['panels'][0]['visibility'],'unknown')
        self.assertNotIn('missing_foot',json.dumps(report))

    def test_general_manual_layout_with_mixed_aspects_and_roles(self):
        layout=self.layout(); layout['panels']=layout['panels'][:3]; layout['method']='manual'
        layout['panels'][0]['box']=[1,1,12,25]
        layout['panels'][1]['box']=[14,1,33,9]; layout['panels'][1]['role']='portrait'
        layout['panels'][2]['box']=[14,11,33,26]; layout['panels'][2]['role']='action'
        self.extract(layout)

    def test_panel_names_cannot_be_paths_or_collide_with_packet_members(self):
        layout=self.layout(); layout['panels'][0]['id']='../escape'; path=self.write_layout(layout)
        with self.assertRaises(ValueError): self.call('preview',self.packet,path,self.root/'preview')
        layout=self.layout(); layout['panels'][0]['id']='master'
        _,out,report=self.extract(layout)
        self.assertEqual(report['panels'][0]['path'],'panel-master.png')
        self.assertEqual((out/'master.png').read_bytes(),(self.packet/'normalized.png').read_bytes())

    def test_total_crop_pixel_budget_precedes_publication(self):
        path=self.write_layout(self.layout())
        with patch.object(p,'MAX_TOTAL_PIXELS',10,create=True):
            with self.assertRaises(ValueError): self.call('extract',self.packet,path,self.root/'out',source.digest(path.read_bytes()))
        self.assertFalse((self.root/'out').exists())

    def test_output_packet_never_overwrites_existing(self):
        path,out,_=self.extract(); before={f.name:f.read_bytes() for f in out.iterdir()}
        with self.assertRaises(FileExistsError): self.call('extract',self.packet,path,out,source.digest(path.read_bytes()))
        self.assertEqual(before,{f.name:f.read_bytes() for f in out.iterdir()})

    def test_rehashed_wrong_crop_fails_reconstruction(self):
        _,out,report=self.extract(); entry=report['panels'][0]
        with Image.open(out/entry['path']) as im:
            im.putpixel((0,0),(255,0,255,255)); im.save(out/entry['path'])
        receipt=json.loads((out/'receipt.json').read_text())
        receipt['panels'][0]['sha256']=source.digest((out/entry['path']).read_bytes())
        (out/'receipt.json').write_text(json.dumps(receipt))
        with self.assertRaises(ValueError): self.call('verify_extraction',self.packet,out)

    def test_changed_master_or_layout_fails_verification(self):
        _,out,_=self.extract()
        with Image.open(out/'master.png') as master:
            master.putpixel((0,0),(255,0,255,255)); master.save(out/'master.png')
        with self.assertRaises(ValueError): self.call('verify_extraction',self.packet,out)

    def test_no_network_or_model_work_in_inspection_extraction(self):
        with patch.object(socket,'socket',side_effect=AssertionError('network')):
            path,out,_=self.extract()
            self.call('preview',self.packet,path,self.root/'preview')
            self.call('verify_extraction',self.packet,out)

    def test_legacy_manifest_uses_only_existing_supported_fields_and_paths(self):
        _,out,_=self.extract(); legacy=json.loads((out/'legacy-manifest.json').read_text())
        self.assertEqual(legacy['schema_version'],1)
        self.assertEqual(legacy['source']['path'],'master.png')
        self.assertEqual(legacy['source']['sha256'],source.digest((out/'master.png').read_bytes()))
        self.assertEqual(legacy['panels'][0]['instance_id'],'instance-01')

    @unittest.skipUnless((ROOT/'scripts/character_media.py').is_file(),'full repository needed for legacy integration')
    def test_existing_character_media_extract_consumes_export_without_changes(self):
        from scripts.character_media import extract
        _,out,report=self.extract()
        legacy_out=self.root/'legacy'; legacy=extract(out,out/'legacy-manifest.json',legacy_out)
        self.assertEqual(len(legacy['panels']),len(report['panels']))
        for entry in report['panels']:
            with Image.open(out/entry['path']) as actual, Image.open(legacy_out/(entry['id']+'.png')) as old:
                self.assertEqual(actual.tobytes(),old.tobytes())

    def test_verification_enforces_aggregate_encoded_output_budget(self):
        _,out,report=self.extract()
        total=sum(f.stat().st_size for f in out.iterdir() if f.name!='receipt.json')
        last=report['panels'][-1]; target=out/last['path']; raw=target.read_bytes()
        padded=raw[:-12]+source.png_chunk(b'IDAT',b'\0'*500)+raw[-12:]
        target.write_bytes(padded)
        report['panels'][-1]['sha256']=source.digest(padded)
        report['panels'][-1]['bytes']=len(padded)
        (out/'receipt.json').write_text(json.dumps(report))
        with Image.open(BytesIO(padded)) as im: self.assertEqual(source.digest(im.tobytes()),last['pixel_sha256'])
        with patch.object(source,'MAX_OUTPUT_BYTES',total+100):
            with self.assertRaises(ValueError): self.call('verify_extraction',self.packet,out)

    def test_completed_packet_cannot_use_an_external_layout_symlink(self):
        _,out,_=self.extract(); external=self.root/'external.json'
        external.write_bytes((out/'layout.json').read_bytes()); (out/'layout.json').unlink()
        try: (out/'layout.json').symlink_to(external)
        except OSError: self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError): self.call('verify_extraction',self.packet,out)

    def test_oversized_analysis_requires_manual_layout(self):
        before=set(self.root.iterdir())
        with patch.object(p,'MAX_ANALYSIS_PIXELS',10,create=True):
            with self.assertRaises(ValueError): self.call('suggest',self.packet)
        self.assertEqual(before,set(self.root.iterdir()))

    def test_unreviewed_visibility_cannot_become_art_acceptance(self):
        layout=self.layout()
        for entry in layout['panels']: entry['visibility']='complete'; entry['canon_id']='same-canon'
        _,_,report=self.extract(layout)
        self.assertEqual(report['review_state'],'unreviewed')

    def test_captured_pixels_are_used_without_reopening_mutable_master(self):
        path=self.write_layout(self.layout()); captured=(self.packet/'normalized.png').read_bytes()
        real=source.load_packet
        def replace_after_capture(packet):
            result=real(packet)
            (self.packet/'normalized.png').write_bytes(b'replaced')
            return result
        out=self.root/'out'
        with patch.object(source,'load_packet',side_effect=replace_after_capture):
            self.call('extract',self.packet,path,out,source.digest(path.read_bytes()))
        self.assertEqual((out/'master.png').read_bytes(),captured)

    def test_colour_chunks_propagate_to_crops_without_conversion(self):
        from PIL import PngImagePlugin
        import struct
        info=PngImagePlugin.PngInfo(); info.add(b'gAMA',struct.pack('>I',50000))
        with Image.open(self.original) as im: im.save(self.original,pnginfo=info)
        packet=self.root/'coloured'; source.capture(self.original,packet)
        layout=self.call('grid',packet,rows=1,columns=2)
        path=self.write_layout(layout); out=self.root/'coloured-panels'
        report=self.call('extract',packet,path,out,source.digest(path.read_bytes()))
        for entry in report['panels']:
            with Image.open(out/entry['path']) as im: self.assertEqual(im.info['gamma'],0.5)
        self.call('verify_extraction',packet,out)

    def test_orientation_precedes_grid_and_exact_crop_extraction(self):
        with Image.open(self.original) as im:
            exif=im.getexif(); exif[274]=6; im.save(self.original,exif=exif)
        packet=self.root/'oriented'; source.capture(self.original,packet)
        layout=self.call('grid',packet,rows=1,columns=1)
        self.assertEqual(layout['panels'][0]['box'],[0,0,27,35])
        path=self.write_layout(layout); out=self.root/'oriented-panels'
        self.call('extract',packet,path,out,source.digest(path.read_bytes()))
        self.call('verify_extraction',packet,out)

    def test_cli_grid_preview_extract_verify_from_other_directory(self):
        script=str(ROOT/'scripts/repair_panels.py')
        def run(*args):
            result=subprocess.run([sys.executable,script,*args],text=True,capture_output=True,cwd=self.root)
            self.assertEqual(result.returncode,0,result.stderr+result.stdout)
            return json.loads(result.stdout)
        layout=run('grid','--source',str(self.packet),'--rows','2','--columns','3','--gutter','2','3')
        path=self.write_layout(layout)
        view=run('preview','--source',str(self.packet),'--layout',str(path),'--out',str(self.root/'preview'))
        output=self.root/'out'
        run('extract','--source',str(self.packet),'--layout',str(path),'--out',str(output),'--reviewed-layout-sha256',view['layout_sha256'])
        verified=run('verify','--source',str(self.packet),'--packet',str(output))
        self.assertFalse(verified['neural_inference'])

    def test_real_demo_runs_and_verifies_nine_crops(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/repair_panels_demo.py'),'--out',str(self.root/'demo')],cwd=self.root,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        proof=json.loads(result.stdout)
        self.assertEqual(proof['panels'],9)
        self.assertTrue(proof['verified_exact_crops'])
        self.assertFalse(proof['neural_inference'])
        self.assertEqual(proof['review_state'],'unreviewed')

    def test_whitespace_proposal_is_nonsemantic_and_retains_master(self):
        other=self.root/'white.png'
        with Image.new('RGBA',(120,80),'white') as im:
            draw=ImageDraw.Draw(im)
            for b in [(4,4,53,33),(64,4,113,33),(4,44,53,73),(64,44,113,73)]: draw.rectangle(b,fill='black')
            im.save(other)
        packet=self.root/'white-source'; source.capture(other,packet)
        layout=self.call('suggest',packet,min_gutter=4)
        self.assertEqual(len(layout['panels']),4)
        self.assertTrue(all(v['visibility']=='unknown' for v in layout['panels']))
        self.assertTrue(all(v['canon_id'] is None for v in layout['panels']))
        self.assertEqual((packet/'source.png').read_bytes(),other.read_bytes())

    def test_no_gutters_or_blank_source_falls_back_without_guessing(self):
        layout=self.call('suggest',self.packet,min_gutter=4)
        self.assertEqual(len(layout['panels']),1)
        self.assertEqual(layout['panels'][0]['box'],[0,0,35,27])

if __name__=='__main__': unittest.main()
