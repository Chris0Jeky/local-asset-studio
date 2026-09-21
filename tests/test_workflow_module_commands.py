"""Portable Step commands, reversible authoring and real Workspace persistence."""
import copy
import hashlib
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from workspace import AssetWorkspace
from studio_workflow import commands as command_api
from studio_workflow.core import canonical, catalog, compile_document, digest, new_document, MAX_BYTES
from studio_workflow.commands import apply_commands, execution_inputs_sha256
from studio_workflow.documents import WorkflowDocuments, DocumentError

INFO = {
    'Value': {'input': {'required': {'value': ['INT', {'min': 0, 'max': 100}]}}, 'output': ['INT']},
    'Pass': {'input': {'required': {'source': ['INT', {'forceInput': True}]}}, 'output': ['INT']},
    'Save': {'input': {'required': {'source': ['INT', {'forceInput': True}]}}, 'output': [], 'output_node': True},
}


def fixture():
    schema = catalog(INFO, 'primary')
    graph = {
        'input': {'class_type': 'Value', 'inputs': {'value': 3}, '_meta': {'title': 'Original'}},
        'pass': {'class_type': 'Pass', 'inputs': {'source': ['input', 0]}, '_meta': {'opaque': [1, {'keep': True}]}},
        'save': {'class_type': 'Save', 'inputs': {'source': ['pass', 0]}},
        'draft': {'class_type': 'Value', 'inputs': {'value': 5}},
    }
    doc = new_document(graph, schema, 'Module source')
    doc['revision'] = 7
    doc['positions'] = {'pass': [20, 40], 'save': [80, 90]}
    doc['steps'] = [{'id': 'pipeline', 'name': 'Pipeline', 'description': 'A reusable explicit boundary',
                     'nodes': ['pass', 'save'], 'controls': [{'name': 'Source', 'node': 'pass', 'input': 'source'}]}]
    doc['source'] = {'parent_assets': [{'id': 'asset-original', 'sha256': 'a' * 64, 'role': 'identity'}]}
    return doc, schema


def api():
    # A useful assertion on the baseline, rather than a test-collection ImportError.
    from importlib.util import find_spec
    if find_spec('studio_workflow.modules') is None:
        raise AssertionError('Portable Step modules are not implemented')
    from studio_workflow import modules
    return modules


def plan(source, edits):
    from importlib.util import find_spec
    if find_spec('studio_workflow.command_plan') is None:
        raise AssertionError('Reversible command planning is not implemented')
    from studio_workflow.command_plan import plan_commands
    return plan_commands(source, edits)


def import_command(module):
    return {'op': 'import_module', 'module': module, 'module_sha256': digest(module),
            'node_ids': {'pass': 'copy_pass', 'save': 'copy_save'},
            'step_id': 'copy', 'name': 'Copied pipeline', 'bindings': {'input1': ['input', 0]}}


