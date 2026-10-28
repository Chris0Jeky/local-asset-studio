"""Callback-install expressions must not trigger Playwright's auto-invocation."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required for the fixture expression contract')
class BrowserFixtureCallbackTests(unittest.TestCase):
    def check_expression(self, path, marker, target):
        tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
        expressions = [call.args[0].value for call in ast.walk(tree)
                       if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                       and call.func.attr == 'evaluate' and call.args
                       and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)
                       and marker in call.args[0].value]
        self.assertEqual(len(expressions), 1, 'Exercise the actual unique browser-fixture expression')
        source = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const slot={},storage={};let calls=0;
function setItem(){calls++;assert.equal(this,storage,'unbound Storage invocation');}
function handler(event){calls++;assert.ok(event,'restoration must not dispatch a click');}
const scope={Storage:{prototype:{setItem}},sessionStorage:storage,originalSetItem:setItem,
             __choiceDelay:true,__choiceSlotHandler:handler,document:{querySelector:()=>slot}};
scope.window=scope;
let result=vm.runInNewContext(EXPRESSION,scope);
// page.evaluate automatically invokes a function-valued expression with its argument.
if(typeof result==='function')result=result(null);
assert.equal(result,undefined,'callback installation must return no callable or pending operation');
assert.equal(calls,0,'restoring a callback must not execute it');
assert.equal(typeof vm.runInNewContext(TARGET,scope),'function');
""".replace('EXPRESSION', json.dumps(expressions[0])).replace('TARGET', json.dumps(target))
        result = subprocess.run([shutil.which('node'), '-e', source], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_make_storage_restore_does_not_invoke_native_setter(self):
        self.check_expression('tests/make_privacy_transitions_browser.py',
                              'Storage.prototype.setItem=window.originalSetItem', 'Storage.prototype.setItem')

    def test_scene_fault_install_does_not_invoke_its_replacement(self):
        self.check_expression('tests/make_privacy_transitions_browser.py',
                              'window.sceneSetItem=Storage.prototype.setItem', 'Storage.prototype.setItem')

    def test_slot_handler_restore_does_not_dispatch_a_null_event(self):
        self.check_expression('tests/source_slot_choices_browser.py',
                              "document.querySelector('#uxSecondSlots').onclick=__choiceSlotHandler",
                              "document.querySelector('#uxSecondSlots').onclick")
