import email.message
import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fetch_hf',ROOT/'scripts/fetch-hf.py')
hf=importlib.util.module_from_spec(spec);spec.loader.exec_module(hf)

class FakeResponse:
    def __init__(self,status,headers,body):
        self.status=status;self.headers=email.message.Message();self.body=body;self.offset=0
        for key,value in headers.items():self.headers[key]=value
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,size=-1):
        if self.offset>=len(self.body):return b''
        if size<0:size=len(self.body)-self.offset
        chunk=self.body[self.offset:self.offset+size];self.offset+=len(chunk);return chunk

class FakeOpener:
    def __init__(self,response):self.response=response;self.request=None
    def open(self,request,timeout=None):self.request=request;return self.response

class HuggingFaceResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
    def target(self):return self.root/'models/loras/demo.safetensors'
    def test_resume_appends_exact_range_and_publishes_atomically(self):
        body=b'prefix-rest';offset=len(b'prefix');target=self.target();part=target.with_suffix('.safetensors.part')
        part.parent.mkdir(parents=True);part.write_bytes(body[:offset])
        response=FakeResponse(206,{'Content-Range':f'bytes {offset}-{len(body)-1}/{len(body)}','Content-Length':str(len(body)-offset),'Content-Encoding':'identity'},body[offset:])
        opener=FakeOpener(response)
        size,digest,_=hf.download('https://huggingface.co/o/r/resolve/main/x.safetensors',target,len(body),hashlib.sha256(body).hexdigest(),resume=True,opener=opener)
        self.assertEqual((size,digest),(len(body),hashlib.sha256(body).hexdigest()))
        self.assertEqual(target.read_bytes(),body);self.assertFalse(part.exists())
        self.assertEqual(opener.request.get_header('Range'),f'bytes={offset}-')
        self.assertEqual(dict(opener.request.header_items())['Accept-encoding'],'identity')
    def test_complete_verified_partial_publishes_without_network(self):
        body=b'complete';target=self.target();part=target.with_suffix('.safetensors.part');part.parent.mkdir(parents=True);part.write_bytes(body)
        opener=FakeOpener(FakeResponse(416,{},b''))
        size,digest,_=hf.download('https://example.invalid/x',target,len(body),hashlib.sha256(body).hexdigest(),resume=True,opener=opener)
        self.assertEqual((size,digest),(len(body),hashlib.sha256(body).hexdigest()));self.assertIsNone(opener.request)
    def test_resume_rejects_missing_partial_before_network(self):
        opener=FakeOpener(FakeResponse(206,{},b''))
        with self.assertRaisesRegex(SystemExit,'requires an existing partial file'):
            hf.download('https://example.invalid/x',self.target(),8,'a'*64,resume=True,opener=opener)
        self.assertIsNone(opener.request)
    def test_resume_rejects_wrong_range_and_preserves_partial(self):
        body=b'prefix-rest';offset=len(b'prefix');target=self.target();part=target.with_suffix('.safetensors.part');part.parent.mkdir(parents=True);part.write_bytes(body[:offset])
        response=FakeResponse(206,{'Content-Range':f'bytes {offset+1}-{len(body)-1}/{len(body)}','Content-Length':str(len(body)-offset-1)},body[offset+1:])
        with self.assertRaisesRegex(SystemExit,'Content-Range mismatch'):
            hf.download('https://example.invalid/x',target,len(body),hashlib.sha256(body).hexdigest(),resume=True,opener=FakeOpener(response))
        self.assertEqual(part.read_bytes(),body[:offset]);self.assertFalse(target.exists())
    def test_resume_requires_pinned_size_and_sha_for_complete_partial(self):
        target=self.target();part=target.with_suffix('.safetensors.part');part.parent.mkdir(parents=True);part.write_bytes(b'abc')
        with self.assertRaisesRegex(SystemExit,'pinned file size'):
            hf.download('https://example.invalid/x',target,None,'a'*64,resume=True,opener=FakeOpener(FakeResponse(206,{},b'')))
        with self.assertRaisesRegex(SystemExit,'pinned SHA-256'):
            hf.download('https://example.invalid/x',target,3,None,resume=True,opener=FakeOpener(FakeResponse(206,{},b'')))
    def test_resume_rejects_ignored_range_compression_and_oversize(self):
        body=b'prefix-rest';offset=len(b'prefix');target=self.target();part=target.with_suffix('.safetensors.part')
        cases=[
            (FakeResponse(200,{'Content-Length':str(len(body)-offset)},body[offset:]),'HTTP 206'),
            (FakeResponse(206,{'Content-Range':f'bytes {offset}-{len(body)-1}/{len(body)}','Content-Length':str(len(body)-offset),'Content-Encoding':'gzip'},body[offset:]),'identity content encoding'),
        ]
        for response,pattern in cases:
            with self.subTest(pattern=pattern):
                target.unlink(missing_ok=True);part.parent.mkdir(parents=True,exist_ok=True);part.write_bytes(body[:offset])
                with self.assertRaisesRegex(SystemExit,pattern):
                    hf.download('https://example.invalid/x',target,len(body),hashlib.sha256(body).hexdigest(),resume=True,opener=FakeOpener(response))
                self.assertEqual(part.read_bytes(),body[:offset]);self.assertFalse(target.exists())
        part.write_bytes(body+b'extra');opener=FakeOpener(FakeResponse(206,{},b''))
        with self.assertRaisesRegex(SystemExit,'larger than the pinned size'):
            hf.download('https://example.invalid/x',target,len(body),hashlib.sha256(body).hexdigest(),resume=True,opener=opener)
        self.assertIsNone(opener.request)
    def test_resume_rejects_symlink_and_hardlink_partials(self):
        body=b'partial';target=self.target();part=target.with_suffix('.safetensors.part');part.parent.mkdir(parents=True)
        original=self.root/'original';original.write_bytes(body)
        try:part.symlink_to(original)
        except OSError:pass
        else:
            with self.assertRaisesRegex(SystemExit,'unshared regular partial'):
                hf.download('https://example.invalid/x',target,20,'a'*64,resume=True,opener=FakeOpener(FakeResponse(206,{},b'')))
            part.unlink()
        try:os.link(original,part)
        except OSError:self.skipTest('hard links are unavailable on this filesystem')
        with self.assertRaisesRegex(SystemExit,'unshared regular partial'):
            hf.download('https://example.invalid/x',target,20,'a'*64,resume=True,opener=FakeOpener(FakeResponse(206,{},b'')))
    def test_corrupted_complete_partial_is_retained(self):
        expected=b'complete';corrupt=b'corrupt!';target=self.target();part=target.with_suffix('.safetensors.part');part.parent.mkdir(parents=True);part.write_bytes(corrupt)
        opener=FakeOpener(FakeResponse(416,{},b''))
        with self.assertRaisesRegex(SystemExit,'SHA-256 mismatch for complete partial'):
            hf.download('https://example.invalid/x',target,len(expected),hashlib.sha256(expected).hexdigest(),resume=True,opener=opener)
        self.assertEqual(part.read_bytes(),corrupt);self.assertFalse(target.exists());self.assertIsNone(opener.request)
    def test_help_exposes_explicit_resume_without_network(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/fetch-hf.py'),'--help'],capture_output=True,text=True,check=False)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('--resume',result.stdout)
    def test_default_mode_still_refuses_existing_partial(self):
        target=self.target();part=target.with_suffix('.safetensors.part');part.parent.mkdir(parents=True);part.write_bytes(b'partial')
        with self.assertRaisesRegex(SystemExit,'already in place'):
            hf.download('https://example.invalid/x',target,8,'a'*64,opener=FakeOpener(FakeResponse(200,{},b'')))

if __name__=='__main__':unittest.main()
