"""Keep execution-bearing picker entries tied to their retained receipts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from app.server import Studio

ROOT = Path(__file__).resolve().parents[1]
RECORD = 'experiments/curated/anima-modular-baseline-20260913/execution-evidence.json'
CASES = {'anima-v1-base': 'anima-base', 'anima-v1-first-adapter-comparison': 'anima-style'}
BASELINE_RECORD = 'experiments/curated/goal-baselines-20260913/provenance.json'
BASELINE_CASES = {
    'cstati-v3-base': 'cstati-v3-base',
    'yumeflux-ilv1-base': 'yumeflux-ilv1-base',
    'janima-v1-base': 'janima-v1-base',
}


class RecipeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.recipes = {r['id']: r for r in json.loads((ROOT / 'presets/recipes.json').read_text(encoding='utf-8'))['recipes']}
        self.observations = {r['case']: r for r in json.loads((ROOT / RECORD).read_text(encoding='utf-8'))['observations']}
        self.presets = {p['id']: p for p in json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))['presets']}
        self.baselines = {r['id']: r for r in json.loads((ROOT / BASELINE_RECORD).read_text(encoding='utf-8'))['baselines']}

    def test_picker_evidence_matches_exact_retained_execution(self):
        for identifier, case in CASES.items():
            with self.subTest(recipe=identifier):
                recipe, observation = self.recipes[identifier], self.observations[case]
                evidence = recipe.get('evidence')
                self.assertIsInstance(evidence, dict)
                self.assertEqual(recipe['preset_id'], observation['preset_id'])
                self.assertEqual(evidence['prompt_id'], observation['prompt_ids'][0])
                self.assertEqual(evidence['job_id'], observation['job_id'])
                self.assertEqual(evidence['seconds'], observation['seconds'])
                self.assertEqual(evidence['record'], RECORD)
                self.assertEqual(evidence['case'], case)
                self.assertIn(observation['output']['sha256'], evidence['note'])

    def test_retained_recipe_bytes_match_the_evidence_pin(self):
        for case in CASES.values():
            with self.subTest(case=case):
                observation = self.observations[case]
                raw = (ROOT / RECORD).parent.joinpath(observation['recipe']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), observation['recipe_sha256'])

    def test_baseline_picker_entries_match_the_retained_recipe_and_effective_workflow(self):
        binder = Studio.__new__(Studio)
        for identifier, case in BASELINE_CASES.items():
            with self.subTest(recipe=identifier):
                recipe, observation = self.recipes[identifier], self.baselines[case]
                evidence = recipe.get('evidence')
                retained_recipe = (ROOT / BASELINE_RECORD).parent / observation['recipe']['path']
                retained_workflow = (ROOT / BASELINE_RECORD).parent / observation['workflow']['path']
                archived_recipe = json.loads(retained_recipe.read_text(encoding='utf-8'))
                archived_workflow = json.loads(retained_workflow.read_text(encoding='utf-8'))

                self.assertEqual(recipe['status'], 'executed')
                self.assertEqual(recipe['preset_id'], observation['preset_id'])
                self.assertEqual(recipe['controls'], observation['controls'])
                self.assertEqual(recipe['controls'], archived_recipe['controls'])
                self.assertEqual(recipe['batch_count'], archived_recipe['batch_count'])
                self.assertEqual(hashlib.sha256(retained_recipe.read_bytes()).hexdigest(), observation['recipe']['sha256'])
                self.assertEqual(hashlib.sha256(retained_workflow.read_bytes()).hexdigest(), observation['workflow']['sha256'])
                self.assertEqual(evidence['job_id'], observation['job_id'])
                self.assertEqual(evidence['prompt_id'], observation['prompt_id'])
                self.assertEqual(evidence['seconds'], observation['output']['elapsed_seconds'])
                self.assertEqual(evidence['record'], BASELINE_RECORD)
                self.assertEqual(evidence['case'], case)
                self.assertIn(observation['output']['sha256'], evidence['note'])

                preset = self.presets[recipe['preset_id']]
                graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
                for key, value in recipe['controls'].items():
                    binder._bind_control(graph, preset, key, value)
                Studio.prune_disabled_loras(None, graph)
                self.assertEqual(graph, archived_workflow)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for the shipped renderer contract')
    def test_actual_description_displays_catalogue_prompt_and_timing(self):
        script = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const elements = new Map();
const element = selector => {
  if (!elements.has(selector)) elements.set(selector, {value:'', files:[], textContent:'',
    classList:{toggle(){}}, addEventListener(){}});
  return elements.get(selector);
};
let calls = 0;
const context = vm.createContext({URL, window:{}, location:{hash:''}, setInterval(){},
  document:{querySelector:element, querySelectorAll:()=>[], addEventListener(){}},
  fetch:()=>{calls++;return new Promise(()=>{});}});
vm.runInContext(fs.readFileSync('app/static/app.js','utf8'),context); // Hold only startup's catalogue read.
const initialCalls = calls;
const recipes = JSON.parse(fs.readFileSync('presets/recipes.json','utf8')).recipes;
const record = JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const records = record.observations || record.baselines;
for (const [id, name] of Object.entries(JSON.parse(process.argv[2]))) {
  const recipe=recipes.find(r=>r.id===id), observation=records.find(r=>(r.case||r.id)===name);
  const promptId=observation.prompt_ids?.[0]||observation.prompt_id;
  const seconds=observation.seconds??observation.output?.elapsed_seconds;
  context.recipe=recipe;
  const before=JSON.stringify(recipe), html=vm.runInContext('describeRecipe(recipe)',context);
  assert.ok(html.includes('ComfyUI prompt '+promptId),id+' lacks retained prompt ID');
  assert.ok(html.includes(String(seconds)+' s'),id+' lacks retained timing');
  assert.ok(html.includes('Generated locally; inspect separately'));
  assert.equal(JSON.stringify(recipe),before,'Rendering must not rewrite evidence');
}
assert.equal(calls,initialCalls,'Describing evidence must not perform a request');
"""
        for record, cases in ((RECORD, CASES), (BASELINE_RECORD, BASELINE_CASES)):
            with self.subTest(record=record):
                result = subprocess.run(['node', '-e', script, record, json.dumps(cases)], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
