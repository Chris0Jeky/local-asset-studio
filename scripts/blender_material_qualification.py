"""Retained, bounded qualification of the synthetic native corpus material repair."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import blender_lab as lab

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'tests' / 'blender_corpus_material_probe.py'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def need(condition, message):
    if not condition: raise ValueError(message)


def validate_observation(receipt):
    need(receipt['label']['to'] == 'BodyTextured' and receipt['label']['from'] == 'BadgeGreen', 'Unexpected material defect label')
    need(receipt['retention']['BadgeGreen'] is True, 'Displaced original material was not retained')
    need(receipt['retention']['A_UnusedMaterial'] is False and receipt['retention']['BodyTextured'] is False,
         'Unrelated material was promoted')
    for stage in ('seeded', 'reopened', 'repaired'):
        need(receipt['materials'][stage] == receipt['materials']['before'], f'Material membership changed at {stage}')
    checksums = receipt['checksums']
    need(checksums['seeded'] != checksums['before'], 'Seeded defect did not change the scene')
    need(checksums['reopened'] == checksums['seeded'], 'Seeded scene changed after save/reopen')
    need(checksums['repaired'] == checksums['before'], 'Repair did not restore original checksum after save/reopen')


def run_blender(command, **options):
    return subprocess.run(command, **options)


def qualify(blender, output):
    out = Path(output).resolve(); out.mkdir(parents=True, exist_ok=False)
    command = [str(blender), '--background', '--factory-startup', '--disable-autoexec', '--offline-mode',
               '--python-exit-code', '1', '--python', str(PROBE), '--', str(out)]
    sources = (Path(__file__), PROBE, Path(lab.__file__), Path(lab.bpy_side.__file__), ROOT / 'tests/test_blender_corpus.py')
    plan = {'scope': 'synthetic-native-corpus-material-retention', 'command': command, 'timeout_seconds': 120,
            'source_sha256': {str(path.relative_to(ROOT)): lab.file_sha(path) for path in sources}}
    for key, args in (('source_revision', ['rev-parse', 'HEAD']), ('source_tree', ['rev-parse', 'HEAD^{tree}']),
                      ('source_dirty', ['status', '--porcelain'])):
        result = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, timeout=10)
        plan[key] = result.stdout.strip() if result.returncode == 0 else None
    write_json(out / 'plan.json', plan)
    receipt = {'schema_version': 1, 'scope': plan['scope'], 'state': 'failed', 'source_revision': plan['source_revision'],
               'started_utc': datetime.now(timezone.utc).isoformat(), 'returncode': None,
               'not_established': ['realistic-v2-corpus', 'agent-repair-rates', 'configured-Windows-runtime', 'rendered-appearance']}
    write_json(out / 'receipt.json', receipt)
    stdout = stderr = ''
    try:
        command[0] = str(lab.executable(blender))
        write_json(out / 'plan.json', plan)
        result = run_blender(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
        receipt['returncode'], stdout, stderr = result.returncode, result.stdout, result.stderr
        need(result.returncode == 0, f'Blender exited {result.returncode}; see retained logs')
        observed = json.loads((out / 'material-repair.json').read_text(encoding='utf-8'))
        validate_observation(observed)
        for filename in ('lab-asset.blend', 'damaged.blend', 'repaired.blend', 'lab-checker.png'):
            need((out / 'assets' / filename).is_file(), f'Missing native artifact {filename}')
        receipt.update(state='passed', blender=observed['blender'], checksums=observed['checksums'])
    except Exception as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            receipt['returncode'], stdout, stderr = 'timeout', exc.stdout, exc.stderr
        receipt['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        decode = lambda value: value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
        (out / 'blender-stdout.log').write_text(decode(stdout), encoding='utf-8')
        (out / 'blender-stderr.log').write_text(decode(stderr), encoding='utf-8')
        receipt['outputs'] = {path.relative_to(out).as_posix(): lab.file_sha(path)
                              for path in sorted(out.rglob('*')) if path.is_file() and path != out / 'receipt.json'}
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(out / 'receipt.json', receipt)
    return receipt
