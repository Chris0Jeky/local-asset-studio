"""Native output faults must not be confirmed by an audio/container duration."""
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from studio_av import project
rendering=importlib.import_module('studio_av.render')


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg not installed')
class OutputVideoVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_tmp=tempfile.TemporaryDirectory();cls.source=Path(cls.source_tmp.name)/'source.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x64:r=24:d=3',
                        '-c:v','libx264','-pix_fmt','yuv420p',str(cls.source)],check=True)

    @classmethod
    def tearDownClass(cls):cls.source_tmp.cleanup()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        shutil.copyfile(self.source,self.root/'source.mp4')
        self.doc={'schema_version':1,'name':'Output verification','fps':[24,1],'size':[64,64],
                  'sample_rate':48000,'master_gain_db':0,
                  'assets':{'clip':{'path':'source.mp4','kind':'video','sha256':project.file_hash(self.root/'source.mp4')}},
                  'shots':[{'id':'shot','asset':'clip','source_in':0,'frames':72,'transition_frames':0}],
                  'audio':[],'overlays':[]}

    def inspect_output(self,path):
        result=subprocess.run(['ffprobe','-v','error','-count_frames','-show_entries',
                               'format=duration:stream=codec_type,duration,nb_read_frames','-of','json',str(path)],
                              capture_output=True,text=True,check=True,timeout=20)
        return json.loads(result.stdout)

    def test_short_sparse_and_sped_up_picture_never_completes_on_audio_duration(self):
        original=rendering._run_owned
        cases=(('short',24,1,24,'frame count'),('sparse',8,3,24,'frame count'),
               ('sped-up',48,1.5,72,'duration'))
        for name,rate,duration,decoded,refusal in cases:
            with self.subTest(name=name):
                out=self.root/name
                def replace_picture(command,log_path,timeout,cancel):
                    original(command,log_path,timeout,cancel)
                    if log_path.name=='ffmpeg.log':
                        fault=log_path.parent/'fault-picture.mp4'
                        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
                                        f'color=c=red:s=64x64:r={rate}:d={duration}',
                                        '-c:v','libx264','-pix_fmt','yuv420p',str(fault)],check=True)
                        fault.replace(log_path.parent/'picture.mp4')
                with mock.patch.object(rendering,'_run_owned',side_effect=replace_picture):
                    with self.assertRaisesRegex(ValueError,'Output video '+refusal+' mismatch'):
                        rendering.render(self.doc,self.root,out)
                observed=self.inspect_output(out/'preview.mp4')
                video=next(s for s in observed['streams'] if s['codec_type']=='video')
                self.assertEqual(int(video['nb_read_frames']),decoded)
                self.assertAlmostEqual(float(video['duration']),duration,places=3)
                self.assertAlmostEqual(float(observed['format']['duration']),3,places=3)
                self.assertTrue((out/'.incomplete').is_file())
                self.assertFalse((out/'receipt.json').exists())
                self.assertTrue((out/'render-plan.json').is_file())
                self.assertTrue((out/'ffmpeg.log').is_file());self.assertTrue((out/'mux.log').is_file())
                self.assertEqual(project.file_hash(self.root/'source.mp4'),self.doc['assets']['clip']['sha256'])

    def test_unavailable_decoded_frame_count_keeps_render_incomplete(self):
        original=rendering.probe;out=self.root/'unknown-frame-count'
        def no_decoded_count(path,kind,*args,**kwargs):
            result=original(path,kind,*args,**kwargs)
            if Path(path).name=='preview.mp4':
                for stream in result['streams']:stream.pop('nb_read_frames',None)
            return result
        with mock.patch.object(rendering,'probe',side_effect=no_decoded_count):
            with self.assertRaisesRegex(ValueError,'Output video frame count mismatch'):
                rendering.render(self.doc,self.root,out)
        self.assertTrue((out/'.incomplete').is_file());self.assertFalse((out/'receipt.json').exists())

    def test_correct_integer_and_fractional_rate_previews_complete(self):
        for fps,frames in (([24,1],72),([30000,1001],30)):
            with self.subTest(fps=fps):
                self.doc['fps']=fps;self.doc['shots'][0]['frames']=frames
                out=self.root/('valid-'+str(fps[0]));receipt=rendering.render(self.doc,self.root,out)
                observed=self.inspect_output(out/'preview.mp4')
                video=next(s for s in observed['streams'] if s['codec_type']=='video')
                self.assertEqual(int(video['nb_read_frames']),frames)
                self.assertAlmostEqual(float(video['duration']),frames*fps[1]/fps[0],places=5)
                self.assertEqual(receipt['frames_expected'],frames)
                self.assertTrue((out/'receipt.json').is_file());self.assertFalse((out/'.incomplete').exists())


if __name__=='__main__':unittest.main()
