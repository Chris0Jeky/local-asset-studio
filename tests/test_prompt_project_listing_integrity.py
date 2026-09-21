"""Read-only prompt listing faults against real SQLite and production validators."""
import json
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from studio_prompt import projects as p
from studio_prompt.schema import canonical, digest, new_brief


class PromptProjectListingIntegrityTests(unittest.TestCase):
    def setUp(self):
        # Only the connection/scope adapter is a fixture. SQL, joins, document
        # validation and strict reads execute the real PromptProjects service.
        self.db=sqlite3.connect(':memory:')
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.addCleanup(self.db.close)
        self.scope='a'*32
        workspace=SimpleNamespace(connection=lambda:self.db,
            _validate_scope=self.check_scope,_check_scope=lambda db,scope:scope)
        self.service=p.PromptProjects(workspace)
        self.broken='1'*32;self.healthy='2'*32
        self.doc={'format':p.FORMAT,'name':'Saved keeper','profile_id':'sdxl-prose-v1',
                  'intent':new_brief('Keep the pose'),'reference_context':None}
        raw=canonical(self.doc)
        with self.db:
            for key in (self.broken,self.healthy):
                self.db.execute('INSERT INTO prompt_projects_v1 VALUES (?,1)',(key,))
                self.db.execute('INSERT INTO prompt_project_revisions_v1 VALUES (?,1,?,?,?,0)',
                    (key,raw.decode('utf-8'),digest(self.doc),len(raw)))

    def check_scope(self,scope):
        p.need(scope==self.scope,'Workspace mismatch')

    def snapshot(self):
        return tuple(tuple(tuple(row) for row in self.db.execute('SELECT * FROM '+table+' ORDER BY 1,2'))
            for table in ('prompt_projects_v1','prompt_project_revisions_v1','prompt_project_commands_v1'))

    def listing(self):
        before=self.snapshot()
        reply=self.service.list(self.scope)
        self.assertEqual(self.snapshot(),before,'Listing must not repair or delete stored evidence')
        self.assertEqual(reply['workspace_id'],self.scope)
        for flag in p.FLAGS:self.assertIs(reply[flag],False)
        rows={row['id']:row for row in reply['projects']}
        self.assertEqual(set(rows),{self.broken,self.healthy})
        self.assertFalse(rows[self.healthy]['unreadable'])
        self.assertEqual(rows[self.healthy]['name'],'Saved keeper')
        return rows

    def test_intact_heads_remain_readable_and_keep_the_recorded_digest(self):
        rows=self.listing()
        self.assertFalse(rows[self.broken]['unreadable'])
        self.assertEqual(rows[self.broken]['document_sha256'],digest(self.doc))
        self.assertEqual(self.service.get(self.scope,self.broken)['document'],self.doc)

    def test_missing_head_is_listed_as_unreadable_without_hiding_healthy_briefs(self):
        with self.db:self.db.execute('UPDATE prompt_projects_v1 SET head=2 WHERE id=?',(self.broken,))
        row=self.listing()[self.broken]
        self.assertTrue(row['unreadable'])
        self.assertEqual(row['revision'],2)
        self.assertIsNone(row['document_sha256'])
        with self.assertRaises(p.ProjectError) as error:self.service.get(self.scope,self.broken)
        self.assertEqual(error.exception.code,'project_not_found')

    def test_checksum_damage_is_marked_unreadable_and_strict_reads_still_refuse(self):
        with self.db:self.db.execute('UPDATE prompt_project_revisions_v1 SET document_sha=? WHERE id=?',('0'*64,self.broken))
        self.assertTrue(self.listing()[self.broken]['unreadable'])
        with self.assertRaises(p.ProjectError) as error:self.service.get(self.scope,self.broken)
        self.assertEqual(error.exception.code,'project_storage_invalid')

    def test_recorded_size_damage_is_marked_unreadable(self):
        with self.db:self.db.execute('UPDATE prompt_project_revisions_v1 SET bytes=bytes+1 WHERE id=?',(self.broken,))
        self.assertTrue(self.listing()[self.broken]['unreadable'])
        with self.assertRaises(p.ProjectError):self.service.get(self.scope,self.broken)

    def test_invalid_head_bounds_are_marked_unreadable(self):
        with self.db:
            self.db.execute('UPDATE prompt_projects_v1 SET head=0 WHERE id=?',(self.broken,))
            self.db.execute('UPDATE prompt_project_revisions_v1 SET revision=0 WHERE id=?',(self.broken,))
        self.assertTrue(self.listing()[self.broken]['unreadable'])
        with self.assertRaises(p.ProjectError):self.service.get(self.scope,self.broken)

    def test_oversized_stored_text_is_not_parsed_or_recovered_by_the_name_fallback(self):
        oversized=' '*p.MAX_DOCUMENT_BYTES+canonical(self.doc).decode('utf-8')
        with self.db:self.db.execute('UPDATE prompt_project_revisions_v1 SET document_json=?,bytes=? WHERE id=?',
            (oversized,len(oversized.encode('utf-8')),self.broken))
        with patch.object(p,'decode',wraps=p.decode) as decode:
            row=self.listing()[self.broken]
        self.assertTrue(row['unreadable'])
        self.assertIsNone(row['name'])
        self.assertTrue(all(len(call.args[0])<=p.MAX_DOCUMENT_BYTES for call in decode.call_args_list))

    def test_missing_heads_cannot_bypass_the_project_count_limit(self):
        with self.db:self.db.execute('UPDATE prompt_projects_v1 SET head=2 WHERE id=?',(self.broken,))
        before=self.snapshot()
        with patch.object(p,'MAX_PROJECTS',1),self.assertRaisesRegex(ValueError,'count exceeds'):
            self.service.list(self.scope)
        self.assertEqual(self.snapshot(),before)

    def test_future_schema_name_is_bounded_but_never_certified_readable(self):
        for name,expected in (('Future keeper','Future keeper'),('x'*121,None),('\x00bad',None)):
            with self.subTest(name=name):
                raw=json.dumps({'name':name,'future_format':2})
                with self.db:self.db.execute('UPDATE prompt_project_revisions_v1 SET document_json=? WHERE id=?',(raw,self.broken))
                row=self.listing()[self.broken]
                self.assertTrue(row['unreadable'])
                self.assertEqual(row['name'],expected)

    def test_wrong_workspace_cannot_enumerate_even_damaged_rows(self):
        with self.db:self.db.execute('UPDATE prompt_projects_v1 SET head=2 WHERE id=?',(self.broken,))
        with self.assertRaisesRegex(ValueError,'Workspace'):self.service.list('b'*32)


if __name__=='__main__':unittest.main()