class ExecutionIdentityTests(unittest.TestCase):
    def test_layout_and_metadata_do_not_change_execution_identity(self):
        doc, schema = fixture()
        original = compile_document(doc, schema)
        self.assertIn('graph_execution_sha256', original)
        changed = copy.deepcopy(doc)
        changed['nodes']['pass']['_meta']['opaque'] = ['other']
        changed['name'] = 'Presentation'
        changed['positions']['pass'] = [90, 40]
        changed['steps'][0]['name'] = 'New label'
        changed['revision'] += 1
        result = compile_document(changed, schema)
        self.assertEqual(result['graph_execution_sha256'], original['graph_execution_sha256'])
        self.assertNotEqual(result['graph_sha256'], original['graph_sha256'])
        self.assertEqual(original['graph_sha256'], digest(original['graph']))
        self.assertNotEqual(result['document_sha256'], original['document_sha256'])
        self.assertEqual(original['graph_execution_format'], 'studio.workflow-execution/v1')

    def test_only_selected_closure_affects_executable_identity(self):
        doc, schema = fixture()
        original = compile_document(doc, schema)
        self.assertIn('graph_execution_sha256', original)
        disconnected = copy.deepcopy(doc)
        disconnected['nodes']['draft']['inputs']['value'] = 99
        self.assertNotEqual(execution_inputs_sha256(doc), execution_inputs_sha256(disconnected))
        self.assertEqual(original['graph_execution_sha256'], compile_document(disconnected, schema)['graph_execution_sha256'])
        connected = copy.deepcopy(doc)
        connected['nodes']['input']['inputs']['value'] = 8
        self.assertNotEqual(original['graph_execution_sha256'], compile_document(connected, schema)['graph_execution_sha256'])

    def test_backend_and_schema_are_part_of_execution_identity(self):
        doc, schema = fixture()
        original = compile_document(doc, schema)
        self.assertIn('graph_execution_sha256', original)
        for field, value in [('backend_id', 'isolated'), ('schema_sha256', 'f' * 64)]:
            with self.subTest(field=field):
                other_doc, other_schema = copy.deepcopy(doc), copy.deepcopy(schema)
                other_doc[field] = other_schema[field] = value
                result = compile_document(other_doc, other_schema)
                self.assertEqual(result['graph_sha256'], original['graph_sha256'])
                self.assertNotEqual(result['graph_execution_sha256'], original['graph_execution_sha256'])

    def test_invalid_graph_has_no_execution_identity(self):
        doc, schema = fixture()
        doc['nodes']['pass']['inputs']['source'] = ['absent', 0]
        result = compile_document(doc, schema)
        self.assertFalse(result['valid'])
        self.assertIn('graph_execution_sha256', result)
        self.assertIsNone(result['graph_execution_sha256'])


