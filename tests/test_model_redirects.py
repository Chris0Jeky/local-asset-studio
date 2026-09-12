"""Redirect-policy fixtures use tiny local bytes behind logical provider HTTPS URLs."""
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPSHandler,Request,build_opener
from urllib.response import addinfourl

sys.path.insert(0,str(Path(__file__).parents[1]/'app'))
import download_contracts as contracts
import model_library as models


def public_resolver(host,port,**kwargs):
    return [(2,1,6,'',(f'93.184.216.{len(host)%200+1}',port))]


class LocalHttpsHandler(HTTPSHandler):
    """Route logical HTTPS hosts to the inert local server; production never gets this handler."""
    def __init__(self,port):self.port=port
    def https_open(self,req):
        parsed=urlparse(req.full_url);headers=dict(req.header_items());headers['Host']=parsed.netloc
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=req.timeout)
        connection.request(req.get_method(),parsed.path+('?' + parsed.query if parsed.query else ''),req.data,headers)
        response=connection.getresponse();wrapped=addinfourl(response,response.headers,req.full_url,response.status)
        wrapped.msg=response.reason
        return wrapped


class RedirectServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self):
        super().__init__(('127.0.0.1',0),RedirectHandler);self.routes={};self.hits=[]


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.hits.append((self.path,{key.lower():value for key,value in self.headers.items()}))
        status,headers,body=self.server.routes[self.path]
        self.send_response(status)
        for name,value in headers.items():self.send_header(name,value)
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass


