"""SDK/CLI history reads use the existing routes, without sockets or generation."""
import copy
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import test_recipe_shortlist_apply as fixture
from workspace import WorkspaceError
from studio_workflow.client import Client, ClientError
from studio_workflow.core import canonical, digest
from studio_workflow.sdk import WorkflowClient
from studio_workflow.setup_draft_client import SetupDraftClient, UnknownSetupOutcome, main
from studio_workflow.setup_draft_http import route
from studio_workflow.setup_drafts import PREFIX, SetupError
from studio_workflow.setup_history import FLAGS, MAX_READ_BYTES


class RouteClient:
    def __init__(self, studio):self.studio=studio;self.calls=[]
    def request(self, path, body=None):
        self.calls.append((path,body))
        if body is not None:raise AssertionError('History must use GET')
        try:return route(path,None,self.studio)
        except (SetupError,WorkspaceError) as exc:
            raw=canonical(exc.result() if isinstance(exc,SetupError) else {'code':exc.code,'error':str(exc),'generation_submitted':False})
            raise HTTPError(path,exc.status,str(exc),{'Content-Length':str(len(raw))},io.BytesIO(raw)) from exc


class ReviewedSetupHistoryClientTests(unittest.TestCase):
    store=fixture.SetupApplyTests.store
    command=fixture.SetupApplyTests.command
    create=fixture.SetupApplyTests.create

    def setUp(self):
        fixture.SetupApplyTests.setUp(self)
        self.key=self.create()['draft_id']
        for revision in (2,3):
            draft=copy.deepcopy(self.before);draft['recipe']['controls']['positive']='Revision '+str(revision)
            self.command('replace',request_id='history-'+str(revision),draft_id=self.key,expected_revision=revision-1,draft=draft)
        self.transport=RouteClient(self.s);self.client=SetupDraftClient(self.transport.request)

    def page(self, **options):return self.client.history(self.key,workspace_id=self.scope,**options)
    def compare(self, **options):return self.client.compare(self.key,1,3,workspace_id=self.scope,**options)
    def export(self, **options):return self.client.export_revision(self.key,1,workspace_id=self.scope,**options)
    def dump(self):
        with self.s.assets.connection() as db:return list(db.iterdump())

    def test_sdk_namespace_pages_compares_and_exports_without_mutation(self):
        sdk=WorkflowClient();sdk.request=self.transport.request;before=self.dump()
        page=sdk.setup_drafts.history(self.key,workspace_id=self.scope,limit=2)
        self.assertEqual([r['revision'] for r in page['revisions']],[3,2])
        last=sdk.setup_drafts.history(self.key,workspace_id=self.scope,limit=2,
                                     before_revision=page['next_before_revision'],expected_head=page['head_revision'])
        self.assertEqual([r['revision'] for r in last['revisions']],[1]);self.assertIsNone(last['next_before_revision'])
        comparison=sdk.setup_drafts.compare(self.key,1,3,workspace_id=self.scope,expected_head=3)
        self.assertTrue(next(s for s in comparison['sections'] if s['section']=='wording')['changed'])
        exported=sdk.setup_drafts.export_revision(self.key,1,workspace_id=self.scope,expected_head=3)
        self.assertEqual(exported['export']['draft'],self.before)
        self.assertEqual(exported['export_sha256'],digest(exported['export']))
        self.assertEqual(exported['export_json'].encode(),canonical(exported['export']))
        for result in (page,last,comparison,exported):
            self.assertEqual(result['workspace_id'],self.scope)
            for field,value in FLAGS.items():self.assertIs(result[field],value)
        self.assertEqual(self.dump(),before);self.assertEqual(self.s.upload_count,0)
        self.assertTrue(all(body is None for _,body in self.transport.calls))

    def test_queries_preserve_exact_workspace_revisions_and_head(self):
        self.page(limit=1,before_revision=3,expected_head=3);self.compare(expected_head=3);self.export(expected_head=3)
        for (path,body),action,values in zip(self.transport.calls,('history','compare','export'),
                ({'limit':'1','before_revision':'3'},{'left':'1','right':'3'},{'revision':'1'})):
            parsed=urlsplit(path);self.assertEqual(parsed.path,PREFIX+'/'+self.key+'/'+action)
            self.assertEqual(parse_qs(parsed.query),{k:[v] for k,v in dict(workspace_id=self.scope,expected_head='3',**values).items()})
            self.assertIsNone(body)

    def test_invalid_arguments_refuse_before_transport(self):
        for options in ({'limit':0},{'limit':21},{'limit':True},{'before_revision':2},
                        {'before_revision':0,'expected_head':3},{'before_revision':4,'expected_head':3},
                        {'expected_head':False},{'expected_head':257}):
            with self.subTest(options=options),self.assertRaises(ValueError):self.page(**options)
        for scope in (None,'','f'*31,'F'*32,'f'*32+'&limit=20',True):
            with self.subTest(scope=scope),self.assertRaises(ValueError):self.client.history(self.key,workspace_id=scope)
        for key in ('../escape','..','.','bad?limit=2'):
            with self.subTest(key=key),self.assertRaises(ValueError):self.client.history(key,workspace_id=self.scope)
        for revision in (0,257,True,'1'):
            for operation in (lambda:self.client.compare(self.key,revision,3,workspace_id=self.scope),
                              lambda:self.client.compare(self.key,1,revision,workspace_id=self.scope),
                              lambda:self.client.export_revision(self.key,revision,workspace_id=self.scope)):
                with self.subTest(revision=revision),self.assertRaises(ValueError):operation()
        self.assertEqual(self.transport.calls,[])

    def test_foreign_workspace_and_stale_head_map_to_client_error_without_retry(self):
        before=self.dump()
        for operation,code in ((lambda:self.client.history(self.key,workspace_id='f'*32),'asset_workspace_conflict'),
                               (lambda:self.page(expected_head=2),'setup_history_head_changed'),
                               (lambda:self.compare(expected_head=2),'setup_history_head_changed'),
                               (lambda:self.export(expected_head=2),'setup_history_head_changed')):
            count=len(self.transport.calls)
            with self.assertRaises(ClientError) as got:operation()
            self.assertEqual(got.exception.status,409);self.assertEqual(got.exception.code,code)
            self.assertNotIsInstance(got.exception,UnknownSetupOutcome)
            self.assertEqual(len(self.transport.calls),count+1)
        self.assertEqual(self.dump(),before)

    def test_error_bodies_are_bounded_closed_and_never_retried(self):
        for status,raw,headers in ((503,b'{"code":"setup_history_corrupt","error":"Corrupt"}',{}),
                                   (413,b'not json',{}),(503,b'{}',{'Content-Length':'999999'})):
            stream=io.BytesIO(raw);error=HTTPError('http://127.0.0.1',status,'Refused',headers,stream)
            with patch.object(self.client,'transport',side_effect=error) as calls:
                with self.assertRaises(ClientError) as got:self.page()
            self.assertEqual(got.exception.status,status);self.assertEqual(calls.call_count,1);self.assertTrue(stream.closed)
            if status==503 and not headers:self.assertEqual(got.exception.code,'setup_history_corrupt')

    def test_transport_failure_does_not_become_unknown_write_or_retry(self):
        for failure in (TimeoutError('timeout'),OSError('unavailable')):
            with patch.object(self.client,'transport',side_effect=failure) as calls:
                with self.assertRaises(type(failure)):self.export()
            self.assertEqual(calls.call_count,1)

    def test_wrong_envelope_identity_flags_version_or_size_refuse(self):
        for operation in (self.page,self.compare,self.export):
            original=operation()
            for change in ({'workspace_id':'e'*32},{'draft_id':'another'},{'head_revision':True},
                           {'head_record_sha256':'bad'},{'generation_submitted':True},
                           {'observation_only':False},{'dependencies_checked':True},{'staging_performed':True},
                           {'format':'studio.setup-history-page/v1'},{'padding':'x'*MAX_READ_BYTES}):
                value=dict(original,**change)
                with self.subTest(operation=operation.__name__,change=list(change)),patch.object(self.client,'transport',return_value=value):
                    with self.assertRaises(ValueError):operation()
            for value in (None,[],{'generation_submitted':False}):
                with patch.object(self.client,'transport',return_value=value),self.assertRaises(ValueError):operation()

    def test_response_head_must_match_requested_guard(self):
        for operation in (self.page,self.compare,self.export):
            result=operation()
            with patch.object(self.client,'transport',return_value=result),self.assertRaises(ValueError):operation(expected_head=2)

    def test_bad_page_order_limit_and_cursor_refuse(self):
        original=self.page(limit=2)
        for change in ({'revisions':list(reversed(original['revisions']))},{'revisions':original['revisions']*2},
                       {'next_before_revision':1},{'limit':3},{'revisions':None}):
            with self.subTest(change=list(change)),patch.object(self.client,'transport',return_value=dict(original,**change)):
                with self.assertRaises(ValueError):self.page(limit=2)

    def test_missing_revision_rows_and_false_end_of_history_refuse(self):
        original=self.page(limit=2); full=self.page()
        for change in ({'revisions':[],'next_before_revision':None},
                       {'revisions':original['revisions'][:1],'next_before_revision':3},
                       {'revisions':original['revisions'][1:],'next_before_revision':2},
                       {'revisions':[full['revisions'][0],full['revisions'][2]],'next_before_revision':1},
                       {'next_before_revision':None}):
            with self.subTest(change=change),patch.object(self.client,'transport',return_value=dict(original,**change)):
                with self.assertRaises(ValueError):self.page(limit=2)
        final=self.page(limit=2,before_revision=2,expected_head=3)
        with patch.object(self.client,'transport',return_value=dict(final,next_before_revision=1)),self.assertRaises(ValueError):
            self.page(limit=2,before_revision=2,expected_head=3)
        for options in ({'limit':20},{'limit':2,'before_revision':1,'expected_head':3}):
            value=self.page(**options);value.pop('next_before_revision')
            with patch.object(self.client,'transport',return_value=value),self.assertRaises(ValueError):self.page(**options)

    def test_contiguous_full_partial_and_empty_pages_keep_their_exact_end(self):
        for options,wanted,cursor in (({'limit':2},[3,2],2),
                                     ({'limit':2,'before_revision':2,'expected_head':3},[1],None),
                                     ({'limit':2,'before_revision':1,'expected_head':3},[],None),
                                     ({'limit':20},[3,2,1],None)):
            value=self.page(**options)
            self.assertEqual([row['revision'] for row in value['revisions']],wanted)
            self.assertEqual(value['next_before_revision'],cursor)
        value=self.page()
        with patch.object(self.client,'transport',return_value=dict(value,head_revision=0,revisions=[])),self.assertRaises(ValueError):
            self.page()

    def test_raw_history_response_cap_precedes_decoding_and_counts_whitespace(self):
        sdk=WorkflowClient();calls=[];streams=[];reads=[]
        class Response(io.BytesIO):
            def read(self,size=-1):reads.append(size);return super().read(size)
        def open_reply(request,timeout):
            calls.append((request.get_method(),request.data))
            raw=json.dumps(self.transport.request(request.selector)).encode()+b' '*MAX_READ_BYTES
            stream=Response(raw);stream.headers={'Content-Length':str(len(raw))} if declared else {}
            streams.append(stream);return stream
        for declared in (True,False):
            for method,args in ((sdk.setup_drafts.history,(self.key,)),
                                (sdk.setup_drafts.compare,(self.key,1,3)),
                                (sdk.setup_drafts.export_revision,(self.key,1))):
                with self.subTest(declared=declared,method=method.__name__),patch.object(sdk.opener,'open',side_effect=open_reply):
                    before=len(calls);read_before=len(reads)
                    with self.assertRaises(ValueError):method(*args,workspace_id=self.scope)
                    self.assertEqual(len(calls),before+1);self.assertTrue(streams[-1].closed)
                    self.assertEqual(reads[read_before:],[] if declared else [MAX_READ_BYTES+1])
        self.assertEqual(calls,[('GET',None)]*6)

    def test_raw_duplicate_keys_refuse_in_every_history_reader(self):
        sdk=WorkflowClient();streams=[];calls=[]
        def open_reply(request,timeout):
            calls.append(request.get_method())
            raw=json.dumps(self.transport.request(request.selector)).encode()
            raw=raw.replace(b'"head_revision": 3',b'"head_revision": 2, "head_revision": 3')
            stream=io.BytesIO(raw);stream.headers={'Content-Length':str(len(raw))};streams.append(stream)
            return stream
        with patch.object(sdk.opener,'open',side_effect=open_reply):
            for method,args in ((sdk.setup_drafts.history,(self.key,)),
                                (sdk.setup_drafts.compare,(self.key,1,3)),
                                (sdk.setup_drafts.export_revision,(self.key,1))):
                with self.subTest(method=method.__name__),self.assertRaisesRegex(ValueError,'Duplicate JSON key'):
                    method(*args,workspace_id=self.scope)
        self.assertEqual(calls,['GET']*3);self.assertTrue(all(stream.closed for stream in streams))

    def test_nonhistory_reads_and_post_keep_the_existing_raw_transport_contract(self):
        client=Client();raw=json.dumps({'padding':'x'*MAX_READ_BYTES}).encode();streams=[]
        def open_reply(request,timeout):
            stream=io.BytesIO(raw);stream.headers={'Content-Length':str(len(raw))};streams.append(stream)
            return stream
        paths=[PREFIX+'/requests/'+action for action in ('history','compare','export')]+['/api/catalog']
        with patch.object(client.opener,'open',side_effect=open_reply):
            for path in paths:self.assertEqual(client.request(path)['padding'],'x'*MAX_READ_BYTES)
            self.assertEqual(client.request(PREFIX+'/'+self.key+'/history',{'sentinel':'POST'})['padding'],'x'*MAX_READ_BYTES)
        self.assertTrue(all(stream.closed for stream in streams))

    def test_comparison_revision_mismatch_refuses(self):
        original=self.compare()
        for change in ({'left_revision':2},{'right_revision':2},{'sections':None}):
            with patch.object(self.client,'transport',return_value=dict(original,**change)),self.assertRaises(ValueError):self.compare()

    def test_export_identity_bytes_and_projection_mismatch_refuse(self):
        original=self.export()
        for change in ({'export_sha256':'a'*64},{'export_bytes':1},{'export_json':'{}'},
                       {'export':dict(original['export'],revision=2)}):
            with patch.object(self.client,'transport',return_value=dict(original,**change)),self.assertRaises(ValueError):self.export()
        for change in ({'workspace_id':'e'*32},{'draft_id':'other'},{'revision':2},{'authority':'execute'},{'draft_sha256':'a'*64}):
            value=copy.deepcopy(original);value['export'].update(change);raw=canonical(value['export'])
            value.update(export_json=raw.decode(),export_sha256=digest(value['export']),export_bytes=len(raw))
            with patch.object(self.client,'transport',return_value=value),self.assertRaises(ValueError):self.export()

    def test_cli_history_compare_and_export_match_sdk(self):
        for args,expected in ((['history',self.key,'--limit','2'],self.page(limit=2)),
                              (['history',self.key,'--limit','2','--before-revision','2','--expected-head','3'],
                               self.page(limit=2,before_revision=2,expected_head=3)),
                              (['compare',self.key,'1','3','--expected-head','3'],self.compare(expected_head=3)),
                              (['export',self.key,'1'],self.export())):
            out=io.StringIO()
            with patch.object(Client,'request',side_effect=self.transport.request),patch('sys.stdout',out):
                self.assertEqual(main(args+['--workspace-id',self.scope]),0)
            self.assertEqual(json.loads(out.getvalue()),expected)
        self.assertTrue(all(body is None for _,body in self.transport.calls))

    def test_cli_stale_head_is_read_error_without_write_recovery(self):
        error=io.StringIO()
        with patch.object(Client,'request',side_effect=self.transport.request),patch('sys.stderr',error):
            self.assertEqual(main(['history',self.key,'--workspace-id',self.scope,'--expected-head','2']),2)
        result=json.loads(error.getvalue());self.assertEqual(result['code'],'setup_history_head_changed')
        self.assertNotIn('request_id',result);self.assertNotIn('recovery',result)

    def test_sdk_uses_bounded_shared_transport_and_get_requests(self):
        sdk=WorkflowClient();calls=[]
        def open_reply(request,timeout):
            calls.append((request.get_method(),request.data,timeout))
            result=self.transport.request(request.selector);raw=json.dumps(result).encode()
            response=io.BytesIO(raw);response.headers={'Content-Length':str(len(raw))}
            return response
        with patch.object(sdk.opener,'open',side_effect=open_reply):
            self.assertEqual(sdk.setup_drafts.history(self.key,workspace_id=self.scope),self.page())
            self.assertEqual(sdk.setup_drafts.compare(self.key,1,3,workspace_id=self.scope),self.compare())
            self.assertEqual(sdk.setup_drafts.export_revision(self.key,1,workspace_id=self.scope),self.export())
        self.assertEqual(calls,[('GET',None,30)]*3)

    def test_cli_invalid_history_arguments_never_send_a_request(self):
        with patch.object(Client,'request',side_effect=AssertionError('Transport reached')),patch('sys.stderr',io.StringIO()):
            self.assertEqual(main(['history',self.key,'--workspace-id',self.scope,'--before-revision','2']),2)
            with self.assertRaises(SystemExit) as got:main(['history',self.key])
        self.assertEqual(got.exception.code,2)


if __name__=='__main__':unittest.main()
