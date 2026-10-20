"""Isolated, inert full-envelope intake measurement; no Studio or model process.

python tests/reference_preview_memory.py --output .runtime/reference-preview-intake/memory.json
Add --baseline <local-git-revision> to measure that revision's original HTTP/review
modules against identical bodies. Each measurement runs in a fresh subprocess;
fixture creation, file-backed request bytes and interpreter imports are excluded
from Python tracing. RSS includes native Pillow allocations and allocator effects.
"""
from __future__ import annotations
import argparse
import base64
import gc
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, __version__ as pillow_version
import psutil

IMAGE_BYTES = 8 * 1024 * 1024
HTTP_BYTES = 48 * 1024 * 1024
DIMENSION = 4096


def fixture(directory, codec):
    from studio_prompt import reference_analysis as analysis
    from studio_prompt.schema import new_brief
    refs = []; observations = []; inputs = []; files = []
    for index in range(4):
        key = 'picture-%d' % (index + 1)
        stream = io.BytesIO(); image = Image.new('RGB', (DIMENSION, DIMENSION), (31 + index, 40, 50))
        try: image.save(stream, format=codec)
        finally: image.close()
        raw = stream.getvalue(); stream.close()
        assert len(raw) <= IMAGE_BYTES
        # Valid trailing padding reaches the compressed-byte cap independently
        # of the uniform 16 MiPixel surface. These are not worst-case codecs.
        raw += bytes((index,)) * (IMAGE_BYTES - len(raw))
        path = directory / (key + '.' + codec.lower()); path.write_bytes(raw); files.append(path)
        sha = hashlib.sha256(raw).hexdigest()
        refs.append({'id': key, 'path': 'refs/' + path.name, 'sha256': sha, 'role_hint': 'style'})
        inputs.append({'reference_id': key, 'source_sha256': sha, 'analysis_sha256': sha, 'analysis_size': [768, 768]})
        observations.append({'reference_id': key, 'suggested_role': 'style', 'description': 'Synthetic plain colour',
                             'tags': [], 'facets': {'style': 'plain colour'}, 'uncertain_facets': [], 'unknowns': []})
    report = analysis.make_report(analysis.new_request('Keep the reviewed colours', refs),
        {'summary': 'Synthetic full-envelope originals', 'assumptions': [], 'questions': [], 'images': observations}, inputs)
    value = {'analysis': report, 'review': analysis.review_template(report),
             'intent': new_brief('Keep this exact current instruction'), 'adopt_brief': False}
    body = directory / (codec.lower() + '.json')
    with body.open('wb') as output:
        output.write(json.dumps(value, separators=(',', ':')).encode()[:-1] + b',"images":[')
        for index, path in enumerate(files):
            if index: output.write(b',')
            output.write(b'{"reference_id":"picture-%d","media_base64":"' % (index + 1))
            output.write(base64.b64encode(path.read_bytes())); output.write(b'"}')
        output.write(b']}')
        output.write(b' ' * (HTTP_BYTES - output.tell()))
    return body


def original_modules(revision):
    import studio_prompt
    for short in ('reference_review', 'http_extension'):
        name = 'studio_prompt.' + short
        source = subprocess.check_output(['git', 'show', revision + ':studio_prompt/' + short + '.py'], cwd=ROOT)
        module = types.ModuleType(name); module.__package__ = 'studio_prompt'
        module.__file__ = str(ROOT / 'studio_prompt' / (short + '.py'))
        sys.modules[name] = module; setattr(studio_prompt, short, module)
        exec(compile(source, module.__file__, 'exec'), module.__dict__)


