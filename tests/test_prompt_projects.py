"""Immutable prompt revisions and receipts in the real Workspace database."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from workspace import AssetWorkspace
from studio_prompt import projects as p
from studio_prompt.schema import new_brief, digest


class PromptProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.workspace=AssetWorkspace(self.tmp.name);self.service=p.PromptProjects(self.workspace)
        self.scope=self.service.capabilities()['workspace_id']
        self.doc={'format':p.FORMAT,'name':'Observatory keeper','profile_id':'sdxl-prose-v1',
                  'intent':new_brief('Keep the reference pose'),'reference_context':None}
        self.request={'workspace_id':self.scope,'request_id':'prompt-request-0001','document':self.doc}
    def create(self):return self.service.command('create',self.request)
    def save(self,created,**updates):
        value={'workspace_id':self.scope,'request_id':'prompt-request-0002','id':created['project']['id'],
               'expected_revision':1,'document':copy.deepcopy(self.doc)}
        value.update(updates);return self.service.command('save',value)
    def count(self):
        with self.workspace.connection() as db:return db.execute('SELECT COUNT(*) FROM prompt_project_revisions_v1').fetchone()[0]
    def test_create_is_complete_scoped_and_nonexecuting(self):
        before=copy.deepcopy(self.request);reply=self.create();row=reply['project']
        self.assertEqual(row['document'],self.doc);self.assertEqual(row['revision'],1)
        self.assertEqual(row['document_sha256'],digest(self.doc));self.assertEqual(reply['request'],self.request)
        self.assertEqual(row['workspace_id'],self.scope);self.assertEqual(self.request,before)
        self.assertFalse(reply['generation_submitted']);self.assertFalse(reply['inference_submitted'])
        self.assertFalse(reply['execution_authorized']);self.assertEqual(self.count(),1)
    def test_identical_create_replay_once_and_changed_content_conflicts(self):
        first=self.create();second=self.create();self.assertEqual(first['project'],second['project'])
        self.assertTrue(second['replayed']);self.assertEqual(self.count(),1)
        self.doc['name']='Changed'
        with self.assertRaisesRegex(p.ProjectError,'different'):self.create()
    def test_empty_brief_saves_but_unknown_fields_do_not(self):
        self.doc['intent']['brief']='';self.assertEqual(self.create()['project']['document'],self.doc)
        self.request['request_id']='prompt-request-0003';self.doc['execute']=True
        with self.assertRaises(ValueError):self.create()
    def test_save_preserves_exact_fields_and_old_revision(self):
        first=self.create();new=copy.deepcopy(self.doc);new['intent']['tags']=['ink, bold','青い','青い']
        new['intent']['references']=[{'id':'picture-1','path':'original.png','sha256':'a'*64,'role':'pose','kind':'image','take':['raised arm'],'ignore':[]}]
        second=self.save(first,document=new);key=second['project']['id']
        self.assertEqual(second['project']['revision'],2);self.assertEqual(second['project']['document'],new)
        self.assertEqual(self.service.get(self.scope,key,1)['document'],self.doc)
    def test_stale_save_conflicts_and_does_not_allocate_receipt(self):
        first=self.create();self.save(first)
        with self.assertRaises(p.ProjectError) as error:self.save(first,request_id='prompt-request-0003')
        self.assertEqual(error.exception.code,'revision_conflict');self.assertEqual(self.count(),2)
        with self.assertRaises(p.ProjectError):self.service.status(self.scope,'prompt-request-0003')
    def test_receipt_is_historical_after_another_save(self):
        first=self.create();self.save(first)
        status=self.service.status(self.scope,self.request['request_id'])
        self.assertEqual(status['project']['revision'],1);self.assertEqual(status['project']['head_revision'],2)
        self.assertEqual(status['request'],self.request)
    def test_restore_appends_instead_of_rewinding(self):
        first=self.create();new=copy.deepcopy(self.doc);new['name']='Newer';self.save(first,document=new)
        value={'workspace_id':self.scope,'request_id':'prompt-restore-0001','id':first['project']['id'],
               'expected_revision':2,'restore_revision':1}
        reply=self.service.command('restore',value)
        self.assertEqual(reply['project']['revision'],3);self.assertEqual(reply['project']['document'],self.doc)
        self.assertEqual(self.service.command('restore',value)['project']['revision'],3);self.assertEqual(self.count(),3)
    def test_restore_obeys_newer_locks(self):
        first=self.create();new=copy.deepcopy(self.doc);new['intent']['facets']['style']='ink';new['intent']['locked'].append('facets.style')
        self.save(first,document=new)
        with self.assertRaisesRegex(ValueError,'Locked'):
            self.service.command('restore',{'workspace_id':self.scope,'request_id':'prompt-restore-0001',
                'id':first['project']['id'],'expected_revision':2,'restore_revision':1})
    def test_save_cannot_remove_locks_or_modify_locked_values(self):
        self.doc['intent']['facets']['style']='ink';self.doc['intent']['locked'].append('facets.style');first=self.create()
        for modify in (lambda d:d['intent']['locked'].clear(),lambda d:d['intent']['facets'].update(style='oil')):
            new=copy.deepcopy(self.doc);modify(new)
            with self.assertRaisesRegex(ValueError,'Locked'):self.save(first,document=new)
    def test_wrong_workspace_refused_for_all_reads_and_writes(self):
        first=self.create();key=first['project']['id'];wrong='a'*32
        for operation in (lambda:self.service.get(wrong,key),lambda:self.service.list(wrong),
                          lambda:self.service.history(wrong,key),lambda:self.service.status(wrong,self.request['request_id']),
                          lambda:self.service.command('create',{**self.request,'workspace_id':wrong})):
            with self.subTest(op=operation),self.assertRaisesRegex(ValueError,'Workspace'):operation()
        self.assertEqual(self.count(),1)
    def test_restart_reopens_without_replay(self):
        first=self.create();other=p.PromptProjects(AssetWorkspace(self.tmp.name))
        self.assertEqual(other.status(self.scope,self.request['request_id'])['project'],first['project'])
        self.assertEqual(self.count(),1)
    def test_concurrent_writers_cannot_both_save_the_same_revision(self):
        first=self.create()
        def write(n):
            try:return self.save(first,request_id='concurrent-request-%02d'%n)['project']['revision']
            except p.ProjectError as e:return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,range(2)))
        self.assertCountEqual(results,[2,'revision_conflict']);self.assertEqual(self.count(),2)
    def test_atomic_rollback_when_receipt_insert_fails(self):
        with self.workspace.connection() as db:db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON prompt_project_commands_v1 BEGIN SELECT RAISE(ABORT,'fixture receipt failure'); END")
        with self.assertRaises(sqlite3.Error):self.create()
        self.assertEqual(self.count(),0);self.assertEqual(self.service.list(self.scope)['projects'],[])
        with self.workspace.connection() as db:db.execute('DROP TRIGGER fail_receipt')
        self.assertEqual(self.create()['project']['revision'],1)
    def test_corrupt_document_or_receipt_refuses(self):
        first=self.create()
        with self.workspace.connection() as db:db.execute("UPDATE prompt_project_revisions_v1 SET document_json='{}'")
        with self.assertRaises(p.ProjectError):self.service.get(self.scope,first['project']['id'])

    def test_one_unreadable_revision_does_not_hide_the_list(self):
        first=self.create()
        other={**self.request,'request_id':'prompt-request-0002','document':copy.deepcopy(self.doc)}
        other['document']['name']='Second keeper'
        second=self.service.command('create',other)
        with self.workspace.connection() as db:
            db.execute("UPDATE prompt_project_revisions_v1 SET document_json='{}' WHERE id=?",(first['project']['id'],))
        listed=self.service.list(self.scope)['projects']
        self.assertEqual(len(listed),2)
        by_id={row['id']:row for row in listed}
        broken,ok=by_id[first['project']['id']],by_id[second['project']['id']]
        self.assertTrue(broken['unreadable'])
        self.assertFalse(ok['unreadable'])
        self.assertEqual(ok['name'],'Second keeper')
        with self.assertRaises(p.ProjectError) as error:
            self.service.get(self.scope,first['project']['id'])
        self.assertEqual(error.exception.code,'project_storage_invalid')
    def test_modified_receipt_cannot_certify_a_save(self):
        self.create()
        with self.workspace.connection() as db:db.execute("UPDATE prompt_project_commands_v1 SET command_sha='broken'")
        with self.assertRaises(p.ProjectError):self.service.status(self.scope,self.request['request_id'])
    def test_count_revision_and_history_byte_caps_preserve_existing_receipts(self):
        first=self.create()
        with patch.object(p,'MAX_PROJECTS',1):
            with self.assertRaises(ValueError):self.service.command('create',{**self.request,'request_id':'another-request-0001'})
        with patch.object(p,'MAX_REVISIONS',1):
            with self.assertRaises(ValueError):self.save(first)
        with patch.object(p,'MAX_HISTORY_BYTES',1):
            with self.assertRaises(ValueError):self.save(first)
        self.assertEqual(self.count(),1);self.assertEqual(self.service.status(self.scope,self.request['request_id'])['project']['revision'],1)
    def test_history_is_paginated_and_read_only(self):
        first=self.create();key=first['project']['id']
        for revision in range(1,35):self.save(first,request_id='history-request-%03d'%revision,expected_revision=revision)
        firstpage=self.service.history(self.scope,key);self.assertEqual(len(firstpage['revisions']),32)
        second=self.service.history(self.scope,key,before=firstpage['next_before'])
        self.assertEqual([x['revision'] for x in second['revisions']],[3,2,1]);self.assertEqual(self.count(),35)
    def test_reference_context_validated_but_not_claimed_pixel_verified(self):
        from test_reference_review import ReferenceReviewTests
        fixture=ReferenceReviewTests();fixture.setUp()
        self.doc['reference_context']={'analysis':fixture.report,'review':fixture.review}
        row=self.create()['project'];self.assertEqual(row['document']['reference_context'],self.doc['reference_context'])
        self.assertFalse(row['source_bytes_verified'])
    def test_corrupt_or_cross_role_context_refused(self):
        from test_reference_review import ReferenceReviewTests
        fixture=ReferenceReviewTests();fixture.setUp();fixture.review['selections'][0]['facets']=['subject']
        self.doc['reference_context']={'analysis':fixture.report,'review':fixture.review}
        with self.assertRaisesRegex(ValueError,'role'):self.create()
        self.assertEqual(self.count(),0)
    def test_unknown_revision_bool_number_and_unbounded_commands_refuse(self):
        first=self.create()
        for value in (True,0,1.0,'1'):
            with self.subTest(value=value),self.assertRaises(ValueError):self.save(first,expected_revision=value)
        with self.assertRaises(p.ProjectError):self.service.get(self.scope,first['project']['id'],99)
        with self.assertRaises(ValueError):self.service.command('run',self.request)
        with self.assertRaises(ValueError):self.service.command('create',{**self.request,'extra':'x'*p.REQUEST_LIMIT})

    def test_command_revision_cannot_be_reassociated_with_an_identical_later_save(self):
        first=self.create();self.save(first)
        with self.workspace.connection() as db:
            db.execute("UPDATE prompt_project_commands_v1 SET revision=2 WHERE request_id=?",(self.request['request_id'],))
        with self.assertRaises(p.ProjectError):self.service.status(self.scope,self.request['request_id'])
    def test_rehashed_command_with_unknown_fields_is_not_a_valid_receipt(self):
        self.create()
        with self.workspace.connection() as db:
            raw=json.loads(db.execute('SELECT command_json FROM prompt_project_commands_v1').fetchone()[0])
            raw['request']['invented']='not in contract'
            from studio_prompt.schema import canonical
            encoded=canonical(raw)
            db.execute('UPDATE prompt_project_commands_v1 SET command_json=?,command_sha=?,bytes=?',(encoded.decode(),digest(raw),len(encoded)))
        with self.assertRaises(p.ProjectError):self.service.status(self.scope,self.request['request_id'])
    def test_context_validation_does_not_open_or_verify_originals(self):
        from test_reference_review import ReferenceReviewTests
        from studio_prompt import reference_analysis
        fixture=ReferenceReviewTests();fixture.setUp()
        self.doc['reference_context']={'analysis':fixture.report,'review':fixture.review}
        with patch.object(reference_analysis,'file_bytes',side_effect=AssertionError('No pixel access')):
            self.assertFalse(self.create()['project']['source_bytes_verified'])

if __name__=='__main__':unittest.main()
