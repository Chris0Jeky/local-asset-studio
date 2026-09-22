"""Synthetic PCM fixtures prove transport integrity, not voice quality."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import types
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
from action_stack_export import export_brief, validate_request, generate

def digest(raw): return hashlib.sha256(raw).hexdigest()
def request():
    text='Review the release. Check the evidence before approval.'
    value={'schema':'action-stack.request/v1','briefId':'a'*64,'actionId':'demo:a','narration':text,'narrationSha256':digest(text.encode()),'profileId':'kokoro-af-heart-control-v1','deliveryId':'calm-brief'}
    value['jobId']=digest('\n'.join(value[k] for k in ('briefId','narrationSha256','profileId','deliveryId')).encode())
    return value

def wav(rate=48000):
    stream=io.BytesIO()
    with wave.open(stream,'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(b'\x00\x00'*4800)
    return stream.getvalue()

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.calls=0;self.change=None
    def producer(self,source,value,base_url):
        self.calls+=1
        run=self.root/'_spoken'/'run';run.mkdir(parents=True,exist_ok=True)
        audio=run/'COMPRESSED.spoken.wav';audio.write_bytes(wav())
        receipt={'source':{'sha256':digest(source.read_bytes())},'output':{'sha256':digest(audio.read_bytes())},'producer_sha256':'b'*64}
        if self.change:self.change(source,audio,receipt)
        target=run/'receipt.json';target.write_text(json.dumps(receipt))
        return {'output':str(audio),'receipt':str(target)}
    def test_verified_publish_and_completed_reuse(self):
        self.assertFalse(export_brief(request(),self.root,producer=self.producer)['reused'])
        bundle=json.loads((self.root/'bundle.json').read_text())
        self.assertEqual(bundle['audioSha256'],digest((self.root/'audio.wav').read_bytes()))
        self.assertTrue(export_brief(request(),self.root,producer=self.producer)['reused'])
        self.assertEqual(self.calls,1)
    def test_changed_request_hash_rejected_before_generation(self):
        value=request();value['narration']='changed'
        with self.assertRaises(ValueError):export_brief(value,self.root,producer=self.producer)
        self.assertEqual(self.calls,0)
    def test_unknown_request_fields_rejected(self):
        value=request();value['command']='not executable'
        with self.assertRaises(ValueError):validate_request(value)
    def test_wrong_source_receipt_never_published(self):
        self.change=lambda s,a,r:r['source'].update(sha256='c'*64)
        with self.assertRaises(ValueError):export_brief(request(),self.root,producer=self.producer)
        self.assertFalse((self.root/'bundle.json').exists())
    def test_changed_source_during_generation_never_published(self):
        self.change=lambda s,a,r:s.write_text('changed')
        with self.assertRaises(ValueError):export_brief(request(),self.root,producer=self.producer)
        self.assertFalse((self.root/'bundle.json').exists())
    def test_wrong_audio_hash_never_published(self):
        self.change=lambda s,a,r:a.write_bytes(wav()+b'changed')
        with self.assertRaises(ValueError):export_brief(request(),self.root,producer=self.producer)
    def test_wrong_pcm_format_rejected_even_when_hash_matches(self):
        def alter(s,a,r):a.write_bytes(wav(24000));r['output']['sha256']=digest(a.read_bytes())
        self.change=alter
        with self.assertRaises(ValueError):export_brief(request(),self.root,producer=self.producer)
    def test_foreign_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(ValueError):
                export_brief(request(),self.root,producer=lambda *args:{'output':other+'/a.wav','receipt':other+'/receipt.json'})
    def test_corrupt_retained_audio_does_not_regenerate(self):
        export_brief(request(),self.root,producer=self.producer);(self.root/'audio.wav').write_bytes(b'bad')
        with self.assertRaises(ValueError):export_brief(request(),self.root,producer=self.producer)
        self.assertEqual(self.calls,1)
    def test_corrupt_retained_provenance_rejected_without_regeneration(self):
        export_brief(request(),self.root,producer=self.producer)
        p=self.root/'bundle.json';b=json.loads(p.read_text());b['receiptSha256']='_'*64;p.write_text(json.dumps(b))
        with self.assertRaises(ValueError):export_brief(request(),self.root,producer=self.producer)
        self.assertEqual(self.calls,1)
    def test_missing_original_receipt_blocks_completed_reuse(self):
        export_brief(request(),self.root,producer=self.producer)
        (self.root/'_spoken'/'run'/'receipt.json').unlink()
        with self.assertRaises((ValueError,OSError)):
            export_brief(request(),self.root,producer=self.producer)
        self.assertEqual(self.calls,1)
    def test_modified_original_receipt_blocks_completed_reuse(self):
        export_brief(request(),self.root,producer=self.producer)
        path=self.root/'_spoken'/'run'/'receipt.json'
        record=json.loads(path.read_text());record['producer_sha256']='c'*64
        path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):export_brief(request(),self.root,producer=self.producer)
        self.assertEqual(self.calls,1)
    def test_retained_producer_identity_must_match_the_original_receipt(self):
        export_brief(request(),self.root,producer=self.producer)
        path=self.root/'bundle.json';record=json.loads(path.read_text());record['producerSha256']='c'*64
        path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):export_brief(request(),self.root,producer=self.producer)
        self.assertEqual(self.calls,1)
    def test_projection_check_does_not_replace_a_retained_manifest(self):
        source=self.root/'COMPRESSED.md';source.write_text(request()['narration'])
        directory=self.root/'_spoken'/'run';directory.mkdir(parents=True)
        target=directory/'manifest.json';target.write_text('{"corrupt":true}')
        before=target.read_bytes();manifest={'segments':[{'text':request()['narration']}],'manifest_sha256':'c'*64}
        def unsafe_plan(*args,**kwargs):
            target.write_text(json.dumps(manifest));return {'manifest':str(target)}
        runtime=types.SimpleNamespace(plan=unsafe_plan,run=lambda *a,**k:{})
        compiler=types.SimpleNamespace(compile_source=lambda *a,**k:manifest,run_directory=lambda *a:directory)
        profiles=types.SimpleNamespace(resolve_profile=lambda *a:{'speaker_id':'af_heart'},require_executable=lambda *a:None)
        with patch.dict(sys.modules,{'spoken_brief_runtime':runtime,'spoken_brief_compile':compiler,'voice_profile':profiles}):
            with self.assertRaises(ValueError):generate(source,request(),'http://127.0.0.1:8191')
        self.assertEqual(target.read_bytes(),before)
    def projection_modules(self, text, run):
        manifest={'segments':[{'text':text}],'manifest_sha256':'c'*64}
        compiler=types.SimpleNamespace(compile_source=lambda *a,**k:manifest,run_directory=lambda *a:self.root/'_spoken'/'run')
        profiles=types.SimpleNamespace(resolve_profile=lambda *a:{'speaker_id':'af_heart'},require_executable=lambda *a:None)
        return {'spoken_brief_runtime':types.SimpleNamespace(run=run),'spoken_brief_compile':compiler,'voice_profile':profiles}
    def test_projection_mismatch_blocks_before_run(self):
        ran=[]
        with patch.dict(sys.modules,self.projection_modules('different',lambda *a,**k:ran.append(True))):
            with self.assertRaises(ValueError):generate(self.root/'COMPRESSED.md',request(),'http://127.0.0.1:8191')
        self.assertEqual(ran,[])
    def test_matching_projection_calls_existing_run_without_writing_a_manifest(self):
        ran=[]
        with patch.dict(sys.modules,self.projection_modules(request()['narration'],lambda *a,**k:ran.append(k) or {'ok':True})):
            self.assertEqual(generate(self.root/'COMPRESSED.md',request(),'http://127.0.0.1:8191'),{'ok':True})
        self.assertEqual(len(ran),1)
        self.assertFalse((self.root/'_spoken'/'run'/'manifest.json').exists())
    def test_cached_receipt_reference_cannot_escape_the_run(self):
        export_brief(request(),self.root,producer=self.producer)
        (self.root/'.receipt-reference.json').write_text(json.dumps({'receipt':'../foreign.json'}))
        with self.assertRaises(ValueError):export_brief(request(),self.root,producer=self.producer)
        self.assertEqual(self.calls,1)
    def test_lock_does_not_expire_or_repeat_an_uncertain_job(self):
        (self.root/'.action-stack-export.lock').write_text('previous process')
        with self.assertRaises(FileExistsError):export_brief(request(),self.root,producer=self.producer)
        self.assertEqual(self.calls,0)

if __name__=='__main__':unittest.main()
