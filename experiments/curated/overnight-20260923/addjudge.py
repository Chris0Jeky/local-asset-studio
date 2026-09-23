"""Append one protocol-shaped judgement: python addjudge.py <folder> <image> <scores a,an,s,t,c[,ctl]> <verdict> <worst> [fix] [notes] [--open] [--prompt ID] [--job ID]

Scores are adherence,anatomy,style,technical,composition[,control] (use - for control when no control input exists).
`--open` marks the judgement as not blind (single outputs, census); blind is the default for A/B folders.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labkit  # noqa: E402

args = sys.argv[1:]; blind = True; prompt = job = None
if '--open' in args: args.remove('--open'); blind = False
if '--prompt' in args: i = args.index('--prompt'); prompt = args[i + 1]; del args[i:i + 2]
if '--job' in args: i = args.index('--job'); job = args[i + 1]; del args[i:i + 2]
folder, image, raw, verdict, worst = args[:5]
fix = args[5] if len(args) > 5 else None; notes = args[6] if len(args) > 6 else ''
vals = raw.split(','); keys = ['adherence', 'anatomy', 'style', 'technical', 'composition', 'control']
scores = dict((k, (None if v in ('-', '') else int(v))) for k, v in zip(keys, vals + ['-'] * (6 - len(vals))))
assert verdict in ('keep', 'fixable', 'reject', 'skipped'), verdict
low = min(v for v in scores.values() if v is not None)
if verdict == 'keep': assert low >= 4, 'keep needs every criterion >= 4'
if verdict == 'fixable': assert low >= 3, 'fixable needs nothing below 3'
rec = labkit.judge(folder, image, scores, verdict, worst, fix, notes, prompt_id=prompt, job_id=job, blind=blind)
print(rec['verdict'], rec['scores'], Path(image).name)
