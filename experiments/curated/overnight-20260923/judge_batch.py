"""Run addjudge.py once per entry of a JSON list of argument lists: python judge_batch.py <batch.json> [--sources a.png,b.png]

Each entry is exactly the argument list addjudge.py takes, so every record passes the same checks (verdict bounds, R7, the
run lookup). `--sources` names source pictures sealed into blind groups: an image whose SHA-256 equals one of them is passed
with --no-run, and nothing else is. Stops at the first refusal.
"""
import hashlib, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


args = sys.argv[1:]; sources = set()
if '--sources' in args:
    i = args.index('--sources'); sources = {sha(p) for p in args[i + 1].split(',') if p}; del args[i:i + 2]
for entry in json.loads(Path(args[0]).read_text(encoding='utf-8')):
    entry = ['' if a is None else str(a) for a in entry]
    if sources and sha(entry[1]) in sources and '--no-run' not in entry: entry.append('--no-run')
    done = subprocess.run([sys.executable, str(HERE / 'addjudge.py')] + entry, capture_output=True, text=True)
    print((done.stdout or done.stderr).strip()[:200])
    if done.returncode: raise SystemExit('refused: %s' % entry[:2])
