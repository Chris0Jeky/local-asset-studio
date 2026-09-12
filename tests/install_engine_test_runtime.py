"""CI-only explicit Godot test setup; never imported by Studio or its adapters."""
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
from urllib.request import urlopen
import zipfile

PINS = {
    'Linux': ('Godot_v4.5-stable_linux.x86_64.zip', 'Godot_v4.5-stable_linux.x86_64',
              'c7316e1fd782ad276a4d985a7673b5976eaaa8d90561a2bea5289210dc53e9ba'),
    'Windows': ('Godot_v4.5-stable_win64.exe.zip', 'Godot_v4.5-stable_win64.exe',
                '303206071cb8be502cfa5b1e2b37b848c280347c03f78dcc2eb8a630857f7d10'),
}

def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('This downloader is for explicit GitHub Actions test setup only. Configure your own installed Godot for local tests.')
    archive, member, digest = PINS[platform.system()]
    root = Path(os.environ['RUNNER_TEMP']) / 'studio-godot-test'; root.mkdir(exist_ok=True)
    url = 'https://github.com/godotengine/godot-builds/releases/download/4.5-stable/' + archive
    with urlopen(url, timeout=60) as reply:
        body = reply.read(100 * 1024**2 + 1)
    if len(body) > 100 * 1024**2 or hashlib.sha256(body).hexdigest() != digest:
        raise SystemExit('Pinned Godot archive checksum/size mismatch')
    executable = root / member
    with zipfile.ZipFile(io.BytesIO(body)) as zipped:
        info = zipped.getinfo(member)
        if info.file_size > 256 * 1024**2:
            raise SystemExit('Unexpected Godot executable size')
        with zipped.open(member) as source, executable.open('xb') as destination:
            shutil.copyfileobj(source, destination, 1024**2)
    executable.chmod(0o755)
    node = Path(shutil.which('node')).resolve()  # Test setup only; production never searches PATH.
    evidence = Path('engine-evidence').resolve(); evidence.mkdir(exist_ok=True)
    (evidence/'test-runtime.json').write_text(json.dumps({'godot_archive_url':url,'archive_sha256':digest,
        'godot_executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
        'node':str(node),'platform':platform.platform()},indent=2),encoding='utf-8')
    with Path(os.environ['GITHUB_ENV']).open('a',encoding='utf-8') as env:
        env.write(f'STUDIO_TEST_GODOT={executable}\nSTUDIO_TEST_NODE={node}\nSTUDIO_ENGINE_EVIDENCE={evidence}\nSTUDIO_REQUIRE_ENGINE_TESTS=1\n')

if __name__=='__main__':main()
