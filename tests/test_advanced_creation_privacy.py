"""Unsupported advanced operations must not publish private work into regular artifacts."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_production as production_fixture
# NativeExports adds scripts/ to sys.path; resolve the package before its CLI namesake.
from studio_av import project as _av_project
import test_native_exports as native_fixture
import test_workflow_document_runs as workflow_fixture
import test_recipe_shortlist_apply as setup_fixture
import test_gpu_lease as lease_fixture
import test_looks as look_fixture
from review_fixture import FixtureStudio, seed
from studio_workflow.execution import prepare_ticket, run_ticket
import backends
import parallax
import tiles
import looks


class ProductionPrivacyTests(unittest.TestCase):
    setUp = production_fixture.ProductionTests.setUp
    intent = production_fixture.ProductionTests.intent

    def assert_empty(self, studio, before):
        self.assertEqual(set(studio.production.root.rglob('*')), before)
        with studio.production.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM projects').fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM budgets').fetchone())
        self.assertTrue(studio.queue.empty())

    def test_private_production_payload_and_recipe_refuse_before_preparation(self):
        studio = production_fixture.FakeStudio(self.root, [])
        before = set(studio.production.root.rglob('*'))
        for placement in ('payload', 'recipe'):
            for privacy in ('private', 'all', None, True):
                with self.subTest(placement=placement, privacy=privacy):
                    payload = self.intent()
                    (payload if placement == 'payload' else payload['recipe'])['privacy'] = privacy
                    with patch.object(studio, 'prepare', wraps=studio.prepare) as prepare:
                        with self.assertRaisesRegex(ValueError, 'Private creation is not supported'):
                            studio.production.create(payload)
                    prepare.assert_not_called()
                    self.assert_empty(studio, before)

    def test_private_planned_stage_refuses_before_any_stage_preparation(self):
        studio = production_fixture.FakeStudio(self.root, [])
        before = set(studio.production.root.rglob('*'))
        stages = [{'label': 'regular', 'engine': 'demo', 'seed': 1,
                   'request': {'preset_id': 'demo', 'controls': {}}},
                  {'label': 'private', 'engine': 'demo', 'seed': 2,
                   'request': {'preset_id': 'demo', 'controls': {}, 'privacy': 'private'}}]
        with patch.object(studio, 'prepare', wraps=studio.prepare) as prepare:
            with self.assertRaisesRegex(ValueError, 'Private creation is not supported'):
                studio.production._create({'name': 'Private planned input'}, planned=stages)
        prepare.assert_not_called()
        self.assert_empty(studio, before)

    def test_native_source_never_copies_a_private_job_recipe(self):
        studio = production_fixture.FakeStudio(self.root, [])
        asset = studio.import_image('source.png', 'image/png', production_fixture.png())['asset']
        studio.jobs[asset['job_id']]['privacy'] = 'private'
        with patch.object(studio, 'export_recipe', wraps=studio.export_recipe) as export:
            with self.assertRaisesRegex(ValueError, 'Unknown asset'):
                studio.production._native_assets([asset['id']])
        export.assert_not_called()


class ReviewPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.studio = FixtureStudio(Path(self.temp.name)); self.project_id = seed(self.studio)

    def test_production_snapshot_does_not_join_private_job_details(self):
        job = next(iter(self.studio.jobs.values())); job['privacy'] = 'private'
        job['message'] = 'secret-private-message'
        result = self.studio.production.get(self.project_id)
        self.assertIsNone(result['stages'][0]['job'])
        self.assertNotIn('secret-private-message', json.dumps(result))

    def test_review_refuses_private_job_before_saving_evidence(self):
        job = next(iter(self.studio.jobs.values())); job['privacy'] = 'private'
        before = set(self.studio.production.root.rglob('*'))
        with self.assertRaisesRegex(ValueError, 'Unknown job'):
            self.studio.production.review(self.project_id, {'action': 'open'})
        self.assertEqual(set(self.studio.production.root.rglob('*')), before)
        with self.studio.production.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM comparison_reviews').fetchone())


@unittest.skipUnless(native_fixture.Image is not None, 'Optional Pillow not installed')
class NativePrivacyTests(unittest.TestCase):
    setUp = native_fixture.NativeExportTests.setUp
    tearDown = native_fixture.NativeExportTests.tearDown
    asset = native_fixture.NativeExportTests.asset

    def test_raw_private_asset_recipe_and_metadata_refuse_before_file_reads_or_exports(self):
        for field in ('asset', 'recipe', 'metadata'):
            with self.subTest(field=field):
                asset = self.asset('first.png', 'first-frame')
                if field == 'asset': asset['privacy'] = 'private'
                else: asset[field] = {'privacy': 'private', 'prompt': 'private source'}
                target = self.root / ('private-' + field)
                with patch('native_exports.sha256', wraps=__import__('native_exports').sha256) as read:
                    with self.assertRaisesRegex(native_fixture.NativeExportError, 'Private creation is not supported'):
                        self.exports.execute(target, 'atlas', [asset], {})
                read.assert_not_called()
                self.assertFalse(target.exists())


class JobContinuationPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name); (root / 'uploads').mkdir()
        self.source_data = b'fixture source'
        (root / 'uploads' / ('1' * 32 + '_source.png')).write_bytes(self.source_data)
        self.studio = SimpleNamespace(jobs={}, lock=threading.RLock(), experiments=root,
                                      runs=root / 'runs', _save=Mock())

    def stage(self, identifier, stage, privacy='regular'):
        plan = {'version': parallax.VERSION, 'preset_id': 'parallax-fixture',
                'source_asset_id': 'source-asset', 'source_sha256': hashlib.sha256(self.source_data).hexdigest(),
                'source_file': '1' * 32 + '_source.png', 'width': 512, 'height': 512,
                'objects': 'the desk', 'view_polygons': []}
        plan['plan_id'] = parallax.plan_id(plan)
        job = {'id': identifier, 'privacy': privacy, 'status': 'completed',
               'parallax': dict(plan, stage=stage), 'outputs': [{'asset_id': identifier + '-asset'}]}
        self.studio.jobs[identifier] = job
        return job

    def test_private_tile_job_is_unknown_even_when_a_cached_finish_exists(self):
        identifier = 'private-repaint'; finished_id = tiles.finish_id(identifier)
        self.studio.jobs[identifier] = {'id': identifier, 'privacy': 'private', 'tile': {'source': 'secret'},
                                        'tile_finish': {'job_id': finished_id}}
        self.studio.jobs[finished_id] = {'id': finished_id, 'outputs': []}
        before = copy.deepcopy(self.studio.jobs)
        with self.assertRaisesRegex(ValueError, '^Unknown job$'):
            tiles.finish(self.studio, identifier)
        self.assertEqual(self.studio.jobs, before); self.studio._save.assert_not_called()

    def test_regular_tile_cannot_recover_a_private_cached_finish(self):
        identifier = 'regular-repaint'; finished_id = tiles.finish_id(identifier)
        self.studio.jobs[identifier] = {'id': identifier, 'tile': {'source': 'regular'}}
        self.studio.jobs[finished_id] = {'id': finished_id, 'privacy': 'private', 'outputs': []}
        before = copy.deepcopy(self.studio.jobs)
        with self.assertRaisesRegex(ValueError, '^Unknown job$'):
            tiles.finish(self.studio, identifier)
        self.assertEqual(self.studio.jobs, before); self.studio._save.assert_not_called()

    def test_private_tile_and_parallax_recipes_refuse_before_claim_or_source_inspection(self):
        for module, key in ((tiles, 'tile'), (parallax, 'parallax')):
            with self.subTest(operation=key):
                with self.assertRaisesRegex(ValueError, 'Private creation is not supported'):
                    module.validate(self.studio, {'privacy': 'private', key: {}}, {key + '_route': True}, {}, 1)

    def test_private_parallax_next_stage_is_unknown(self):
        job = self.stage('private-plate', 'plate', 'private')
        with patch.object(parallax.continuation, 'source_context', return_value={'sha256': job['parallax']['source_sha256']}) as source:
            with self.assertRaisesRegex(ValueError, '^Unknown job$'):
                parallax.next_stage(self.studio, {'job_id': job['id']})
        source.assert_not_called()
        self.studio._save.assert_not_called()

    def test_private_parallax_primary_or_explicit_other_is_refused(self):
        plate = self.stage('plate', 'plate'); isolate = self.stage('isolate', 'isolate')
        for selected, expected in ((plate, '^Unknown job$'), (isolate, 'other job is not the other stage')):
            with self.subTest(job=selected['id']):
                selected['privacy'] = 'private'
                with self.assertRaisesRegex(ValueError, expected):
                    parallax._pair(self.studio, plate['id'], isolate['id'])
                selected['privacy'] = 'regular'
        self.studio._save.assert_not_called()

    def test_parallax_sibling_excludes_private_work_in_both_directions(self):
        plate = self.stage('plate', 'plate'); private = self.stage('private-isolate', 'isolate', 'private')
        self.assertIsNone(parallax.sibling(self.studio, plate))
        self.assertIsNone(parallax.sibling(self.studio, private))
        regular = self.stage('regular-isolate', 'isolate')
        self.assertIs(parallax.sibling(self.studio, plate), regular)


class WorkflowPrivacyTests(workflow_fixture.RunFixture, unittest.TestCase):
    def test_private_ticket_recipe_refuses_before_journal_directory_creation(self):
        ticket = prepare_ticket(self.runtime, {'preset_id': 'example', 'controls': {}})
        ticket['recipe']['privacy'] = 'private'
        with self.assertRaises(ValueError): run_ticket(self.runtime, ticket, True)
        self.assertFalse((self.runtime.runs / 'workflow-requests').exists())
        self.assertEqual(self.runtime.submissions, 0)

    def test_private_job_replay_has_the_same_response_as_absent_job(self):
        report = self.prepare()['record']['report']; run_ticket(self.runtime, report['ticket'], True)
        job = self.runtime.jobs.pop(report['job_id'])
        missing = run_ticket(self.runtime, report['ticket'], True)
        job.update(privacy='private', prompt_ids=['private-prompt'], outputs=[{'asset_id': 'private-output'}])
        self.runtime.jobs[job['id']] = job
        private = run_ticket(self.runtime, report['ticket'], True)
        self.assertEqual(private, missing); self.assertEqual(self.runtime.submissions, 1)

    def test_private_job_observation_has_the_same_response_as_absent_job(self):
        report = self.prepare()['record']['report']; run_ticket(self.runtime, report['ticket'], True)
        job = self.runtime.jobs.pop(report['job_id'])
        missing = self.store.observe(self.runtime, 'prepare-first')
        job.update(privacy='private', prompt_ids=['private-prompt'], outputs=[{'asset_id': 'private-output'}])
        self.runtime.jobs[job['id']] = job
        self.assertEqual(self.store.observe(self.runtime, 'prepare-first'), missing)
        self.assertEqual(self.runtime.submissions, 1)


class SetupPrivacyTests(unittest.TestCase):
    setUp = setup_fixture.SetupApplyTests.setUp
    store = setup_fixture.SetupApplyTests.store
    command = setup_fixture.SetupApplyTests.command

    def evidence(self):
        self.store()
        with self.s.assets.connection() as db:
            return [tuple(tuple(row) for row in db.execute('SELECT * FROM ' + table))
                    for table in ('setup_drafts_v1', 'setup_versions_v1', 'setup_operations_v1')]

    def test_private_reference_or_continuation_label_refuses_before_checkpoint(self):
        before = self.evidence()
        for placement in ('reference', 'continuation'):
            with self.subTest(placement=placement):
                draft = copy.deepcopy(self.before)
                if placement == 'reference': draft['recipe']['references'] = [{'privacy': 'private'}]
                else: draft['recipe']['continuation'] = {'privacy': 'private'}
                with self.assertRaisesRegex(ValueError, 'Private creation is not supported'):
                    self.command('create', request_id='private-' + placement, draft=draft)
                self.assertEqual(self.evidence(), before)
                self.assertEqual(self.s.upload_count, 0)

    def test_private_and_missing_lineage_sources_share_unavailable_refusal(self):
        before = self.evidence(); source_id = self.items[0]['asset_id']
        regular = self.s.assets.get(source_id)
        for placement in ('parent_assets', 'reference', 'continuation'):
            for source in ('private', 'missing'):
                with self.subTest(placement=placement, source=source):
                    draft = copy.deepcopy(self.before)
                    if placement == 'parent_assets': draft['recipe']['parent_assets'] = [source_id]
                    elif placement == 'reference': draft['recipe']['references'] = [{'parent_asset': source_id}]
                    else: draft['recipe']['continuation'] = {'source_asset_id': source_id}
                    with patch.object(self.s.assets, 'get', return_value=dict(regular, privacy='private'),
                                      side_effect=ValueError('Asset not found') if source == 'missing' else None) as lookup:
                        with self.assertRaisesRegex(ValueError, '^Setup source is unavailable; reselect it before checkpointing$'):
                            self.command('create', request_id=placement + '-' + source, draft=draft)
                    lookup.assert_called_once_with(source_id)
                    self.assertEqual(self.evidence(), before)
                    self.assertEqual(self.s.upload_count, 0)

    def test_regular_lineage_still_checkpoints_without_staging(self):
        source_id = self.items[0]['asset_id']; draft = copy.deepcopy(self.before)
        draft['recipe']['parent_assets'] = [source_id]
        result = self.command('create', draft=draft)
        self.assertEqual(result['draft'], draft); self.assertEqual(self.s.upload_count, 0)


class LookPrivacyTests(unittest.TestCase):
    setUp = look_fixture.LookTests.setUp
    create = look_fixture.LookTests.create

    def test_private_look_payload_refuses_before_seed_or_owner_writes(self):
        with patch.object(looks, 'ensure_seeds', wraps=looks.ensure_seeds) as seed:
            with self.assertRaisesRegex(ValueError, 'Private creation is not supported'):
                self.create(privacy='private')
        seed.assert_not_called(); self.assertEqual(self.studio.assets.cards('look'), [])

    def test_private_caller_lineage_refuses_before_seed_or_owner_writes(self):
        with patch.object(looks, 'ensure_seeds', wraps=looks.ensure_seeds) as seed:
            with self.assertRaisesRegex(ValueError, 'Private creation is not supported'):
                self.create(lineage=[{'role': 'evidence', 'privacy': 'private'}])
        seed.assert_not_called(); self.assertEqual(self.studio.assets.cards('look'), [])

    def test_known_private_job_lineage_refuses_before_seed_or_owner_writes(self):
        self.studio.jobs['private-job'] = {'id': 'private-job', 'privacy': 'private'}
        with patch.object(looks, 'ensure_seeds', wraps=looks.ensure_seeds) as seed:
            with self.assertRaisesRegex(ValueError, '^Unknown job$'):
                self.create(lineage=[{'role': 'anchor', 'job_id': 'private-job', 'sha256': 'a' * 64}])
        seed.assert_not_called(); self.assertEqual(self.studio.assets.cards('look'), [])

    def test_private_anchor_or_caller_asset_refuses_before_seed_or_owner_writes(self):
        private = {'id': 'private-asset', 'privacy': 'private', 'sha256': 'a' * 64, 'job_id': 'private-job'}
        for value in ({'anchor_asset_id': private['id']},
                      {'lineage': [{'role': 'anchor', 'asset_id': private['id']}]}):
            with self.subTest(value=value), patch.object(self.studio.assets, 'get', return_value=private), \
                 patch.object(looks, 'ensure_seeds', wraps=looks.ensure_seeds) as seed:
                with self.assertRaisesRegex(ValueError, '^Asset not found$'):
                    self.create(**value)
                seed.assert_not_called(); self.assertEqual(self.studio.assets.cards('look'), [])


class BackendPrivacyTests(unittest.TestCase):
    def manager(self, job):
        manager = backends.BackendManager.__new__(backends.BackendManager)
        manager.studio = SimpleNamespace(jobs={job['id']: job}, production=SimpleNamespace(list=lambda: []))
        manager.profiles = {'primary': {'id': 'primary', 'name': 'ComfyUI'}}
        manager.process = Mock(return_value=object())
        manager.request = Mock(return_value={'private-prompt': {'outputs': {}}})
        return manager

    def test_private_history_still_blocks_switching_without_disclosing_job_id(self):
        job = {'id': 'secret-private-job', 'privacy': 'private', 'status': 'uncertain',
               'tracking_disposition': {'status': 'stopped'}, 'prompt_ids': ['private-prompt']}
        manager = self.manager(job)
        with self.assertRaisesRegex(ValueError, 'Private work has a result') as caught:
            manager._stopped_results()
        self.assertNotIn('secret-p', str(caught.exception))
        manager.request.assert_called_once_with(manager.profiles['primary'], '/history/private-prompt')

    def test_private_active_jobs_still_reserve_gpu_work(self):
        for state in ('queued', 'waiting', 'submitting', 'running', 'uncertain'):
            with self.subTest(state=state):
                manager = self.manager({'id': 'private-job', 'privacy': 'private', 'status': state})
                self.assertTrue(manager._local_work())


class LeasePrivacyTests(unittest.TestCase):
    setUp = lease_fixture.GpuLeaseTests.setUp

    def stale_jobs(self):
        self.now[0] = 100_000.0
        self.studio.jobs = {
            key: {'id': key, 'privacy': privacy, 'status': 'uncertain', 'created_at': 1.0}
            for key, privacy in (('regular-stale', 'regular'), ('secret-private-stale', 'private'))}
        return tuple(sorted(self.studio.jobs))

    def test_stale_private_work_is_checked_but_redacted_from_grant_and_log(self):
        all_stale = self.stale_jobs(); manager = self.studio.backends
        with patch.object(manager, '_local_work', return_value=False) as work, \
             patch.object(manager, '_stopped_results') as history:
            result = self.lease.acquire({'holder': 'fixture-helper', 'ttl_seconds': 600})
        work.assert_called_once_with(ignore_job_ids=all_stale)
        history.assert_called_once_with(extra_job_ids=all_stale)
        self.assertEqual(result['ignored_stale_uncertain'], ['regular-stale'])
        self.assertNotIn('secret-private-stale', json.dumps(result))
        self.assertNotIn('secret-private-stale', (self.studio.root / '.runtime/studio-gpu-lease.log').read_text())

    def test_stale_private_ids_are_redacted_when_other_work_refuses_the_lease(self):
        all_stale = self.stale_jobs()
        with patch.object(self.studio.backends, '_local_work', return_value=True) as work:
            with self.assertRaises(lease_fixture.GpuLeaseError) as caught:
                self.lease.acquire({'holder': 'fixture-helper', 'ttl_seconds': 600})
        work.assert_called_once_with(ignore_job_ids=all_stale)
        self.assertEqual(caught.exception.details['ignored_stale_uncertain'], ['regular-stale'])
        self.assertNotIn('secret-private-stale', json.dumps(caught.exception.response()))
        self.assertFalse(self.lease.snapshot()['held'])


if __name__ == '__main__': unittest.main()