class ModuleTests(unittest.TestCase):
    def setUp(self):
        self.doc, self.schema = fixture()

    def exported(self):
        return api().export_module(self.doc, 'pipeline', document_id='source-document')

    def test_export_is_bounded_deterministic_and_source_preserving(self):
        before = canonical(self.doc)
        module = self.exported()
        self.assertEqual(module, api().export_module(json.loads(before), 'pipeline', document_id='source-document'))
        self.assertEqual(canonical(self.doc), before)
        self.assertEqual(set(module['document']['nodes']), {'pass', 'save'})
        self.assertEqual(module['document']['revision'], 0)
        self.assertEqual(module['document']['source'], self.doc['source'])
        self.assertEqual(module['inputs'], [{'id': 'input1', 'node': 'pass', 'input': 'source', 'source': ['input', 0]}])
        self.assertEqual(module['origin'], {'document_id': 'source-document', 'revision': 7,
                                           'document_sha256': digest(self.doc), 'step_id': 'pipeline'})
        module['document']['nodes']['pass']['_meta']['opaque'].append('edit')
        self.assertEqual(canonical(self.doc), before)

    def test_import_remaps_internal_links_and_preserves_external_consumers(self):
        module = self.exported()
        before = canonical(self.doc)
        result = apply_commands(self.doc, [import_command(module)])
        self.assertEqual(canonical(self.doc), before)
        self.assertEqual(result['nodes']['copy_pass']['inputs']['source'], ['input', 0])
        self.assertEqual(result['nodes']['copy_save']['inputs']['source'], ['copy_pass', 0])
        self.assertEqual(result['nodes']['save'], self.doc['nodes']['save'])
        self.assertEqual(result['outputs'], self.doc['outputs'])
        self.assertEqual(result['positions']['copy_pass'], [20, 40])
        self.assertEqual(result['steps'][-1]['controls'][0]['node'], 'copy_pass')
        evidence = result['source']['module_imports'][0]
        self.assertEqual(evidence['module_sha256'], digest(module))
        self.assertEqual(evidence['origin'], module['origin'])
        self.assertEqual(evidence['source'], self.doc['source'])
        self.assertEqual(evidence['bindings'], {'input1': ['input', 0]})
        self.assertEqual(result['source']['parent_assets'], self.doc['source']['parent_assets'])
        self.assertTrue(compile_document(result, self.schema)['valid'])
        self.assertEqual(compile_document(result, self.schema)['graph_sha256'], compile_document(self.doc, self.schema)['graph_sha256'])

    def test_disabled_and_bypass_data_survive_export_and_import(self):
        self.doc['disabled'] = ['pass']
        self.doc['bypass'] = {'pass': {'0': 'source'}}
        result = apply_commands(self.doc, [import_command(self.exported())])
        self.assertIn('copy_pass', result['disabled'])
        self.assertEqual(result['bypass']['copy_pass'], {'0': 'source'})
        self.assertTrue(compile_document(result, self.schema)['valid'])

    def test_all_boundary_bindings_and_node_mappings_must_be_exact(self):
        module = self.exported()
        alterations = [
            {'bindings': {}}, {'bindings': {'input1': ['input', 0], 'extra': ['input', 0]}},
            {'bindings': {'input1': ['missing', 0]}}, {'bindings': {'input1': ['copy_pass', 0]}},
            {'bindings': {'input1': ['input', True]}}, {'bindings': {'input1': ['input', 10000]}},
            {'node_ids': {'pass': 'copy_pass'}}, {'node_ids': {'pass': 'new', 'save': 'new'}},
            {'node_ids': {'pass': 'input', 'save': 'copy_save'}}, {'step_id': 'pipeline'},
            {'module_sha256': '0' * 64}, {'name': ''},
        ]
        for alteration in alterations:
            with self.subTest(alteration=alteration):
                before = canonical(self.doc)
                with self.assertRaises(ValueError):
                    apply_commands(self.doc, [import_command(module) | alteration])
                self.assertEqual(canonical(self.doc), before)

    def test_module_requires_matching_backend_and_schema(self):
        module = self.exported()
        for field, value in [('backend_id', 'other'), ('schema_sha256', 'b' * 64)]:
            target = copy.deepcopy(self.doc)
            target[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                apply_commands(target, [import_command(module)])

    def test_tampered_boundary_and_versions_fail_validation(self):
        module = self.exported()
        variants = []
        for changed in ({'format': 'studio.workflow-module/v99'}, {'surprise': 1}, {'inputs': []}):
            variants.append(module | changed)
        bad = copy.deepcopy(module); bad['inputs'][0]['source'] = ['wrong', 0]; variants.append(bad)
        bad = copy.deepcopy(module); bad['inputs'].append(copy.deepcopy(bad['inputs'][0])); variants.append(bad)
        bad = copy.deepcopy(module); bad['document']['revision'] = 1; variants.append(bad)
        bad = copy.deepcopy(module); bad['origin']['step_id'] = 'wrong'; variants.append(bad)
        bad = copy.deepcopy(module); bad['document']['nodes']['outside'] = self.doc['nodes']['input']; variants.append(bad)
        for changed in variants:
            with self.subTest(changed=digest(changed)), self.assertRaises(ValueError):
                api().validate_module(changed)

    def test_opaque_target_lineage_is_refused_instead_of_discarded(self):
        module = self.exported()
        for source in (['opaque'], 'opaque', None, {'module_imports': 'reserved collision'}):
            target = copy.deepcopy(self.doc); target['source'] = source
            before = canonical(target)
            with self.subTest(source=source), self.assertRaises(ValueError):
                apply_commands(target, [import_command(module)])
            self.assertEqual(canonical(target), before)

    def test_provenance_and_module_size_are_bounded(self):
        module = self.exported()
        target = copy.deepcopy(self.doc); target['source']['module_imports'] = [{} for _ in range(64)]
        with self.assertRaises(ValueError): apply_commands(target, [import_command(module)])
        huge = copy.deepcopy(module); huge['document']['source'] = {'padding': 'x' * (256 * 1024)}
        with self.assertRaises(ValueError): api().validate_module(huge)

    def test_dangling_external_source_requires_a_deliberate_rebinding(self):
        self.doc['nodes']['pass']['inputs']['source'] = ['missing', 0]
        module = self.exported()
        self.assertEqual(module['inputs'][0]['source'], ['missing', 0])
        result = apply_commands(self.doc, [import_command(module)])
        self.assertEqual(result['nodes']['copy_pass']['inputs']['source'], ['input', 0])
        self.assertEqual(result['nodes']['pass']['inputs']['source'], ['missing', 0])

    def test_multiple_external_inputs_get_stable_explicit_ports(self):
        self.doc['nodes']['save']['inputs']['source'] = ['draft', 0]
        module = self.exported()
        self.assertEqual([(x['id'], x['node']) for x in module['inputs']], [('input1', 'pass'), ('input2', 'save')])
        request = import_command(module)
        request['bindings']['input2'] = ['input', 0]
        result = apply_commands(self.doc, [request])
        self.assertEqual(result['nodes']['copy_save']['inputs']['source'], ['input', 0])


class ReversiblePlanTests(unittest.TestCase):
    def test_undo_redo_preserve_complete_authoring_state_across_new_revisions(self):
        doc, _ = fixture()
        doc['disabled'] = ['pass']; doc['bypass'] = {'pass': {'0': 'source'}}
        edits = [{'op': 'remove_node', 'id': 'pass'}, {'op': 'rename', 'name': 'After'}]
        result = plan(doc, edits)
        self.assertEqual(result['format'], 'studio.workflow-command-plan/v1')
        self.assertEqual(result['document']['nodes']['save']['inputs']['source'], ['pass', 0])
        after = copy.deepcopy(result['document']); after['revision'] = 8
        undone = apply_commands(after, result['inverse_commands'])
        self.assertEqual(undone, doc | {'revision': 8})
        undone['revision'] = 9
        redone = apply_commands(undone, result['redo_commands'])
        self.assertEqual(redone, result['document'] | {'revision': 9})
        self.assertEqual(result['before_document_sha256'], digest(doc))
        self.assertEqual(result['after_document_sha256'], digest(result['document']))
        self.assertFalse(result['generation_submitted'])

    def test_inverse_refuses_unrelated_state_even_with_a_new_revision(self):
        doc, _ = fixture()
        result = plan(doc, [{'op': 'rename', 'name': 'After'}])
        unrelated = copy.deepcopy(result['document']); unrelated['positions']['pass'] = [999, 999]
        with self.assertRaises(ValueError) as caught:
            apply_commands(unrelated, result['inverse_commands'])
        self.assertEqual(type(caught.exception).__name__, 'StateConflict')
        self.assertEqual(unrelated['positions']['pass'], [999, 999])

    def test_malformed_assertions_are_not_coerced(self):
        doc, _ = fixture()
        self.assertTrue(hasattr(command_api, 'state_sha256'))
        for value in (None, '', 'x' * 64, True, 'a' * 65):
            with self.subTest(value=value), self.assertRaises(ValueError):
                apply_commands(doc, [{'op': 'assert_state', 'sha256': value}])
        self.assertEqual(apply_commands(doc, [{'op': 'assert_state', 'sha256': command_api.state_sha256(doc)}]), doc)

    def test_plan_copies_inputs_and_guard_covers_source_and_metadata(self):
        doc, _ = fixture(); edits = [{'op': 'rename', 'name': 'After'}]
        original = canonical(doc)
        result = plan(doc, edits)
        self.assertEqual(canonical(doc), original)
        edits[0]['name'] = 'Caller mutation'
        self.assertEqual(result['commands'][0]['name'], 'After')
        for mutation in ('source', 'metadata'):
            after = copy.deepcopy(result['document'])
            if mutation == 'source': after['source']['parent_assets'].clear()
            else: after['nodes']['pass']['_meta'] = {'edited': True}
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                apply_commands(after, result['inverse_commands'])

    def test_untransportable_inverse_refuses_only_planning_not_legacy_commands(self):
        doc, _ = fixture(); doc['source'] = {'padding': ''}
        doc['source']['padding'] = 'x' * (MAX_BYTES - len(canonical(doc)))
        self.assertEqual(len(canonical(doc)), MAX_BYTES)
        edits = [{'op': 'rename', 'name': 'After'}]
        self.assertEqual(apply_commands(doc, edits)['name'], 'After')
        with self.assertRaisesRegex(ValueError, 'restore'):
            plan(doc, edits)

    def test_failed_import_batch_has_no_partial_source_mutation(self):
        doc, _ = fixture(); module = api().export_module(doc, 'pipeline')
        before = canonical(doc)
        with self.assertRaises(ValueError):
            plan(doc, [{'op': 'rename', 'name': 'Never'}, import_command(module) | {'bindings': {}}])
        self.assertEqual(canonical(doc), before)


class ModuleReviewTests(unittest.TestCase):
    def test_boolean_boundary_port_cannot_alias_integer_port(self):
        doc, _ = fixture(); module = api().export_module(doc, 'pipeline')
        module['inputs'][0]['source'][1] = False
        with self.assertRaises(ValueError): api().validate_module(module)

    def test_node_limit_refuses_import_without_partial_changes(self):
        doc, _ = fixture(); module = api().export_module(doc, 'pipeline')
        for index in range(252): doc['nodes']['extra' + str(index)] = {'class_type': 'Value', 'inputs': {'value': 1}}
        before = canonical(doc)
        with self.assertRaises(ValueError): apply_commands(doc, [import_command(module)])
        self.assertEqual(canonical(doc), before)

    def test_nested_module_lineage_and_unselected_cycle_stay_inert(self):
        doc, schema = fixture(); module = api().export_module(doc, 'pipeline')
        first = apply_commands(doc, [import_command(module)])
        second_module = api().export_module(first, 'copy')
        self.assertEqual(second_module['document']['source']['module_imports'][0]['module_sha256'], digest(module))
        # The original module is editable authoring data; cyclic copies that are
        # not selected cannot suddenly become execution authority.
        cyclic = copy.deepcopy(module)
        cyclic['document']['nodes']['pass']['inputs']['source'] = ['save', 0]
        cyclic['inputs'] = []
        request = import_command(cyclic); request['bindings'] = {}
        imported = apply_commands(doc, [request])
        self.assertTrue(compile_document(imported, schema)['valid'])
        imported['outputs'].append('copy_save')
        self.assertFalse(compile_document(imported, schema)['valid'])


class ModulePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workspace = AssetWorkspace(self.temp.name); self.store = WorkflowDocuments(self.workspace)
        doc, self.schema = fixture()
        self.created = self.store.create({'request_id': 'module-create', 'document': doc})
        self.key = self.created['id']

    def snapshots(self):
        with self.workspace.connection() as db:
            return [tuple(row) for row in db.execute('SELECT revision,document,sha256 FROM workflow_revisions_v1 ORDER BY revision')]

    def test_saved_module_import_plan_undo_redo_and_historical_replay(self):
        self.assertTrue(hasattr(self.store, 'export_module'))
        exported = self.store.export_module(self.key, 'pipeline', 1)
        self.assertEqual(exported['module']['origin']['revision'], 1)
        self.assertEqual(exported['module']['origin']['document_id'], self.key)
        edits = [import_command(exported['module'])]
        before = self.snapshots()
        planned = self.store.plan(self.key, {'expected_revision': 1, 'commands': edits})
        self.assertEqual(self.snapshots(), before)
        payload = {'request_id': 'module-import', 'expected_revision': 1, 'commands': edits}
        first = self.store.command(self.key, payload)
        self.assertEqual(first['document_sha256'], planned['document_sha256'])
        self.assertEqual(planned['after_document_sha256'], first['document_sha256'])
        undone = self.store.command(self.key, {'request_id': 'module-undo', 'expected_revision': 2, 'commands': planned['inverse_commands']})
        self.assertEqual(undone['document'], self.created['document'] | {'revision': 3})
        redone = self.store.command(self.key, {'request_id': 'module-redo', 'expected_revision': 3, 'commands': planned['redo_commands']})
        self.assertEqual(redone['document'], first['document'] | {'revision': 4})
        reopened = WorkflowDocuments(AssetWorkspace(self.temp.name))
        self.assertEqual(reopened.get(self.key)['document'], redone['document'])
        replay = reopened.command(self.key, payload)
        self.assertTrue(replay['replayed']); self.assertEqual(replay['revision'], 2)
        self.assertEqual(replay['head_revision'], 4)
        self.assertEqual(replay['document'], first['document'])
        self.assertEqual(self.snapshots()[:1], before)

    def test_receipt_failure_rolls_back_all_import_changes(self):
        module = api().export_module(self.created['document'], 'pipeline')
        before = self.snapshots()
        with self.workspace.connection() as db:
            db.execute("CREATE TRIGGER refuse_request BEFORE INSERT ON workflow_requests_v1 BEGIN SELECT RAISE(ABORT,'fault'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.command(self.key, {'request_id': 'failed-import', 'expected_revision': 1, 'commands': [import_command(module)]})
        self.assertEqual(self.snapshots(), before)
        self.assertEqual(self.store.get(self.key)['revision'], 1)
        with self.workspace.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workflow_requests_v1').fetchone()[0], 1)

    def test_two_writers_cannot_import_at_the_same_revision(self):
        module = api().export_module(self.created['document'], 'pipeline')
        stores = [WorkflowDocuments(AssetWorkspace(self.temp.name)) for _ in range(2)]
        barrier = threading.Barrier(2)
        def attempt(index):
            barrier.wait(timeout=5)
            try:
                return stores[index].command(self.key, {'request_id': 'writer-' + str(index), 'expected_revision': 1,
                                                       'commands': [import_command(module)]})['revision']
            except DocumentError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(attempt, (0, 1)))
        self.assertCountEqual(results, [2, 'revision_conflict'])
        self.assertEqual(len(self.snapshots()), 2)

    def test_same_request_with_changed_module_is_not_repurposed(self):
        module = api().export_module(self.created['document'], 'pipeline')
        payload = {'request_id': 'one-import', 'expected_revision': 1, 'commands': [import_command(module)]}
        self.store.command(self.key, payload)
        before = self.snapshots()
        changed = copy.deepcopy(payload); changed['commands'][0]['name'] = 'Different'
        with self.assertRaises(DocumentError) as caught: self.store.command(self.key, changed)
        self.assertEqual(caught.exception.code, 'request_conflict')
        self.assertEqual(self.snapshots(), before)

    def test_legacy_v1_rows_remain_byte_identical_through_extension_use(self):
        # Simulate a v1 writer's noncanonical stored JSON, whose digest was
        # intentionally canonical. No migration is allowed to rewrite it.
        with self.workspace.connection() as db:
            legacy = json.dumps(self.created['document'], indent=2, ensure_ascii=False)
            db.execute('UPDATE workflow_revisions_v1 SET document=? WHERE document_id=?', (legacy, self.key))
        before = self.snapshots()
        reopened = WorkflowDocuments(AssetWorkspace(self.temp.name))
        self.assertEqual(reopened.get(self.key)['document'], self.created['document'])
        self.assertTrue(hasattr(reopened, 'export_module'))
        exported = reopened.export_module(self.key, 'pipeline', 1)
        reopened.command(self.key, {'request_id': 'legacy-module-import', 'expected_revision': 1,
                                   'commands': [import_command(exported['module'])]})
        self.assertEqual(self.snapshots()[:1], before)
        self.assertTrue(reopened.create({'request_id': 'module-create', 'document': fixture()[0]})['replayed'])
        self.assertEqual(self.snapshots()[:1], before)

    def test_saved_plan_limit_and_stale_guard_do_not_write(self):
        self.assertTrue(hasattr(self.store, 'plan'))
        before = self.snapshots()
        with patch('studio_workflow.documents.MAX_REVISIONS', 1), self.assertRaises(ValueError):
            self.store.plan(self.key, {'expected_revision': 1, 'commands': [{'op': 'rename', 'name': 'Next'}]})
        with self.assertRaises(DocumentError):
            self.store.plan(self.key, {'expected_revision': 2, 'commands': [{'op': 'rename', 'name': 'Next'}]})
        self.assertEqual(self.snapshots(), before)


if __name__ == '__main__':
    unittest.main()
