import copy
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.append(str(ROOT/'scripts'))
from studio_av import project as p
from studio_av.render import compile_project,render,inspect_wav,validate_media
try:import PIL;HAS_PIL=True
except ImportError:HAS_PIL=False

@unittest.skipUnless(HAS_PIL,'Pillow needed only for procedural test fixtures')
class AVTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from studio_av_demo import create
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)/'fixture';cls.base=create(cls.root)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):self.doc=copy.deepcopy(self.base)
    def test_valid_layout(self):
        result=p.validate(self.doc,self.root);self.assertEqual(result['frames'],144);self.assertEqual(result['samples'],288000)
        self.assertEqual([s['start_frame'] for s in result['shots']],[0,48,96])
    def test_unknown_fields(self):
        self.doc['shell']='bad'
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_nonfinite(self):
        self.doc['master_gain_db']=float('nan')
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_bool_number(self):
        self.doc['shots'][0]['frames']=True
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_bad_rate(self):
        self.doc['sample_rate']=44100
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_frame_cap(self):
        self.doc['shots'][0]['frames']=7000
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_duplicate_clip(self):
        self.doc['audio'][0]['id']='shot0'
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_first_transition(self):
        self.doc['shots'][0]['transition_frames']=1
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_transition_consumes_shot(self):
        self.doc['shots'][1]['transition_frames']=60
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_wrong_media_kind(self):
        self.doc['shots'][0]['asset']='music'
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_bad_overlay(self):
        self.doc['overlays'][0]['x']=630
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_fade_overlaps(self):
        self.doc['audio'][0]['fade_in']=288000
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_audio_past_end(self):
        self.doc['audio'][0]['start_sample']=1
        with self.assertRaises(ValueError):p.validate(self.doc)
    def test_invalid_paths(self):
        for name in ('../x','/x','a//b','a/./b','C:\\secret','https://host/a'):
            with self.assertRaises(ValueError):p.safe_path(self.root,name,False)
    def test_symlink_escape(self):
        path=Path(self.tmp.name)/'outside';path.write_text('outside')
        link=self.root/'escaped'
        try:link.symlink_to(path)
        except OSError:self.skipTest('Symlinks not supported')
        with self.assertRaises(ValueError):p.safe_path(self.root,'escaped')
    def test_hash_mismatch(self):
        self.doc['assets']['music']['sha256']='0'*64
        with self.assertRaises(ValueError):p.validate(self.doc,self.root)
    def test_edit_is_immutable(self):
        before=p.digest(self.doc);r=p.edit(self.doc,before,'audio','music-clip','gain_db',-24)
        self.assertEqual(p.digest(self.doc),before);self.assertNotEqual(r['revision'],before)
        self.assertEqual(r['operation']['before'],-12)
    def test_stale_edit(self):
        with self.assertRaises(ValueError):p.edit(self.doc,'wrong','audio','music-clip','gain_db',-24)
    def test_unsupported_edit(self):
        with self.assertRaises(ValueError):p.edit(self.doc,p.digest(self.doc),'audio','music-clip','asset','fx')
    def test_no_overwrite(self):
        path=self.root/'unique.json';p.write_new(path,{})
        with self.assertRaises(FileExistsError):p.write_new(path,{})
    def test_duplicate_json(self):
        path=self.root/'bad.json';path.write_text('{"a":1,"a":2}')
        with self.assertRaises(ValueError):p.read_json(path)
    def test_compile_no_execution(self):
        r=compile_project(self.doc,self.root);self.assertIn('xfade=transition=fade',r['filter_complex'])
        self.assertIn('normalize=0',r['filter_complex']);self.assertFalse(r['gpu_required'])
    def test_audio_qc(self):
        report=inspect_wav(self.root/'media/music.wav');self.assertEqual(report['samples'],288000);self.assertFalse(report['near_or_at_clipping'])
    def test_clipping_detection(self):
        path=self.root/'clip.wav'
        with wave.open(str(path),'wb') as w:w.setparams((1,2,48000,0,'NONE',''));w.writeframes(struct.pack('<hhh',32767,-32768,0))
        r=inspect_wav(path);self.assertEqual(r['full_scale_sample_count'],[2])
    def test_silence_null_db(self):
        path=self.root/'silence.wav'
        with wave.open(str(path),'wb') as w:w.setparams((1,2,48000,0,'NONE',''));w.writeframes(b'\0'*100)
        self.assertEqual(inspect_wav(path)['sample_peak_dbfs'],[None])
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg not installed')
    def test_real_render(self):
        result=render(self.doc,self.root,self.root/'render-dissolves')
        self.assertEqual(result['audio_qc']['samples'],288000);self.assertFalse(result['generation_performed'])
        # Decode frame count, not only a container duration.
        data=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames','-of','csv=p=0',str(self.root/'render-dissolves/preview.mp4')],capture_output=True,text=True,check=True)
        self.assertEqual(int(data.stdout.strip()),144)
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg not installed')
    def test_real_cut_silent(self):
        self.doc['shots']=self.doc['shots'][:2]
        self.doc['shots'][1]['transition_frames']=0;self.doc['overlays']=[];self.doc['audio']=[]
        result=render(self.doc,self.root,self.root/'render-cuts')
        self.assertEqual(result['frames_expected'],120);self.assertEqual(result['audio_qc']['sample_peak_dbfs'],[None,None])
    @unittest.skipUnless(shutil.which('ffprobe'),'FFprobe not installed')
    def test_source_too_short(self):
        self.doc['audio'][0]['source_sample']=20
        with self.assertRaises(ValueError):validate_media(self.doc,self.root)

class BlenderContractTests(unittest.TestCase):
    def test_narrow_operations(self):
        sys.path.insert(0,str(ROOT/'integrations/blender'));from av_job import validate_job
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(validate_job({'operation':'inspect_scene','report':'report.json'},tmp)['operation'],'inspect_scene')
            for j in ({'operation':'eval','report':'r.json'}, {'operation':'render_frame','frame':True,'output':'x.png','report':'r.json'}, {'operation':'inspect_scene','report':'../r.json'}):
                with self.assertRaises(ValueError):validate_job(j,tmp)

if __name__=='__main__':unittest.main()
