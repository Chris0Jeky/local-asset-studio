"""Existing evidence file ownership and real CLI integration for stream mode."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'app'))
import resource_receipts as receipts
import inference_trace_stream as stream_trace
from test_inference_trace_stream import event, wire


class EvidenceStreamTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(receipts, 'read_evidence_stream', None)),
                        'The existing evidence boundary has no incremental consumer yet')
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'trace.json';self.path.write_bytes(wire([event()]))

    def test_missing_consumer_refuses_before_open_or_whole_file_read(self):
        with patch.object(receipts.os, 'open', side_effect=AssertionError('no open')):
            with self.assertRaisesRegex(receipts.EvidenceError, '^stream_consumer_invalid$'):
                receipts.read_evidence_stream(self.path, 1024, None)

    def test_stream_result_matches_byte_reader_and_leaves_no_files(self):
        before=self.path.read_bytes()
        result=receipts.read_evidence_stream(self.path,1024,stream_trace.summarize_trace_stream)
        self.assertEqual(result['input_sha256'],hashlib.sha256(before).hexdigest())
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(list(self.path.parent.iterdir()),[self.path])
        self.assertEqual(receipts.read_evidence_file(self.path,1024),before)

    def test_incomplete_consumer_cannot_return_success(self):
        with self.assertRaisesRegex(receipts.EvidenceError,'^artifact_not_consumed$'):
            receipts.read_evidence_stream(self.path,1024,lambda stream: {'premature':stream.read(1)})

    def test_unbounded_oversized_and_boolean_read_requests_refuse(self):
        for count in (-1,65537,True):
            with self.subTest(count=count),self.assertRaisesRegex(receipts.EvidenceError,'^stream_read_invalid$'):
                receipts.read_evidence_stream(self.path,1024,lambda stream:stream.read(count))

    def test_zero_read_does_not_fabricate_eof(self):
        with self.assertRaisesRegex(receipts.EvidenceError,'^artifact_not_consumed$'):
            receipts.read_evidence_stream(self.path,1024,lambda stream:stream.read(0))

    def test_descriptor_closes_after_success_and_parse_failure(self):
        opened=[];fdopen=receipts.os.fdopen
        def track(*args,**kwargs):
            result=fdopen(*args,**kwargs);opened.append(result);return result
        with patch.object(receipts.os,'fdopen',track):
            receipts.read_evidence_stream(self.path,1024,stream_trace.summarize_trace_stream)
            self.path.write_bytes(b'{')
            with self.assertRaises(stream_trace.TraceError):
                receipts.read_evidence_stream(self.path,1024,stream_trace.summarize_trace_stream)
        self.assertEqual(len(opened),2)
        self.assertTrue(all(stream.closed for stream in opened))

    def test_source_replacement_after_parsing_invalidates_result(self):
        def consume(stream):
            result=stream_trace.summarize_trace_stream(stream)
            replacement=self.path.with_suffix('.new');replacement.write_bytes(self.path.read_bytes())
            os.replace(replacement,self.path)
            return result
        with self.assertRaisesRegex(receipts.EvidenceError,'^file_changed$'):
            receipts.read_evidence_stream(self.path,1024,consume)

    def test_growth_and_in_place_change_after_parsing_invalidate_result(self):
        for replacement in (wire([event(ts=9)]),wire([event()])+b' '):
            with self.subTest(replacement=replacement):
                self.path.write_bytes(wire([event()]))
                def consume(stream):
                    result=stream_trace.summarize_trace_stream(stream)
                    before=self.path.stat().st_mtime_ns
                    self.path.write_bytes(replacement)
                    later=before+1_000_000;os.utime(self.path,ns=(later,later))   # a real edit lands later; inside one Windows clock tick a same-length rewrite is invisible (#467)
                    return result
                with self.assertRaisesRegex(receipts.EvidenceError,'^file_changed$'):
                    receipts.read_evidence_stream(self.path,1024,consume)

    def test_bound_applies_to_actual_reads_when_source_grows(self):
        raw=self.path.read_bytes()
        def consume(stream):
            with self.path.open('ab') as file:file.write(b' ' * 1024)
            return stream.read(1024)
        with self.assertRaisesRegex(receipts.EvidenceError,'^artifact_too_large$'):
            receipts.read_evidence_stream(self.path,len(raw),consume)

    def test_consumer_read_error_is_payload_free(self):
        def consume(stream):raise OSError('CANARY/path')
        with self.assertRaisesRegex(receipts.EvidenceError,'^artifact_unreadable$'):
            receipts.read_evidence_stream(self.path,1024,consume)

    def test_oversized_file_refuses_before_consumer(self):
        with patch.object(stream_trace,'summarize_trace_stream',side_effect=AssertionError('no parse')) as consume:
            with self.assertRaisesRegex(receipts.EvidenceError,'^artifact_too_large$'):
                receipts.read_evidence_stream(self.path,1,consume)
        consume.assert_not_called()

    def test_symlink_remains_refused(self):
        link=self.path.with_suffix('.link')
        try:link.symlink_to(self.path)
        except OSError:self.skipTest('Symlink permission unavailable')
        with self.assertRaisesRegex(receipts.EvidenceError,'^file_not_regular$'):
            receipts.read_evidence_stream(link,1024,stream_trace.summarize_trace_stream)

    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX FIFO fixture')
    def test_fifo_refuses_without_opening_or_blocking(self):
        fifo=self.path.with_suffix('.fifo');os.mkfifo(fifo)
        with self.assertRaisesRegex(receipts.EvidenceError,'^file_not_regular$'):
            receipts.read_evidence_stream(fifo,1024,stream_trace.summarize_trace_stream)


class TraceStreamCliTests(unittest.TestCase):
    def invoke(self,path,*args):
        return subprocess.run([sys.executable,str(ROOT/'scripts/inspect-inference-trace.py'),str(path),*args],
                              cwd=ROOT,capture_output=True,text=True,timeout=20)

    def test_opt_in_larger_trace_default_refusal_and_stream_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trace.json'
            raw=wire([event(args={'padding':'x'*2000}) for _ in range(600)]);path.write_bytes(raw)
            default=self.invoke(path)
            self.assertEqual(default.returncode,2,default.stderr)
            self.assertEqual(json.loads(default.stdout)['code'],'artifact_too_large')
            streamed=self.invoke(path,'--stream','--sha256',hashlib.sha256(raw).hexdigest())
            self.assertEqual(streamed.returncode,0,streamed.stderr)
            result=json.loads(streamed.stdout)
            self.assertEqual(result['recognized_events'],600)
            self.assertEqual(result['input_bytes'],len(raw))
            self.assertFalse(result['causal_speedup_qualified'])
            self.assertEqual(list(path.parent.iterdir()),[path])
            self.assertEqual(path.read_bytes(),raw)

    def test_late_error_is_nonzero_without_partial_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'CANARY.json';path.write_bytes(wire([event()]*1000)+b'{')
            result=self.invoke(path,'--stream')
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(json.loads(result.stdout)['code'],'trace_json_invalid')
            self.assertNotIn('recognized_events',result.stdout)
            self.assertNotIn('CANARY',result.stdout+result.stderr)

    def test_help_and_abbreviated_stream_flag_do_not_launch_any_work(self):
        result=self.invoke('missing','--stre')
        self.assertEqual(result.returncode,2)
        self.assertIn('unrecognized arguments',result.stderr)


if __name__=='__main__':unittest.main()
