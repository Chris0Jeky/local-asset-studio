"""CPU finishing owns a bounded queue; all generation replies are inert fixtures."""
import copy
import threading
import unittest
import uuid
from unittest.mock import patch

import test_parallax as fixture

parallax = fixture.parallax


class FinishWorkerTests(unittest.TestCase):
    setUp = fixture.RouteTests.setUp
    source = fixture.RouteTests.source
    prepared = fixture.RouteTests.prepared
    payload = fixture.RouteTests.payload
    run_stage = fixture.RouteTests.run_stage

    def studio(self):
        studio = fixture.FakeStudio(self.root)
        patch.stopall()  # Studio's generation/recovery threads remain parked; start only owned test threads.
        self.addCleanup(lambda: getattr(studio, 'parallax_finisher', None) and studio.parallax_finisher.close(timeout=5))
        return studio

    def pair(self, studio):
        stage = self.prepared(studio)
        with patch.object(parallax, 'finish_after_run'):
            plate = self.run_stage(studio, stage, self.pictures[1], 1)
            isolate = self.run_stage(studio, parallax.next_stage(studio, {'job_id': plate['id']}), self.pictures[2], 2)
        return plate, isolate

    def callers(self, studio, identifier, count=1):
        results, errors, threads = [], [], []
        def run():
            try: results.append(parallax.finish(studio, identifier))
            except Exception as exc: errors.append(exc)
        for _ in range(count):
            thread = threading.Thread(target=run, name='parallax-test-caller', daemon=True)
            thread.start(); threads.append(thread)
        return results, errors, threads

    def copied_stage(self, studio, job):
        copied = copy.deepcopy(job); copied['id'] = str(uuid.uuid4()); copied.pop('parallax_finish', None)
        copied['finished_at'] += 1
        (studio.runs / copied['id']).mkdir()
        studio.index_outputs(copied); studio._save(copied)
        studio.jobs[copied['id']] = copied
        return copied

    def test_one_cpu_worker_two_waiting_pairs_and_duplicate_callers_share_the_same_task(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        plates = [plate] + [self.copied_stage(studio, plate) for _ in range(3)]
        entered, release = threading.Event(), threading.Event()
        layers = parallax.layers; calls, owners = [], set()
        def blocked(*args, **kwargs):
            owners.add(threading.get_ident()); calls.append('split'); entered.set()
            if not release.wait(10): raise ValueError('test did not release CPU finishing')
            return layers(*args, **kwargs)
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(parallax, 'layers', side_effect=blocked):
            results, errors, callers = self.callers(studio, plate['id'], count=3)
            try:
                self.assertTrue(entered.wait(5))
                finisher = studio.parallax_finisher
                active = finisher.submit(plate['id'], isolate['id'])
                self.assertIs(finisher.submit(isolate['id'], plate['id']), active)
                for waiting in plates[1:3]: finisher.submit(waiting['id'], isolate['id'])
                with finisher.changed:
                    self.assertEqual(len(finisher.tasks), 3)
                    self.assertEqual(len(finisher.pending), 2)
                    self.assertEqual(finisher.active.id, active.id)
                    retained_worker = finisher.worker
                with self.assertRaisesRegex(ValueError, 'queue is full'):
                    parallax.finish(studio, plates[3]['id'], isolate['id'])
                parallax.finish_after_run(studio, plates[3])
                self.assertIn('queue is full', plates[3]['parallax_finish']['error'])
                self.assertEqual(plates[3]['status'], 'completed')
                self.assertEqual(len(calls), 1, 'waiting and duplicate calls must not decode or split yet')
            finally:
                release.set()
                for thread in callers: thread.join(10)
                self.assertTrue(studio.parallax_finisher.wait_idle(10))
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 3)
        self.assertTrue(all(result is results[0] for result in results))
        self.assertEqual(len(calls), 3)
        self.assertEqual(owners, {retained_worker.ident})
        self.assertFalse(retained_worker.is_alive(), 'a drained finisher must retire its owned thread')
        self.assertEqual(studio.parallax_finisher.tasks, {})

    def test_failure_releases_capacity_and_keeps_the_next_pair_running(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        next_plate = self.copied_stage(studio, plate)
        entered, release = threading.Event(), threading.Event(); calls = []
        layers = parallax.layers
        def fail_first(*args, **kwargs):
            calls.append('split')
            if len(calls) == 1:
                entered.set()
                if not release.wait(10): raise ValueError('test did not release CPU finishing')
                raise ValueError('synthetic CPU fault')
            return layers(*args, **kwargs)
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(parallax, 'layers', side_effect=fail_first):
            first = studio.parallax_finisher.submit(plate['id'], isolate['id'])
            try:
                self.assertTrue(entered.wait(5))
                second = studio.parallax_finisher.submit(next_plate['id'], isolate['id'])
            finally:
                release.set(); self.assertTrue(studio.parallax_finisher.wait_idle(10))
        self.assertIn('synthetic CPU fault', first.error)
        self.assertIn('synthetic CPU fault', plate['parallax_finish']['error'])
        self.assertEqual(plate['status'], 'completed')
        self.assertEqual(second.result['status'], 'completed')
        self.assertEqual(isolate['parallax_finish']['job_id'], second.id)
        self.assertIsNone(studio.parallax_finisher.worker)
        self.assertEqual(studio.parallax_finisher.tasks, {})
        self.assertNotIn(first.id, studio.jobs)

    def test_close_revokes_active_publication_and_clears_waiting_work(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        next_plate = self.copied_stage(studio, plate)
        entered, release = threading.Event(), threading.Event()
        layers = parallax.layers
        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(10): raise ValueError('test did not release CPU finishing')
            return layers(*args, **kwargs)
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(parallax, 'layers', side_effect=blocked):
            first = studio.parallax_finisher.submit(plate['id'], isolate['id'])
            try:
                self.assertTrue(entered.wait(5))
                second = studio.parallax_finisher.submit(next_plate['id'], isolate['id'])
                self.assertFalse(studio.parallax_finisher.close(timeout=0), 'a blocked CPU thread is reported, never silently treated as stopped')
                self.assertTrue(first.done.is_set()); self.assertTrue(second.done.is_set())
                self.assertFalse(studio.parallax_finisher.pending)
                with self.assertRaisesRegex(ValueError, 'stopped'): parallax.finish(studio, plate['id'], isolate['id'])
            finally:
                release.set(); self.assertTrue(studio.parallax_finisher.wait_idle(10))
        self.assertNotIn(first.id, studio.jobs); self.assertNotIn(second.id, studio.jobs)
        self.assertFalse((studio.runs / first.id).exists())
        self.assertFalse((studio.runs / second.id).exists())
        self.assertEqual(studio.parallax_finisher.tasks, {})

    def test_closed_cpu_owner_cannot_rewrite_a_newer_stage_record_on_exit(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        entered, release = threading.Event(), threading.Event(); layers = parallax.layers
        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(10): raise ValueError('test did not release CPU finishing')
            return layers(*args, **kwargs)
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(parallax, 'layers', side_effect=blocked):
            studio.parallax_finisher.submit(plate['id'], isolate['id'])
            try:
                self.assertTrue(entered.wait(5))
                self.assertFalse(studio.parallax_finisher.close(timeout=0))
                replacement = copy.deepcopy(plate); replacement['label'] = 'New owner after close'
                studio._save(replacement)
                path = studio.runs / plate['id'] / 'state.json'; retained = path.read_bytes()
                self.assertFalse(studio.parallax_finisher.close(timeout=0), 'a repeated close must not reacquire stage publication')
                parallax.finish_after_run(studio, plate)  # generation may finish after the HTTP server closes
            finally:
                release.set(); self.assertTrue(studio.parallax_finisher.wait_idle(10))
        self.assertEqual(path.read_bytes(), retained, 'closing revokes late status writes as well as output publication')

    def test_restart_keeps_explicit_split_retry_without_automatic_cpu_or_generation_work(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        identifier = parallax.finish_id(plate['id'], isolate['id'])
        for status, job in zip(('queued', 'running'), (plate, isolate)):
            job['parallax_finish'] = {'status': status, 'finish_id': identifier, 'attempt_id': 'interrupted',
                                      'stages': {'plate': plate['id'], 'isolate': isolate['id']}}
            studio._save(job)
        with patch.object(threading.Thread, 'start') as start:
            restarted = fixture.FakeStudio(self.root)
        self.addCleanup(restarted.parallax_finisher.close)
        self.assertIsNone(restarted.parallax_finisher.worker)
        self.assertTrue(restarted.queue.empty()); self.assertEqual(restarted.requests, [])
        for original in (plate, isolate):
            retained = restarted.jobs[original['id']]
            self.assertEqual(retained['status'], 'completed')
            self.assertEqual(retained['parallax_finish']['status'], 'failed')
            self.assertIn('Press Split layers', retained['parallax_finish']['error'])
            self.assertEqual(retained['submissions'], original['submissions'])
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})):
            result = parallax.finish(restarted, isolate['id'])
        self.assertEqual(result['id'], identifier)
        self.assertEqual(restarted.requests, [])

    def test_pending_pair_keeps_its_original_isolate_and_older_completion_cannot_take_its_link(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        next_plate = self.copied_stage(studio, plate)
        entered = [threading.Event(), threading.Event()]; release = [threading.Event(), threading.Event()]
        layers = parallax.layers; calls = []
        def blocked(*args, **kwargs):
            index = len(calls); calls.append(index); entered[index].set()
            if not release[index].wait(10): raise ValueError('test did not release CPU finishing')
            return layers(*args, **kwargs)
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(parallax, 'layers', side_effect=blocked):
            first = studio.parallax_finisher.submit(plate['id'], isolate['id'])
            try:
                self.assertTrue(entered[0].wait(5))
                second = studio.parallax_finisher.submit(next_plate['id'])
                newer_isolate = self.copied_stage(studio, isolate)
                release[0].set(); self.assertTrue(entered[1].wait(5))
                self.assertEqual(isolate['parallax_finish']['finish_id'], second.id)
                self.assertEqual(isolate['parallax_finish']['status'], 'running')
                self.assertNotIn('job_id', isolate['parallax_finish'], 'the older split must not replace the newer pending link')
                self.assertEqual(plate['parallax_finish']['job_id'], first.id)
            finally:
                for event in release: event.set()
                self.assertTrue(studio.parallax_finisher.wait_idle(10))
        self.assertEqual(second.result['parallax_receipt']['stages']['isolate']['job_id'], isolate['id'])
        self.assertNotIn('parallax_finish', newer_isolate)

    def test_claim_output_changes_and_job_deletion_revoke_publication(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        for change in ('claim', 'output', 'delete'):
            with self.subTest(change=change):
                current = self.copied_stage(studio, plate)
                entered, release = threading.Event(), threading.Event(); layers = parallax.layers
                def blocked(*args, **kwargs):
                    entered.set()
                    if not release.wait(10): raise ValueError('test did not release CPU finishing')
                    return layers(*args, **kwargs)
                with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
                     patch.object(parallax, 'layers', side_effect=blocked):
                    task = studio.parallax_finisher.submit(current['id'], isolate['id'])
                    try:
                        self.assertTrue(entered.wait(5))
                        with studio.lock:
                            if change == 'claim': current['parallax']['objects'] = 'changed foreground'
                            elif change == 'output': current['outputs'][0]['prompt_id'] = 'replaced-prompt'
                            else: studio.jobs.pop(current['id'])
                    finally:
                        release.set(); self.assertTrue(studio.parallax_finisher.wait_idle(10))
                self.assertIn('changed or was removed', task.error)
                self.assertNotIn(task.id, studio.jobs)
                self.assertFalse((studio.runs / task.id).exists())

    def test_png_failure_closes_owned_images_and_records_a_visible_split_failure(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        owned = []
        def registered(source, edit, fill):
            result = edit.copy(); owned.extend((source, edit, result)); return result, {'fallback': 'fixture'}
        with patch.object(parallax, 'register', side_effect=registered), \
             patch.object(parallax, 'png_bytes', side_effect=OSError('synthetic PNG failure')):
            with self.assertRaisesRegex(ValueError, 'synthetic PNG failure'): parallax.finish(studio, plate['id'], isolate['id'])
        self.assertTrue(studio.parallax_finisher.wait_idle(5))
        for image in owned:
            with self.assertRaises(ValueError): image.getpixel((0, 0))
        self.assertEqual(studio.parallax_finisher.tasks, {})
        self.assertIn('synthetic PNG failure', isolate['parallax_finish']['error'])
        self.assertFalse((studio.runs / parallax.finish_id(plate['id'], isolate['id'])).exists())

    def test_abnormal_worker_exit_returns_a_failure_to_the_explicit_waiter(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(parallax, 'layers', side_effect=SystemExit('synthetic CPU exit')):
            with self.assertRaisesRegex(ValueError, 'synthetic CPU exit'):
                parallax.finish(studio, plate['id'], isolate['id'])
        self.assertTrue(studio.parallax_finisher.wait_idle(5))
        self.assertEqual(studio.parallax_finisher.tasks, {})

    def test_link_save_fault_keeps_completed_receipt_and_exposes_non_durable_link(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        save = studio._save
        def fail_link(job, **kwargs):
            if job['id'] == plate['id'] and (job.get('parallax_finish') or {}).get('status') == 'completed':
                raise OSError('synthetic link-save failure')
            return save(job, **kwargs)
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(studio, '_save', side_effect=fail_link):
            result = parallax.finish(studio, plate['id'], isolate['id'])
        self.assertEqual(result['status'], 'completed')
        self.assertTrue((studio.runs / result['id'] / 'state.json').is_file())
        self.assertEqual(plate['parallax_finish']['job_id'], result['id'])
        self.assertIn('synthetic link-save failure', studio.public(plate)['parallax_finish'].get('recording_error', ''),
                      'a saved result survives, but its failed link publication must be visible')

    def test_cached_finish_record_must_belong_to_the_exact_pair(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        identifier = parallax.finish_id(plate['id'], isolate['id'])
        studio.jobs[identifier] = {'id': identifier, 'operation': parallax.OPERATION, 'status': 'completed', 'outputs': [],
                                   'parallax_receipt': {'plan': {}, 'stages': {}}}
        with self.assertRaisesRegex(ValueError, 'record'):
            parallax.finish(studio, plate['id'], isolate['id'])
        self.assertNotIn('parallax_finish', plate)

    def test_cached_status_retry_uses_its_completed_pair_after_a_newer_shared_pair_fails(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        entered, release = threading.Event(), threading.Event()
        def fail_newer_pair(*args, **kwargs):
            entered.set()
            if not release.wait(10): raise ValueError('test did not release CPU finishing')
            raise ValueError('synthetic newer pair failure')
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})):
            completed = parallax.finish(studio, plate['id'], isolate['id'])
            self.assertTrue(studio.parallax_finisher.wait_idle(5))
            newer_plate = self.copied_stage(studio, plate)
            with patch.object(parallax, 'layers', side_effect=fail_newer_pair):
                newer = studio.parallax_finisher.submit(newer_plate['id'], isolate['id'])
                try:
                    self.assertTrue(entered.wait(5))
                    running = copy.deepcopy(isolate['parallax_finish'])
                    self.assertIs(parallax.finish(studio, plate['id'], isolate['id']), completed)
                    self.assertEqual(isolate['parallax_finish'], running, 'cached reads must preserve a newer running pair')
                finally:
                    release.set(); self.assertTrue(studio.parallax_finisher.wait_idle(5))
            self.assertIn('synthetic newer pair failure', newer.error)
            self.assertEqual(isolate['parallax_finish']['finish_id'], newer.id)
            self.assertEqual(isolate['parallax_finish']['status'], 'failed')

            save = studio._save
            def fail_status_save(job, **kwargs):
                if job is isolate and (job.get('parallax_finish') or {}).get('status') == 'completed':
                    raise OSError('synthetic status save fault')
                return save(job, **kwargs)
            with patch.object(studio, '_save', side_effect=fail_status_save):
                self.assertIs(parallax.finish(studio, plate['id'], isolate['id']), completed)
            pair = {stage: record['job_id'] for stage, record in completed['parallax_receipt']['stages'].items()}
            for job in (plate, isolate):
                marker = job['parallax_finish']
                self.assertEqual(marker['job_id'], completed['id'])
                self.assertEqual(marker['finish_id'], completed['id'])
                self.assertEqual(marker['stages'], pair)
            self.assertNotIn('attempt_id', isolate['parallax_finish'], 'the failed newer attempt cannot describe a cached result')
            self.assertIn('synthetic status save fault', isolate['parallax_finish']['recording_error'])
            with patch.object(parallax, 'layers', wraps=parallax.layers) as split_again:
                # The status button sends its stage and this retained counterpart.
                result = parallax.finish(studio, isolate['id'], isolate['parallax_finish']['stages']['plate'])
            self.assertIs(result, completed)
            split_again.assert_not_called()
            self.assertNotIn('recording_error', isolate['parallax_finish'])
            self.assertNotIn(newer.id, studio.jobs)
            self.assertIsNone(studio.parallax_finisher.worker)

    def test_changed_source_is_rejected_before_final_output_files_exist(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        entered, release = threading.Event(), threading.Event()
        layers = parallax.layers
        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(10): raise ValueError('test did not release CPU finishing')
            return layers(*args, **kwargs)
        # Publication ownership is independent of the affine fit, covered by RegistrationTests.
        # Keep the event barrier reachable under the full suite's allocation tracing.
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(parallax, 'layers', side_effect=blocked):
            results, errors, callers = self.callers(studio, isolate['id'])
            try:
                self.assertTrue(entered.wait(5))
                studio.assets.file(plate['parallax']['source_asset_id']).write_bytes(fixture.png(fixture.Image.new('RGB', (512, 512), 'black')))
            finally:
                release.set()
                for thread in callers: thread.join(10)
        identifier = parallax.finish_id(plate['id'], isolate['id'])
        self.assertFalse(results, 'changed source bytes must never acquire a finished receipt')
        self.assertEqual(len(errors), 1)
        self.assertNotIn(identifier, studio.jobs)
        self.assertFalse((studio.runs / identifier).exists(), 'reject stale inputs before creating final outputs')
        self.assertEqual(plate['status'], 'completed')

    def test_replaced_stage_cannot_publish_or_link_the_replacement(self):
        studio = self.studio(); plate, isolate = self.pair(studio)
        entered, release = threading.Event(), threading.Event()
        layers = parallax.layers
        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(10): raise ValueError('test did not release CPU finishing')
            return layers(*args, **kwargs)
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(parallax, 'layers', side_effect=blocked):
            results, errors, callers = self.callers(studio, isolate['id'])
            try:
                self.assertTrue(entered.wait(5))
                replacement = copy.deepcopy(isolate); replacement.pop('parallax_finish', None)
                with studio.lock: studio.jobs[isolate['id']] = replacement
            finally:
                release.set()
                for thread in callers: thread.join(10)
        self.assertFalse(results, 'a removed or replaced stage revokes the original task publication')
        self.assertEqual(len(errors), 1)
        self.assertNotIn('parallax_finish', replacement)
        self.assertNotIn(parallax.finish_id(plate['id'], isolate['id']), studio.jobs)

    def test_next_generation_starts_while_resumed_stage_cpu_split_is_blocked(self):
        self.exercise_generation_queue('observe')

    def test_next_generation_starts_while_new_stage_cpu_split_is_blocked(self):
        self.exercise_generation_queue('generate')

    def exercise_generation_queue(self, action):
        studio = self.studio(); plate, isolate = self.pair(studio)
        replies = []
        if action == 'generate':
            stage = parallax.next_stage(studio, {'job_id': plate['id']})
            isolate = studio.jobs[studio.create_job(self.payload(stage), enqueue=False)['id']]
            replies = [{'queue_running': [], 'queue_pending': []}, {'prompt_id': 'isolate-prompt-2'},
                       {'isolate-prompt-2': {'status': {'status_str': 'success'}, 'outputs': {'13': {'images': [
                           {'filename': 'FLUX-Edit_00002_.png', 'subfolder': 'Verified', 'type': 'output'}]}}}}]
        else: isolate['status'] = 'uncertain'
        following = studio.jobs[studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)['id']]
        studio.replies = iter(replies + [{'queue_running': [], 'queue_pending': []}, {'prompt_id': 'following'},
                               {'following': {'status': {'status_str': 'success'}, 'outputs': {}}}])
        entered, release, submitted = threading.Event(), threading.Event(), threading.Event()
        layers, request = parallax.layers, studio._request
        finish_threads = []
        def blocked(*args, **kwargs):
            finish_threads.append(threading.get_ident()); entered.set()
            if not release.wait(10): raise ValueError('test did not release CPU finishing')
            return layers(*args, **kwargs)
        def observe_request(path, *args, **kwargs):
            response = request(path, *args, **kwargs)
            if path == '/prompt' and response.get('prompt_id') == 'following': submitted.set()
            return response
        # Exercise the real generation consumer and finish owner; the affine fit has separate tests.
        with patch.object(parallax, 'register', side_effect=lambda source, edit, fill: (edit.copy(), {'fallback': 'fixture'})), \
             patch.object(parallax, 'layers', side_effect=blocked), patch.object(studio, '_request', side_effect=observe_request), \
             patch.object(studio.queue, 'get', side_effect=[(action, isolate['id']), ('generate', following['id']), SystemExit]):
            worker = threading.Thread(target=studio._work, name='parallax-test-generation', daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(5), 'the retained pair must reach real CPU finishing')
                self.assertTrue(submitted.wait(2), 'the next queued generation must proceed while layer splitting is blocked')
                self.assertNotEqual(finish_threads, [worker.ident], 'CPU finishing must have a different owner from generation')
            finally:
                release.set(); worker.join(10)
                finisher = getattr(studio, 'parallax_finisher', None)
                if finisher: self.assertTrue(finisher.wait_idle(10))
        self.assertFalse(worker.is_alive())
        self.assertEqual(following['status'], 'completed')
        self.assertEqual(isolate['status'], 'completed')
        finished = studio.jobs[parallax.finish_id(plate['id'], isolate['id'])]
        self.assertEqual(finished['parallax_receipt']['stages']['isolate']['prompt_id'], 'isolate-prompt-2')


if __name__ == '__main__': unittest.main()
