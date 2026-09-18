"""Manual, finite CPU before/after harness; no models, network or private assets.

Example: python tests/benchmark_cpu_copies.py --operation decode --edge 4096 \
    --baseline .runtime/review-baseline.py --candidate app/review_media.py

Each sample is a fresh process. Peak RSS includes setup/imports, is captured before
output verification, and is unavailable on platforms without resource.getrusage.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'app'))


def pixel_hash(image):
    """Hash canonical decoded rows using bounded verification scratch."""
    result = hashlib.sha256(json.dumps([image.mode, image.size]).encode())
    for y in range(0, image.height, 64):
        with closing(image.crop((0, y, image.width, min(y + 64, image.height)))) as rows:
            result.update(rows.tobytes())
    return result.hexdigest()


def peak_rss():
    try:
        import resource
    except ImportError:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == 'darwin' else value * 1024)


def load_module(path):
    spec = importlib.util.spec_from_file_location('cpu_copy_subject', path)
    if spec is None or spec.loader is None: raise ValueError('Cannot load selected Python module')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture(edge, mode):
    image = Image.new(mode, (edge, edge), (17, 31, 47, 0) if mode == 'RGBA' else (17, 31, 47))
    draw = ImageDraw.Draw(image)
    colours = [(90, 120, 180, 127), (30, 210, 70, 255)]
    for i, colour in enumerate(colours):
        draw.rectangle((i * edge // 2, edge // 2, (i + 1) * edge // 2 - 1, edge - 1),
                       fill=colour if mode == 'RGBA' else colour[:3])
    return image


def trial(path, operation, edge, mode):
    module = load_module(path)
    if operation == 'decode':
        with closing(fixture(edge, mode)) as source:
            buffer = io.BytesIO(); source.save(buffer, format='PNG')
            data = buffer.getvalue(); buffer.close()
        input_hash = hashlib.sha256(data).hexdigest()
        start = time.perf_counter_ns(); result, transform = module.decode(data)
        elapsed = time.perf_counter_ns() - start; peak = peak_rss()
        try: output_hash = pixel_hash(result)
        finally: result.close()
    else:
        with closing(fixture(edge, 'RGBA')) as a, closing(a.copy()) as b:
            for x, y in ((0, 0), (511, 511), (512, 512), (edge - 1, edge - 1)):
                if x < edge and y < edge:
                    pixel = b.getpixel((x, y)); b.putpixel((x, y), ((pixel[0] + 1) % 256, *pixel[1:]))
            input_hash = hashlib.sha256((pixel_hash(a) + pixel_hash(b)).encode()).hexdigest()
            start = time.perf_counter_ns(); result = module.changed_mask(a, b)
            elapsed = time.perf_counter_ns() - start; peak = peak_rss()
            try: output_hash = pixel_hash(result)
            finally: result.close()
        transform = None
    return {'elapsed_ms': elapsed / 1e6, 'process_peak_rss_bytes': peak,
            'input_sha256': input_hash, 'decoded_output_sha256': output_hash,
            'transform': transform}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', required=True, choices=('decode', 'changed_mask'))
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--edge', type=int, default=2048)
    parser.add_argument('--repeats', type=int, choices=range(1, 10), default=3)
    parser.add_argument('--mode', choices=('RGB', 'RGBA'), default='RGBA')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 64 <= args.edge <= 4096: parser.error('edge must be between 64 and 4096')
    if args.operation == 'changed_mask' and args.mode != 'RGBA': parser.error('changed_mask fixture is RGBA')
    if args.worker is not None:
        print(json.dumps(trial(args.worker, args.operation, args.edge, args.mode))); return
    if args.baseline is None or args.candidate is None: parser.error('select baseline and candidate modules')
    sources = {'baseline': args.baseline.resolve(strict=True), 'candidate': args.candidate.resolve(strict=True)}
    samples = []
    for repeat in range(args.repeats):
        order = ('baseline', 'candidate') if repeat % 2 == 0 else ('candidate', 'baseline')
        for label in order:
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', str(sources[label]),
                       '--operation', args.operation, '--edge', str(args.edge), '--mode', args.mode]
            process = subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
            samples.append(dict(json.loads(process.stdout), implementation=label, repeat=repeat))
    signatures = {json.dumps([r['input_sha256'], r['decoded_output_sha256'], r['transform']], sort_keys=True)
                  for r in samples}
    if len(signatures) != 1: raise ValueError('Input/output/transform parity failed; no performance result accepted')
    summaries = {}
    for label in sources:
        rows = [r for r in samples if r['implementation'] == label]
        timings = [r['elapsed_ms'] for r in rows]
        peaks = [r['process_peak_rss_bytes'] for r in rows if r['process_peak_rss_bytes'] is not None]
        summaries[label] = {'median_ms': statistics.median(timings), 'range_ms': [min(timings), max(timings)],
                            'median_process_peak_rss_bytes': statistics.median(peaks) if peaks else None}
    print(json.dumps({'schema': 'studio.cpu-copy-benchmark/v1', 'operation': args.operation,
        'edge': args.edge, 'mode': args.mode, 'repeats_per_implementation': args.repeats,
        'python': platform.python_version(), 'pillow': Image.__version__, 'platform': platform.platform(),
        'module_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sources.items()},
        'output_parity': True, 'neural_executions': 0, 'samples': samples, 'summary': summaries,
        'limitations': ['Synthetic CPU fixture; not inference performance or owner-machine evidence',
                        'Process-lifetime peak RSS includes setup; not Windows commit or GPU memory',
                        'Small samples do not qualify p95/p99; output hashing follows timed/peak observation']}, indent=2))


if __name__ == '__main__': main()