class ModelRedirectTests(unittest.TestCase):
    def setUp(self):
        self.server=RedirectServer();self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def open(self,url,resolver=public_resolver,headers=None,max_redirects=contracts.MAX_DOWNLOAD_REDIRECTS):
        handler=contracts.DownloadRedirectHandler(contracts.download_source_provider(url),resolver,max_redirects)
        # Build directly only to configure a non-default redirect bound; the
        # production helper always installs its own policy handler.
        opener=build_opener(handler,LocalHttpsHandler(self.server.server_port))
        contracts.validate_download_url(url,resolver=resolver)
        return opener.open(Request(url,headers=headers or {}),timeout=60)

    def test_allowed_huggingface_cdn_hops_retain_range_and_drop_cross_host_headers(self):
        self.server.routes={
            '/start':(302,{'Location':'https://cdn-lfs-us-1.hf.co/edge'},b''),
            '/edge':(302,{'Location':'https://us.aws.cdn.hf.co/body'},b''),
            '/body':(200,{},b'inert'),
        }
        with self.open('https://huggingface.co/start',headers={
                'User-Agent':'LocalAssetStudio/1','Accept-Encoding':'identity','Range':'bytes=5-',
                'Authorization':'Bearer secret','Cookie':'session=secret','X-Diagnostic':'private'}) as response:
            self.assertEqual(response.read(),b'inert')
        self.assertEqual([path for path,_ in self.server.hits],['/start','/edge','/body'])
        final=self.server.hits[-1][1]
        self.assertEqual(final['range'],'bytes=5-');self.assertEqual(final['accept-encoding'],'identity')
        for forbidden in ('authorization','cookie','x-diagnostic'):
            self.assertNotIn(forbidden,final)

    def test_allowed_civitai_delivery_worker_hop(self):
        target='https://civitai-delivery-worker-prod.5ac0637cfd0766c97916cefa3764fbdf.r2.cloudflarestorage.com/body'
        self.server.routes={'/start':(307,{'Location':target},b''),'/body':(200,{},b'civitai inert')}
        with self.open('https://civitai.com/start') as response:self.assertEqual(response.read(),b'civitai inert')
        self.assertEqual([path for path,_ in self.server.hits],['/start','/body'])

    def test_forbidden_targets_are_rejected_before_contact(self):
        cases=[
            ('http://cdn-lfs-us-1.hf.co/body',public_resolver,'HTTPS'),
            ('https://127.0.0.1/body',public_resolver,'untrusted host'),
            ('https://user:pass@cdn-lfs-us-1.hf.co/body',public_resolver,'credentials'),
            ('https://cdn-lfs-us-1.hf.co:444/body',public_resolver,'port 443'),
            ('https://example.com/body',public_resolver,'untrusted host'),
            ('https://cdn-lfs-us-1.hf.co/body',lambda host,port,**kwargs:[(2,1,6,'',(('127.0.0.1' if host.startswith('cdn-lfs') else '93.184.216.34'),port))],'loopback'),
            ('https://cdn-lfs-us-1.hf.co/body',lambda host,port,**kwargs:[(2,1,6,'',(('10.0.0.8' if host.startswith('cdn-lfs') else '93.184.216.34'),port))],'private'),
        ]
        for index,(target,resolver,message) in enumerate(cases):
            with self.subTest(target=target):
                path=f'/reject-{index}';self.server.routes={path:(302,{'Location':target},b''),'/body':(200,{},b'bad')};self.server.hits=[]
                with self.assertRaisesRegex(ValueError,message):self.open('https://huggingface.co'+path,resolver=resolver)
                self.assertEqual([hit[0] for hit in self.server.hits],[path])

    def test_multicast_addresses_are_rejected_before_transport(self):
        for address in ('224.0.0.1','239.255.255.250','ff02::1'):
            with self.subTest(address=address):
                def resolver(host,port,**kwargs):return [(10,1,6,'',(address,port))]
                self.server.routes={'/start':(200,{},b'unexpected transport')};self.server.hits=[]
                with self.assertRaisesRegex(ValueError,'multicast'):
                    self.open('https://huggingface.co/start',resolver=resolver)
                self.assertEqual(self.server.hits,[])

    def test_cross_provider_redirect_and_unscoped_storage_hosts_are_refused(self):
        for target in (
            'https://civitai.com/api/download/models/1',
            'https://attacker.r2.cloudflarestorage.com/model',
            'https://other-bucket.f004.backblazeb2.com/model',
        ):
            with self.subTest(target=target):
                self.server.routes={'/start':(302,{'Location':target},b'')};self.server.hits=[]
                with self.assertRaisesRegex(ValueError,'untrusted host'):self.open('https://huggingface.co/start')
                self.assertEqual(len(self.server.hits),1)

    def test_loop_and_distinct_redirect_chain_are_bounded(self):
        self.server.routes={'/loop':(302,{'Location':'https://huggingface.co/loop'},b'')}
        with self.assertRaises(HTTPError) as caught:self.open('https://huggingface.co/loop')
        caught.exception.close()
        self.assertLessEqual(len(self.server.hits),contracts.MAX_DOWNLOAD_REDIRECTS+1)
        self.server.routes={f'/hop/{i}':(302,{'Location':f'https://huggingface.co/hop/{i+1}'},b'') for i in range(7)}
        self.server.routes['/hop/7']=(200,{},b'never');self.server.hits=[]
        with self.assertRaisesRegex(ValueError,'redirect limit'):self.open('https://huggingface.co/hop/0')
        self.assertEqual(len(self.server.hits),contracts.MAX_DOWNLOAD_REDIRECTS+1)

    def test_supported_provider_storage_hosts_are_explicit(self):
        allowed=(
            ('https://cdn-lfs-eu-1.hf.co/file','huggingface'),
            ('https://asia-southeast1.us.gcp.cdn.hf.co/file','huggingface'),
            ('https://b2.civitai.com/file/civitai-modelfiles/model/x','civitai'),
            ('https://civitai-delivery-worker-prod.5ac0637cfd0766c97916cefa3764fbdf.r2.cloudflarestorage.com/model/x','civitai'),
            ('https://s3.us-west-004.backblazeb2.com/civitai-modelfiles-b2/model/x','civitai'),
        )
        for url,provider in allowed:
            with self.subTest(url=url):self.assertEqual(contracts.validate_download_url(url,provider,public_resolver),provider)
        with self.assertRaisesRegex(ValueError,'untrusted host'):
            contracts.validate_download_url('https://s3.us-west-004.backblazeb2.com/other-bucket/model','civitai',public_resolver)
        with self.assertRaisesRegex(ValueError,'loopback'):
            contracts.validate_download_url('https://huggingface.co/model',resolver=lambda *args,**kwargs:[(2,1,6,'',('127.0.0.1',443))])


class RedirectInstallIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'models').mkdir();(self.root/'home/Downloads').mkdir(parents=True)
        self.body=b'0123456789 inert redirect fixture';self.asset={'id':'demo','file':'loras/demo.safetensors','bytes':len(self.body),
            'sha256':hashlib.sha256(self.body).hexdigest(),'url':'https://huggingface.co/start'}
        (self.root/'models/library.json').write_text(json.dumps({'assets':[self.asset]}));self.lib=models.ModelLibrary(self.root,self.root/'comfy')
        self.target=self.lib.destination(self.asset);self.target.parent.mkdir(parents=True);self.part=self.lib.partial_path(self.target)
        self.home=patch.object(Path,'home',return_value=self.root/'home');self.home.start();self.reserve=patch.object(models,'RESERVE_BYTES',0);self.reserve.start()
        self.server=RedirectServer();self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.reserve.stop();self.home.stop();self.temp.cleanup()
    def transport(self,resolver=public_resolver):
        handlers=(LocalHttpsHandler(self.server.server_port),)
        return lambda request,timeout=60:contracts.open_download(request,timeout,resolver,handlers)
    def receipt(self):return json.loads((self.lib.state/'demo.json').read_text())

    def test_allowed_redirect_completes_resume_and_receipt(self):
        offset=5;self.part.write_bytes(self.body[:offset]);size=len(self.body)
        self.server.routes={
            '/start':(302,{'Location':'https://cdn-lfs-us-1.hf.co/body'},b''),
            '/body':(206,{'Content-Range':f'bytes {offset}-{size-1}/{size}'},self.body[offset:]),
        }
        with patch.object(models,'urlopen',side_effect=self.transport()):receipt=self.lib.install('demo')
        self.assertEqual(self.target.read_bytes(),self.body);self.assertEqual(receipt['status'],'installed')
        self.assertEqual(self.server.hits[-1][1]['range'],f'bytes={offset}-')

    def test_refused_private_resolution_preserves_partial_and_failure_receipt(self):
        original=self.body[:5];self.part.write_bytes(original)
        self.server.routes={'/start':(302,{'Location':'https://cdn-lfs-us-1.hf.co/body'},b''),'/body':(200,{},b'bad')}
        def resolver(host,port,**kwargs):
            address='10.0.0.8' if host=='cdn-lfs-us-1.hf.co' else '93.184.216.34'
            return [(2,1,6,'',(address,port))]
        with patch.object(models,'urlopen',side_effect=self.transport(resolver)):
            with self.assertRaisesRegex(ValueError,'private'):self.lib.install('demo')
        self.assertEqual([path for path,_ in self.server.hits],['/start']);self.assertEqual(self.part.read_bytes(),original)
        self.assertFalse(self.target.exists());self.assertEqual(self.receipt()['bytes_done'],len(original));self.assertEqual(self.receipt()['status'],'failed')

    def test_complete_partial_still_requires_a_curated_source_without_dns_or_http(self):
        self.part.write_bytes(self.body);self.asset['url']='https://example.com/model';(self.root/'models/library.json').write_text(json.dumps({'assets':[self.asset]}))
        with patch.object(contracts.socket,'getaddrinfo') as resolver,patch.object(models,'urlopen') as request:
            # Outer gate: a missing file with no curated URL is refused before a lease or receipt exists.
            with self.assertRaisesRegex(ValueError,'copy this file in by hand'):self.lib.install('demo')
            self.assertFalse((self.lib.state/'install.lock').exists());self.assertFalse((self.lib.state/'demo.json').exists())
            # Inner gate, unchanged: the transfer itself still refuses the origin, with no DNS and no HTTP.
            with self.assertRaisesRegex(ValueError,'curated HTTPS model source'):self.lib._download(self.asset,self.target)
        resolver.assert_not_called();request.assert_not_called();self.assertEqual(self.part.read_bytes(),self.body);self.assertFalse(self.target.exists())


if __name__=='__main__':unittest.main()
