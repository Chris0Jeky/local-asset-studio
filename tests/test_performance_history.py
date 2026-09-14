"""Offline receipt contracts; numbers below are synthetic bytes, not GPU benchmarks."""
import copy
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def metadata(samples=2):
    return {'type': 'metadata', 'schema': 'studio.resource-profile/v1', 'samples_requested': samples,
            'interval_seconds_after_completion': 2, 'sampler_sha256': 'a' * 64, 'notes': ['PRIVATE_NOTE']}


def sample(index=0):
    return {'type': 'sample', 'observed_at': f'2026-09-14T00:00:{index:02d}+00:00',
            'host_commit': {'limit_bytes': 200, 'committed_bytes': 100, 'available_bytes': 100, 'unknown_reason': None},
            'physical_ram': {'total_bytes': 80, 'available_bytes': 30, 'unknown_reason': None},
            'processes': [{'pid': 12, 'created_at': 10, 'working_set_bytes': 20, 'private_bytes': 40,
                           'peak_working_set_bytes': 9999, 'cpu_one_core_percent': 150, 'unknown_reason': None}],
            'comfy': {'observed': True, 'versions': {'comfyui_version': '0.35.0', 'pytorch_version': '2.9.1'},
                      'devices': [{'index': 0, 'vram_total_bytes': 100, 'vram_free_bytes': 60,
                                   'torch_vram_total_bytes': 80, 'torch_vram_free_bytes': 30}],
                      'response_bytes': 500, 'elapsed_seconds': 0.01, 'unknown_reason': None},
            'sample_seconds': 0.02, 'private_extra': 'PRIVATE_PATH'}


def receipt(*records):
    return ''.join(json.dumps(record, allow_nan=False) + '\n' for record in records).encode()


class SummaryTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec('performance_history')
        self.assertIsNotNone(spec, 'The offline resource summary feature is not implemented yet')
        self.module = importlib.import_module('performance_history')

    def summarize(self, *records):
        return self.module.summarize_resource_profile(io.BytesIO(receipt(*records)))

    def test_same_sample_extrema_and_distinct_memory_domains(self):
        a, b = sample(), sample(2)
        b['host_commit'].update(committed_bytes=120, available_bytes=80)
        b['comfy']['devices'][0].update(vram_total_bytes=200, vram_free_bytes=170)
        raw = receipt(metadata(), a, b)
        result = self.module.summarize_resource_profile(io.BytesIO(raw))
        self.assertEqual(result['schema'], 'studio.resource-summary/v1')
        self.assertEqual(result['source']['receipt_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['source']['sampler_sha256'], 'a' * 64)
        self.assertEqual(result['metrics']['commit_headroom_bytes']['sampled_min'], 80)
        self.assertEqual(result['metrics']['physical_available_bytes']['sampled_min'], 30)
        self.assertEqual(result['comfy']['devices'][0]['metrics']['vram_used_bytes']['sampled_max'], 40)
        self.assertEqual(result['processes'][0]['metrics']['working_set_bytes']['sampled_max'], 20)
        self.assertEqual(result['processes'][0]['metrics']['cpu_one_core_percent']['sampled_max'], 150)
        self.assertNotIn('peak_working_set', json.dumps(result))
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertTrue(result['sampling']['complete'])
        self.assertEqual(result['sampling']['observed_span_seconds'], 2)

    def test_unknown_is_not_zero_and_zero_is_known(self):
        a, b, c = sample(), sample(1), sample(2)
        b['host_commit'] = {'unknown_reason': 'PRIVATE_COUNTER_ERROR'}
        c['host_commit'].update(committed_bytes=200, available_bytes=0)
        m = self.summarize(metadata(3), a, b, c)['metrics']['commit_headroom_bytes']
        self.assertEqual(m, {'sampled_min': 0, 'sampled_max': 100, 'known_samples': 2, 'unknown_samples': 1})

    def test_invalid_numeric_counters_become_unknown(self):
        for bad in (True, -1, '12', 2**100, None):
            with self.subTest(bad=bad):
                a = sample(); a['physical_ram']['available_bytes'] = bad
                m = self.summarize(metadata(1), a)['metrics']['physical_available_bytes']
                self.assertIsNone(m['sampled_min']); self.assertEqual(m['unknown_samples'], 1)
        raw = receipt(metadata(1), sample()).replace(b'"available_bytes": 30', b'"available_bytes": 1e9999')
        m = self.module.summarize_resource_profile(io.BytesIO(raw))['metrics']['physical_available_bytes']
        self.assertEqual(m['known_samples'], 0)

    def test_contradictory_pairs_and_status_are_not_trusted(self):
        a = sample(); a['host_commit']['available_bytes'] = 99
        a['physical_ram']['available_bytes'] = 81
        a['comfy']['devices'][0]['vram_free_bytes'] = 101
        a['processes'][0]['unknown_reason'] = 'unavailable'
        result = self.summarize(metadata(1), a)
        for key in ('commit_headroom_bytes', 'commit_used_bytes', 'physical_available_bytes'):
            self.assertEqual(result['metrics'][key]['known_samples'], 0)
        self.assertEqual(result['comfy']['devices'][0]['metrics']['vram_used_bytes']['known_samples'], 0)
        self.assertEqual(result['processes'][0]['metrics']['private_bytes']['known_samples'], 0)

    def test_zero_device_and_torch_totals_are_valid_observations(self):
        a = sample()
        a['comfy']['devices'][0].update(vram_total_bytes=0, vram_free_bytes=0,
                                       torch_vram_total_bytes=0, torch_vram_free_bytes=0)
        result = self.summarize(metadata(1), a)
        for key in ('vram_total_bytes', 'vram_free_bytes', 'vram_used_bytes',
                    'torch_vram_total_bytes', 'torch_vram_free_bytes', 'torch_vram_used_bytes'):
            self.assertEqual(result['comfy']['devices'][0]['metrics'][key],
                             {'sampled_min': 0, 'sampled_max': 0, 'known_samples': 1, 'unknown_samples': 0})

    def test_invalid_collection_shapes_and_identity_types_refused(self):
        mutations = [lambda a: a.update(host_commit=[]), lambda a: a.update(physical_ram='bad'),
                     lambda a: a.update(processes={}), lambda a: a.update(comfy=[]),
                     lambda a: a['processes'][0].update(pid=True),
                     lambda a: a['processes'][0].update(created_at=True),
                     lambda a: a['comfy'].update(versions=[]),
                     lambda a: a['comfy'].update(devices={}),
                     lambda a: a['comfy']['devices'][0].update(index=True)]
        for mutate in mutations:
            a = sample(); mutate(a)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.summarize(metadata(1), a)

    def test_missing_versions_do_not_erase_previously_known_identity(self):
        a, b, c = sample(), sample(1), sample(2)
        b['comfy']['versions'] = {}
        result = self.summarize(metadata(3), a, b, c)
        self.assertEqual(result['comfy']['versions'], a['comfy']['versions'])
        c['comfy']['versions']['pytorch_version'] = 'different'
        with self.assertRaises(ValueError): self.summarize(metadata(3), a, b, c)

    def test_offline_runtime_does_not_contribute_device_values(self):
        a, b = sample(), sample(1); b['comfy']['observed'] = False
        b['comfy']['devices'][0]['vram_free_bytes'] = 0
        result = self.summarize(metadata(), a, b)
        self.assertEqual(result['comfy']['unobserved_samples'], 1)
        self.assertEqual(result['comfy']['devices'][0]['metrics']['vram_free_bytes']['sampled_min'], 60)
        self.assertEqual(result['comfy']['devices'][0]['metrics']['vram_free_bytes']['unknown_samples'], 1)

    def test_metadata_only_and_interrupted_receipts_are_explicit(self):
        for samples in ((), (sample(),)):
            result = self.summarize(metadata(), *samples)
            self.assertFalse(result['sampling']['complete'])
            self.assertEqual(result['sampling']['observed'], len(samples))
            self.assertNotIn('success', result)
            self.assertNotIn('job_wall_seconds', result)
        self.assertIsNone(self.summarize(metadata())['sampling']['observed_span_seconds'])

    def test_missing_metrics_stay_unknown_without_invented_devices(self):
        a = {'type': 'sample', 'observed_at': sample()['observed_at']}
        result = self.summarize(metadata(1), a)
        self.assertEqual(result['comfy']['devices'], [])
        self.assertEqual(result['metrics']['commit_headroom_bytes']['unknown_samples'], 1)

    def test_observable_runtime_version_and_device_layout_changes_refused(self):
        for mutate in (lambda x: x['comfy']['versions'].update(pytorch_version='changed'),
                       lambda x: x['comfy'].update(devices=[])):
            a, b = sample(), sample(1); mutate(b)
            with self.assertRaises(ValueError): self.summarize(metadata(), a, b)

    def test_pid_reuse_and_late_initial_identity_refused(self):
        for created in (10, None):
            a, b = sample(), sample(1); a['processes'][0]['created_at'] = created
            b['processes'][0]['created_at'] = 11
            with self.assertRaises(ValueError): self.summarize(metadata(), a, b)

    def test_missing_process_samples_count_towards_coverage(self):
        a, b = sample(), sample(1); a['processes'] = []
        result = self.summarize(metadata(), a, b)
        self.assertEqual(result['processes'][0]['metrics']['private_bytes']['unknown_samples'], 1)

    def test_no_created_identity_cannot_certify_process_counters(self):
        a = sample(); a['processes'][0]['created_at'] = None
        result = self.summarize(metadata(1), a)
        self.assertEqual(result['processes'][0]['metrics']['working_set_bytes']['known_samples'], 0)

    def test_timestamp_order_timezone_and_shape(self):
        for value in ('invalid', '2026-09-14T00:00:00', 'PRIVATE' * 20, None):
            a = sample(); a['observed_at'] = value
            with self.assertRaises(ValueError): self.summarize(metadata(1), a)
        with self.assertRaises(ValueError): self.summarize(metadata(), sample(2), sample(1))
        self.assertTrue(self.summarize(metadata(), sample(), sample())['sampling']['complete'])

    def test_metadata_validation_and_extra_samples(self):
        cases = [dict(metadata(), schema='future'), dict(metadata(), samples_requested=True),
                 dict(metadata(), samples_requested=121), dict(metadata(), samples_requested=0),
                 dict(metadata(), sampler_sha256='PRIVATE'), dict(metadata(), interval_seconds_after_completion=0)]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError): self.summarize(case)
        with self.assertRaises(ValueError): self.summarize(metadata(1), sample(), sample(1))
        with self.assertRaises(ValueError): self.summarize(metadata(), sample(), metadata())
        with self.assertRaises(ValueError): self.summarize(sample())

    def test_bad_json_duplicate_keys_constants_and_truncation(self):
        for raw in (b'', b'\n', b'{}\n', b'[]\n', b'{', b'{"type":"metadata","type":"sample"}\n',
                    b'{"value":NaN}\n', b'\xff', b'[' * 2000):
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                self.module.summarize_resource_profile(io.BytesIO(raw))
        raw = receipt(metadata(), sample()) + b'{"type":"sam'
        with self.assertRaises(ValueError): self.module.summarize_resource_profile(io.BytesIO(raw))

    def test_duplicate_processes_and_device_indices_refused(self):
        for group in ('processes', 'devices'):
            a = sample()
            values = a['processes'] if group == 'processes' else a['comfy']['devices']
            values.append(copy.deepcopy(values[0]))
            with self.assertRaises(ValueError): self.summarize(metadata(1), a)

    def test_cardinality_and_line_limits(self):
        for n, group in ((17, 'processes'), (9, 'devices')):
            a = sample()
            if group == 'processes': a[group] = [dict(a[group][0], pid=i+1) for i in range(n)]
            else: a['comfy'][group] = [dict(a['comfy'][group][0], index=i) for i in range(n)]
            with self.assertRaises(ValueError): self.summarize(metadata(1), a)
        raw = b' ' * (self.module.MAX_LINE_BYTES + 1)
        with self.assertRaises(ValueError): self.module.summarize_resource_profile(io.BytesIO(raw))
        records = [dict(sample(), observed_at='2026-09-14T00:00:00+00:00') for _ in range(120)]
        self.assertTrue(self.summarize(metadata(120), *records)['sampling']['complete'])
        with self.assertRaises(ValueError): self.summarize(metadata(120), *records, sample())

    def test_global_process_bound_not_only_per_sample(self):
        records=[]
        for i in range(17):
            a=sample(i); a['processes'][0]['pid']=i+1; records.append(a)
        with self.assertRaises(ValueError): self.summarize(metadata(17), *records)

    def test_reads_bounded_lines_and_hashes_exact_bytes(self):
        class Bounded(io.BytesIO):
            def readline(self, size=-1):
                if size <= 0 or size > 1024 * 1024 + 1: raise AssertionError('unbounded read')
                return super().readline(size)
            def read(self, *args): raise AssertionError('whole-file read')
        raw = receipt(metadata(1), sample()).rstrip(b'\n')
        result = self.module.summarize_resource_profile(Bounded(raw))
        self.assertEqual(result['source']['receipt_sha256'], hashlib.sha256(raw).hexdigest())

    def test_actual_producer_output_is_consumed_without_live_probes(self):
        from resource_probe import write_samples
        observations = iter([sample(), sample(2)])
        out = io.StringIO()
        write_samples(out, SimpleNamespace(sample=lambda: next(observations)), samples=2, interval=2, sleep=lambda _: None)
        result = self.module.summarize_resource_profile(io.BytesIO(out.getvalue().encode()))
        self.assertEqual(result['sampling']['observed'], 2)
        self.assertEqual(result['source']['sampler_sha256'], hashlib.sha256((ROOT/'app/resource_probe.py').read_bytes()).hexdigest())


class CommandTests(unittest.TestCase):
    def run_command(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(ROOT/'scripts/summarize-resources.py'), *map(str,args)],
                              capture_output=True, text=True, cwd=cwd, timeout=10)

    def test_cli_round_trip_stdout_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); src=root/'input.jsonl'; dest=root/'summary.json'
            original=receipt(metadata(1),sample()); src.write_bytes(original)
            result=self.run_command(src, '--output', dest, cwd=directory)
            self.assertEqual(result.returncode,0,result.stderr)
            data=json.loads(dest.read_text()); self.assertEqual(data['sampling']['observed'],1)
            self.assertEqual(src.read_bytes(),original)
            before=dest.read_bytes()
            self.assertNotEqual(self.run_command(src,'--output',dest).returncode,0)
            self.assertEqual(dest.read_bytes(),before)
            self.assertNotEqual(self.run_command(src,'--output',src).returncode,0)
            self.assertEqual(src.read_bytes(),original)
            result=self.run_command(src,cwd=directory)
            self.assertEqual(json.loads(result.stdout),data)

    def test_bad_input_leaves_no_output_and_does_not_echo_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            src=Path(directory)/'input'; dest=Path(directory)/'result'
            for data in (b'PRIVATE_PATH',receipt(metadata())+b'{'):
                src.write_bytes(data); result=self.run_command(src,'--output',dest)
                self.assertNotEqual(result.returncode,0); self.assertFalse(dest.exists())
                self.assertNotIn('PRIVATE_PATH',result.stderr); self.assertNotIn('Traceback',result.stderr)
            for path in (Path(directory),Path(directory)/'missing'):
                result=self.run_command(path,'--output',dest)
                self.assertNotEqual(result.returncode,0); self.assertFalse(dest.exists())

    @unittest.skipUnless(hasattr(os,'mkfifo'),'FIFO fixture is POSIX-specific')
    def test_non_regular_input_cannot_block(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pipe'; os.mkfifo(path)
            result=self.run_command(path)
            self.assertNotEqual(result.returncode,0); self.assertNotIn('Traceback',result.stderr)

    def test_cli_does_not_import_live_owners_or_start_network_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            src=Path(directory)/'input'; src.write_bytes(receipt(metadata(1),sample()))
            program='''import sys,runpy
blocked={'torch','server','psutil','resource_probe','subprocess','http.client'}
class Guard:
 def find_spec(self,fullname,path=None,target=None):
  if fullname in blocked: raise AssertionError('live dependency '+fullname)
sys.meta_path.insert(0,Guard())
def audit(event,args):
 if event in ('socket.connect','socket.bind','subprocess.Popen','os.system'): raise AssertionError(event)
sys.addaudithook(audit)
sys.argv=[sys.argv[1],sys.argv[2]]
runpy.run_path(sys.argv[0],run_name='__main__')
'''
            result=subprocess.run([sys.executable,'-c',program,str(ROOT/'scripts/summarize-resources.py'),str(src)],
                                  capture_output=True,text=True,timeout=10,cwd=directory)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['sampling']['observed'],1)


if __name__=='__main__': unittest.main()
