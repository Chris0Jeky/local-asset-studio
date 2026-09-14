"""Offline catalog traversal and inert loopback schema discovery; no Comfy runtime."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('validate_live_fixture',ROOT/'scripts/validate-live.py')
validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
SCHEMA={'Literal':{'input':{'required':{'value':['INT',{'min':0,'max':10}]}},'output':[]}}
GRAPH={'1':{'class_type':'Literal','inputs':{'value':3}}}


class CatalogValidationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);(self.root/'presets').mkdir();(self.root/'graphs').mkdir()
        self.presets=[{'id':'lab','graph':'graphs/lab.json','collection':'workflow-lab'},
                      {'id':'other','graph':'graphs/other.json','collection':'production-workspace'},
                      {'id':'uncollected','graph':'graphs/uncollected.json'},
                      {'id':'isolated','graph':'graphs/isolated.json','backend_id':'hidream'}]
        for preset in self.presets:(self.root/preset['graph']).write_text(json.dumps(GRAPH))
        self.catalog=self.root/'presets/catalog.json';self.catalog.write_text(json.dumps({'presets':self.presets}))
        self.snapshot=self.root/'object-info.json';self.snapshot.write_bytes(json.dumps(SCHEMA).encode())

    def run_cli(self,*args):
        out=io.StringIO();err=io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            code=validator.main(['--repo-root',str(self.root),'--object-info',str(self.snapshot),*args])
        return code,out.getvalue(),err.getvalue()

    def test_default_checks_all_collections_uncollected_and_backend_rows_without_network(self):
        with patch.object(validator,'build_opener',side_effect=AssertionError('Offline mode must not open the network')):
            code,out,err=self.run_cli('--json')
        self.assertEqual(code,0,err);report=json.loads(out)
        self.assertEqual(report['catalog_total'],4);self.assertEqual(report['selected'],4)
        self.assertEqual(report['passed'],4);self.assertEqual(report['failed'],0)
        self.assertEqual([r['preset_id'] for r in report['results']],[p['id'] for p in self.presets])
        self.assertEqual(report['schema_sha256'],hashlib.sha256(self.snapshot.read_bytes()).hexdigest())
        self.assertEqual(report['submissions'],0);self.assertFalse(report['inference_verified'])

    def test_collection_backend_and_exact_preset_filters_are_explicit(self):
        for args,ids in ((['--collection','workflow-lab'],['lab']),(['--backend','primary'],['lab','other','uncollected']),
                         (['--backend','hidream'],['isolated']),(['--preset','other','--preset','uncollected'],['other','uncollected'])):
            with self.subTest(args=args):
                code,out,err=self.run_cli('--json',*args);self.assertEqual(code,0,err)
                self.assertEqual([r['preset_id'] for r in json.loads(out)['results']],ids)

    def test_empty_or_unknown_selection_is_error_before_schema_read(self):
        for args in (['--collection','missing'],['--backend','missing'],['--preset','missing']):
            with self.subTest(args=args),patch.object(validator,'load_schema') as load:
                code,out,err=self.run_cli(*args)
            self.assertEqual(code,2);load.assert_not_called();self.assertEqual(out,'')
            self.assertEqual(json.loads(err)['submissions'],0)

    def test_failed_graph_does_not_hide_later_results(self):
        (self.root/self.presets[0]['graph']).write_text(json.dumps({'1':{'class_type':'Literal','inputs':{'value':99}}}))
        (self.root/self.presets[1]['graph']).unlink()
        code,out,err=self.run_cli('--json');report=json.loads(out)
        self.assertEqual(code,1,err);self.assertEqual(report['selected'],4);self.assertEqual(report['failed'],2)
        self.assertEqual(report['passed'],2);self.assertIn('Above input maximum',report['results'][0]['error'])
        self.assertEqual(report['results'][-1]['status'],'passed')

    def test_shared_checker_is_called_not_a_second_validator(self):
        with patch.object(validator.pipeline,'graph_check',wraps=validator.pipeline.graph_check) as check:
            report=validator.validate_catalog(self.root,self.presets,SCHEMA)
        self.assertEqual(check.call_count,4);self.assertEqual(report['passed'],4)
        for call in check.call_args_list:self.assertEqual(call.args,(GRAPH,SCHEMA))

    def test_catalog_paths_cannot_escape_root(self):
        outside=self.root.parent/(self.root.name+'-outside.json');outside.write_text(json.dumps(GRAPH));self.addCleanup(outside.unlink)
        bad=[{'id':'outside','graph':'../'+outside.name},{'id':'absolute','graph':str(outside)}]
        with patch.object(validator.pipeline,'graph_check') as check:report=validator.validate_catalog(self.root,bad,SCHEMA)
        self.assertEqual(report['failed'],2);check.assert_not_called()
        link=self.root/'graphs/link.json'
        try:link.symlink_to(outside)
        except OSError:return
        report=validator.validate_catalog(self.root,[{'id':'linked','graph':'graphs/link.json'}],SCHEMA)
        self.assertEqual(report['failed'],1)

    def test_duplicate_or_invalid_catalog_refuses_before_network(self):
        for presets in ([],[self.presets[0],self.presets[0]],['not-a-record'],[{'id':None}]):
            self.catalog.write_text(json.dumps({'presets':presets}))
            with self.subTest(presets=presets),patch.object(validator,'load_schema') as load:code,out,err=self.run_cli()
            self.assertEqual(code,2);load.assert_not_called()

    def test_schema_is_bounded_and_rejects_malformed_data(self):
        for raw in (b'[]',b'{}',b'{"A":null}',b'{"A":{},"A":{}}',b'{"A":{"x":NaN}}',b'\xff',b'{'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):validator.read_schema(io.BytesIO(raw))
        with patch.object(validator,'MAX_SCHEMA_BYTES',8),self.assertRaisesRegex(ValueError,'exceeds'):validator.read_schema(io.BytesIO(b'x'*9))

    def test_schema_read_error_is_json_and_creates_no_outputs(self):
        self.snapshot.write_bytes(b'not json');before=sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*'))
        code,out,err=self.run_cli('--json')
        self.assertEqual(code,2);self.assertEqual(out,'');self.assertIn('error',json.loads(err))
        self.assertEqual(before,sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')))

    def test_text_summary_explains_one_schema_and_no_inference(self):
        code,out,err=self.run_cli();self.assertEqual(code,0,err)
        self.assertIn('4 of 4',out);self.assertIn('no submissions',out)
        self.assertIn('One schema only',out);self.assertIn('not certified',out)

    def test_import_is_inert_and_does_not_parse_callers_arguments(self):
        command="""import importlib.util,sys,urllib.request
