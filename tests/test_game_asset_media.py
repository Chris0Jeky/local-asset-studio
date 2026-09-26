import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
try:
 from PIL import Image
except ImportError:Image=None
import game_asset_pipeline as p
import game_asset_media as m


@unittest.skipUnless(Image is not None,'Optional Pillow not installed')
class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.im=Image.new('RGBA',(4,6),(12,34,56,128));self.im.save(self.root/'a.png')
        self.entry={'id':'frame-a','path':'a.png','sha256':p.file_sha(self.root/'a.png'),'duration_ms':80}
        self.fm={'schema_version':1,'canvas':[4,6],'anchor':[2,6],'clip':'test-idle','loop':True,'frames':[self.entry]}
        self.lm={'schema_version':1,'canvas':[4,6],'layers':[dict(self.entry,name='A layer')]}
    def tearDown(self):self.temp.cleanup()
    def test_rgba_pixel_roundtrip(self):
        out=m.atlas(self.fm,self.root,self.root/'pack')
        with Image.open(self.root/'pack/atlas.png') as sheet:
            x,y,w,h=out['frames'][0]['region'];self.assertEqual(sheet.crop((x,y,x+w,y+h)).tobytes(),self.im.tobytes())
        self.assertEqual(out['anchor'],[2,6]);self.assertEqual(out['frames'][0]['duration_ms'],80)
        self.assertFalse((self.root/'pack/.incomplete').exists())
    def test_padding_extrusion(self):
        m.atlas(self.fm,self.root,self.root/'pack',padding=2,extrude=1)
        with Image.open(self.root/'pack/atlas.png') as sheet:
            self.assertEqual(sheet.getpixel((1,1)),self.im.getpixel((0,0)))
            self.assertEqual(sheet.getpixel((0,0)),(0,0,0,0))
    def test_no_overwrite(self):
        m.atlas(self.fm,self.root,self.root/'pack')
        with self.assertRaises(FileExistsError):m.atlas(self.fm,self.root,self.root/'pack')
    def test_bad_hash(self):
        self.entry['sha256']='0'*64
        with self.assertRaises(ValueError):m.atlas(self.fm,self.root,self.root/'pack')
    def test_frame_canvas_mismatch(self):
        self.fm['canvas']=[5,6]
        with self.assertRaises(ValueError):m.atlas(self.fm,self.root,self.root/'pack')
    def test_duplicate_frame_id(self):
        self.fm['frames'].append(dict(self.entry))
        with self.assertRaises(ValueError):m.atlas(self.fm,self.root,self.root/'pack')
    def test_no_silent_duration_or_anchor_fix(self):
        self.entry['duration_ms']=0
        with self.assertRaises(ValueError):m.atlas(self.fm,self.root,self.root/'pack')
        self.entry['duration_ms']=80;self.fm['anchor']=[9,6]
        with self.assertRaises(ValueError):m.atlas(self.fm,self.root,self.root/'pack')
    def test_empty_requires_consent(self):
        Image.new('RGBA',(4,6)).save(self.root/'a.png');self.entry['sha256']=p.file_sha(self.root/'a.png')
        with self.assertRaises(ValueError):m.atlas(self.fm,self.root,self.root/'pack')
        self.entry['allow_empty']=True;m.atlas(self.fm,self.root,self.root/'pack')
    def test_rgb_conversion_must_be_explicit(self):
        self.im.convert('RGB').save(self.root/'a.png');self.entry['sha256']=p.file_sha(self.root/'a.png')
        with self.assertRaises(ValueError):m.atlas(self.fm,self.root,self.root/'pack')
    def test_duplicate_pixels_are_warning(self):
        self.fm['frames'].append(dict(self.entry,id='frame-b'))
        result=m.atlas(self.fm,self.root,self.root/'pack')
        self.assertTrue(any('same pixels' in x for x in result['qa']['warnings']))
    def test_ora_mimetype_layout(self):
        result=m.ora(self.lm,self.root,self.root/'art.ora')
        self.assertFalse(result['krita_live_import_tested'])
        with zipfile.ZipFile(self.root/'art.ora') as z:
            self.assertEqual(z.infolist()[0].filename,'mimetype');self.assertEqual(z.infolist()[0].compress_type,zipfile.ZIP_STORED)
            self.assertEqual(z.read('mimetype'),b'image/openraster')
            self.assertIn('mergedimage.png',z.namelist());self.assertIn('Thumbnails/thumbnail.png',z.namelist())
            doc=ET.fromstring(z.read('stack.xml'));self.assertEqual(doc.find('stack/layer').get('name'),'A layer')
    def test_ora_bytes_are_reproducible_across_zip_timestamps(self):
        timestamps=[(2026,1,1,0,0,0)] * 5 + [(2026,1,1,0,0,2)] * 5
        with mock.patch('zipfile.time.localtime', side_effect=lambda *_: timestamps.pop(0)):
            m.ora(self.lm,self.root,self.root/'first.ora')
            m.ora(self.lm,self.root,self.root/'second.ora')
        self.assertEqual(p.file_sha(self.root/'first.ora'),p.file_sha(self.root/'second.ora'))
    def test_ora_topmost_and_hidden(self):
        top=Image.new('RGBA',(4,6),(255,0,0,255));top.save(self.root/'top.png')
        self.lm['layers'].insert(0,dict(id='top-layer',name='Top',path='top.png',sha256=p.file_sha(self.root/'top.png')))
        m.ora(self.lm,self.root,self.root/'visible.ora')
        with zipfile.ZipFile(self.root/'visible.ora') as z:
            im=Image.open(io.BytesIO(z.read('mergedimage.png')));self.assertEqual(im.getpixel((0,0)),(255,0,0,255))
        self.lm['layers'][0]['visible']=False;m.ora(self.lm,self.root,self.root/'hidden.ora')
        with zipfile.ZipFile(self.root/'hidden.ora') as z:
            im=Image.open(io.BytesIO(z.read('mergedimage.png')));self.assertEqual(im.getpixel((0,0)),self.im.getpixel((0,0)))
    def test_ora_refuses_unsupported_blend(self):
        self.lm['layers'][0]['blend']='multiply'
        with self.assertRaises(ValueError):m.ora(self.lm,self.root,self.root/'art.ora')
    def test_ora_xml_escaping(self):
        self.lm['layers'][0]['name']='A <b> & "quoted" layer'
        m.ora(self.lm,self.root,self.root/'art.ora')
        with zipfile.ZipFile(self.root/'art.ora') as z:
            doc=ET.fromstring(z.read('stack.xml'));self.assertEqual(doc.find('stack/layer').get('name'),self.lm['layers'][0]['name'])
    def test_ora_never_replaces_existing(self):
        m.ora(self.lm,self.root,self.root/'art.ora')
        with self.assertRaises(FileExistsError):m.ora(self.lm,self.root,self.root/'art.ora')
    def test_demo_pipeline(self):
        from game_asset_demo import create
        root=create(self.root/'demo');self.assertTrue((root/'editable.ora').is_file())
        plan=p.read_json(root/'plan.json');self.assertEqual(len(p.next_tasks(plan,[],root)['ready']),1)


