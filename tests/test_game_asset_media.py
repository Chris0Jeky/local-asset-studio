import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
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


if __name__=='__main__':unittest.main()
