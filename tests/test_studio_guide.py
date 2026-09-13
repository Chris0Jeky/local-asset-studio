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

    def test_manifest_uses_saved_workflow_execution_and_safe_source_fallbacks(self):
        paths={g['id']:g for g in guides()['guides']}
        self.assertEqual(paths['workflow']['steps'][-1]['target'],'#prepareSavedRun')
        self.assertIn('#referenceWrap',paths['reference-edit']['steps'][1]['alternatives'])
        self.assertIn('runs review',json.dumps(paths['agents']))

    @unittest.skipUnless(shutil.which('node'),'Node is required for browser rule contracts')
    def test_node_evidence_contracts(self):
        subprocess.run(['node','--test',str(ROOT/'tests/studio_guide_state.cjs')],cwd=ROOT,check=True,capture_output=True,text=True,timeout=30)
