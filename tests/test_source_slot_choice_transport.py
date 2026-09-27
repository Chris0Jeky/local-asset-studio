"""Deterministic scheduling contracts for the browser fixture's actual API wrapper."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required to exercise the browser fixture')
class SourceSlotChoiceTransportTests(unittest.TestCase):
    def run_case(self, body):
        tree = ast.parse((ROOT / 'tests/source_slot_choices_browser.py').read_text(encoding='utf-8'))
        install = next(node.value for node in ast.walk(tree)
                       if isinstance(node, ast.Constant) and isinstance(node.value, str)
                       and node.value.startswith('() => {') and 'const original=api;' in node.value)
        script = """
const assert=require('node:assert/strict'),vm=require('node:vm');
const reads=[];
const page={api:(url,options)=>new Promise((resolve,reject)=>reads.push({url,options,resolve,reject}))};
page.window=page;
vm.runInNewContext('('+INSTALL+')()',page);
const tick=()=>new Promise(setImmediate);
const copy=()=>page.api('/api/assets/reference',{body:JSON.stringify({id:'asset-1'})});
(async()=>{ BODY })().then(()=>console.log('transport case complete')).catch(error=>{console.error(error);process.exitCode=1;});
""".replace('INSTALL', json.dumps(install)).replace('BODY', body)
        result = subprocess.run([shutil.which('node'), '--unhandled-rejections=strict', '-e', script],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('transport case complete', result.stdout, 'The asynchronous case exited before completion')

    def test_copy_release_is_consumed_before_a_later_response_arrives(self):
        self.run_case("""
page.__choiceDelay=true;
const first=copy(); reads.shift().resolve({file:'first.png'}); await tick();
const firstRelease=page.__choiceRelease; assert.equal(typeof firstRelease,'function');
firstRelease(); assert.equal((await first).file,'first.png');
assert.equal(page.__choiceRelease,undefined,'settled copies must not satisfy the next readiness poll');
const second=copy(); let finished=false; second.then(()=>{finished=true});
await tick();
assert.equal(page.__choiceRelease,undefined,'there is no second release before the response arrives');
reads.shift().resolve({file:'second.png'}); await tick();
const secondRelease=page.__choiceRelease;
assert.equal(typeof secondRelease,'function'); assert.notEqual(secondRelease,firstRelease);
firstRelease(); await tick();
assert.equal(page.__choiceRelease,secondRelease,'an old callback cannot erase the current hold');
assert.equal(finished,false,'an old callback cannot release a later copy');
secondRelease(); assert.equal((await second).file,'second.png');
assert.equal(page.__choiceRelease,undefined);
""")

    def test_upload_release_is_one_shot_and_preserves_the_selected_file(self):
        self.run_case("""
page.__choiceUploadDelay=true;
const file={name:'later-role.png'};
const first=page.api('/api/upload',{body:file});
const oldRelease=page.__choiceUploadRelease;
assert.equal(page.__choiceUploadedFile,file); assert.equal(reads.length,0);
oldRelease(); assert.equal((await first).file,'later-role.png');
assert.equal(page.__choiceUploadRelease,undefined,'completed upload must retire its callback');
const second=page.api('/api/upload',{body:file}); const release=page.__choiceUploadRelease;
let finished=false; second.then(()=>{finished=true}); oldRelease(); await tick();
assert.equal(page.__choiceUploadRelease,release); assert.equal(finished,false);
release(); await second; assert.equal(page.__choiceUploadRelease,undefined);
""")

    def test_network_failure_does_not_install_a_release_handle(self):
        self.run_case("""
page.__choiceDelay=true;
const request=copy(); const refused=assert.rejects(request,/network unavailable/);
reads.shift().reject(Error('network unavailable')); await refused;
assert.equal(page.__choiceRelease,undefined);
assert.equal(page.__choiceCalls.join(','),'asset-1');
""")

    def test_ordinary_requests_and_synthetic_refusals_keep_their_contract(self):
        self.run_case("""
const request=copy(); const response={file:'unchanged.png'};
reads.shift().resolve(response); assert.equal(await request,response);
assert.equal(page.__choiceRelease,undefined);
page.__choiceFailure=true; await assert.rejects(copy(),/Synthetic copy unavailable/);
assert.equal(reads.length,0);
""")


if __name__ == '__main__':
    unittest.main()
