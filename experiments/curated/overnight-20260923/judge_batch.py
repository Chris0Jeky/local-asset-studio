"""Run addjudge.py once per entry of a JSON list of argument lists: python judge_batch.py <batch.json>

Each entry is exactly the argument list addjudge.py takes, so every record passes the same checks (verdict bounds, R7).
Stops at the first refusal.
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for args in json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')):
    done = subprocess.run([sys.executable, str(HERE / 'addjudge.py')] + [str(a) for a in args], capture_output=True, text=True)
    print((done.stdout or done.stderr).strip()[:200])
    if done.returncode: raise SystemExit('refused: %s' % args[:2])
