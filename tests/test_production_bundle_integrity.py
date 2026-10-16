"""Execution admission revalidates recorded bytes; disposable models only."""
import hashlib
import os
import unittest
from unittest.mock import patch

import test_preset_model_readiness as fixture
import test_production as production_fixture

server = fixture.server


class ProductionBundleIntegrityTests(unittest.TestCase):
    setUp = fixture.PresetModelReadinessTests.setUp
    studio = fixture.PresetModelReadinessTests.studio
    put = fixture.PresetModelReadinessTests.put
    pin = fixture.PresetModelReadinessTests.pin
    pinned_file = fixture.PresetModelReadinessTests.pinned_file
    cache = fixture.PresetModelReadinessTests.cache
    preflight = fixture.PresetModelReadinessTests.preflight

    def bundle(self):
        pin, path = self.pinned_file()
        studio = self.studio()
        return studio, path, self.preflight(studio)

    def test_unchanged_recorded_model_is_freshly_hashed_without_cache_authority(self):
        studio, path, bundle = self.bundle()
        self.cache(path, 'f' * 64)
        with patch.object(server, 'digest_file', wraps=server.digest_file) as digest:
            studio.check_production_bundle(bundle)
        digest.assert_called_once_with(path.resolve())
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_same_size_rewrite_and_replacement_with_restored_mtime_are_refused(self):
        studio, path, bundle = self.bundle()
        original = path.read_bytes(); stamp = path.stat()
        for replace in (False, True):
            with self.subTest(replace=replace):
                path.write_bytes(original)
                os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                target = path.with_name('replacement.tmp') if replace else path
                target.write_bytes(b'x' * len(original))
                os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                if replace: os.replace(target, path)
                self.assertEqual(path.stat().st_size, bundle['models'][0]['bytes'])
                self.assertEqual(path.stat().st_mtime_ns, bundle['models'][0]['mtime_ns'])
                with self.assertRaisesRegex(server.StudioError, 'pinned model changed'):
                    studio.check_production_bundle(bundle)
                self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_missing_and_unreadable_recorded_models_are_clear_refusals(self):
        studio, path, bundle = self.bundle()
        raw = path.read_bytes(); stamp = path.stat()
        path.unlink()
        with self.assertRaisesRegex(server.StudioError, 'pinned model changed'):
            studio.check_production_bundle(bundle)
        path.write_bytes(raw); os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with patch.object(server, 'digest_file', side_effect=PermissionError('synthetic read denied')):
            with self.assertRaisesRegex(server.StudioError, 'pinned model changed'):
                studio.check_production_bundle(bundle)
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_model_changed_during_hash_is_refused_even_with_old_digest(self):
        studio, path, bundle = self.bundle()
        def changing(candidate):
            candidate.write_bytes(b'changed during admission')
            return bundle['models'][0]['sha256']
        with patch.object(server, 'digest_file', side_effect=changing):
            with self.assertRaisesRegex(server.StudioError, 'pinned model changed'):
                studio.check_production_bundle(bundle)
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())


class ProductionBundleCallerTests(unittest.TestCase):
    setUp = production_fixture.ProductionTests.setUp
    tearDown = production_fixture.ProductionTests.tearDown
    intent = production_fixture.ProductionTests.intent
    post_count = production_fixture.ProductionTests.post_count

    def test_each_unsubmitted_stage_checks_model_bytes_before_dispatch(self):
        self.patches[2].stop()
        for timing in ('before_start', 'between_stages', 'job_creation', 'unchanged'):
            for replace in (False, True):
                with self.subTest(timing=timing, replace=replace):
                    replies = []
                    for prompt in ('first', 'second'):
                        replies.extend([{'queue_running': [], 'queue_pending': []}, {'prompt_id': prompt},
                                        {prompt: {'status': {'status_str': 'success'}, 'outputs': {}}}])
                    studio = production_fixture.FakeStudio(self.root, replies)
                    path = self.root / 'fake-comfy/models/synthetic.safetensors'
                    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'synthetic')
                    stamp = path.stat()
                    bundle = dict(comfy_url=studio.comfy_url, comfy_root=str(studio.comfy_root),
                                  node_classes=[], schema_sha256=server.fingerprint({}), inputs=[],
                                  models=[dict(path=str(path), bytes=stamp.st_size, mtime_ns=stamp.st_mtime_ns,
                                               sha256=hashlib.sha256(path.read_bytes()).hexdigest())])
                    with patch.object(studio, 'production_preflight', return_value=bundle):
                        project = studio.production.create(self.intent())
                    plan_path = studio.production.root / project['id'] / 'plan.json'
                    planned = plan_path.read_bytes()
                    def rewrite():
                        target = path.with_name('replacement.tmp') if replace else path
                        target.write_bytes(b'x' * stamp.st_size)
                        os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                        if replace: os.replace(target, path)
                        self.assertEqual(path.stat().st_size, stamp.st_size)
                        self.assertEqual(path.stat().st_mtime_ns, stamp.st_mtime_ns)
                    create_job, run = studio.create_job, studio._run
                    def create(*args, **kwargs):
                        result = create_job(*args, **kwargs)
                        if timing == 'job_creation': rewrite()
                        return result
                    def generate(job):
                        run(job)
                        if timing == 'between_stages': rewrite()
                    if timing == 'before_start': rewrite()
                    studio.production.start(project['id'])
                    with patch.object(studio, 'create_job', side_effect=create), patch.object(studio, '_run', side_effect=generate):
                        if timing == 'unchanged': studio.production.run(project['id'])
                        else:
                            with self.assertRaisesRegex(server.StudioError, 'pinned model changed'):
                                studio.production.run(project['id'])
                    self.assertEqual(self.post_count(studio), 2 if timing == 'unchanged' else 1 if timing == 'between_stages' else 0)
                    self.assertEqual(plan_path.read_bytes(), planned)

    def test_changed_recorded_model_refuses_comparison_before_job_creation(self):
        # The normal Production fixture bypasses admission; restore the shipped check.
        self.patches[2].stop()
        studio = production_fixture.FakeStudio(self.root, [])
        path = self.root / 'fake-comfy/models/synthetic.safetensors'
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'synthetic')
        stamp = path.stat()
        bundle = dict(comfy_url=studio.comfy_url, comfy_root=str(studio.comfy_root),
                      node_classes=[], schema_sha256=server.fingerprint({}), inputs=[],
                      models=[dict(path=str(path), bytes=stamp.st_size, mtime_ns=stamp.st_mtime_ns,
                                   sha256=hashlib.sha256(path.read_bytes()).hexdigest())])
        with patch.object(studio, 'production_preflight', return_value=bundle):
            project = studio.production.create(self.intent(values=[1]))
        studio.production.start(project['id'])
        path.write_bytes(b'x' * stamp.st_size)
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with patch.object(studio, 'create_job', side_effect=AssertionError('Changed model reached job creation')) as create, \
                patch.object(studio, '_run') as generate:
            with self.assertRaisesRegex(server.StudioError, 'pinned model changed'):
                studio.production.run(project['id'])
        create.assert_not_called(); generate.assert_not_called()
        self.assertFalse(studio.jobs); self.assertEqual(self.post_count(studio), 0)
