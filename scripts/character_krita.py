"""Prepare and explicitly execute a source-bound edit in a new Krita file.

Uses the existing protected compositor, a fixed native API module and a configured
kritarunner. It never submits generation or edits an open user document.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import character_edit_pixels as pixels
from scripts.character_study import inside, read_json, require, sha, verify_artifact, write_json
from scripts.krita_roundtrip import inspect_kra
from integrations.krita import native_edit
from scripts.character_krita_dependencies import collect

MODULE = ROOT / 'integrations/krita/native_edit.py'
TIMEOUT = 120


def _expected(root, dependencies, *, bind_live_dependencies=True):
    plan = read_json(verify_artifact(root, dependencies['plan']))
    current = read_json(verify_artifact(root, dependencies['current_document']))
    require(sha(current) == plan['intent']['document_sha256'], 'Current exported document is stale')
    result_receipt = read_json(verify_artifact(root, dependencies['result']))
    require(result_receipt.get('kind') == 'character_edit_result' and result_receipt.get('schema_version') == 1, 'Expected an existing protected edit result')
    require(result_receipt.get('receipt_sha256') == sha({k:v for k,v in result_receipt.items() if k != 'receipt_sha256'}), 'Edit result receipt changed')
    require(result_receipt.get('plan_sha256') == plan['plan_sha256'] and result_receipt.get('semantic_approval') is False, 'Edit result belongs to another plan or claims approval')
    rendered = pixels.render(root, plan, dependencies['bundle'], result_receipt['candidate'])
    actual = pixels.png(verify_artifact(root, result_receipt['output'])).convert('RGBA')
    expected = rendered['result'].convert('RGBA')
    source = rendered['source'].convert('RGBA')
    require(actual.size == expected.size and actual.tobytes() == expected.tobytes(), 'Published edit pixels differ from the recomputed protected result')
    require(result_receipt['bundle_sha256'] == rendered['bundle']['bundle_sha256'], 'Edit result bundle changed')
    require(result_receipt['outside_mask_changed_pixels'] == 0 and result_receipt['protected_changed_pixels'] == 0, 'Edit result does not preserve its protected pixels')
    require(source.getchannel('A').getextrema() == (255,255) and expected.getchannel('A').getextrema() == (255,255), 'Native layer import currently requires opaque source and result')
    require(not rendered['source'].info.get('icc_profile') and not rendered['result'].info.get('icc_profile'), 'Native layer import requires an explicit profile-free PNG intake')
    require(source.width * source.height <= native_edit.MAX_PIXELS, 'Native canvas exceeds pixel budget')
    kra = verify_artifact(root, dependencies['native_source'])
    inspect_kra(kra)
    require(kra.stat().st_size <= 256 * 1024**2, 'Native source exceeds byte budget')
    raw_kra = kra.read_bytes()
    require(native_edit.digest(raw_kra) == dependencies['native_source']['sha256'], 'Native source changed during snapshot')
    overlay = expected.copy()
    overlay.putalpha(rendered['delta'])
    buffers = {'native-source.kra':raw_kra, 'source.bgra':source.tobytes('raw','BGRA'),
               'overlay.bgra':overlay.tobytes('raw','BGRA'), 'result.bgra':expected.tobytes('raw','BGRA')}
    native_plan = {'schema_version':1, 'operation':'character.krita-layer.v1', 'workspace':str(root.resolve()),
                   'dependencies':dependencies, 'edit_plan_sha256':plan['plan_sha256'],
                   'canvas':list(source.size), 'profile':native_edit.PROFILE,
                   'changed_pixels':rendered['delta'].histogram()[255],
                   'files':{name:{'bytes':len(raw),'sha256':native_edit.digest(raw)} for name,raw in buffers.items()},
                   'neural_inference':False, 'semantic_approval':False, 'review_state':'unreviewed',
                   'limitations':['Saved source file only; unsaved GUI edits are not read or changed.',
                                  'Flat normal non-animated RGBA U8 layers only; native preflight checks the source projection.',
                                  'Candidate execution and semantic success are not inferred by native packaging.']}
    if bind_live_dependencies:
        native_plan['live_dependencies'] = collect(root, dependencies)
    return native_plan, buffers


def record(root, name):
    path = inside(root, name)
    return {'path':name, 'sha256':pixels.file_sha(path)}


def prepare(root, plan, bundle, result, current_document, native_source, output):
    root = Path(root).resolve(strict=True)
    dependencies = {name:record(root, value) for name,value in
                    [('plan',plan), ('result',result), ('current_document',current_document), ('native_source',native_source)]}
    dependencies['bundle'] = bundle
    native_plan, buffers = _expected(root, dependencies)
    with pixels._new_output(root, output) as stage:
        for name, raw in buffers.items():
            with (stage/name).open('xb') as stream:
                stream.write(raw)
        write_json(stage/'native-plan.json', native_plan)
    return {'package':output, 'edit_plan_sha256':native_plan['edit_plan_sha256'],
            'changed_pixels':native_plan['changed_pixels'], 'native_executed':False, 'semantic_approval':False}


def install(config):
    """Install one inert hash-named module; no existing module is overwritten."""
    runtime = Path(config.get('kritarunner',''))
    scripts = Path(config.get('kritarunner_scripts',''))
    require(runtime.is_absolute() and runtime.is_file() and runtime.name.lower() == 'kritarunner.exe', 'Configure an absolute kritarunner executable in config/local.json')
    require(scripts.is_absolute(), 'Configure the Krita runner script directory in config/local.json')
    source = MODULE.read_bytes()
    module_hash = native_edit.digest(source)
    module_name = 'studio_native_edit_' + module_hash
    scripts.mkdir(parents=True, exist_ok=True)
    target = scripts/(module_name+'.py')
    require(not target.is_symlink(), 'Installed native module is a link')
    if target.exists():
        require(target.read_bytes() == source, 'Installed native module differs from its pinned source')
    else:
        with target.open('xb') as stream:
            stream.write(source)
    return {'executable':str(runtime), 'executable_sha256':pixels.file_sha(runtime),
            'module':module_name, 'module_sha256':module_hash, 'installed_path':str(target)}


def status(root, package):
    path = inside(Path(root), package+'/native-plan.json')
    folder = path.parent
    plan, buffers = native_edit.read_plan(path)
    output = folder/'native-result.json'
    if output.exists():
        result = read_json(output)
        require(result.get('native_plan_sha256') == native_edit.digest(path.read_bytes()), 'Native result belongs to another package')
        require(result.get('schema_version') == 1 and result.get('operation') == plan['operation']
                and result.get('edit_plan_sha256') == plan['edit_plan_sha256'], 'Native result contract changed')
        require(result.get('semantic_approval') is False and result.get('neural_inference') is False
                and result.get('review_state') == 'unreviewed', 'Native result cannot grant art approval or claim inference')
        require(all(result.get(key) is True for key in ('native_save_reopen_verified', 'native_projection_exact', 'hide_restores_source')),
                'Native result lacks its required checks')
        require(result.get('canvas') == plan['canvas'] and result.get('profile') == plan['profile'], 'Native result canvas/profile changed')
        require(result.get('original_layers') and len(result.get('result_layers', [])) == len(result['original_layers']) + 1
                and result['result_layers'][:-1] == result['original_layers'], 'Native result does not preserve the original layer records')
        require(set(result.get('outputs',{})) == {'edited.kra','reopened.png'}, 'Unexpected native output set')
        for name, record in result['outputs'].items():
            actual = folder/name
            require(not actual.is_symlink() and actual.is_file() and actual.stat().st_size == record['bytes']
                    and pixels.file_sha(actual) == record['sha256'], 'Native output changed: '+name)
        png = pixels.png(folder/'reopened.png').convert('RGBA')
        require(list(png.size) == plan['canvas'] and png.tobytes('raw','BGRA') == buffers['result.bgra'],
                'Reopened PNG differs from the verified result')
        require(not (folder/'native-failure.json').exists(), 'Native attempt has conflicting failure evidence')
        return {'state':'completed', 'result':result}
    if (folder/'native-failure.json').exists():
        return {'state':'failed', 'failure':read_json(folder/'native-failure.json')}
    return {'state':'uncertain' if (folder/'native-intent.json').exists() else 'prepared',
            'edit_plan_sha256':plan['edit_plan_sha256']}


def execute(root, package, config):
    root = Path(root).resolve(strict=True)
    path = inside(root, package+'/native-plan.json')
    plan = read_json(path)
    require(plan.get('workspace') == str(root), 'Native package belongs to another workspace')
    require(status(root, package)['state'] == 'prepared', 'Native attempt already recorded; inspect status and retained artifacts')
    expected, _ = _expected(root, plan['dependencies'], bind_live_dependencies='live_dependencies' in plan)
    require(plan == expected, 'Native plan changed since preparation')
    native_edit.read_plan(path)
    runtime = install(config)
    command = [runtime['executable'], '-s', runtime['module'], '-f', 'run', str(path)]
    environment = os.environ.copy()
    environment.pop('QT_QPA_PLATFORM', None)
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
    intent = {'at':time.time(), 'runtime':runtime, 'argv':command,
              'native_plan_sha256':native_edit.digest(path.read_bytes()), 'timeout_seconds':TIMEOUT}
    with (path.parent/'native-intent.json').open('x',encoding='utf-8') as stream:
        json.dump(intent,stream,indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        completed = subprocess.run(command, cwd=path.parent, env=environment, shell=False,
                                   capture_output=True, text=True, timeout=TIMEOUT, startupinfo=startupinfo,
                                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0), check=False)
        log = {'returncode':completed.returncode, 'stdout':completed.stdout, 'stderr':completed.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        write_json(path.parent/'runner-error.json', {'error':str(exc)})
        raise ValueError('Native runner did not complete; preserve the attempt and inspect status') from exc
    write_json(path.parent/'runner-log.json', log)
    outcome = status(root, package)
    require(completed.returncode == 0 and outcome['state'] == 'completed', 'Native edit lacks a verified result; exit code alone is insufficient')
    require(verify_artifact(root, plan['dependencies']['native_source']).is_file(), 'Original native source changed during execution')
    return outcome


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    setup = sub.add_parser('install')
    setup.add_argument('--config',type=Path,default=ROOT/'config/local.json')
    p = sub.add_parser('prepare')
    p.add_argument('--workspace',type=Path,required=True)
    for name in ('plan','bundle','result','current-document','native-source','out'):
        p.add_argument('--'+name,required=True)
    for name in ('execute','status'):
        p = sub.add_parser(name)
        p.add_argument('--workspace',type=Path,required=True)
        p.add_argument('--package',required=True)
        if name == 'execute':
            p.add_argument('--config',type=Path,default=ROOT/'config/local.json')
    args = parser.parse_args(argv)
    try:
        if args.command == 'install':
            value = install(read_json(args.config))
        elif args.command == 'prepare':
            value = prepare(args.workspace,args.plan,args.bundle,args.result,args.current_document,args.native_source,args.out)
        elif args.command == 'execute':
            value = execute(args.workspace,args.package,read_json(args.config))
        else:
            value = status(args.workspace,args.package)
        print(json.dumps(value,indent=2)); return 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        parser.exit(2, 'character-krita: '+str(exc)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
