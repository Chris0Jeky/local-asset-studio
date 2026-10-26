"""Measure ten existing adult-character creation journeys without submitting generation.

Reuses studio_use_cases' production frontend/synthetic HTTP fixture and intent drivers. Adds all
performed input calls (including typing and keyboard), automated elapsed time, fixed driver waits,
screenshot overhead and viewport movement. These are automation measurements, never human task time
or a claim about generated artwork. Fixture/setup injections and native browser auto scrolling are
reported separately from deliberate input calls.

python tests/creation_workflow_journeys.py [--zoom 200] [--chromium PATH]
Other flags are studio_use_cases.py's flags. Default output is .runtime/creation-workflow-journeys/.
"""
from pathlib import Path
import hashlib
from importlib.metadata import version
import json
import platform
import sys
import time

import studio_use_cases as cases

CASES = (
    'make-an-anime-character',
    'make-anime-look-chosen-model-and-lora',
    'specific-lora-in-full-editor',
    'make-compare-looks',
    'reuse-keeper-as-reference',
    'restyle-recent-output-with-a-look',
    'combine-character-with-another-pose',
    'three-reference-identity-pose-style',
    'vary-a-keeper',
    'guided-edit-or-preserve-character',
)
INPUT_ACTIONS = ('click', 'check', 'select', 'fill', 'press')
LIMITS = ('Automated elapsed wall time includes application waits, driver waits, assertion work and evidence capture. '
          'It is not human completion time. Browser auto scrolling is observed viewport movement, not a counted human gesture. '
          'Synthetic setup and direct driver state injections are not user actions. No model runs or artistic acceptance are measured.')


def instrument():
    original_act, original_shot, original_run = cases.CaseRun.act, cases.CaseRun._shot, cases.run_case

    def shot(self, index):
        started = time.perf_counter()
        try: return original_shot(self, index)
        finally: self.capture_ms = getattr(self, 'capture_ms', 0) + (time.perf_counter() - started) * 1000

    def act(self, *args, **kwargs):
        scroll, captures = self.page.evaluate('scrollY'), getattr(self, 'capture_ms', 0)
        started = time.perf_counter()
        record = original_act(self, *args, **kwargs)
        record.update(automation_elapsed_ms=round((time.perf_counter()-started)*1000, 2),
                      evidence_capture_ms=round(getattr(self, 'capture_ms', 0)-captures, 2),
                      driver_fixed_wait_ms=kwargs.get('wait', 250) if record.get('performed') and record['action'] != 'read' else 0,
                      viewport_scroll_delta_px=round(abs(self.page.evaluate('scrollY')-scroll), 2))
        return record

    def run(*args, **kwargs):
        started = time.perf_counter()
        row = original_run(*args, **kwargs)
        inputs = [step for step in row['steps'] if step.get('performed') and step['action'] in INPUT_ACTIONS]
        row.update(automation_elapsed_ms=round((time.perf_counter()-started)*1000, 2),
                   browser_version=args[1].context.browser.version,
                   input_actions=len(inputs),
                   typed_fields=sum(step['action']=='fill' for step in inputs),
                   typed_characters=sum(len(step.get('typed') or '') for step in inputs if step['action']=='fill'),
                   keyboard_actions=sum(step['action']=='press' for step in inputs),
                   driver_fixed_wait_ms=sum(step.get('driver_fixed_wait_ms', 0) for step in row['steps']),
                   evidence_capture_ms=round(sum(step.get('evidence_capture_ms', 0) for step in row['steps']), 2),
                   viewport_scroll_delta_px=round(sum(step.get('viewport_scroll_delta_px', 0) for step in row['steps']), 2),
                   timing_limits=LIMITS)
        return row

    cases.CaseRun.act, cases.CaseRun._shot, cases.run_case = act, shot, run


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    output = cases.ROOT / '.runtime/creation-workflow-journeys'
    if '--out' not in argv: argv += ['--out', str(output/'report.json')]
    if '--screenshots' not in argv: argv += ['--screenshots', str(output/'screenshots')]
    if '--case' not in argv:
        for case in CASES: argv += ['--case', case]
    sources = ('app/static/make.js', 'app/static/app.js', 'app/static/studio-workbench.js',
               'app/static/workspace.js', 'tests/studio_use_cases.py', 'tests/creation_workflow_journeys.py')
    hashes = {path: hashlib.sha256((cases.ROOT/path).read_bytes()).hexdigest() for path in sources}
    instrument()
    result = cases.main(argv)
    report = Path(argv[argv.index('--out')+1])
    data = json.loads(report.read_text(encoding='utf-8'))
    data['measurement_limits'] = LIMITS
    data['provenance'] = {'python': platform.python_version(), 'playwright': version('playwright'),
                          'source_sha256': hashes,
                          'sources_unchanged_during_run': all(hashlib.sha256((cases.ROOT/path).read_bytes()).hexdigest()==value for path,value in hashes.items())}
    report.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    return result


if __name__=='__main__': raise SystemExit(main())
