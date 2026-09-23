"""Read-only preview routing and native compiler integration; no speech inference."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import spoken_brief as cli


class PreviewRoutingTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.binding = {'speaker_id': 'control', 'profile_id': 'control-profile'}
        self.source = Path('/synthetic/COMPRESSED.md')
        self.manifest = {'kind': 'spoken-brief', 'source': {'sha256': 'a' * 64},
                         'segments': [{'text': 'Caveat: the native check failed.'}],
                         'omissions': {'code_blocks': 1}}
        # create=True lets the pre-implementation control reach the missing-command failure.
        self.bind = self.stack.enter_context(mock.patch.object(
            cli, '_resolve_voice_profile', return_value=self.binding, create=True))
        self.resolve = self.stack.enter_context(mock.patch.object(cli, 'resolve_source', return_value=self.source))
        self.compile = self.stack.enter_context(mock.patch.object(cli, 'compile_source', return_value=self.manifest))
        self.plan = self.stack.enter_context(mock.patch.object(cli, 'plan', return_value={'kind': 'plan-control'}))
        self.run = self.stack.enter_context(mock.patch.object(cli, 'run', return_value={'kind': 'run-control'}))

    def invoke(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try: code = cli.main(args)
            except SystemExit as exc: code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_preview_emits_existing_manifest_without_plan_or_run(self):
        before = copy.deepcopy(self.manifest)
        code, out, err = self.invoke(['preview', 'pack'])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), before)
        self.assertEqual(self.manifest, before)
        self.bind.assert_called_once_with(
            cli.DEFAULT_PROFILE_ID, cli.DEFAULT_DELIVERY_ID, None, None, executable=False)
        self.resolve.assert_called_once_with('pack')
        self.compile.assert_called_once_with(self.source, speaker_id='control', voice_profile=self.binding)
        self.plan.assert_not_called(); self.run.assert_not_called()

    def test_preview_forwards_profile_and_metadata_options(self):
        code, _, err = self.invoke(['preview', 'pack', '--profile-id', 'selected',
                                   '--delivery-id', 'measured', '--profile-registry', 'local.json',
                                   '--speaker-id', 'narrator'])
        self.assertEqual(code, 0, err)
        self.bind.assert_called_once_with('selected', 'measured', 'local.json', 'narrator', executable=False)

    def test_preview_preserves_unicode(self):
        self.manifest['segments'] = [{'text': 'Résumé: 12 ms, not 12 s.'}]
        code, out, err = self.invoke(['preview', 'pack'])
        self.assertEqual(code, 0, err)
        self.assertIn('Résumé', out)

    def test_binding_failure_has_no_success_payload_or_compilation(self):
        self.bind.side_effect = cli.SpokenBriefError('binding refused')
        code, out, err = self.invoke(['preview', 'pack'])
        self.assertEqual(code, 1); self.assertEqual(out, '')
        self.assertIn('binding refused', err)
        self.compile.assert_not_called(); self.plan.assert_not_called(); self.run.assert_not_called()

    def test_source_failure_has_no_success_payload(self):
        self.resolve.side_effect = cli.SpokenBriefError('source refused')
        code, out, err = self.invoke(['preview', 'pack'])
        self.assertEqual(code, 1); self.assertEqual(out, '')
        self.assertIn('source refused', err)
        self.compile.assert_not_called(); self.plan.assert_not_called(); self.run.assert_not_called()

    def test_compiler_failure_has_no_success_payload(self):
        for error in (cli.SpokenBriefError('invalid Markdown'), OSError('cannot read')):
            with self.subTest(error=type(error).__name__):
                self.compile.side_effect = error
                code, out, err = self.invoke(['preview', 'pack'])
                self.assertEqual(code, 1); self.assertEqual(out, '')
                self.assertIn(str(error), err)
        self.plan.assert_not_called(); self.run.assert_not_called()

    def test_preview_refuses_execution_only_options(self):
        for option, value in (('--base-url', 'http://127.0.0.1:8191'),
                              ('--poll-seconds', '1'), ('--deadline-minutes', '1')):
            with self.subTest(option=option):
                code, out, _ = self.invoke(['preview', 'pack', option, value])
                self.assertEqual(code, 2); self.assertEqual(out, '')
        self.bind.assert_not_called(); self.plan.assert_not_called(); self.run.assert_not_called()

    def test_plan_control_keeps_existing_dispatch(self):
        code, out, err = self.invoke(['plan', 'pack'])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), {'kind': 'plan-control'})
        self.plan.assert_called_once_with('pack', profile_id=cli.DEFAULT_PROFILE_ID,
                                         delivery_id=cli.DEFAULT_DELIVERY_ID,
                                         profile_registry=None, speaker_id=None)
        self.bind.assert_not_called(); self.compile.assert_not_called(); self.run.assert_not_called()

    def test_run_control_keeps_deadline_conversion(self):
        code, out, err = self.invoke(['run', 'pack', '--deadline-minutes', '2', '--poll-seconds', '0.5'])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), {'kind': 'run-control'})
        self.assertEqual(self.run.call_args.kwargs['deadline_seconds'], 120)
        self.assertEqual(self.run.call_args.kwargs['poll_seconds'], 0.5)
        self.bind.assert_not_called(); self.compile.assert_not_called(); self.plan.assert_not_called()


class PreviewCompilerIntegrationTests(unittest.TestCase):
    """Uses the repository's real compiler, profile catalogue and read-only resolver."""
    def invoke(self, pack):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), \
                mock.patch.object(cli, 'plan', side_effect=AssertionError('preview called plan')), \
                mock.patch.object(cli, 'run', side_effect=AssertionError('preview called run')):
            code = cli.main(['preview', str(pack)])
        return code, out.getvalue(), err.getvalue()

    def test_real_preview_preserves_caveat_hash_omissions_and_retained_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = b'# Result\r\n\r\nThe unit check passed. Caveat: native playback failed.\r\n\r\n```text\r\nprivate diagnostic\r\n```\r\n'
            (root / 'COMPRESSED.md').write_bytes(raw)
            (root / 'INDEX.md').write_text('Wrong fallback.', encoding='utf-8')
            retained = root / '_spoken' / 'retained'
            retained.mkdir(parents=True)
            (retained / 'manifest.json').write_bytes(b'original manifest, never repair me')
            (retained / 'state.json').write_bytes(b'{"status":"create-unconfirmed"}')
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            names = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
            code, out, err = self.invoke(root)
            self.assertEqual(code, 0, err)
            value = json.loads(out)
            self.assertEqual(value['source']['name'], 'COMPRESSED.md')
            self.assertEqual(value['source']['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(value['source']['bytes'], len(raw))
            self.assertEqual(value['omissions']['code_blocks'], 1)
            text = ' '.join(s['text'] for s in value['segments'])
            self.assertIn('native playback failed', text)
            self.assertNotIn('private diagnostic', text)
            self.assertNotIn('Wrong fallback', text)
            self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()})
            self.assertEqual(names, sorted(str(p.relative_to(root)) for p in root.rglob('*')))

    def test_real_index_fallback_creates_no_spoken_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'INDEX.md').write_text('No action needed.', encoding='utf-8')
            code, out, err = self.invoke(root)
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)['source']['name'], 'INDEX.md')
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['INDEX.md'])

    def test_real_invalid_utf8_fails_without_output_or_pack_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'COMPRESSED.md').write_bytes(b'\xff')
            code, out, err = self.invoke(root)
            self.assertEqual(code, 1); self.assertEqual(out, '')
            self.assertIn('UTF-8', err)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['COMPRESSED.md'])


if __name__ == '__main__':
    unittest.main()
