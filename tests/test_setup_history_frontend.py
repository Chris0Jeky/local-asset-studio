import shutil,subprocess,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class SetupHistoryFrontend(unittest.TestCase):
    def test_read_only_history_panel_contracts(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node is not installed')
        result=subprocess.run([node,'--test','--test-concurrency=1',str(ROOT/'tests/setup_history_client.cjs'),str(ROOT/'tests/setup_history_restore_client.cjs')],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_shell_loads_the_panel_after_the_apply_panel_exists(self):
        shell=(ROOT/'app/static/studio-shell.js').read_text(encoding='utf-8')
        self.assertLess(shell.index("apply.src='/static/setup-apply.js'"),shell.index("history.src='/static/setup-history.js'"))
        script=(ROOT/'app/static/setup-history.js').read_text(encoding='utf-8')
        for forbidden in ('method:','POST','localStorage','sessionStorage','innerHTML','.adopt(','.capture('):self.assertNotIn(forbidden,script)


if __name__=='__main__':unittest.main()