urllib.request.build_opener=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network at import'))
sys.path.insert(0,sys.argv[1]);spec=importlib.util.spec_from_file_location('inert_validator',sys.argv[2]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
print('imported')
"""
        result=subprocess.run([sys.executable,'-c',command,str(ROOT/'scripts'),str(ROOT/'scripts/validate-live.py'),'--not-a-real-arg'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'imported')

    def test_real_offline_cli_exit_status_and_json(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/validate-live.py'),'--repo-root',str(self.root),'--object-info',str(self.snapshot),'--json'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['selected'],4)

    def test_bad_backend_urls_refuse_before_opening_transport(self):
        for url in ('https://127.0.0.1:8188','http://localhost:8188','http://127.0.0.1:8188/x','http://other:8188','http://127.0.0.1:0'):
            with self.subTest(url=url),patch.object(validator,'build_opener') as opener,self.assertRaises(ValueError):validator.load_schema(comfy_url=url)
            opener.assert_not_called()

    def test_live_mode_uses_one_get_and_ignores_environment_proxy(self):
        routes=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                routes.append(('GET',self.path));payload=json.dumps(SCHEMA).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            def do_POST(self):routes.append(('POST',self.path));self.send_error(500)
            def log_message(self,*args):pass
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
        try:
            with patch.dict(os.environ,{'HTTP_PROXY':'http://127.0.0.1:1','http_proxy':'http://127.0.0.1:1','NO_PROXY':'','no_proxy':''}):
                data,digest=validator.load_schema(comfy_url=f'http://127.0.0.1:{http.server_port}')
            self.assertEqual(data,SCHEMA);self.assertEqual(routes,[('GET','/object_info')])
        finally:http.shutdown();http.server_close();worker.join(2)

    def test_redirects_are_not_followed_even_to_another_local_route(self):
        routes=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                routes.append(self.path);self.send_response(302);self.send_header('Location','/prompt');self.end_headers()
            def log_message(self,*args):pass
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
        try:
            with self.assertRaises(OSError) as caught:validator.load_schema(comfy_url=f'http://127.0.0.1:{http.server_port}')
            self.addCleanup(caught.exception.close)
            self.assertTrue(caught.exception.closed)
            self.assertEqual(routes,['/object_info'])
        finally:http.shutdown();http.server_close();worker.join(2)


if __name__=='__main__':unittest.main()
