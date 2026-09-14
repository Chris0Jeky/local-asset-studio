"""Guide manifest and pure-rule checks. Native browser is a separate opt-in gate."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from urllib.parse import urlsplit
from studio_workflow.guides import guides

ROOT = Path(__file__).resolve().parents[1]
# A step is a prompt to act, not a paragraph: verb-initial title, at most two
# sentences of concrete instruction. Widening a cap needs an owner decision.
TITLE_WORDS, DETAIL_CHARS, DETAIL_SENTENCES = 6, 220, 2
IMPERATIVES = {'approve','assign','build','change','check','choose','connect','decide','describe','discover','generate',
               'load','observe','open','pick','plan','prepare','read','record','review','run','save','select',
               'set','show','start','test','write'}
# A terminator followed by a capitalised word or the end of the detail. Keeps
# 'app/server.py' and '--repo-root .' from being counted as sentence ends.
SENTENCE = re.compile(r'[.!?](?=\s+["“(]?[A-Z0-9]|\s*$)')
BANNED = ('Guide position is navigation only', 'is not the same as', 'separate.')

class GuideManifestTests(unittest.TestCase):
    def test_versioned_stages_are_unique_and_targets_exist_in_feature_sources(self):
        manifest=guides(); self.assertEqual(manifest['version'],2)
        self.assertFalse(manifest['generation_submitted']); self.assertEqual(len(manifest['guides']),7)
        sources='\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'app/static').glob('*') if p.suffix in ('.js','.html'))
        checks={'manual','recipe','reference_recipe','prompt','references','readiness','output','review','selection','schema','graph_check','saved'}
        for guide in manifest['guides']:
            ids=[s['id'] for s in guide['steps']]; self.assertEqual(len(ids),len(set(ids)))
            for step in guide['steps']:
                self.assertRegex(step['id'],r'^[a-z-]+$'); self.assertIn(step['check'],checks)
                self.assertIn(urlsplit(step['route']).path,('/','/workflow-studio.html','/av.html','/voice.html'))
                for target in [step['target'],*step.get('alternatives',[])]:
                    if target:
                        self.assertRegex(target,r'^#[A-Za-z][A-Za-z0-9_-]+$')
                        self.assertIn(target[1:],sources, 'Missing feature anchor: '+target)
        self.assertEqual(manifest,guides(), 'Manifest reads are stable and do not mutate common steps')

    def test_every_step_stays_inside_the_copy_budget(self):
        seen = 0
        for guide in guides()['guides']:
            for step in guide['steps']:
                where = guide['id'] + '/' + step['id']; seen += 1
                words = step['title'].split()
                self.assertLessEqual(len(words), TITLE_WORDS, where + ' title: ' + step['title'])
                self.assertIn(words[0].lower().strip(',;:'), IMPERATIVES, where + ' title is not imperative: ' + step['title'])
                self.assertLessEqual(len(step['detail']), DETAIL_CHARS, where + ' detail is ' + str(len(step['detail'])) + ' chars')
                sentences = len(SENTENCE.findall(step['detail']))
                self.assertTrue(1 <= sentences <= DETAIL_SENTENCES, where + ' has ' + str(sentences) + ' sentences')
                for phrase in BANNED:
                    self.assertNotIn(phrase, step['detail'], where + ' repeats a panel-level disclaimer: ' + phrase)
        self.assertEqual(seen, 33)

    def test_recommended_recipes_are_real_catalog_ids_on_recipe_steps(self):
        catalog = json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))
        known = {p['id'] for p in (catalog['presets'] if isinstance(catalog, dict) else catalog)}
        for guide in guides()['guides']:
            chooses = [s for s in guide['steps'] if s['check'] in ('recipe', 'reference_recipe')]
            self.assertEqual(bool(chooses), 'recommended' in guide, guide['id'] + ' recommends recipes only where one is chosen')
            for value in guide.get('recommended', []):
                self.assertRegex(value, r'^[A-Za-z0-9_-]{1,64}$')
                self.assertIn(value, known, guide['id'] + ' recommends an unknown recipe: ' + value)
            if chooses: self.assertTrue(guide['recommended'], guide['id'] + ' needs at least one recommended recipe')

    def test_panel_carries_one_short_footer_and_an_automatic_check(self):
        source = (ROOT / 'app/static/studio-guide.js').read_text(encoding='utf-8')
        footer = 'The guide checks readiness; it never generates, approves art or clears licences.'
        self.assertEqual(source.count(footer), 1)
        self.assertNotIn('Guide position is navigation only', source)
        self.assertIn("add('Re-check'", source)
        self.assertNotIn("add('Check this step'", source)

    def test_manifest_uses_saved_workflow_execution_and_safe_source_fallbacks(self):
        paths={g['id']:g for g in guides()['guides']}
        self.assertEqual(paths['workflow']['steps'][-1]['target'],'#prepareSavedRun')
        self.assertIn('#referenceWrap',paths['reference-edit']['steps'][1]['alternatives'])
        self.assertIn('runs review',json.dumps(paths['agents']))

    @unittest.skipUnless(shutil.which('node'),'Node is required for browser rule contracts')
    def test_node_evidence_contracts(self):
        subprocess.run(['node','--test',str(ROOT/'tests/studio_guide_state.cjs')],cwd=ROOT,check=True,capture_output=True,text=True,timeout=30)

    @unittest.skipUnless(shutil.which('node'),'Node is required for coach context contracts')
    def test_node_context_contracts(self):
        subprocess.run(['node','--test',str(ROOT/'tests/studio_guide_context.cjs')],cwd=ROOT,check=True,capture_output=True,text=True,timeout=30)
