"""Public runtime schemas must not enumerate private reference filenames."""
import copy
import json
import threading
import unittest

import test_server as fixture
from studio_workflow.agent_bridge import AgentBridge
from studio_workflow.core import new_document
from studio_workflow.control_preview import request as control_preview
from studio_workflow.http_extension import schema, get
from studio_workflow.schema_privacy import public_node_info

_THREAD_START=threading.Thread.start  # The server fixture suppresses worker startup during setUp.


class PrivateSchemaTests(unittest.TestCase):
    setUp = fixture.ServerTests.setUp
    tearDown = fixture.ServerTests.tearDown
    studio = fixture.ServerTests.studio

    def source(self):
        studio=self.studio()
        regular=studio.upload('regular-source','image/png',fixture.png())
        private=studio.upload('PRIVATE-SCHEMA-CANARY','image/png',fixture.png(),privacy='private')
        info={'LoadImage':{'input':{'required':{'image':[[regular['file'],private['file']],{'image_upload':True}]}},'output':['IMAGE']},
              'ComboImage':{'input':{'required':{'image':['COMBO',{'options':[regular['file'],private['file']]}]}},'output':['IMAGE']}}
        studio.node_info=lambda refresh=False:info
        return studio,regular,private,info

    def test_public_catalog_and_raw_definition_hide_private_inputs_without_mutating_runtime(self):
        studio,regular,private,info=self.source();before=copy.deepcopy(info)
        public=schema(studio)
        self.assertNotIn(private['file'],json.dumps(public));self.assertNotIn('PRIVATE-SCHEMA-CANARY',json.dumps(public))
        self.assertIn(regular['file'],json.dumps(public));self.assertEqual(info,before)
        self.assertEqual(studio.jobs,{})

    def test_private_choice_changes_do_not_change_public_schema_identity(self):
        studio,regular,private,info=self.source();info['LoadImage']['input']['required']['image'][0].remove(private['file'])
        info['ComboImage']['input']['required']['image'][1]['options'].remove(private['file'])
        before=schema(studio)
        info['LoadImage']['input']['required']['image'][0].append(private['file'])
        info['ComboImage']['input']['required']['image'][1]['options'].append(private['file'])
        self.assertEqual(schema(studio),before)

    def test_control_preview_has_only_regular_source_choices(self):
        studio,regular,private,info=self.source()
        document=new_document({'image':{'class_type':'LoadImage','inputs':{'image':regular['file']}}},schema(studio))
        request={'document':document,'expected_revision':0,'control':{'format':'studio.control/v1','name':'Source','targets':[{'node':'image','input':'image'}]},'value':regular['file']}
        result=control_preview(request,studio)
        self.assertEqual(result['state'],'ready');self.assertNotIn(private['file'],json.dumps(result))
        self.assertIn(regular['file'],json.dumps(result));self.assertEqual(studio.jobs,{})

    def test_default_agent_node_tool_never_gets_the_private_choice(self):
        studio,regular,private,info=self.source()
        class LocalClient:
            def request(self,path,body=None):
                self.path=path;return get(path,studio)
        result=AgentBridge(LocalClient()).invoke('studio_nodes',{'limit':10})
        self.assertTrue(result['ok']);self.assertNotIn(private['file'],json.dumps(result))
        self.assertIn(regular['file'],result['data_json'])

    def test_retained_private_job_source_stays_hidden_after_its_upload_copy_is_missing(self):
        studio,regular,private,info=self.source()
        root=studio.experiments/'private/uploads'
        for path in root.iterdir():path.unlink()
        studio.jobs['private-retained']={'id':'private-retained','privacy':'private','controls':{'reference':private['file']}}
        self.assertNotIn(private['file'],json.dumps(schema(studio)))

    def test_private_output_paths_and_annotated_input_choices_are_filtered(self):
        studio,regular,private,info=self.source()
        info['LoadImage']['input']['required']['image'][0]+=[
            'C:\\Comfy\\input\\'+private['file']+' [input]',
            'local-asset-studio/private/private-run/output.png [output]']
        result=schema(studio)
        self.assertNotIn('PRIVATE-SCHEMA-CANARY',json.dumps(result))
        self.assertNotIn('private-run',json.dumps(result));self.assertIn(regular['file'],json.dumps(result))

    def test_job_admission_cannot_mutate_retained_sources_mid_projection(self):
        studio,regular,private,info=self.source()
        observed,attempting,changed=threading.Event(),threading.Event(),threading.Event()
        class RacingJobs(dict):
            def values(self):
                for index,job in enumerate(super().values()):
                    yield job
                    if index==0:
                        observed.set();self.test.assertTrue(attempting.wait(2))
                        changed.wait(.05)
        studio.jobs=RacingJobs({'first':{'privacy':'private','controls':{'reference':private['file']}},'second':{'privacy':'regular'}})
        studio.jobs.test=self
        def admit():
            if not observed.wait(2):return
            attempting.set()
            with studio.lock:studio.jobs['admitted']={'privacy':'regular'}
            changed.set()
        thread=threading.Thread(target=admit);_THREAD_START(thread)
        try:
            projected=public_node_info(studio)
            self.assertNotIn(private['file'],json.dumps(projected))
        finally:thread.join(3)
        self.assertFalse(thread.is_alive());self.assertTrue(changed.is_set())


if __name__=='__main__':unittest.main()
