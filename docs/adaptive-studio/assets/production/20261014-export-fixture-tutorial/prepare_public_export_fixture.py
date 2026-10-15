"""Replay bootstrap added after capture; copies verified public files only."""
from pathlib import Path
import argparse, hashlib, json, subprocess
from PIL import Image

p=argparse.ArgumentParser()
p.add_argument('--repo-root',type=Path,required=True)
p.add_argument('--source-shelf',type=Path,required=True)
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--python-executable',type=Path,required=True)
p.add_argument('--input-provenance',type=Path,required=True)
a=p.parse_args();repo=a.repo_root.resolve();shelf=a.source_shelf.resolve();evidence=a.evidence.resolve()
assert (repo/'.git').is_file(), 'Use a fresh owned linked worktree, never the primary checkout'
git_directory=subprocess.check_output(['git','rev-parse','--git-dir'],cwd=repo,text=True).strip()
common_directory=subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=repo,text=True).strip()
assert Path(git_directory).resolve()!=Path(common_directory).resolve()
assert not subprocess.check_output(['git','rev-parse','--show-superproject-working-tree'],cwd=repo,text=True).strip(), 'Do not use a submodule'
assert not (repo/'config/local.json').exists(), 'Preserve any existing local configuration'
assert a.python_executable.is_file()
records=json.loads(a.input_provenance.read_text())
assert [row['original'] for row in records]==['lantern-duel-320.webp','pocket-borough-320.webp']
manifest=json.loads((shelf/'manifest.json').read_text())
verified=[]
for row in records:
    item=next(item for item in manifest['assets'] if item['file']==row['original'])
    data=(shelf/row['original']).read_bytes()
    assert len(data)==row['bytes']==item['bytes']
    assert hashlib.sha256(data).hexdigest()==row['sha256']==item['sha256']
    verified.append((row,data))
runtime=repo/'.runtime/export-public-fixture'
assert not runtime.exists() and not evidence.exists()
evidence.mkdir(parents=True);inputs=evidence/'public-inputs';inputs.mkdir()
for row,data in verified:
    destination=inputs/row['imported_filename'];assert destination.parent==inputs and destination.name.startswith('imported-public-')
    destination.write_bytes(data)
    with Image.open(destination) as image:
        image.load();assert list(image.size)==row['dimensions']
(runtime/'uninstalled-comfy/input').mkdir(parents=True)
config=dict(comfy_url='http://127.0.0.1:18188',comfy_root=str(runtime/'uninstalled-comfy'),python=str(a.python_executable.resolve()),experiments_root=str(runtime/'experiments'),runtime_auto_recover=False,idle_cache_release_minutes=0,observe_job_resources=False,enforce_stage_resource_admission=False,enable_large_job_resource_cleanup=False,enable_idle_retained_commit_cleanup=False,enable_large_job_backend_restart=False)
(repo/'config/local.json').write_text(json.dumps(config,indent=2)+'\n')
(evidence/'PREFLIGHT.json').write_text(json.dumps(dict(inputs=records,classification='Public imports and controlled destination collision; no generation',replay_bootstrap_added_after_original_capture=True,shared_configuration_changed=False),indent=2)+'\n')
print(json.dumps(dict(repo_root=str(repo),evidence=str(evidence),public_inputs=len(records),backend_started=False,generation_submitted=False)))