def measured(body, revision):
    if revision: original_modules(revision)
    from test_reference_preview_intake import PreviewIntakeTests
    Image.init()
    # /proc/self follows this process even in sandboxes whose getpid() namespace
    # differs from the mounted /proc. A numeric psutil PID can name another task.
    if sys.platform.startswith('linux'):
        def memory():
            values = {}
            with open('/proc/self/status') as stream:
                for line in stream:
                    if line.startswith(('VmRSS:', 'VmHWM:')):
                        key, value, _ = line.split(); values[key] = int(value) * 1024
            return values['VmRSS:'], values['VmHWM:']
        rss_method = '/proc/self/status VmRSS and VmHWM'
    else:
        process = psutil.Process()
        def memory():
            info = process.memory_info()
            if sys.platform == 'win32': return info.rss, info.peak_wset
            import resource
            return info.rss, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_method = 'psutil RSS and platform process high water'
    stop = threading.Event(); peak = [0]
    def observe():
        while not stop.wait(0.002):
            peak[0] = max(peak[0], *memory())
    watcher = threading.Thread(target=observe, daemon=True); watcher.start()
    gc.collect(); baseline_rss, initial_peak = memory(); peak[0] = initial_peak
    reads = []
    with body.open('rb') as source:
        class Reader:
            def read(self, size): reads.append(size); return source.read(size)
            read1 = read
        case = PreviewIntakeTests()
        tracemalloc.start(); start = time.monotonic()
        status, result = case.call(b'', reader=Reader(), lengths=[str(body.stat().st_size)])
        elapsed = time.monotonic() - start
        python_live, python_peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        assert status == 200, result.get('error')
        assert result['source_bytes_verified'] and len(result['intent']['references']) == 4
        assert not result['inference_submitted'] and not result['generation_submitted']
        assert source.tell() == body.stat().st_size
        if not revision: assert max(reads) <= 65536
    peak[0] = max(peak[0], *memory())
    stop.set(); watcher.join()
    gc.collect()
    return {'implementation': revision or 'working-tree', 'codec': body.stem.upper(), 'status': status,
            'original_count': 4, 'bytes_per_original': IMAGE_BYTES, 'pixels_per_original': DIMENSION ** 2,
            'body_bytes': body.stat().st_size, 'maximum_read_bytes': max(reads), 'read_count': len(reads),
            'python_peak_bytes': python_peak, 'python_live_at_response_bytes': python_live,
            'rss_baseline_bytes': baseline_rss, 'rss_peak_bytes': peak[0],
            'rss_increase_bytes': max(0, peak[0] - baseline_rss), 'rss_after_gc_bytes': memory()[0],
            'rss_method': rss_method, 'elapsed_seconds': round(elapsed, 4)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline'); parser.add_argument('--output', type=Path)
    parser.add_argument('--child', type=Path)
    args = parser.parse_args()
    if args.child:
        print(json.dumps(measured(args.child, args.baseline))); return
    rows = []
    with tempfile.TemporaryDirectory(prefix='reference-preview-memory-') as temporary:
        directory = Path(temporary)
        for codec in ('PNG', 'JPEG', 'WEBP'):
            body = fixture(directory, codec)
            for revision in ([args.baseline, None] if args.baseline else [None]):
                command = [sys.executable, str(Path(__file__).resolve()), '--child', str(body)]
                if revision: command += ['--baseline', revision]
                completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
                if completed.returncode: raise RuntimeError(completed.stderr or completed.stdout)
                row = json.loads(completed.stdout); rows.append(row)
                print(json.dumps(row), flush=True)
    report = {'format': 'studio.reference-preview-memory/v1', 'python': platform.python_version(),
              'pillow': pillow_version, 'platform': platform.platform(),
              'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'working_tree_modified': bool(subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT)),
              'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                  ('studio_prompt/http_extension.py', 'studio_prompt/reference_intake.py', 'studio_prompt/reference_review.py',
                   'tests/test_reference_preview_intake.py', 'tests/test_reference_review_http.py', 'tests/reference_preview_memory.py')},
              'results': rows,
              'limits': ['Synthetic uniform-colour PNG/JPEG/WebP, each padded to 8 MiB and decoding to 16 MiPixels.',
                         'Insignificant trailing JSON whitespace exercises the entire 48 MiB wire budget.',
                         'Not a worst-case codec-memory guarantee or a host/generation admission test.',
                         'Python tracemalloc excludes native Pillow allocations; RSS also reflects the process allocator.',
                         'Fixture construction and file-backed body bytes are outside each isolated measured process.']}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__': main()
