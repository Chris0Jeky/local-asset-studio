"""Reference-analysis admission distinguishes retained evidence from live generation."""
from types import SimpleNamespace
import unittest

from studio_prompt.reference_jobs import ReferenceJobs


class ReferenceIdleHistoryTests(unittest.TestCase):
    @staticmethod
    def service(jobs, *, running=None, pending=None):
        studio = SimpleNamespace(
            jobs=jobs,
            _tracking_stopped=lambda job: (
                isinstance(job.get('tracking_disposition'), dict)
                and job['tracking_disposition'].get('status') == 'stopped'
            ),
            _request=lambda *args, **kwargs: {
                'queue_running': list(running or []),
                'queue_pending': list(pending or []),
            },
        )
        return SimpleNamespace(studio=studio)

    def test_terminal_partial_and_stop_tracked_uncertain_history_do_not_block(self):
        service = self.service({
            'partial-history': {'status': 'partial'},
            'resolved-unknown': {
                'status': 'uncertain',
                'tracking_disposition': {'status': 'stopped', 'reason': 'operator reconciled'},
            },
            'completed-history': {'status': 'completed'},
        })
        ReferenceJobs._idle(service)

    def test_genuinely_live_or_unresolved_generation_still_blocks(self):
        for status in ('submitting', 'running', 'uncertain'):
            with self.subTest(status=status):
                service = self.service({'generation': {'status': status}})
                with self.assertRaisesRegex(ValueError, 'Reconcile existing generation work'):
                    ReferenceJobs._idle(service)

    def test_live_comfy_queue_still_blocks_when_retained_history_is_terminal(self):
        service = self.service(
            {'partial-history': {'status': 'partial'}},
            running=[{'prompt_id': 'live'}],
        )
        with self.assertRaisesRegex(ValueError, 'Comfy queue is busy'):
            ReferenceJobs._idle(service)


if __name__ == '__main__':
    unittest.main()