@unittest.skipUnless(Image is not None,'Optional Pillow not installed')
class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_cleanup_threshold_boundaries(self):
        alphas=[0,1,7,8,100,223,224,254,255];im=Image.new('RGBA',(9,1))
        for x,a in enumerate(alphas):im.putpixel((x,0),(x*20,255-x*20,7,a))
        before=im.tobytes();out=m.alpha_cleanup(im)
        self.assertEqual([out.getpixel((x,0))[3] for x in range(9)],[0,0,0,8,100,223,255,255,255])
        self.assertEqual([out.getpixel((x,0))[:3] for x in range(9)],[im.getpixel((x,0))[:3] for x in range(9)])
        self.assertEqual(im.tobytes(),before)
    def test_cleanup_tightens_bbox_and_matte(self):
        im=Image.new('RGBA',(8,8));px=im.load()
        for y in range(2,6):
            for x in range(2,6):px[x,y]=(200,10,10,230)
        px[0,0]=(0,0,0,3);px[7,7]=(0,0,0,3)
        before=m.alpha_report(im)
        self.assertEqual(before['bbox'],[0,0,8,8]);self.assertEqual(before['components'],3)
        self.assertEqual(before['bands']['dust'],2);self.assertEqual(before['bands']['body'],16)
        out=m.alpha_cleanup(im);after=m.alpha_report(out)
        self.assertEqual(after['bbox'],[2,2,6,6]);self.assertEqual(after['components'],1)
        self.assertEqual(after['largest_component'],16);self.assertEqual(after['bands']['dust'],0)
        self.assertEqual(after['bands']['opaque'],16)
    def test_matte_uses_four_connectivity(self):
        im=Image.new('RGBA',(2,2),(0,0,0,0));im.putpixel((0,0),(1,2,3,255));im.putpixel((1,1),(1,2,3,255))
        self.assertEqual(m.matte_components(im)['components'],2)
    def test_cleanup_keeps_edge_band(self):
        im=Image.new('RGBA',(216,1))
        for x in range(216):im.putpixel((x,0),(9,9,9,8+x))
        self.assertEqual(m.alpha_cleanup(im).tobytes(),im.tobytes())
    def test_empty_image_reports_no_matte(self):
        im=Image.new('RGBA',(4,6));report=m.alpha_report(im)
        self.assertIsNone(report['bbox']);self.assertEqual(report['components'],0)
        self.assertEqual(report['largest_component'],0)
        self.assertEqual(m.alpha_cleanup(im).tobytes(),im.tobytes())
    def test_to_rgb_drops_alpha(self):
        im=Image.new('RGBA',(3,2),(11,22,33,240));out=m.to_rgb(im)
        self.assertEqual(out.mode,'RGB');self.assertEqual(out.tobytes(),Image.new('RGB',(3,2),(11,22,33)).tobytes())
    def test_cleanup_cli_writes_evidence(self):
        src=self.root/'dusty.png';Image.new('RGBA',(4,4),(5,6,7,3)).save(src)
        buf=io.StringIO()
        with redirect_stdout(buf):
            rc=m.main(['cleanup',str(src),'--out',str(self.root/'clean.png'),'--evidence',str(self.root/'evidence.json')])
        self.assertEqual(rc,0);record=json.loads(buf.getvalue())
        self.assertEqual(record['before']['bbox'],[0,0,4,4]);self.assertIsNone(record['after']['bbox'])
        self.assertEqual(record['thresholds'],{'dust_below':8,'solid_from':224})
        self.assertEqual(record['output_sha256'],p.file_sha(self.root/'clean.png'))
        self.assertEqual(json.loads((self.root/'evidence.json').read_text()),record)
        with redirect_stdout(io.StringIO()):self.assertEqual(m.main(['cleanup',str(src),'--out',str(self.root/'clean.png')]),2)
    def test_cleanup_leaves_no_orphan_when_evidence_blocked(self):
        src=self.root/'dusty.png';Image.new('RGBA',(4,4),(5,6,7,3)).save(src)
        (self.root/'taken.json').write_text('{}')
        with self.assertRaises(ValueError):m.cleanup(src,self.root/'clean.png',evidence=self.root/'taken.json')
        self.assertFalse((self.root/'clean.png').exists())
        with self.assertRaises(OSError):m.cleanup(src,self.root/'clean2.png',evidence=self.root/'nodir/ev.json')
        self.assertFalse((self.root/'clean2.png').exists())
    def test_cleaned_frame_packs_without_edge_warning(self):
        im=Image.new('RGBA',(8,8),(0,0,0,0))
        for y in range(2,6):
            for x in range(2,6):im.putpixel((x,y),(200,10,10,255))
        im.putpixel((0,0),(0,0,0,3));im.save(self.root/'dusty.png')
        dusty={'id':'dusty','path':'dusty.png','sha256':p.file_sha(self.root/'dusty.png'),'duration_ms':80}
        fm={'schema_version':1,'canvas':[8,8],'anchor':[4,8],'clip':'dust','loop':True,'frames':[dusty]}
        self.assertTrue(any('touch logical frame edge' in w for w in m.atlas(fm,self.root,self.root/'dusty-pack')['qa']['warnings']))
        m.cleanup(self.root/'dusty.png',self.root/'clean.png')
        clean=dict(dusty,id='clean',path='clean.png',sha256=p.file_sha(self.root/'clean.png'))
        fm['frames']=[clean]
        result=m.atlas(fm,self.root,self.root/'clean-pack')
        self.assertFalse(any('touch logical frame edge' in w for w in result['qa']['warnings']))
        with Image.open(self.root/'clean-pack/atlas.png') as sheet:
            x,y,w,h=result['frames'][0]['region']
            self.assertEqual(sheet.crop((x,y,x+w,y+h)).getchannel('A').getbbox(),(2,2,6,6))


if __name__=='__main__':unittest.main()
