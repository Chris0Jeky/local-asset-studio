"""Real loopback Handler checks; Studio worker and Comfy transport stay inert."""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import socket
import threading
import unittest

import test_production as fixtures
from http_refusal_transport import atomic_json_post
from test_server import FakeStudio, server


class RecoveryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ProductionTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.studio=FakeStudio(self.fixture.root,[])
        self.project=self.studio.production.create(self.fixture.intent(max_seconds=60));self.identifier=self.project['id']
        self.studio.production.start(self.identifier);self.studio.production._mutate(self.identifier,status='stopped')
        self.job=self.studio.jobs[self.studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]
        self.job.update(status='uncertain',pending_submission={});self.studio._save(self.job)
        self.fixture.patches[0].stop()  # Only the fake Studio worker was suppressed.
        handler=type('RecoveryHandler',(server.Handler,),{'studio':self.studio})
        self.http=ThreadingHTTPServer(('127.0.0.1',0),handler)
        self.worker=threading.Thread(target=self.http.serve_forever,daemon=True);self.worker.start()
        self.addCleanup(self.close)
    def close(self):
        self.http.shutdown();self.http.server_close();self.worker.join(2)
    def request(self,path,payload=None,headers=None,method='POST'):
        connection=HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            options={'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json',**(headers or {})}
            connection.request(method,path,json.dumps(payload),options)
            if connection.sock:
                try:connection.sock.shutdown(socket.SHUT_WR)
                except OSError:pass  # Early rejection may have already closed the peer.
            response=connection.getresponse();return response.status,json.loads(response.read())
        finally:connection.close()
    def test_abandon_requires_explicit_unknown_ack_and_retains_public_evidence(self):
        route=f"/api/jobs/{self.job['id']}/abandon"
        self.assertEqual(self.request(route,{'reason':'Keep receipt'})[0],400)
        status,data=self.request(route,{'reason':'Keep receipt','acknowledge_unknown':True})
        self.assertEqual(status,200);self.assertEqual(data['status'],'abandoned')
        self.assertTrue(data['has_pending_submission']);self.assertNotIn('pending_submission',data)
        self.assertEqual(self.job['pending_submission'],{});self.assertEqual(self.studio.requests,[])
        self.assertEqual(self.studio.production.get(self.identifier)['budget']['reserved'],2)
        self.assertEqual(self.request(route,{'reason':'Keep receipt','acknowledge_unknown':True})[1],data)
    def test_commands_keep_existing_host_and_origin_guards(self):
        for route,payload in ((f"/api/jobs/{self.job['id']}/abandon",{'reason':'Keep','acknowledge_unknown':True}),
                              (f'/api/production/{self.identifier}/extend-time',{'reason':'Finish','expected_revision':0,'seconds':60})):
            for headers in ({'Host':'evil.invalid'},{'Origin':'https://evil.invalid'},{'Origin':'null'}):
                options={'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191',**headers}
                with self.subTest(route=route,headers=headers):self.assertEqual(atomic_json_post(self.http.server_port,route,json.dumps(payload).encode(),host=options['Host'],origin=options['Origin'])[0],403)
        self.assertEqual(self.job['status'],'uncertain');self.assertEqual(self.studio.requests,[])
    def test_extension_conflict_and_rejection_do_not_enqueue(self):
        route=f'/api/production/{self.identifier}/extend-time';queued=self.studio.queue.qsize()
        payload={'reason':'Finish reserved candidate','expected_revision':0,'seconds':60}
        status,data=self.request(route,payload);self.assertEqual(status,200)
        self.assertEqual(data['state']['time_budget']['limit_seconds'],120)
        self.assertEqual(data['state']['status'],'stopped');self.assertEqual(data['budget']['reserved'],2)
        self.assertEqual(self.request(route,payload)[0],400)
        self.assertEqual(self.studio.queue.qsize(),queued);self.assertEqual(self.studio.requests,[])
    def test_bad_bodies_and_route_shapes_fail_without_mutations(self):
        for route in (f"/api/jobs/{self.job['id']}/abandon",f'/api/production/{self.identifier}/extend-time'):
            for value in (None,[],True,'not a command'):
                with self.subTest(route=route,value=value):self.assertEqual(self.request(route,value)[0],400)
            bad=route.rsplit('/',1)[0]+'/extra/'+route.rsplit('/',1)[1]
            self.assertEqual(atomic_json_post(self.http.server_port,bad,json.dumps({}).encode())[0],400)
        self.assertEqual(self.job['status'],'uncertain');self.assertEqual(self.studio.requests,[])
