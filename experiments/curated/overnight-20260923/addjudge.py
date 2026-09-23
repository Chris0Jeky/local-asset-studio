"""Append one protocol-shaped judgement: python addjudge.py <folder> <image> <scores a,an,s,t,c[,ctl]> <verdict> <worst> [fix] [notes] [--open] [--prompt ID] [--job ID] [--criterion KEY] [--no-run]

R7: when `fix` is given (a fix is needed before use), the worst defect must name its criterion (--criterion anatomy) and
that criterion must score 3 or lower.

Scores are adherence,anatomy,style,technical,composition[,control] (use - for control when no control input exists).
`--open` marks the judgement as not blind (single outputs, census); blind is the default for A/B folders.

The job and prompt IDs and the original image are looked up from <folder>/results.json by sha256; an image that matches no
recorded run is refused unless --no-run says it is not a run of this experiment (a source picture in a blind group).

R8b: a correction-pass output passes --correction-pass fixed|partial|untouched. `untouched` requires adherence <= 2 and a reject;
a worst_defect that says the defect remains ("still", "unchanged", "untouched", ...) is refused under fixed/partial. Without the
flag, a record whose worst_defect says a defect remains and whose adherence is above 2 is refused unless --correction-free says
it is not a correction pass.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labkit  # noqa: E402

args = sys.argv[1:]; blind = True; prompt = job = criterion = None
if '--open' in args: args.remove('--open'); blind = False
if '--criterion' in args: i = args.index('--criterion'); criterion = args[i + 1]; del args[i:i + 2]
no_run = '--no-run' in args
if no_run: args.remove('--no-run')
if '--correction-free' in args: args.remove('--correction-free')
correction = None
if '--correction-pass' in args: i = args.index('--correction-pass'); correction = args[i + 1]; del args[i:i + 2]
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
# R8/R8a/R8b (PROTOCOL.md): a correction-pass output (inpaint, repair, detail fix, refine) states what happened to the named defect.
# untouched -> adherence <= 2 and reject (R8b); a lost or merged subject is judged on control (R8a: control 2, reject).
UNTOUCHED_WORDS = ('still ', 'unchanged', 'untouched', 'remains', ' stay', 'not repainted', 'nothing repainted')
if correction is not None:
    if correction not in ('fixed', 'partial', 'untouched'): raise SystemExit('--correction-pass takes fixed, partial or untouched')
    if correction == 'untouched' and (scores['adherence'] > 2 or verdict != 'reject'):
        raise SystemExit('R8b: the named defect was left untouched, so adherence must be 2 or lower and the verdict reject')
    if correction != 'untouched' and any(w in (' ' + worst.lower()) for w in UNTOUCHED_WORDS):
        raise SystemExit('R8b: worst_defect says the defect remains (%r) but --correction-pass is %s; use untouched' % (worst[:60], correction))
elif no_run is False and any(w in (' ' + worst.lower()) for w in UNTOUCHED_WORDS) and scores['adherence'] > 2 and '--correction-free' not in sys.argv:
    raise SystemExit('R8b guard: worst_defect says a defect remains; if this is a correction-pass output pass --correction-pass untouched '
                     '(adherence <= 2, reject), otherwise pass --correction-free')
rec = labkit.judge(folder, image, scores, verdict, worst, fix, notes, prompt_id=prompt, job_id=job, blind=blind, no_run=no_run)
if correction is not None:
    import json
    path = Path(folder) / 'judgements.jsonl'; lines = path.read_text(encoding='utf-8').splitlines()
    last = json.loads(lines[-1]); last['correction_pass'] = correction; lines[-1] = json.dumps(last)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
print(rec['verdict'], rec['scores'], Path(image).name)
