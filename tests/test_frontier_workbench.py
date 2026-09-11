import copy
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('frontier_workbench', ROOT / 'scripts/frontier_workbench.py')
fw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fw)


class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.catalog, self.recipes = fw.load(ROOT)

    def sample(self, tmp, name='minimax_h3_fl2va_pruned_int8_convrot.safetensors', header=None):
        header = header or {'weight': {'dtype': 'F32', 'shape': [1], 'data_offsets': [0, 4]}}
        raw = json.dumps(header).encode()
        path = Path(tmp) / name
        path.write_bytes(struct.pack('<Q', len(raw)) + raw + b'\0' * 4)
        return path

    def test_catalog_valid(self):
        result = fw.validate(self.catalog, self.recipes)
        self.assertGreaterEqual(result['entries'], 40)
        self.assertGreaterEqual(result['blueprints'], 12)
        self.assertFalse(result['generation_submitted'])

    def test_duplicate_id(self):
        self.catalog['entries'].append(self.catalog['entries'][0])
        with self.assertRaises(ValueError): fw.validate(self.catalog, self.recipes)

    def test_unsafe_url(self):
        self.catalog['entries'][0]['source'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError): fw.validate(self.catalog, self.recipes)

    def test_credentials_in_url(self):
        self.catalog['entries'][0]['source'] = 'https://secret@example.com/path'
        with self.assertRaises(ValueError): fw.validate(self.catalog, self.recipes)

    def test_no_implicit_verification(self):
        self.catalog['entries'][0]['local_verified'] = True
        with self.assertRaises(ValueError): fw.validate(self.catalog, self.recipes)

    def test_access_blocked_stays_unresolved(self):
        self.catalog['entries'][0]['source_status'] = 'access_blocked'
        with self.assertRaises(ValueError): fw.validate(self.catalog, self.recipes)

    def test_unknown_recipe_source(self):
        self.recipes['recipes'][0]['sources'] = ['not-a-source']
        with self.assertRaises(ValueError): fw.validate(self.catalog, self.recipes)

    def test_non_executable_required(self):
        self.recipes['kind'] = 'executable'
        with self.assertRaises(ValueError): fw.validate(self.catalog, self.recipes)

    def test_empty_stages(self):
        self.recipes['recipes'][0]['stages'] = []
        with self.assertRaises(ValueError): fw.validate(self.catalog, self.recipes)

    def test_duplicate_variants(self):
        self.recipes['recipes'][0]['variants'] = ['same', 'same']
        with self.assertRaises(ValueError): fw.validate(self.catalog, self.recipes)

    def test_plan_reproducible(self):
        one = fw.plan(self.catalog, self.recipes, 'h3-seed-lab', 'Observatory')
        two = fw.plan(self.catalog, self.recipes, 'h3-seed-lab', 'Observatory')
        self.assertEqual(one, two)
        self.assertFalse(one['executable'])
        self.assertEqual(len(one['jobs']), 6)
        self.assertEqual({j['seed'] for j in one['jobs']}, {4200, 4201})

    def test_changed_brief_changes_hash(self):
        a = fw.plan(self.catalog, self.recipes, 'h3-seed-lab', 'Observatory')
        b = fw.plan(self.catalog, self.recipes, 'h3-seed-lab', 'Garden')
        self.assertNotEqual(a['plan_sha256'], b['plan_sha256'])

    def test_source_change_changes_hash(self):
        a = fw.plan(self.catalog, self.recipes, 'h3-seed-lab', 'Observatory')
        changed = copy.deepcopy(self.catalog)
        changed['entries'][0]['caveat'] += ' Updated.'
        b = fw.plan(changed, self.recipes, 'h3-seed-lab', 'Observatory')
        self.assertNotEqual(a['plan_sha256'], b['plan_sha256'])

    def test_budget_rejected_not_silently_truncated(self):
        with self.assertRaises(ValueError):
            fw.plan(self.catalog, self.recipes, 'h3-seed-lab', 'Observatory', count=5, max_jobs=12)

    def test_seed_overflow(self):
        with self.assertRaises(ValueError):
            fw.plan(self.catalog, self.recipes, 'h3-seed-lab', 'Observatory', seed=2**64-1, count=2)

    def test_negative_or_bool_seed(self):
        for seed in (-1, True):
            with self.assertRaises(ValueError):
                fw.plan(self.catalog, self.recipes, 'h3-seed-lab', 'Observatory', seed=seed)

    def test_unknown_recipe(self):
        with self.assertRaises(ValueError): fw.plan(self.catalog, self.recipes, 'missing', 'Brief')

    def test_bad_count(self):
        with self.assertRaises(ValueError): fw.plan(self.catalog, self.recipes, 'h3-seed-lab', 'Brief', count=0)

    def test_header_h3_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.sample(tmp); before = path.read_bytes()
            result = fw.inspect_header(path)
            self.assertEqual(result['suggested_relative_folder'], 'models/diffusion_models')
            self.assertFalse(result['loaded_weights'])
            self.assertFalse(result['moved_file'])
            self.assertEqual(before, path.read_bytes())

    def test_unknown_file_no_folder_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(fw.inspect_header(self.sample(tmp, 'mystery.safetensors'))['suggested_relative_folder'])

    def test_encoder_and_vae_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, folder in [('qwen3vl_32b_minimax_h3_bf16.safetensors', 'models/text_encoders'),
                                 ('minimax_h3_audio_vae_fp32.safetensors', 'models/vae')]:
                self.assertEqual(fw.inspect_header(self.sample(tmp, name))['suggested_relative_folder'], folder)

    def test_truncated_and_oversized_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'bad.safetensors'
            for raw in (b'bad', struct.pack('<Q', 50) + b'{}', struct.pack('<Q', fw.MAX_JSON + 1)):
                p.write_bytes(raw)
                with self.assertRaises(ValueError): fw.inspect_header(p)

    def test_out_of_file_tensor(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.sample(tmp, header={'a': {'dtype': 'F32', 'shape': [2], 'data_offsets': [0, 8]}})
            with self.assertRaises(ValueError): fw.inspect_header(p)

    def test_negative_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.sample(tmp, header={'a': {'dtype': 'F32', 'shape': [-1], 'data_offsets': [0, 4]}})
            with self.assertRaises(ValueError): fw.inspect_header(p)

    def test_duplicate_json_keys_and_nan(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(ValueError): fw.decode(raw)

    def test_metadata_is_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = {'__metadata__': {'note': '__import__("os").system("exit 1")'},
                      'a': {'dtype': 'F32', 'shape': [1], 'data_offsets': [0, 4]}}
            p = self.sample(tmp, header=header)
            self.assertEqual(fw.inspect_header(p)['metadata'], header['__metadata__'])

    def test_pickle_extension_rejected(self):
        with self.assertRaises(ValueError): fw.inspect_header(Path('untrusted.pt'))

    def test_html_script_escape(self):
        self.catalog['entries'][0]['opportunity'] = '</script><script>alert(1)</script>'
        rendered = fw.render(self.catalog, self.recipes, '<script type="application/json">__FRONTIER_DATA__</script>')
        self.assertEqual(rendered.count('</script>'), 1)
        self.assertIn('\\u003c', rendered)

    def test_template_slot_required(self):
        with self.assertRaises(ValueError): fw.render(self.catalog, self.recipes, 'missing')

    def test_main_unknown_recipe_errors(self):
        self.assertEqual(fw.main(['plan', '--recipe', 'missing', '--brief', 'Brief']), 2)


if __name__ == '__main__':
    unittest.main()
