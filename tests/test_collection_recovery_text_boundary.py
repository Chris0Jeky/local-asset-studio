"""Verify real Python receipts against JavaScript recovery, not a JS-only mock."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from workspace import AssetWorkspace


class CollectionRecoveryTextBoundary(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_python_normalization_does_not_make_a_real_commit_unconfirmable(self):
        cases = []
        with tempfile.TemporaryDirectory() as temp:
            workspace = AssetWorkspace(temp)
            scope = workspace.snapshot()['workspace_id']
            # These are retained by JS trim but stripped by Python, including
            # a mixed boundary where FEFF must stay after Python strips NEL.
            for index, name in enumerate([
                '\u0085Clicked\u0085', '\x1cClicked\x1f',
                '\u0085 \x1dClicked\x1e \u0085',
                '\u0085\ufeffClicked\ufeff\u0085', 'Café 🐈',
            ]):
                command = {'format': 'studio.collection-command/v1', 'workspace_id': scope,
                           'request_id': f'text-boundary-request-{index}', 'action': 'create',
                           'name': name, 'description': '\u0085Notes\u0085'}
                reply = workspace.collection(command)
                self.assertEqual(reply['receipt']['result']['name'], name.strip())
                cases.append({'command': command, 'reply': reply})
            script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs');
const R=require('./app/static/collection-recovery.js');
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
(async()=>{
  for(const {command,reply} of cases){
    const pending=R.pending(command,123);
    assert.equal(pending.body,R.canonical(command));
    const receipt=await R.verifyReceipt(reply,pending,require('node:crypto').webcrypto);
    assert.equal(receipt.result.name,reply.receipt.result.name);
    assert.equal(receipt.result.description,'Notes');
  }
  console.log('verified '+cases.length+' real Python receipts');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
            result = subprocess.run([shutil.which('node'), '-e', script], cwd=ROOT,
                                    input=json.dumps(cases), capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('verified 5 real Python receipts', result.stdout)
