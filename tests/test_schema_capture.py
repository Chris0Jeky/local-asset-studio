"""Backend-labelled schema evidence, exclusive publication and offline replay."""
import base64
import copy
from contextlib import redirect_stdout, redirect_stderr
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from loopback_transport_audit import LoopbackTransportAudit
import test_validate_live as fixtures

validator=fixtures.validator


class SchemaCaptureTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.CatalogValidationTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.output=self.root/'capture.json';self.routes=[];self.route_audit=None
        self.raw=json.dumps(fixtures.SCHEMA,indent=2).encode()+b'\n'
        case=self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                case.routes.append(('GET',self.path))
                self.send_response(200);self.send_header('Content-Length',str(len(case.raw)))
                self.end_headers();self.wfile.write(case.raw)
            def do_POST(self):case.routes.append(('POST',self.path));self.send_error(500)
            def log_message(self,*args):pass
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        def close():self.http.shutdown();self.http.server_close();self.thread.join(3)
        self.addCleanup(close);self.url=f'http://127.0.0.1:{self.http.server_port}'

    def cli(self,*args):
        out=io.StringIO();err=io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            try:code=validator.main(['--repo-root',str(self.root),'--json',*args])
            except SystemExit as exc:code=exc.code
        return code,out.getvalue(),err.getvalue()

    def capture(self,*args):
        result=self.cli('--backend','primary','--comfy-url',self.url,'--capture-schema',str(self.output),*args)
        self.assertIn(result[0],(0,1),result[2]);return result

    def route_diagnostic(self):
        return self.route_audit.describe(self.routes) if self.route_audit is not None else None

    def test_one_get_captures_exact_bytes_and_all_matching_backend_graphs(self):
        code,out,err=self.capture();report=json.loads(out);saved=json.loads(self.output.read_text())
        self.assertEqual(code,0,err);self.assertEqual(self.routes,[('GET','/object_info')])
        self.assertEqual(base64.b64decode(saved['schema_base64']),self.raw)
        self.assertEqual(saved['schema_sha256'],hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(saved['backend_id'],'primary');self.assertFalse(saved['backend_identity_verified'])
        self.assertEqual([r['preset_id'] for r in saved['bindings']],['lab','other','uncollected'])
        self.assertEqual(report['selected'],3);self.assertFalse(report['inference_verified'])
        self.assertEqual(report['submissions'],0);self.assertEqual(report['schema_capture'],str(self.output))

    def test_offline_replay_uses_recorded_backend_and_recomputes_validation(self):
        self.capture();before=self.output.read_bytes()
        with patch.object(validator,'build_opener',side_effect=AssertionError('Replay opened transport')):
            code,out,err=self.cli('--schema-snapshot',str(self.output))
        self.assertEqual(code,0,err);report=json.loads(out);self.assertEqual(report['selected'],3)
        self.assertEqual(report['schema_scope'],'backend-bound-snapshot');self.assertEqual(report['passed'],3)
        self.assertEqual(self.output.read_bytes(),before);self.assertEqual(len(self.routes),1)

    def test_failed_graph_is_retained_and_still_fails_on_replay(self):
        (self.root/'graphs/lab.json').write_text(json.dumps({'1':{'class_type':'Missing','inputs':{}}}))
        code,out,err=self.capture();self.assertEqual(code,1,err);self.assertEqual(json.loads(out)['failed'],1)
        code,out,err=self.cli('--schema-snapshot',str(self.output));self.assertEqual(code,1,err)
        self.assertEqual(json.loads(out)['failed'],1);self.assertEqual(len(self.routes),1)

    def test_capture_requires_backend_before_transport(self):
        code,out,err=self.cli('--comfy-url',self.url,'--capture-schema',str(self.output))
        self.assertEqual(code,2);self.assertIn('backend',err);self.assertEqual(self.routes,[])

    def test_capture_cannot_be_a_filtered_sample_or_relabel_a_raw_file(self):
        for args in (('--preset','lab'),('--collection','workflow-lab'),('--object-info',str(self.fixture.snapshot))):
            with self.subTest(args=args):
                code,out,err=self.cli('--backend','primary','--capture-schema',str(self.output),*args)
                self.assertEqual(code,2);self.assertFalse(self.output.exists());self.assertEqual(self.routes,[])

    def test_existing_target_is_preserved_before_any_get(self):
        self.output.write_bytes(b'previous evidence')
        code,out,err=self.cli('--backend','primary','--comfy-url',self.url,'--capture-schema',str(self.output))
        self.assertEqual(code,2);self.assertEqual(self.output.read_bytes(),b'previous evidence')
        self.assertEqual(self.routes,[])

    def test_missing_output_parent_does_not_fetch_or_create_directories(self):
        target=self.root/'missing/capture.json'
        code,out,err=self.cli('--backend','primary','--comfy-url',self.url,'--capture-schema',str(target))
        self.assertEqual(code,2);self.assertFalse(target.parent.exists());self.assertEqual(self.routes,[])

    def test_replay_cannot_relabel_backend_or_shrink_coverage(self):
        self.capture()
        for args in (('--backend','hidream'),('--preset','lab'),('--collection','workflow-lab')):
            with self.subTest(args=args):
                code,out,err=self.cli('--schema-snapshot',str(self.output),*args)
                self.assertEqual(code,2);self.assertEqual(out,'')
        self.assertEqual(len(self.routes),1)

    def test_changed_catalog_and_graph_are_stale_not_a_current_pass(self):
        self.capture();catalog=self.fixture.catalog.read_bytes();graph=self.root/'graphs/lab.json';original=graph.read_bytes()
        for target,replacement in ((self.fixture.catalog,catalog.replace(b'workflow-lab',b'changed')), (graph,original.replace(b'3',b'4'))):
            with self.subTest(target=target):
                before=target.read_bytes();target.write_bytes(replacement)
                code,out,err=self.cli('--schema-snapshot',str(self.output));target.write_bytes(before)
                self.assertEqual(code,2);self.assertIn('changed',err);self.assertEqual(out,'')
        self.assertEqual(len(self.routes),1)

    def test_corrupted_schema_and_manifest_are_rejected_without_network(self):
        self.capture();original=self.output.read_bytes()
        for key,value in (('backend_id','hidream'),('schema_base64','AAAA'),('schema_sha256','0'*64),('version',True)):
            with self.subTest(key=key):
                saved=json.loads(original);saved[key]=value;self.output.write_text(json.dumps(saved))
                code,out,err=self.cli('--schema-snapshot',str(self.output));self.assertEqual(code,2);self.assertEqual(out,'')
        self.assertEqual(len(self.routes),1)

    def test_truncated_duplicate_and_nonfinite_snapshot_json_is_rejected(self):
        for raw in (b'{',b'{"version":1,"version":1}',b'{"x":NaN}'):
            with self.subTest(raw=raw):
                self.output.write_bytes(raw);code,out,err=self.cli('--schema-snapshot',str(self.output))
                self.assertEqual(code,2);self.assertEqual(out,'');self.assertEqual(self.routes,[])

    def test_bad_schema_never_publishes_a_successful_capture(self):
        self.raw=b'{"Literal": null}'
        code,out,err=self.cli('--backend','primary','--comfy-url',self.url,'--capture-schema',str(self.output))
        self.assertEqual(code,2);self.assertFalse(self.output.exists());self.assertEqual(self.routes,[('GET','/object_info')])

    def test_symlink_target_is_preserved_without_fetch(self):
        original=self.root/'original';original.write_bytes(b'keep')
        try:self.output.symlink_to(original)
        except OSError:self.skipTest('symlink privilege unavailable')
        code,out,err=self.cli('--backend','primary','--comfy-url',self.url,'--capture-schema',str(self.output))
        self.assertEqual(code,2);self.assertTrue(self.output.is_symlink());self.assertEqual(original.read_bytes(),b'keep')
        self.assertEqual(self.routes,[])

    def test_read_and_write_limits_are_enforced(self):
        self.assertTrue(hasattr(validator,'MAX_CAPTURE_BYTES'),'No bounded snapshot parser')
        with patch.object(validator,'MAX_CAPTURE_BYTES',8):
            self.output.write_bytes(b' ' * 9);code,out,err=self.cli('--schema-snapshot',str(self.output))
            self.assertEqual(code,2);self.assertIn('limit',err)
            self.output.unlink();code,out,err=self.cli('--backend','primary','--comfy-url',self.url,'--capture-schema',str(self.output))
            self.assertEqual(code,2);self.assertFalse(self.output.exists())

    def test_exclusive_publication_preserves_a_concurrent_winner(self):
        self.assertTrue(hasattr(validator,'publish_capture'),'No exclusive snapshot publication')
        def collision(source,target):
            Path(target).write_bytes(b'concurrent capture');raise FileExistsError('captured concurrently')
        with patch.object(validator.os,'link',side_effect=collision):
            code,out,err=self.cli('--backend','primary','--comfy-url',self.url,'--capture-schema',str(self.output))
        self.assertEqual(code,2);self.assertEqual(self.output.read_bytes(),b'concurrent capture')
        self.assertIn('retained',err);self.assertEqual(self.routes,[('GET','/object_info')])

    def test_flush_failure_leaves_no_committed_snapshot(self):
        self.assertTrue(hasattr(validator,'publish_capture'),'No durable snapshot publication')
        with patch.object(validator.os,'fsync',side_effect=OSError('disk full')):
            code,out,err=self.cli('--backend','primary','--comfy-url',self.url,'--capture-schema',str(self.output))
        self.assertEqual(code,2);self.assertFalse(self.output.exists());self.assertIn('retained',err)

    def test_rehashed_manifest_still_requires_real_schema_digest_and_full_coverage(self):
        self.capture();original=self.output.read_bytes()
        for field,value in (('schema_sha256','0'*64),('bindings',[]),('bindings',[json.loads(original)['bindings'][0]])):
            with self.subTest(field=field,value=value):
                saved=json.loads(original);saved[field]=value
                saved['sha256']=validator.pipeline.sha({k:v for k,v in saved.items() if k!='sha256'})
                self.output.write_text(json.dumps(saved))
                code,out,err=self.cli('--schema-snapshot',str(self.output));self.assertEqual(code,2);self.assertEqual(out,'')
        self.assertEqual(len(self.routes),1)

    def test_historical_success_counts_are_not_authority_on_replay(self):
        self.capture();saved=json.loads(self.output.read_bytes());history=saved['capture_results']
        history['results'][0]={**saved['bindings'][0],'status':'invalid','error':'Earlier checker rejected this graph'}
        history.update(passed=2,failed=1)
        saved['sha256']=validator.pipeline.sha({k:v for k,v in saved.items() if k!='sha256'})
        self.output.write_text(json.dumps(saved))
        code,out,err=self.cli('--schema-snapshot',str(self.output))
        self.assertEqual(code,0,err);self.assertEqual(json.loads(out)['passed'],3);self.assertEqual(len(self.routes),1)

    def rehashed(self, saved):
        saved['sha256']=validator.pipeline.sha({k:v for k,v in saved.items() if k!='sha256'})
        self.output.write_text(json.dumps(saved))

    def assert_rehashed_refused(self, saved):
        self.rehashed(saved);before=self.output.read_bytes();diagnostic=self.route_diagnostic()
        with patch.object(validator,'build_opener',side_effect=AssertionError('No replay transport')):
            code,out,err=self.cli('--schema-snapshot',str(self.output))
        self.assertEqual(code,2,err or out);self.assertEqual(out,'')
        self.assertEqual(self.output.read_bytes(),before);self.assertEqual(len(self.routes),1,diagnostic)

    def test_replay_requires_provenance_and_historical_report_even_after_rehash(self):
        self.capture();original=json.loads(self.output.read_bytes())
        for field in ('captured_at','schema_source','capture_results','catalog_sha256'):
            with self.subTest(field=field):
                saved=copy.deepcopy(original);saved.pop(field);self.assert_rehashed_refused(saved)

    def test_capture_time_must_be_an_actual_utc_timestamp(self):
        self.capture();original=json.loads(self.output.read_bytes())
        for value in (None,True,1,'not a timestamp','2026-09-13','2026-09-13T20:00:00','2026-09-13T20:00:00+02:00'):
            with self.subTest(value=value):
                saved=copy.deepcopy(original);saved['captured_at']=value;self.assert_rehashed_refused(saved)
        saved=copy.deepcopy(original);saved['captured_at']='2026-09-13T20:00:00Z';self.rehashed(saved)
        code,out,err=self.cli('--schema-snapshot',str(self.output));self.assertEqual(code,0,err)

    def test_capture_source_must_be_a_numeric_loopback_object_info_endpoint(self):
        self.capture();original=json.loads(self.output.read_bytes())
        for value in (None,3,'http://other:8188/object_info',self.url+'/prompt',self.url+'/object_info?x=1'):
            with self.subTest(value=value):
                saved=copy.deepcopy(original);saved['schema_source']=value
                saved['capture_results']['schema_source']=value;self.assert_rehashed_refused(saved)

    def test_replay_checks_the_complete_schema_source_url(self):
        self.capture();original=json.loads(self.output.read_bytes())
        for suffix in ('/#/object_info','/?/object_info','/object_info#other','/object_info?other=1'):
            with self.subTest(suffix=suffix):
                saved=copy.deepcopy(original);source=self.url+suffix
                saved['schema_source']=source;saved['capture_results']['schema_source']=source
                self.assert_rehashed_refused(saved)

    def test_historical_row_status_excludes_contradictory_fields(self):
        self.capture();original=json.loads(self.output.read_bytes())
        for field,value in (('nodes',2),('nodes',0),('static_topology','passed'),
                            ('node_snapshot_checked',True),('node_snapshot_checked',False)):
            with self.subTest(invalid_field=field,value=value):
                saved=copy.deepcopy(original);report=saved['capture_results']
                report['results'][0]={**saved['bindings'][0],'status':'invalid',
                                      'error':'Earlier failure','inference_verified':False,field:value}
                report.update(passed=2,failed=1);self.assert_rehashed_refused(saved)
        for error in ('Earlier failure','',None):
            with self.subTest(passed_error=error):
                saved=copy.deepcopy(original);saved['capture_results']['results'][0]['error']=error
                self.assert_rehashed_refused(saved)

    def test_historical_report_requires_all_contract_fields_and_valid_shape(self):
        audit=LoopbackTransportAudit(host='127.0.0.1',port=self.http.server_port,max_calls=16,max_frames=16)
        with audit:
            self.route_audit=audit
            try:
                self.capture();original=json.loads(self.output.read_bytes())
                for field in original['capture_results']:
                    with self.subTest(missing=field):
                        saved=copy.deepcopy(original);saved['capture_results'].pop(field);self.assert_rehashed_refused(saved)
                for field,value in (('selected',True),('passed','3'),('passed',999),('failed',-1),('catalog_total',False),('results',{})):
                    with self.subTest(field=field,value=value):
                        saved=copy.deepcopy(original);saved['capture_results'][field]=value;self.assert_rehashed_refused(saved)
            finally:self.route_audit=None

    def test_historical_report_extra_connection_names_same_execution_caller(self):
        from urllib.request import urlopen
        audit=LoopbackTransportAudit(host='127.0.0.1',port=self.http.server_port,max_calls=16,max_frames=16)
        with audit:
            self.route_audit=audit
            try:
                self.capture()
                with urlopen(self.url+'/object_info',timeout=2) as response:response.read()
                saved=json.loads(self.output.read_bytes());saved['capture_results'].pop('selected')
                with self.assertRaises(AssertionError) as caught:self.assert_rehashed_refused(saved)
            finally:self.route_audit=None
        message=str(caught.exception)
        self.assertIn('"observed":2',message)
        self.assertIn('test_historical_report_extra_connection_names_same_execution_caller',message)

    def test_duplicate_identity_and_verification_claims_must_agree(self):
        self.capture();original=json.loads(self.output.read_bytes())
        for field,value in (('backend_id','hidream'),('schema_sha256','0'*64),('schema_source',self.url+'/changed'),
                            ('backend_identity_verified',True),('inference_verified',True),('submissions',1),
                            ('schema_scope','all-backends'),('scope','inference'),('selected',2),('catalog_total',999)):
            with self.subTest(field=field):
                saved=copy.deepcopy(original);saved['capture_results'][field]=value;self.assert_rehashed_refused(saved)

    def test_historical_rows_require_matching_bindings_and_static_only_checks(self):
        self.capture();original=json.loads(self.output.read_bytes())
        for field,value in (('preset_id','other'),('backend_id','hidream'),('graph','graphs/changed.json'),
                            ('graph_sha256','0'*64),('status','invented'),('nodes',True),
                            ('node_snapshot_checked',False),('inference_verified',True),('static_topology','inferred')):
            with self.subTest(field=field):
                saved=copy.deepcopy(original);saved['capture_results']['results'][0][field]=value
                self.assert_rehashed_refused(saved)
        for field in original['capture_results']['results'][0]:
            with self.subTest(missing_row_field=field):
                saved=copy.deepcopy(original);saved['capture_results']['results'][0].pop(field)
                self.assert_rehashed_refused(saved)

    def test_missing_graph_is_an_explicit_failed_result_not_silently_omitted(self):
        (self.root/'graphs/lab.json').unlink();code,out,err=self.capture()
        self.assertEqual(code,1,err);self.assertEqual(json.loads(out)['selected'],3)
        saved=json.loads(self.output.read_bytes());self.assertIsNone(saved['bindings'][0]['graph_sha256'])
        code,out,err=self.cli('--schema-snapshot',str(self.output))
        self.assertEqual(code,1,err);self.assertEqual(json.loads(out)['failed'],1)

    def test_non_loopback_capture_refuses_without_transport(self):
        with patch.object(validator,'build_opener',side_effect=AssertionError('No transport')):
            code,out,err=self.cli('--backend','primary','--comfy-url','https://example.com','--capture-schema',str(self.output))
        self.assertEqual(code,2);self.assertIn('Managed backend URL',err);self.assertFalse(self.output.exists());self.assertEqual(self.routes,[])

    def test_two_real_publishers_cannot_replace_each_other(self):
        real_link=os.link;barrier=threading.Barrier(2);results=[]
        def link(source,target):barrier.wait(timeout=3);return real_link(source,target)
        def publish(number):
            try:validator.publish_capture(self.output,{'publisher':number});results.append(('ok',number))
            except ValueError:results.append(('refused',number))
        with patch.object(validator.os,'link',side_effect=link):
            threads=[threading.Thread(target=publish,args=(i,)) for i in range(2)]
            for thread in threads:thread.start()
            for thread in threads:thread.join(5);self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(r[0] for r in results),['ok','refused'])
        winner=next(i for state,i in results if state=='ok')
        self.assertEqual(json.loads(self.output.read_bytes()),{'publisher':winner});self.assertEqual(self.routes,[])

    def test_real_subprocess_replays_offline(self):
        self.capture()
        result=subprocess.run([sys.executable,str(fixtures.ROOT/'scripts/validate-live.py'),'--repo-root',str(self.root),
                               '--schema-snapshot',str(self.output),'--json'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['selected'],3)
        self.assertEqual(len(self.routes),1)


if __name__=='__main__':unittest.main()