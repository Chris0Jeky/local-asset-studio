"""Generate refuses a wildcard preview whose files changed since it was shown."""
import unittest

import test_server as fixture
import test_wildcard_preview as preview

server = fixture.server


class WildcardFreezeTests(unittest.TestCase):
    setUp = fixture.ServerTests.setUp
    tearDown = fixture.ServerTests.tearDown
    studio = preview.WildcardPreviewTests.studio
    handler = preview.WildcardPreviewTests.handler

    def previewed(self):
        studio = self.studio(); payload = {'preset_id':'demo','controls':{'positive':'portrait __lighting__','seed':'7'},'batch_count':2}
        return studio, payload, studio.wildcard_preview(payload)['wildcard_files']

    def post_jobs(self, studio, payload):
        handler, sent = self.handler(studio, payload); handler.path = '/api/jobs'; handler._require_gpu = lambda: None; handler.do_POST()
        return sent[0]

    def test_matching_digests_submit_and_no_digests_behave_as_before(self):
        studio, payload, digests = self.previewed()
        self.assertTrue(digests)
        self.assertEqual(studio.create_job(dict(payload, wildcard_digests=digests), enqueue=False)['batch_count'], 2)
        self.assertEqual(studio.create_job(payload, enqueue=False)['batch_count'], 2)
        studio.create_job(dict(payload, wildcard_digests={}), enqueue=False)

    def test_changed_or_removed_file_refuses_before_any_job_exists(self):
        studio, payload, digests = self.previewed(); tone = self.root/'presets/wildcards/tone.txt'
        for change in (lambda: tone.write_bytes(tone.read_bytes() + b'extra\n'), tone.unlink):
            with self.subTest(change=change):
                change()
                with self.assertRaisesRegex(server.StaleWildcardsError, 'The wildcard files changed since your preview. Preview again.') as caught:
                    studio.create_job(dict(payload, wildcard_digests=digests), enqueue=False)
                self.assertEqual(caught.exception.response()['files'], ['tone']); self.assertEqual(caught.exception.response()['code'], 'wildcards_changed')
                self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())
                tone.write_bytes(b'warm\ncool\n')

    def test_route_answers_409_for_stale_and_400_for_malformed_digests(self):
        studio, payload, digests = self.previewed()
        (self.root/'presets/wildcards/tone.txt').write_bytes(b'new\n')
        status, body = self.post_jobs(studio, dict(payload, wildcard_digests=digests))
        self.assertEqual(status, 409); self.assertIn('Preview again', body['error'])
        for bad in ('x', [1], {'../x':'0'*64}, {'tone':'nothex'}, {f'w{i}':'0'*64 for i in range(65)}):
            self.assertEqual(self.post_jobs(studio, dict(payload, wildcard_digests=bad))[0], 400, bad)
        self.assertFalse(studio.jobs)


if __name__ == '__main__': unittest.main()
