"""Regression evidence for #71. All artwork and execution are synthetic fixtures."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import character_edit as edit, character_edit_bridge as bridge
from scripts.character_edit_demo import create
from scripts.character_study import read_json, sha
import test_character_edit_bridge as protocol
import test_character_edit_bridge_integration as integration

ROOT = Path(__file__).resolve().parents[1]


class ReferenceRoleContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'art'; self.plan = integration.reviewed_fixture(self.root)

    def optional(self, role, first=False):
        actor = self.plan['document']['actors'][0]
        ref = copy.deepcopy(actor['references'][0]); ref.update(id='optional', role=role)
        actor['references'].insert(0 if first else 1, ref)
        self.plan['intent']['document_sha256'] = sha(self.plan['document'])
        self.plan = edit.make_plan(self.plan['document'], self.plan['intent'], self.plan['catalog'])
        (self.root/'bridge-plan.json').write_text(json.dumps(self.plan), encoding='utf-8')

    def prepare(self, output='handoff'):
        return bridge.prepare(self.root, 'bridge-plan.json', output, [11], repo=ROOT)

    def test_optional_composition_rejected_before_output_or_http(self):
        self.optional('composition')
        with patch.object(bridge.StudioHTTP, 'request', side_effect=AssertionError('No HTTP')):
            with self.assertRaisesRegex(ValueError, 'optional reference'): self.prepare()
        self.assertFalse((self.root/'handoff').exists())

    def test_allowed_optional_roles_preserve_identity_first(self):
        original = copy.deepcopy(self.plan)
        for role in ('costume', 'pose', 'style'):
            with self.subTest(role=role):
                self.plan = copy.deepcopy(original); self.optional(role, first=True)
                value = self.prepare('handoff-'+role)
                self.assertEqual(['composition', 'identity', role], [r['role'] for r in value['references']])
                bridge.validate_handoff(self.root, value)

    def test_rehashed_optional_composition_rejected_at_handoff_boundary(self):
        self.optional('costume'); value = self.prepare()
        value['references'][2]['role'] = 'composition'
        value['sha256'] = bridge.hashed({k:v for k,v in value.items() if k != 'sha256'})
        with self.assertRaisesRegex(ValueError, 'optional reference'):
            bridge.validate_handoff(self.root, value)

    def test_rehashed_identity_slot_swap_rejected(self):
        self.optional('pose'); value = self.prepare()
        value['references'][1], value['references'][2] = value['references'][2], value['references'][1]
        value['sha256'] = bridge.hashed({k:v for k,v in value.items() if k != 'sha256'})
        with self.assertRaisesRegex(ValueError, 'identity'):
            bridge.validate_handoff(self.root, value)


class ContactContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)/'art'; create(root)
        self.doc = read_json(root/'document.json'); self.intent = read_json(root/'intent.json')
        third = copy.deepcopy(self.doc['actors'][0]); third['id'] = 'cobalt'; self.doc['actors'].append(third)
        self.intent.update(operation='interaction', scene_change=None,
            changes=[{'actor':a['id'], 'facet':'pose', 'instruction':'Review the declared contact'} for a in self.doc['actors']],
            budget={'owner':'test-contact', 'max_candidates':8, 'max_repairs':1},
            layout={'actors':[{'id':a['id'], 'bounds':a['bounds'], 'pose_reference':None} for a in self.doc['actors']],
                    'occlusion_order':['amber','violet','cobalt'], 'contact_regions':[]})
        self.cat = read_json(ROOT/'research/character-consistency/edit-routes.json')

    def relations(self, *pairs):
        self.doc['relations'] = [{'kind':'contact','from':a,'to':b,'note':'Explicit fixture contact'} for a,b in pairs]

    def regions(self, *groups):
        self.intent['layout']['contact_regions'] = [
            {'actors':list(g), 'bounds':[100,90,250,180], 'instruction':'Review these contacts'} for g in groups]

    def plan(self):
        self.intent['document_sha256'] = sha(self.doc)
        return edit.make_plan(self.doc, self.intent, self.cat)

    def test_declared_ab_but_region_bc_is_rejected(self):
        self.relations(('amber','violet')); self.regions(('violet','cobalt'))
        with self.assertRaisesRegex(ValueError, 'contact'): self.plan()

    def test_undeclared_extra_actor_in_group_is_rejected(self):
        self.relations(('amber','violet')); self.regions(('amber','violet','cobalt'))
        with self.assertRaisesRegex(ValueError, 'contact'): self.plan()

    def test_every_declared_target_pair_needs_a_region(self):
        self.relations(('amber','violet'), ('violet','cobalt')); self.regions(('amber','violet'))
        with self.assertRaisesRegex(ValueError, 'contact'): self.plan()

    def test_contact_is_undirected_and_regions_can_repeat_for_two_joints(self):
        self.relations(('violet','amber')); self.regions(('amber','violet'), ('violet','amber'))
        self.assertFalse(self.plan()['submits_generation'])

    def test_connected_three_actor_region_does_not_infer_a_clique(self):
        self.relations(('amber','violet'), ('violet','cobalt')); self.regions(('amber','violet','cobalt'))
        plan = self.plan(); self.assertEqual(2, len(plan['document']['relations']))
        edit.check_plan(plan)

    def test_pairwise_regions_cover_a_chain(self):
        self.relations(('amber','violet'), ('violet','cobalt')); self.regions(('amber','violet'), ('cobalt','violet'))
        edit.check_plan(self.plan())

    def test_disconnected_group_needs_separate_regions(self):
        fourth = copy.deepcopy(self.doc['actors'][0]); fourth['id'] = 'jade'; self.doc['actors'].append(fourth)
        self.intent['changes'].append({'actor':'jade','facet':'pose','instruction':'Contact cobalt'})
        self.intent['layout']['actors'].append({'id':'jade','bounds':fourth['bounds'],'pose_reference':None})
        self.intent['layout']['occlusion_order'].append('jade')
        self.relations(('amber','violet'), ('cobalt','jade')); self.regions(('amber','violet','cobalt','jade'))
        with self.assertRaisesRegex(ValueError, 'contact'): self.plan()
        self.regions(('amber','violet'), ('cobalt','jade')); edit.check_plan(self.plan())

    def test_scenario_cannot_smuggle_an_undeclared_contact(self):
        self.intent.update(operation='scenario', scene_change=copy.deepcopy(self.doc['scene']))
        self.relations(); self.regions(('amber','violet'))
        with self.assertRaisesRegex(ValueError, 'contact'): self.plan()
        self.relations(('amber','violet')); edit.check_plan(self.plan())

    def test_scenario_without_contacts_still_works(self):
        self.intent.update(operation='scenario', scene_change=copy.deepcopy(self.doc['scene']))
        self.relations(); self.regions(); edit.check_plan(self.plan())

    def test_rehashed_plan_cannot_bypass_contact_validation(self):
        self.relations(('amber','violet')); self.regions(('amber','violet')); plan = self.plan()
        plan['intent']['layout']['contact_regions'][0]['actors'] = ['violet','cobalt']
        plan['plan_sha256'] = sha({k:v for k,v in plan.items() if k != 'plan_sha256'})
        with self.assertRaises(ValueError): edit.check_plan(plan)


class CollectionRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        _, template = protocol.handoff(self.root); self.http = protocol.InertStudio(template)
        self.bridge = bridge.Bridge(self.root, 'handoff.json', self.http)
        self.pid = self.bridge.stage()['project']['id']; self.bridge.start(); self.aid = self.http.finish(self.pid)
        self.dest = self.bridge.directory/'candidate-0'
        self.posts = sum(m == 'POST' for m,_,_,_ in self.http.calls)

    def assert_read_only(self):
        self.assertEqual(self.posts, sum(m == 'POST' for m,_,_,_ in self.http.calls))
        self.assertEqual(1, len(self.http.projects))
        self.assertEqual(2, self.http.projects[self.pid]['budget']['reserved'])

    def test_failure_after_image_write_can_collect_again_without_generation(self):
        save = bridge.save_new
        def fail(path, data):
            save(path, data)
            if Path(path).name == 'candidate.png': raise OSError('Injected loss after image write')
        with patch.object(bridge, 'save_new', side_effect=fail), self.assertRaises(OSError):
            self.bridge.collect(0)
        self.assertFalse(self.dest.exists(), 'An incomplete candidate must not occupy the final path')
        partials = list(self.bridge.directory.glob('.candidate-0-*'))
        self.assertEqual(1, len(partials)); retained = (partials[0]/'candidate.png').read_bytes()
        recovered = bridge.Bridge(self.root, 'handoff.json', self.http).collect(0)
        self.assertEqual(retained, bridge.bytes_of(self.root, recovered['candidate']))
        self.assertEqual(retained, (partials[0]/'candidate.png').read_bytes())
        self.assertEqual(['fixture-prompt-not-a-model'], recovered['prompt_ids']); self.assert_read_only()

    def test_receipt_write_failure_never_publishes_partial_pair(self):
        save = bridge.save_new
        def fail(path, data):
            if Path(path).name == 'receipt.json':
                Path(path).write_bytes(b'{"truncated":'); raise OSError('Injected partial receipt')
            save(path, data)
        with patch.object(bridge, 'save_new', side_effect=fail), self.assertRaises(OSError): self.bridge.collect(0)
        self.assertFalse(self.dest.exists())
        partial = next(self.bridge.directory.glob('.candidate-0-*'))
        self.bridge.collect(0)
        self.assertEqual(b'{"truncated":', (partial/'receipt.json').read_bytes()); self.assert_read_only()

    def test_rename_failure_preserves_complete_stage_and_allows_fresh_collect(self):
        with patch.object(bridge.os, 'rename', side_effect=OSError('Injected rename failure')), self.assertRaises(OSError):
            self.bridge.collect(0)
        self.assertFalse(self.dest.exists())
        partial = next(self.bridge.directory.glob('.candidate-0-*')); before = (partial/'receipt.json').read_bytes()
        self.bridge.collect(0); self.assertEqual(before, (partial/'receipt.json').read_bytes()); self.assert_read_only()

    def test_failure_after_rename_leaves_a_complete_receipt_not_another_attempt(self):
        rename = os.rename
        def fail(src, dst): rename(src, dst); raise OSError('Injected lost return after publication')
        with patch.object(bridge.os, 'rename', side_effect=fail), self.assertRaises(OSError): self.bridge.collect(0)
        receipt = bridge.read(self.dest/'receipt.json'); raw = bridge.bytes_of(self.root, receipt['candidate'])
        with self.assertRaisesRegex(ValueError, 'already collected'): self.bridge.collect(0)
        self.assertEqual(raw, (self.dest/'candidate.png').read_bytes()); self.assert_read_only()

    def test_source_change_during_download_blocks_publication(self):
        request = self.http.request
        def drift(method, path, *args, **kwargs):
            result = request(method, path, *args, **kwargs)
            if path == '/api/assets/'+self.aid+'/file': (self.root/'source.png').write_bytes(b'changed')
            return result
        with patch.object(self.http, 'request', side_effect=drift), self.assertRaisesRegex(ValueError, 'Artifact changed'):
            self.bridge.collect(0)
        self.assertFalse(self.dest.exists()); self.assert_read_only()

    def test_staged_image_corruption_is_rejected_before_publication(self):
        save = bridge.save_new
        def corrupt(path, data):
            save(path, data)
            if Path(path).name == 'candidate.png': Path(path).write_bytes(b'corrupted')
        with patch.object(bridge, 'save_new', side_effect=corrupt), self.assertRaisesRegex(ValueError, 'Artifact changed'):
            self.bridge.collect(0)
        self.assertFalse(self.dest.exists()); self.assert_read_only()

    def test_staged_receipt_corruption_is_rejected_before_publication(self):
        save = bridge.save_new
        def corrupt(path, data):
            save(path, data)
            if Path(path).name == 'receipt.json': Path(path).write_bytes(b'{}')
        with patch.object(bridge, 'save_new', side_effect=corrupt), self.assertRaisesRegex(ValueError, 'receipt changed'):
            self.bridge.collect(0)
        self.assertFalse(self.dest.exists()); self.assert_read_only()

    def test_destination_appearing_during_staging_is_retained(self):
        save = bridge.save_new
        def appear(path, data):
            save(path, data)
            if Path(path).name == 'receipt.json': self.dest.mkdir()
        with patch.object(bridge, 'save_new', side_effect=appear), self.assertRaisesRegex(ValueError, 'already collected'):
            self.bridge.collect(0)
        self.assertEqual([], list(self.dest.iterdir())); self.assert_read_only()

    def test_receipt_byte_limit_precedes_staging(self):
        with patch.object(bridge, 'JSON_LIMIT', 64), self.assertRaisesRegex(ValueError, 'JSON byte limit'):
            self.bridge.collect(0)
        self.assertFalse(self.dest.exists()); self.assertEqual([], list(self.bridge.directory.glob('.candidate-0-*')))
        self.assert_read_only()

    def test_existing_legacy_partial_is_retained_not_silently_replaced(self):
        self.dest.mkdir(); raw = self.http.files[self.aid]; (self.dest/'candidate.png').write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'already collected'): self.bridge.collect(0)
        self.assertEqual(raw, (self.dest/'candidate.png').read_bytes())
        self.assertFalse((self.dest/'receipt.json').exists()); self.assert_read_only()

    def test_existing_empty_destination_is_not_replaced(self):
        self.dest.mkdir()
        with self.assertRaisesRegex(ValueError, 'already collected'): self.bridge.collect(0)
        self.assertEqual([], list(self.dest.iterdir())); self.assert_read_only()

    def test_symlink_destination_is_not_followed(self):
        outside = self.root/'other'; outside.mkdir()
        try: self.dest.symlink_to(outside, target_is_directory=True)
        except OSError as exc: self.skipTest('Symlink capability unavailable: '+str(exc))
        with self.assertRaises(ValueError): self.bridge.collect(0)
        self.assertEqual([], list(outside.iterdir())); self.assert_read_only()

    def test_overlapping_command_never_collects(self):
        with self.bridge.locked():
            with self.assertRaisesRegex(ValueError, 'bridge command'): self.bridge.collect(0)
        self.assertFalse(self.dest.exists()); self.assert_read_only()


class RecoveryHTTP(unittest.TestCase):
    # Reuse fixture setup, not its test methods; discovery must not inflate counts.
    setUp = integration.NativeHTTP.setUp
    shutdown = integration.NativeHTTP.shutdown

    def test_killed_collector_retains_lock_then_recovers_same_real_workspace_job(self):
        pid = self.bridge.stage()['project']['id']; self.bridge.start(); self.studio.queue.get_nowait()
        self.studio.production.run(pid)
        source_before = (self.art/'source.png').read_bytes()
        posts = []; original_post = self.http.RequestHandlerClass.do_POST
        def observed_post(handler):
            posts.append(handler.path); return original_post(handler)
        observer = patch.object(self.http.RequestHandlerClass, 'do_POST', observed_post)
        observer.start(); self.addCleanup(observer.stop)
        code = '''import os, sys
from pathlib import Path
from scripts import character_edit_bridge as b
original = b.save_new
def crash(path, data):
    original(path, data)
    if Path(path).name == "candidate.png": os._exit(73)
b.save_new = crash
print(os.getpid(), flush=True)
b.Bridge(sys.argv[1], "handoff/handoff.json", b.StudioHTTP(int(sys.argv[2]), timeout=10)).collect(0)
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.art), str(self.http.server_port)],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(73, result.returncode, result.stdout+result.stderr)
        lock = self.bridge.directory/'command.lock'; self.assertTrue(lock.is_file())
        self.assertEqual(result.stdout.strip(), lock.read_text().strip())
        self.assertFalse((self.bridge.directory/'candidate-0').exists())
        with self.assertRaisesRegex(ValueError, 'crash lock'): self.bridge.collect(0)
        # Explicit fixture-owner intervention AFTER wait proved the child exited.
        # Production deliberately never steals locks or infers PID reuse safety.
        lock.unlink()
        retained = next(self.bridge.directory.glob('.candidate-0-*'))
        raw = (retained/'candidate.png').read_bytes()
        receipt = self.bridge.collect(0)
        self.assertEqual(raw, bridge.bytes_of(self.art, receipt['candidate']))
        self.assertEqual(raw, (retained/'candidate.png').read_bytes())
        composed = self.bridge.compose(0, 'current-document.json', 'recovered-composition')
        self.assertEqual(4032, composed['composition']['changed_pixels'])
        self.assertEqual(0, composed['composition']['outside_mask_changed_pixels'])
        self.assertEqual(0, composed['composition']['protected_changed_pixels'])
        self.assertEqual(source_before, (self.art/'source.png').read_bytes())
        self.assertEqual(1, len(self.inference_calls)); self.assertEqual([], self.studio.requests)
        self.assertTrue(self.studio.queue.empty()); self.assertEqual(1, len(self.studio.production.list()))
        self.assertEqual({'allowance':3,'reserved':1}, self.studio.production.get(pid)['budget'])
        self.assertFalse(receipt['semantic_approval']); self.assertEqual([], posts)


if __name__ == '__main__': unittest.main()
