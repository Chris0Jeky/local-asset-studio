"""Append one protocol-shaped judgement: python addjudge.py <folder> <image> <scores a,an,s,t,c[,ctl]> <verdict> <worst> [fix] [notes] [--open] [--prompt ID] [--job ID] [--criterion KEY]

R7: when `fix` is given (a fix is needed before use), the worst defect must name its criterion (--criterion anatomy) and
that criterion must score 3 or lower.

Scores are adherence,anatomy,style,technical,composition[,control] (use - for control when no control input exists).
`--open` marks the judgement as not blind (single outputs, census); blind is the default for A/B folders.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labkit  # noqa: E402

args = sys.argv[1:]; blind = True; prompt = job = criterion = None
if '--open' in args: args.remove('--open'); blind = False
if '--criterion' in args: i = args.index('--criterion'); criterion = args[i + 1]; del args[i:i + 2]
if '--prompt' in args: i = args.index('--prompt'); prompt = args[i + 1]; del args[i:i + 2]
if '--job' in args: i = args.index('--job'); job = args[i + 1]; del args[i:i + 2]
folder, image, raw, verdict, worst = args[:5]
fix = args[5] if len(args) > 5 else None; notes = args[6] if len(args) > 6 else ''
if fix is not None and fix.strip() in ('', 'None', 'null'): fix = None  # judge_batch passes JSON null as the string None
vals = raw.split(','); keys = ['adherence', 'anatomy', 'style', 'technical', 'composition', 'control']
scores = dict((k, (None if v in ('-', '') else int(v))) for k, v in zip(keys, vals + ['-'] * (6 - len(vals))))
assert verdict in ('keep', 'fixable', 'reject', 'skipped'), verdict
low = min(v for v in scores.values() if v is not None)
if verdict == 'keep': assert low >= 4, 'keep needs every criterion >= 4'
if verdict == 'fixable': assert low >= 3, 'fixable needs nothing below 3'
# R7 (review calibration, PR #871 at 73b185da): when the record's `fix` names something that must happen before use, the worst
# defect's criterion must score 3 or lower. A `keep` (no fix) may still name a minor worst defect with a 4 or 5.
if fix and not worst.lower().startswith('none'):
    if criterion not in scores or scores[criterion] is None: raise SystemExit('R7: name the worst defect\'s criterion with --criterion <key>')
    if scores[criterion] > 3: raise SystemExit('R7: the worst defect is scored %s on %s; a named defect caps its criterion at 3 (or write "none ...")' % (scores[criterion], criterion))
rec = labkit.judge(folder, image, scores, verdict, worst, fix, notes, prompt_id=prompt, job_id=job, blind=blind)
print(rec['verdict'], rec['scores'], Path(image).name)
